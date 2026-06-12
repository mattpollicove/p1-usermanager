import asyncio
import json
from typing import List
import sys
from pathlib import Path

# Ensure project root is on sys.path when running this module directly
_THIS_FILE = Path(__file__).resolve()
_PROJECT_ROOT = _THIS_FILE.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

import httpx
from PySide6 import QtCore

import api.client as api_client
from tps_tracker import TPSTracker

"""Background worker implementations.

Workers run inside Qt threadpool QRunnable tasks and perform async HTTP
operations via `httpx`. Each worker sends progress/finished/error
signals back to the UI. Detailed API request/response summaries are
optionally written to the connection log when `api_client.API_LOGGING_ENABLED`
is True.
"""


class WorkerSignals(QtCore.QObject):
    """Common Qt signals used by worker tasks.

    - `finished`: emits a dict with task-specific results
    - `progress`: emits (current, total) ints for progress bars
    - `error`: emits a short error message for the UI
    - `tps_update`: emits TPS stats dict for periodic updates during long operations
    """
    finished = QtCore.Signal(dict)
    progress = QtCore.Signal(int, int)
    error = QtCore.Signal(str)
    status = QtCore.Signal(str)
    tps_update = QtCore.Signal(dict)  # Periodic TPS updates


class UserFetchWorker(QtCore.QRunnable):
    """Worker to fetch populations and all users by paging the API.

    The worker obtains an access token, fetches population metadata, then
    iterates over paged user results. Results are emitted via the
    `finished` signal as a dict containing `users` and `pop_map`.
    """
    def __init__(self, client):
        super().__init__()
        self.client, self.signals = client, WorkerSignals()

    @QtCore.Slot()
    def run(self):
        # Entry point called by Qt's threadpool; run the async work
        # inside an asyncio event loop so we can use httpx.AsyncClient.
        asyncio.run(self.execute())

    async def execute(self):
        try:
            # Initialize TPS tracker
            tps_tracker = TPSTracker()
            tps_tracker.start()
            
            # Obtain token (cached by client) - if None, emit an error
            token = await self.client.get_token()
            if not token:
                self.signals.error.emit("Auth Failed. Check credentials.")
                return

            headers = {"Authorization": f"Bearer {token}"}
            # Use a short-lived AsyncClient for this worker to avoid sharing
            # the same AsyncClient across threads/event loops.
            # Add timeout for all HTTP operations
            async with httpx.AsyncClient(timeout=30.0) as session:
                # Fetch populations mapping (small metadata lookup)
                if api_client.API_LOGGING_ENABLED:
                    api_client.api_logger.info(f"GET {self.client.base_url}/populations")
                    try:
                        api_client.append_live_event(f"GET {self.client.base_url}/populations")
                    except Exception:
                        pass
                p_resp = await session.get(f"{self.client.base_url}/populations", headers=headers)
                tps_tracker.record_transaction()  # Record populations API call
                pop_map = {p['id']: p['name'] for p in p_resp.json().get('_embedded', {}).get('populations', [])}
                if api_client.API_LOGGING_ENABLED:
                    api_client.api_logger.info(
                        f"GET {self.client.base_url}/populations - Status: {p_resp.status_code}, Populations: {len(pop_map)}")
                    try:
                        api_client.write_connection_log(f"GET {self.client.base_url}/populations - {p_resp.status_code} - Populations: {len(pop_map)}")
                    except Exception:
                        pass

                # Paginate through users until the `next` link is absent
                all_users = []
                url = f"{self.client.base_url}/users"
                page = 1

                while url:
                    if api_client.API_LOGGING_ENABLED:
                        api_client.api_logger.info(f"GET {url} (page {page})")
                        try:
                            api_client.append_live_event(f"GET {url} (page {page})")
                        except Exception:
                            pass
                    resp = await session.get(url, headers=headers)
                    tps_tracker.record_transaction()  # Record each user page API call
                    data = resp.json()
                    users_page = data.get("_embedded", {}).get("users", [])
                    users_count = len(users_page)
                    all_users.extend(users_page)
                    if api_client.API_LOGGING_ENABLED:
                        api_client.api_logger.info(f"GET {url} - Status: {resp.status_code}, Users in page: {users_count}")
                        try:
                            api_client.write_connection_log(f"GET {url} - {resp.status_code} - Users in page: {users_count}")
                        except Exception:
                            pass
                    url = data.get("_links", {}).get("next", {}).get("href")
                    page += 1

            # Finalize TPS tracking
            tps_tracker.finish()
            tps_stats = tps_tracker.get_statistics()
            
            # Emit the consolidated results back to the UI thread
            # so the main window can refresh its table.
            self.signals.finished.emit({
                "users": all_users,
                "pop_map": pop_map,
                "user_count": len(all_users),
                "pop_count": len(pop_map),
                "tps_stats": tps_stats
            })
        except Exception as e:
            if api_client.API_LOGGING_ENABLED:
                api_client.api_logger.error(f"UserFetchWorker failed: {str(e)}")
                try:
                    api_client.write_connection_log(f"UserFetchWorker ERROR - {str(e)}")
                except Exception:
                    pass
            self.signals.error.emit(str(e))


class BulkDeleteWorker(QtCore.QRunnable):
    """Worker to perform bulk user deletions with optional parallel processing.

    Emits progress updates and a final `finished` result with counts.
    
    Supports both sequential and parallel processing modes:
    - Sequential (concurrency=1): Process one user at a time
    - Parallel (concurrency>1): Process multiple users concurrently
    """
    def __init__(self, client, user_ids: List[str], cancel_check=None, concurrency: int = 1):
        super().__init__()
        self.client, self.user_ids, self.signals = client, user_ids, WorkerSignals()
        self.cancel_check = cancel_check  # Callable that returns True if cancel requested
        self.concurrency = max(1, min(concurrency, 10))  # Limit to 1-10 concurrent requests

    @QtCore.Slot()
    def run(self):
        # Run the async delete loop inside an event loop provided
        # by asyncio.run when the QRunnable executes.
        asyncio.run(self.execute())

    async def _delete_single_user(self, session: httpx.AsyncClient, headers: dict, uid: str,
                                   semaphore: asyncio.Semaphore) -> dict:
        """Delete a single user with rate limit handling.
        
        Returns dict with keys: success, error
        """
        async with semaphore:  # Limit concurrency
            delete_url = f"{self.client.base_url}/users/{uid}"
            
            try:
                if api_client.API_LOGGING_ENABLED:
                    api_client.api_logger.info(f"DELETE {delete_url}")
                
                resp = await session.delete(delete_url, headers=headers)
                resp.raise_for_status()
                
                if api_client.API_LOGGING_ENABLED:
                    api_client.api_logger.info(f"DELETE {delete_url} - Status: {resp.status_code}")
                
                return {"success": True, "error": None}
                
            except httpx.HTTPStatusError as e:
                # Handle 429 rate limit with retry
                if e.response.status_code == 429:
                    await asyncio.sleep(2)  # Back off for rate limit
                    try:
                        resp = await session.delete(delete_url, headers=headers)
                        resp.raise_for_status()
                        
                        if api_client.API_LOGGING_ENABLED:
                            api_client.api_logger.info(f"DELETE {delete_url} - Retry succeeded")
                        
                        return {"success": True, "error": None}
                    except Exception as retry_err:
                        if api_client.API_LOGGING_ENABLED:
                            api_client.api_logger.error(f"DELETE {delete_url} - Retry failed: {retry_err}")
                        return {"success": False, "error": f"Rate limit retry failed: {retry_err}"}
                else:
                    if api_client.API_LOGGING_ENABLED:
                        api_client.api_logger.error(f"DELETE {delete_url} - Failed: {e}")
                    return {"success": False, "error": str(e)}
                    
            except Exception as e:
                if api_client.API_LOGGING_ENABLED:
                    api_client.api_logger.error(f"DELETE {delete_url} - Failed: {e}")
                return {"success": False, "error": str(e)}

    async def execute(self):
        # Use parallel processing if concurrency > 1
        if self.concurrency > 1:
            await self._execute_parallel()
        else:
            await self._execute_sequential()

    async def _execute_parallel(self):
        """Execute with parallel processing of deletes."""
        # Initialize TPS tracker
        tps_tracker = TPSTracker()
        tps_tracker.start()
        
        import time
        last_tps_update = time.time()
        last_status_update = time.time()
        
        token = await self.client.get_token()
        if not token:
            self.signals.error.emit("Auth Failed. Check credentials.")
            return
        headers = self.client._get_auth_headers(token)
        
        success = 0
        failed = 0
        total = len(self.user_ids)
        processed = 0
        failed_ids = []
        
        # Create semaphore to limit concurrency
        semaphore = asyncio.Semaphore(self.concurrency)
        
        async with httpx.AsyncClient(timeout=30.0) as session:
            # Process users in batches
            batch_size = self.concurrency * 2  # Process 2 rounds of concurrent requests at a time
            for batch_start in range(0, total, batch_size):
                if self.cancel_check and self.cancel_check():
                    self.signals.status.emit(f"Delete cancelled after {processed} of {total} users")
                    break
                
                batch_end = min(batch_start + batch_size, total)
                batch = self.user_ids[batch_start:batch_end]
                
                # Process batch in parallel
                tasks = [
                    self._delete_single_user(session, headers, uid, semaphore)
                    for uid in batch
                ]
                results = await asyncio.gather(*tasks, return_exceptions=True)
                
                # Process results
                for i, result in enumerate(results):
                    processed += 1
                    uid = batch[i]
                    
                    if isinstance(result, Exception):
                        failed += 1
                        failed_ids.append(uid)
                        if api_client.API_LOGGING_ENABLED:
                            api_client.api_logger.error(f"Delete {uid}: {str(result)}")
                    elif result.get('success'):
                        success += 1
                        tps_tracker.record_transaction()
                    else:
                        failed += 1
                        failed_ids.append(uid)
                    
                    # Emit progress
                    self.signals.progress.emit(processed, total)
                    
                    # Status update every 1 second
                    current_time = time.time()
                    if current_time - last_status_update >= 1.0 or processed == total:
                        percentage = int(processed / total * 100)
                        self.signals.status.emit(f"Deleting {processed}/{total} ({percentage}%) - {self.concurrency} concurrent")
                        last_status_update = current_time
                    
                    # TPS update every 10 seconds
                    if current_time - last_tps_update >= 10.0:
                        tps_stats = tps_tracker.get_statistics()
                        self.signals.tps_update.emit(tps_stats)
                        last_tps_update = current_time
        
        # Finalize
        tps_tracker.finish()
        tps_stats = tps_tracker.get_statistics()
        
        if api_client.API_LOGGING_ENABLED:
            api_client.api_logger.info(f"Parallel delete completed: {success}/{total} users deleted, {failed} failed")
        
        self.signals.finished.emit({
            "deleted": success,
            "failed": failed,
            "failed_ids": failed_ids,
            "total": total,
            "tps_stats": tps_stats,
        })

    async def _execute_sequential(self):
        """Execute with sequential processing of deletes (original logic)."""
        # Initialize TPS tracker
        tps_tracker = TPSTracker()
        tps_tracker.start()
        
        # Track last TPS update time
        import time
        last_tps_update = time.time()
        
        token = await self.client.get_token()
        if not token:
            self.signals.error.emit("Auth Failed. Check credentials.")
            return
        headers = self.client._get_auth_headers(token)
        success = 0
        failed = 0
        failed_ids = []
        
        # Add timeout for all HTTP operations
        async with httpx.AsyncClient(timeout=30.0) as session:
            # Iterate user IDs and perform DELETE requests one-by-one.
            # This keeps load predictable and allows progress reporting.
            for i, uid in enumerate(self.user_ids):
                # Check for cancellation
                if self.cancel_check and self.cancel_check():
                    self.signals.status.emit(f"Delete cancelled after {success} of {len(self.user_ids)} users")
                    break
                
                delete_url = f"{self.client.base_url}/users/{uid}"
                # Emit status update showing current deletion with counter and percentage
                percentage = int((i + 1) / len(self.user_ids) * 100)
                self.signals.status.emit(f"Deleting user {i+1}/{len(self.user_ids)} ({percentage}%): {uid}")
                
                # Emit TPS update every 10 seconds
                current_time = time.time()
                if current_time - last_tps_update >= 10.0:
                    tps_stats = tps_tracker.get_statistics()
                    self.signals.tps_update.emit(tps_stats)
                    last_tps_update = current_time
                
                try:
                    if api_client.API_LOGGING_ENABLED:
                        api_client.api_logger.info(f"DELETE {delete_url}")
                        try:
                            api_client.append_live_event(f"DELETE {delete_url}")
                        except Exception:
                            pass
                    resp = await session.delete(delete_url, headers=headers)
                    resp.raise_for_status()
                    
                    if api_client.API_LOGGING_ENABLED:
                        api_client.api_logger.info(f"DELETE {delete_url} - Status: {resp.status_code}")
                        try:
                            api_client.write_connection_log(f"DELETE {delete_url} - {resp.status_code}")
                        except Exception:
                            pass
                    success += 1
                    tps_tracker.record_transaction()  # Record successful deletion
                    
                except httpx.HTTPStatusError as e:
                    # Handle 429 rate limit with retry
                    if e.response.status_code == 429:
                        await asyncio.sleep(2)  # Back off for rate limit
                        try:
                            resp = await session.delete(delete_url, headers=headers)
                            resp.raise_for_status()
                            success += 1
                            tps_tracker.record_transaction()
                            if api_client.API_LOGGING_ENABLED:
                                api_client.api_logger.info(f"DELETE {delete_url} - Retry succeeded")
                        except Exception as retry_err:
                            failed += 1
                            failed_ids.append(uid)
                            if api_client.API_LOGGING_ENABLED:
                                api_client.api_logger.error(f"DELETE {delete_url} - Retry failed: {retry_err}")
                    else:
                        failed += 1
                        failed_ids.append(uid)
                        if api_client.API_LOGGING_ENABLED:
                            api_client.api_logger.error(f"DELETE {delete_url} - Failed: {str(e)}")
                            
                except Exception as e:
                    failed += 1
                    failed_ids.append(uid)
                    if api_client.API_LOGGING_ENABLED:
                        api_client.api_logger.error(f"DELETE {delete_url} - Failed: {str(e)}")
                        try:
                            api_client.write_connection_log(f"DELETE {delete_url} - ERROR - {str(e)}")
                        except Exception:
                            pass
                            
                self.signals.progress.emit(i + 1, len(self.user_ids))
        
        # Finalize TPS tracking
        tps_tracker.finish()
        tps_stats = tps_tracker.get_statistics()
        
        if api_client.API_LOGGING_ENABLED:
            api_client.api_logger.info(f"Bulk delete completed: {success}/{len(self.user_ids)} users deleted, {failed} failed")
            try:
                api_client.write_connection_log(f"Bulk delete completed: {success}/{len(self.user_ids)} users deleted, {failed} failed")
            except Exception:
                pass
        self.signals.finished.emit({
            "deleted": success,
            "failed": failed,
            "failed_ids": failed_ids,
            "total": len(self.user_ids),
            "tps_stats": tps_stats,
        })


class BulkCreateWorker(QtCore.QRunnable):
    """Worker to create multiple users with optional parallel processing.

    Emits progress updates and a final `finished` result with counts.
    
    Supports both sequential and parallel processing modes:
    - Sequential (concurrency=1): Process one user at a time
    - Parallel (concurrency>1): Process multiple users concurrently
    """
    def __init__(self, client, users: List[dict], cancel_check=None, concurrency: int = 1):
        super().__init__()
        self.client, self.users, self.signals = client, users, WorkerSignals()
        self.cancel_check = cancel_check  # Callable that returns True if cancel requested
        self.concurrency = max(1, min(concurrency, 10))  # Limit to 1-10 concurrent requests

    def _is_existing_user_error(self, err_text: str) -> bool:
        """Return True when an error indicates the user already exists."""
        txt = str(err_text or "").lower()
        return (
            "409" in txt
            or "already exists" in txt
            or "duplicate" in txt
            or "uniqueness" in txt
            or "not unique" in txt
        )

    async def _build_existing_user_map(self, headers: dict) -> dict:
        """Fetch username->id map from PingOne for retry-on-conflict updates."""
        user_map = {}
        url = f"{self.client.base_url}/users"
        async with httpx.AsyncClient(timeout=10.0) as session:
            while url:
                resp = await session.get(url, headers=headers)
                resp.raise_for_status()
                data = resp.json()
                for u in data.get("_embedded", {}).get("users", []):
                    uid = u.get("id")
                    uname = u.get("username")
                    if uid and uname:
                        user_map[str(uname).strip().lower()] = uid
                url = data.get("_links", {}).get("next", {}).get("href")
        return user_map

    @QtCore.Slot()
    def run(self):
        asyncio.run(self.execute())

    async def _process_single_user(self, session: httpx.AsyncClient, headers: dict, user: dict,
                                    existing_user_map: dict, tps_tracker: 'TPSTracker',
                                    semaphore: asyncio.Semaphore) -> dict:
        """Process a single user with rate limit handling and conflict retry.
        
        Returns dict with keys: success, created, updated, error, created_id
        """
        async with semaphore:  # Limit concurrency
            username = user.get('username') or user.get('id') or 'unknown'
            uname_norm = (str(user.get('username')).strip().lower() if user.get('username') else "")
            
            try:
                # Check if user exists in pre-fetched map
                if existing_user_map and uname_norm and uname_norm in existing_user_map:
                    # Update existing user
                    existing_id = existing_user_map[uname_norm]
                    update_url = f"{self.client.base_url}/users/{existing_id}"
                    resp = await session.put(update_url, headers=headers, json=user)
                    resp.raise_for_status()
                    tps_tracker.record_transaction()
                    return {"success": True, "created": False, "updated": True, "error": None, "created_id": None}
                else:
                    # Create new user
                    create_url = f"{self.client.base_url}/users"
                    resp = await session.post(create_url, headers=headers, json=user)
                    resp.raise_for_status()
                    result = resp.json()
                    tps_tracker.record_transaction()
                    created_id = result.get('id') if isinstance(result, dict) else None
                    return {"success": True, "created": True, "updated": False, "error": None, "created_id": created_id}
                    
            except httpx.HTTPStatusError as e:
                # Handle 429 rate limit with retry
                if e.response.status_code == 429:
                    await asyncio.sleep(2)  # Back off for rate limit
                    try:
                        if existing_user_map and uname_norm and uname_norm in existing_user_map:
                            existing_id = existing_user_map[uname_norm]
                            update_url = f"{self.client.base_url}/users/{existing_id}"
                            resp = await session.put(update_url, headers=headers, json=user)
                        else:
                            create_url = f"{self.client.base_url}/users"
                            resp = await session.post(create_url, headers=headers, json=user)
                        resp.raise_for_status()
                        result = resp.json()
                        tps_tracker.record_transaction()
                        if existing_user_map and uname_norm and uname_norm in existing_user_map:
                            return {"success": True, "created": False, "updated": True, "error": None, "created_id": None}
                        else:
                            created_id = result.get('id') if isinstance(result, dict) else None
                            return {"success": True, "created": True, "updated": False, "error": None, "created_id": created_id}
                    except Exception as retry_err:
                        return {"success": False, "created": False, "updated": False,
                                "error": f"Rate limit retry failed: {retry_err}", "created_id": None}
                
                # Handle 409 conflict errors
                err_text = str(e)
                if self._is_existing_user_error(err_text):
                    try:
                        # Try to update instead
                        if existing_user_map is None:
                            # Can't retry without user map
                            return {"success": False, "created": False, "updated": False,
                                    "error": f"Already exists (no user map for retry)", "created_id": None}
                        
                        existing_id = existing_user_map.get(uname_norm)
                        if existing_id:
                            update_url = f"{self.client.base_url}/users/{existing_id}"
                            resp = await session.put(update_url, headers=headers, json=user)
                            resp.raise_for_status()
                            tps_tracker.record_transaction()
                            return {"success": True, "created": False, "updated": True, "error": None, "created_id": None}
                        else:
                            return {"success": False, "created": False, "updated": False,
                                    "error": "Already exists but not found in user map", "created_id": None}
                    except Exception as retry_err:
                        return {"success": False, "created": False, "updated": False,
                                "error": f"Retry as update failed: {retry_err}", "created_id": None}
                else:
                    return {"success": False, "created": False, "updated": False,
                            "error": err_text, "created_id": None}
                            
            except Exception as e:
                return {"success": False, "created": False, "updated": False,
                        "error": str(e), "created_id": None}

    async def execute(self):
        # Use parallel processing if concurrency > 1
        if self.concurrency > 1:
            await self._execute_parallel()
        else:
            await self._execute_sequential()

    async def _execute_parallel(self):
        """Execute with parallel processing of users."""
        # Initialize TPS tracker
        tps_tracker = TPSTracker()
        tps_tracker.start()
        
        import time
        last_tps_update = time.time()
        last_status_update = time.time()
        
        # Ensure we have a valid token
        token = await self.client.get_token()
        if not token:
            self.signals.error.emit("Auth Failed. Check credentials.")
            return
        headers = self.client._get_auth_headers(token)
        
        created = 0
        updated_on_retry = 0
        total = len(self.users)
        errors = []
        created_ids = []
        processed = 0
        
        # Pre-fetch existing users for large imports
        existing_user_map = None
        if total > 50:
            try:
                self.signals.status.emit("Pre-fetching existing users for conflict detection...")
                existing_user_map = await self._build_existing_user_map(headers)
                self.signals.status.emit(f"Found {len(existing_user_map)} existing users. Starting parallel import...")
            except Exception as e:
                if api_client.API_LOGGING_ENABLED:
                    api_client.api_logger.warning(f"Failed to pre-fetch users: {e}")
        
        # Create semaphore to limit concurrency
        semaphore = asyncio.Semaphore(self.concurrency)
        
        async with httpx.AsyncClient(timeout=30.0) as session:
            # Process users in batches
            batch_size = self.concurrency * 2  # Process 2 rounds of concurrent requests at a time
            for batch_start in range(0, total, batch_size):
                if self.cancel_check and self.cancel_check():
                    errors.append("Import cancelled by user")
                    self.signals.status.emit(f"Import cancelled after {processed} of {total} users")
                    break
                
                batch_end = min(batch_start + batch_size, total)
                batch = self.users[batch_start:batch_end]
                
                # Process batch in parallel
                tasks = [
                    self._process_single_user(session, headers, user, existing_user_map, tps_tracker, semaphore)
                    for user in batch
                ]
                results = await asyncio.gather(*tasks, return_exceptions=True)
                
                # Process results
                for i, result in enumerate(results):
                    processed += 1
                    user = batch[i]
                    username = user.get('username') or user.get('id') or f"user_{batch_start + i + 1}"
                    
                    if isinstance(result, Exception):
                        err_msg = f"User {username}: {str(result)}"
                        errors.append(err_msg)
                    elif result.get('success'):
                        if result.get('created'):
                            created += 1
                            if result.get('created_id'):
                                created_ids.append(result['created_id'])
                        elif result.get('updated'):
                            updated_on_retry += 1
                    else:
                        err_msg = f"User {username}: {result.get('error', 'Unknown error')}"
                        errors.append(err_msg)
                    
                    # Emit progress
                    self.signals.progress.emit(processed, total)
                    
                    # Status update every 1 second
                    current_time = time.time()
                    if current_time - last_status_update >= 1.0 or processed == total:
                        percentage = int(processed / total * 100)
                        self.signals.status.emit(f"Processing {processed}/{total} ({percentage}%) - {self.concurrency} concurrent")
                        last_status_update = current_time
                    
                    # TPS update every 10 seconds
                    if current_time - last_tps_update >= 10.0:
                        tps_stats = tps_tracker.get_statistics()
                        self.signals.tps_update.emit(tps_stats)
                        last_tps_update = current_time
        
        # Finalize
        tps_tracker.finish()
        tps_stats = tps_tracker.get_statistics()
        
        if api_client.API_LOGGING_ENABLED:
            api_client.api_logger.info(f"Parallel import completed: {created}/{total} users created, {updated_on_retry} updated")
        
        self.signals.finished.emit({
            "created": created,
            "updated_on_retry": updated_on_retry,
            "created_ids": created_ids,
            "total": total,
            "errors": errors,
            "tps_stats": tps_stats,
        })

    async def _execute_sequential(self):
        """Execute with sequential processing of users (original logic)."""
        # Initialize TPS tracker
        tps_tracker = TPSTracker()
        tps_tracker.start()
        
        # Track last TPS update time, status update time, and rate limit delay
        import time
        last_tps_update = time.time()
        last_status_update = time.time()
        rate_limit_delay = 0  # Adaptive delay for 429 responses
        
        # Ensure we have a valid token before attempting creates
        token = await self.client.get_token()
        if not token:
            self.signals.error.emit("Auth Failed. Check credentials.")
            return
        headers = self.client._get_auth_headers(token)
        created = 0
        updated_on_retry = 0
        total = len(self.users)
        errors = []
        created_ids = []  # Track IDs of created users for rollback
        
        # PHASE 1 OPTIMIZATION: Pre-fetch existing users for large imports
        existing_user_map = None
        if total > 50:  # Only pre-fetch for larger imports
            try:
                self.signals.status.emit("Pre-fetching existing users for conflict detection...")
                existing_user_map = await self._build_existing_user_map(headers)
                self.signals.status.emit(f"Found {len(existing_user_map)} existing users. Starting import...")
            except Exception as e:
                if api_client.API_LOGGING_ENABLED:
                    api_client.api_logger.warning(f"Failed to pre-fetch users: {e}")

        # PHASE 1 OPTIMIZATION: Use single HTTP session (connection pooling)
        async with httpx.AsyncClient(timeout=30.0) as session:
            # Process users sequentially with optimizations
            for i, user in enumerate(self.users):
                # Check for cancellation
                if self.cancel_check and self.cancel_check():
                    errors.append("Import cancelled by user")
                    self.signals.status.emit(f"Import cancelled after {created} of {total} users")
                    break
                
                # PHASE 1 OPTIMIZATION: Time-based status updates (every 1 second)
                uname = user.get('username') or user.get('id') or f"user_{i+1}"
                percentage = int((i + 1) / total * 100)
                current_time = time.time()
                
                # Emit status update every 1 second or on final user
                if current_time - last_status_update >= 1.0 or i == total - 1:
                    self.signals.status.emit(f"Creating user {i+1}/{total} ({percentage}%): {uname}")
                    last_status_update = current_time
                
                # Emit TPS update every 10 seconds seconds
                current_time = time.time()
                if current_time - last_tps_update >= 10.0:
                    tps_stats = tps_tracker.get_statistics()
                    self.signals.tps_update.emit(tps_stats)
                    last_tps_update = current_time
                
                # Apply rate limit delay if needed
                if rate_limit_delay > 0:
                    await asyncio.sleep(rate_limit_delay)
                
                # Check if user exists in pre-fetched map
                username = user.get('username')
                uname_norm = (str(username).strip().lower() if username else "")
                
                try:
                    # If we have existing user map and user exists, update instead of create
                    if existing_user_map and uname_norm and uname_norm in existing_user_map:
                        if api_client.API_LOGGING_ENABLED:
                            api_client.api_logger.info(f"User {username} exists, updating instead")
                        # Update existing user
                        existing_id = existing_user_map[uname_norm]
                        update_url = f"{self.client.base_url}/users/{existing_id}"
                        resp = await session.put(update_url, headers=headers, json=user)
                        resp.raise_for_status()
                        updated_on_retry += 1
                        tps_tracker.record_transaction()
                        # Reset rate limit delay on success
                        rate_limit_delay = 0
                    else:
                        # Create new user using pooled connection
                        if api_client.API_LOGGING_ENABLED:
                            try:
                                api_client.append_live_event(f"Creating user: {username or uname}")
                            except Exception:
                                pass
                        
                        create_url = f"{self.client.base_url}/users"
                        resp = await session.post(create_url, headers=headers, json=user)
                        resp.raise_for_status()
                        result = resp.json()
                        created += 1
                        tps_tracker.record_transaction()
                        
                        # Track created user ID for rollback
                        if result and isinstance(result, dict) and result.get('id'):
                            created_ids.append(result['id'])
                        
                        # Reset rate limit delay on success
                        rate_limit_delay = 0
                        
                        # Reset rate limit delay on success
                        rate_limit_delay = 0
                
                except httpx.HTTPStatusError as e:
                    # Handle 429 rate limit responses
                    if e.response.status_code == 429:
                        # Exponential backoff: start with 2s, double each time, max 30s
                        rate_limit_delay = min(rate_limit_delay * 2 if rate_limit_delay > 0 else 2, 30)
                        self.signals.status.emit(f"Rate limited (429). Slowing down import (delay: {rate_limit_delay}s)...")
                        if api_client.API_LOGGING_ENABLED:
                            api_client.api_logger.warning(f"Rate limit hit at user {i+1}/{total}. Delay: {rate_limit_delay}s")
                        # Retry this user with delay
                        await asyncio.sleep(rate_limit_delay)
                        try:
                            if existing_user_map and uname_norm and uname_norm in existing_user_map:
                                existing_id = existing_user_map[uname_norm]
                                update_url = f"{self.client.base_url}/users/{existing_id}"
                                resp = await session.put(update_url, headers=headers, json=user)
                            else:
                                create_url = f"{self.client.base_url}/users"
                                resp = await session.post(create_url, headers=headers, json=user)
                            resp.raise_for_status()
                            result = resp.json()
                            if existing_user_map and uname_norm and uname_norm in existing_user_map:
                                updated_on_retry += 1
                            else:
                                created += 1
                                if result and isinstance(result, dict) and result.get('id'):
                                    created_ids.append(result['id'])
                            tps_tracker.record_transaction()
                        except Exception as retry_err:
                            err_msg = f"User {username or uname}: Rate limit retry failed: {retry_err}"
                            errors.append(err_msg)
                            if api_client.API_LOGGING_ENABLED:
                                api_client.api_logger.error(err_msg)
                        err_text = str(e)
                    if self._is_existing_user_error(err_text):
                        try:
                            if i % 10 == 0 or not existing_user_map:
                                self.signals.status.emit(f"Create conflict for {username}, retrying as update...")
                            
                            # Build user map if not already available
                            if existing_user_map is None:
                                self.signals.status.emit("Building existing-user index for retry updates...")
                                existing_user_map = await self._build_existing_user_map(headers)
                            
                            existing_id = existing_user_map.get(uname_norm)
                            if existing_id:
                                update_url = f"{self.client.base_url}/users/{existing_id}"
                                resp = await session.put(update_url, headers=headers, json=user)
                                resp.raise_for_status()
                                updated_on_retry += 1
                                tps_tracker.record_transaction()
                                if api_client.API_LOGGING_ENABLED:
                                    api_client.write_connection_log(
                                        f"Create->Update retry succeeded for username={username}, user_id={existing_id}"
                                    )
                            else:
                                err_msg = f"User {username}: Already exists but not found in user map"
                                errors.append(err_msg)
                        except Exception as retry_err:
                            err_msg = f"User {username}: Retry as update failed: {retry_err}"
                            errors.append(err_msg)
                            if api_client.API_LOGGING_ENABLED:
                                api_client.write_connection_log(f"Create->Update retry failed for username={username}: {retry_err}")
                    else:
                        # Other HTTP errors
                        err_msg = f"User {username or uname}: {err_text}"
                        errors.append(err_msg)
                        if api_client.API_LOGGING_ENABLED:
                            api_client.api_logger.error(f"Create user failed: {err_msg}")
                
                except Exception as e:
                    # Catch-all for non-HTTP errors
                    err_msg = f"User {username or uname}: {str(e)}"
                    errors.append(err_msg)
                    if api_client.API_LOGGING_ENABLED:
                        api_client.api_logger.error(f"Create user failed: {err_msg}")
                        try:
                            api_client.write_connection_log(f"Create user ERROR - {err_msg}")
                        except Exception:
                            pass
                
                # Emit progress update
                self.signals.progress.emit(i + 1, total)

        # Finalize TPS tracking
        tps_tracker.finish()
        tps_stats = tps_tracker.get_statistics()
        
        if api_client.API_LOGGING_ENABLED:
            api_client.api_logger.info(f"Bulk create completed: {created}/{total} users created, {updated_on_retry} updated")
            try:
                api_client.write_connection_log(f"Bulk create completed: {created}/{total} users created, {updated_on_retry} updated")
            except Exception:
                pass

        # Include any captured errors in the finished payload for UI feedback
        self.signals.finished.emit({
            "created": created,
            "updated_on_retry": updated_on_retry,
            "created_ids": created_ids,  # For rollback functionality
            "total": total,
            "errors": errors,
            "tps_stats": tps_stats,
        })


class UserUpdateWorker(QtCore.QRunnable):
    """Worker to update a single user record via the API.

    Emits `finished` with the updated user or `error` on failure.
    """
    def __init__(self, client, user_id: str, data: dict):
        super().__init__()
        self.client, self.user_id, self.data, self.signals = client, user_id, data, WorkerSignals()

    @QtCore.Slot()
    def run(self):
        # Run the async update operation; the worker wraps the async
        # call so the UI thread is not blocked.
        asyncio.run(self.execute())

    async def execute(self):
        try:
            if api_client.API_LOGGING_ENABLED:
                api_client.api_logger.info(f"UserUpdateWorker: Updating user {self.user_id}")
                try:
                    api_client.append_live_event(f"PUT {self.client.base_url}/users/{self.user_id}")
                except Exception:
                    pass
                try:
                    api_client.write_connection_log(f"UserUpdateWorker: Updating user {self.user_id}")
                except Exception:
                    pass
            result = await self.client.update_user(self.user_id, self.data)
            if api_client.API_LOGGING_ENABLED:
                api_client.api_logger.info(f"UserUpdateWorker: User {self.user_id} updated successfully")
                try:
                    api_client.write_connection_log(f"UserUpdateWorker: User {self.user_id} updated successfully")
                except Exception:
                    pass
            self.signals.finished.emit({"updated": True, "user": result})
        except Exception as e:
            if api_client.API_LOGGING_ENABLED:
                api_client.api_logger.error(f"UserUpdateWorker failed: {str(e)}")
                try:
                    api_client.write_connection_log(f"UserUpdateWorker ERROR - {str(e)}")
                except Exception:
                    pass
            self.signals.error.emit(str(e))


class BulkUpdateWorker(QtCore.QRunnable):
    """Worker to update multiple users with optional parallel processing.

    Emits progress updates and a finished dict with counts and errors.
    
    Supports both sequential and parallel processing modes:
    - Sequential (concurrency=1): Process one user at a time
    - Parallel (concurrency>1): Process multiple users concurrently
    """
    def __init__(self, client, user_pairs: List[tuple], cancel_check=None, concurrency: int = 1):
        """`user_pairs` is a list of (user_id, data) tuples."""
        super().__init__()
        self.client = client
        self.user_pairs = user_pairs
        self.signals = WorkerSignals()
        self.cancel_check = cancel_check  # Callable that returns True if cancel requested
        self.concurrency = max(1, min(concurrency, 10))  # Limit to 1-10 concurrent requests

    @QtCore.Slot()
    def run(self):
        asyncio.run(self.execute())

    async def _update_single_user(self, uid: str, data: dict, semaphore: asyncio.Semaphore) -> dict:
        """Update a single user with rate limit handling.
        
        Returns dict with keys: success, error
        """
        async with semaphore:  # Limit concurrency
            try:
                if api_client.API_LOGGING_ENABLED:
                    api_client.api_logger.info(f"Updating user: {uid}")
                
                await self.client.update_user(uid, data)
                
                if api_client.API_LOGGING_ENABLED:
                    api_client.api_logger.info(f"Updated user: {uid}")
                
                return {"success": True, "error": None}
                
            except httpx.HTTPStatusError as e:
                # Handle 429 rate limit with retry
                if e.response.status_code == 429:
                    await asyncio.sleep(2)  # Back off for rate limit
                    try:
                        await self.client.update_user(uid, data)
                        
                        if api_client.API_LOGGING_ENABLED:
                            api_client.api_logger.info(f"Updated user (retry): {uid}")
                        
                        return {"success": True, "error": None}
                    except Exception as retry_err:
                        if api_client.API_LOGGING_ENABLED:
                            api_client.api_logger.error(f"Update {uid} - Retry failed: {retry_err}")
                        return {"success": False, "error": f"Rate limit retry failed: {retry_err}"}
                else:
                    if api_client.API_LOGGING_ENABLED:
                        api_client.api_logger.error(f"Update {uid} - Failed: {e}")
                    return {"success": False, "error": str(e)}
                    
            except Exception as e:
                if api_client.API_LOGGING_ENABLED:
                    api_client.api_logger.error(f"Update {uid} - Failed: {e}")
                return {"success": False, "error": str(e)}

    async def execute(self):
        # Use parallel processing if concurrency > 1
        if self.concurrency > 1:
            await self._execute_parallel()
        else:
            await self._execute_sequential()

    async def _execute_parallel(self):
        """Execute with parallel processing of updates."""
        # Initialize TPS tracker
        tps_tracker = TPSTracker()
        tps_tracker.start()
        
        import time
        last_tps_update = time.time()
        last_status_update = time.time()
        
        token = await self.client.get_token()
        if not token:
            self.signals.error.emit("Auth Failed. Check credentials.")
            return
        
        updated = 0
        failed = 0
        total = len(self.user_pairs)
        processed = 0
        errors = []
        failed_ids = []
        
        # Create semaphore to limit concurrency
        semaphore = asyncio.Semaphore(self.concurrency)
        
        # Process users in batches
        batch_size = self.concurrency * 2  # Process 2 rounds of concurrent requests at a time
        for batch_start in range(0, total, batch_size):
            if self.cancel_check and self.cancel_check():
                errors.append("Update cancelled by user")
                self.signals.status.emit(f"Update cancelled after {processed} of {total} users")
                break
            
            batch_end = min(batch_start + batch_size, total)
            batch = self.user_pairs[batch_start:batch_end]
            
            # Process batch in parallel
            tasks = [
                self._update_single_user(uid, data, semaphore)
                for uid, data in batch
            ]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Process results
            for i, result in enumerate(results):
                processed += 1
                uid, _ = batch[i]
                
                if isinstance(result, Exception):
                    failed += 1
                    failed_ids.append(uid)
                    err_msg = f"User {uid}: {str(result)}"
                    errors.append(err_msg)
                    if api_client.API_LOGGING_ENABLED:
                        api_client.api_logger.error(err_msg)
                elif result.get('success'):
                    updated += 1
                    tps_tracker.record_transaction()
                else:
                    failed += 1
                    failed_ids.append(uid)
                    err_msg = f"User {uid}: {result.get('error', 'Unknown error')}"
                    errors.append(err_msg)
                
                # Emit progress
                self.signals.progress.emit(processed, total)
                
                # Status update every 1 second
                current_time = time.time()
                if current_time - last_status_update >= 1.0 or processed == total:
                    percentage = int(processed / total * 100)
                    self.signals.status.emit(f"Updating {processed}/{total} ({percentage}%) - {self.concurrency} concurrent")
                    last_status_update = current_time
                
                # TPS update every 10 seconds
                if current_time - last_tps_update >= 10.0:
                    tps_stats = tps_tracker.get_statistics()
                    self.signals.tps_update.emit(tps_stats)
                    last_tps_update = current_time
        
        # Finalize
        tps_tracker.finish()
        tps_stats = tps_tracker.get_statistics()
        
        if api_client.API_LOGGING_ENABLED:
            api_client.api_logger.info(f"Parallel update completed: {updated}/{total} users updated, {failed} failed")
        
        self.signals.finished.emit({
            "updated": updated,
            "failed": failed,
            "failed_ids": failed_ids,
            "total": total,
            "errors": errors,
            "tps_stats": tps_stats,
        })

    async def _execute_sequential(self):
        """Execute with sequential processing of updates (original logic)."""
        # Initialize TPS tracker
        tps_tracker = TPSTracker()
        tps_tracker.start()
        
        # Track last TPS update time
        import time
        last_tps_update = time.time()
        
        token = await self.client.get_token()
        if not token:
            self.signals.error.emit("Auth Failed. Check credentials.")
            return
        total = len(self.user_pairs)
        updated = 0
        failed = 0
        errors = []
        failed_ids = []
        
        # Add timeout for all HTTP operations
        async with httpx.AsyncClient(timeout=30.0) as session:
            for i, (uid, data) in enumerate(self.user_pairs):
                # Check for cancellation
                if self.cancel_check and self.cancel_check():
                    errors.append("Update cancelled by user")
                    self.signals.status.emit(f"Update cancelled after {updated} of {total} users")
                    break
                
                try:
                    # Emit status with progress counter and percentage
                    percentage = int((i + 1) / total * 100)
                    self.signals.status.emit(f"Updating user {i+1}/{total} ({percentage}%): {uid}")
                    
                    # Emit TPS update every 10 seconds
                    current_time = time.time()
                    if current_time - last_tps_update >= 10.0:
                        tps_stats = tps_tracker.get_statistics()
                        self.signals.tps_update.emit(tps_stats)
                        last_tps_update = current_time
                    
                    if api_client.API_LOGGING_ENABLED:
                        api_client.api_logger.info(f"Updating user {i+1}/{total} ({percentage}%): {uid}")
                        try:
                            api_client.append_live_event(f"Updating user: {uid}")
                        except Exception:
                            pass
                        try:
                            api_client.write_connection_log(f"Updating user: {uid}")
                        except Exception:
                            pass
                    
                    await self.client.update_user(uid, data)
                    updated += 1
                    tps_tracker.record_transaction()  # Record successful transaction
                    
                except httpx.HTTPStatusError as e:
                    # Handle 429 rate limit with retry
                    if e.response.status_code == 429:
                        await asyncio.sleep(2)  # Back off for rate limit
                        try:
                            await self.client.update_user(uid, data)
                            updated += 1
                            tps_tracker.record_transaction()
                            if api_client.API_LOGGING_ENABLED:
                                api_client.api_logger.info(f"Update {uid} - Retry succeeded")
                        except Exception as retry_err:
                            failed += 1
                            failed_ids.append(uid)
                            err_msg = f"User {uid}: Rate limit retry failed: {retry_err}"
                            errors.append(err_msg)
                            if api_client.API_LOGGING_ENABLED:
                                api_client.api_logger.error(err_msg)
                    else:
                        failed += 1
                        failed_ids.append(uid)
                        err_msg = f"User {uid}: {str(e)}"
                        errors.append(err_msg)
                        if api_client.API_LOGGING_ENABLED:
                            api_client.api_logger.error(f"Update failed: {err_msg}")
                            
                except Exception as e:
                    failed += 1
                    failed_ids.append(uid)
                    err_msg = f"User {uid}: {str(e)}"
                    errors.append(err_msg)
                    if api_client.API_LOGGING_ENABLED:
                        api_client.api_logger.error(f"Update failed: {err_msg}")
                        try:
                            api_client.write_connection_log(f"Update user ERROR - {err_msg}")
                        except Exception:
                            pass
                            
                self.signals.progress.emit(i + 1, total)

        # Finalize TPS tracking
        tps_tracker.finish()
        tps_stats = tps_tracker.get_statistics()
        
        if api_client.API_LOGGING_ENABLED:
            api_client.api_logger.info(f"Bulk update completed: {updated}/{total} users updated, {failed} failed")
            try:
                api_client.write_connection_log(f"Bulk update completed: {updated}/{total} users updated, {failed} failed")
            except Exception:
                pass

        self.signals.finished.emit({
            "updated": updated,
            "failed": failed,
            "failed_ids": failed_ids,
            "total": total,
            "errors": errors,
            "tps_stats": tps_stats,
        })
