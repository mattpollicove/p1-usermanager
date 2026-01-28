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
    """
    finished = QtCore.Signal(dict)
    progress = QtCore.Signal(int, int)
    error = QtCore.Signal(str)


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
            # Obtain token (cached by client) - if None, emit an error
            token = await self.client.get_token()
            if not token:
                self.signals.error.emit("Auth Failed. Check credentials.")
                return

            headers = {"Authorization": f"Bearer {token}"}
            # Use a short-lived AsyncClient for this worker to avoid sharing
            # the same AsyncClient across threads/event loops.
            async with httpx.AsyncClient(timeout=10.0) as session:
                # Fetch populations mapping (small metadata lookup)
                if api_client.API_LOGGING_ENABLED:
                    api_client.api_logger.info(f"GET {self.client.base_url}/populations")
                    try:
                        api_client.append_live_event(f"GET {self.client.base_url}/populations")
                    except Exception:
                        pass
                p_resp = await session.get(f"{self.client.base_url}/populations", headers=headers)
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

            # Emit the consolidated results back to the UI thread
            # so the main window can refresh its table.
            self.signals.finished.emit({
                "users": all_users,
                "pop_map": pop_map,
                "user_count": len(all_users),
                "pop_count": len(pop_map)
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
    """Worker to perform bulk user deletions sequentially.

    Emits progress updates and a final `finished` result with counts.
    """
    def __init__(self, client, user_ids: List[str]):
        super().__init__()
        self.client, self.user_ids, self.signals = client, user_ids, WorkerSignals()

    @QtCore.Slot()
    def run(self):
        # Run the async delete loop inside an event loop provided
        # by asyncio.run when the QRunnable executes.
        asyncio.run(self.execute())

    async def execute(self):
        token = await self.client.get_token()
        if not token:
            self.signals.error.emit("Auth Failed. Check credentials.")
            return
        headers = self.client._get_auth_headers(token)
        success = 0
        # Use a short-lived AsyncClient for deletes to avoid sharing
        async with httpx.AsyncClient(timeout=10.0) as session:
            # Iterate user IDs and perform DELETE requests one-by-one.
            # This keeps load predictable and allows progress reporting.
            for i, uid in enumerate(self.user_ids):
                delete_url = f"{self.client.base_url}/users/{uid}"
                try:
                    if api_client.API_LOGGING_ENABLED:
                        api_client.api_logger.info(f"DELETE {delete_url}")
                        try:
                            api_client.append_live_event(f"DELETE {delete_url}")
                        except Exception:
                            pass
                    resp = await session.delete(delete_url, headers=headers)
                    if api_client.API_LOGGING_ENABLED:
                        api_client.api_logger.info(f"DELETE {delete_url} - Status: {resp.status_code}")
                        try:
                            api_client.write_connection_log(f"DELETE {delete_url} - {resp.status_code}")
                        except Exception:
                            pass
                    success += 1
                except Exception as e:
                    if api_client.API_LOGGING_ENABLED:
                        api_client.api_logger.error(f"DELETE {delete_url} - Failed: {str(e)}")
                        try:
                            api_client.write_connection_log(f"DELETE {delete_url} - ERROR - {str(e)}")
                        except Exception:
                            pass
                self.signals.progress.emit(i + 1, len(self.user_ids))
        if api_client.API_LOGGING_ENABLED:
            api_client.api_logger.info(f"Bulk delete completed: {success}/{len(self.user_ids)} users deleted")
            try:
                api_client.write_connection_log(f"Bulk delete completed: {success}/{len(self.user_ids)} users deleted")
            except Exception:
                pass
        self.signals.finished.emit({"deleted": success, "total": len(self.user_ids)})


class BulkCreateWorker(QtCore.QRunnable):
    """Worker to create multiple users sequentially.

    Emits progress updates and a final `finished` result with counts.
    """
    def __init__(self, client, users: List[dict]):
        super().__init__()
        self.client, self.users, self.signals = client, users, WorkerSignals()

    @QtCore.Slot()
    def run(self):
        asyncio.run(self.execute())

    async def execute(self):
        # Ensure we have a valid token before attempting creates
        token = await self.client.get_token()
        if not token:
            self.signals.error.emit("Auth Failed. Check credentials.")
            return
        created = 0
        total = len(self.users)
        errors = []

        # Removed server-side dry-run validation phase; proceed directly to creates

        # If validation passed for all users, proceed to create them sequentially
        for i, user in enumerate(self.users):
            try:
                if api_client.API_LOGGING_ENABLED:
                    api_client.api_logger.info(f"Creating user: {user.get('username') or user.get('id')}")
                    try:
                        api_client.append_live_event(f"Creating user: {user.get('username') or user.get('id')}")
                    except Exception:
                        pass
                    try:
                        api_client.write_connection_log(f"Creating user: {user.get('username') or user.get('id')}")
                    except Exception:
                        pass
                # Use client.create_user which handles auth and logging
                await self.client.create_user(user)
                created += 1
            except Exception as e:
                # Capture error message for UI feedback
                err_msg = f"User {user.get('username') or user.get('id')}: {str(e)}"
                errors.append(err_msg)
                if api_client.API_LOGGING_ENABLED:
                    api_client.api_logger.error(f"Create user failed: {err_msg}")
                    try:
                        api_client.write_connection_log(f"Create user ERROR - {err_msg}")
                    except Exception:
                        pass
            self.signals.progress.emit(i + 1, total)

        if api_client.API_LOGGING_ENABLED:
            api_client.api_logger.info(f"Bulk create completed: {created}/{total} users created")
            try:
                api_client.write_connection_log(f"Bulk create completed: {created}/{total} users created")
            except Exception:
                pass

        # Include any captured errors in the finished payload for UI feedback
        self.signals.finished.emit({"created": created, "total": total, "errors": errors})


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
    """Worker to update multiple users sequentially.

    Emits progress updates and a finished dict with counts and errors.
    """
    def __init__(self, client, user_pairs: List[tuple]):
        """`user_pairs` is a list of (user_id, data) tuples."""
        super().__init__()
        self.client = client
        self.user_pairs = user_pairs
        self.signals = WorkerSignals()

    @QtCore.Slot()
    def run(self):
        asyncio.run(self.execute())

    async def execute(self):
        token = await self.client.get_token()
        if not token:
            self.signals.error.emit("Auth Failed. Check credentials.")
            return
        total = len(self.user_pairs)
        updated = 0
        errors = []
        async with httpx.AsyncClient(timeout=10.0) as session:
            for i, (uid, data) in enumerate(self.user_pairs):
                try:
                    if api_client.API_LOGGING_ENABLED:
                        api_client.api_logger.info(f"Updating user: {uid}")
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
                except Exception as e:
                    err_msg = f"User {uid}: {str(e)}"
                    errors.append(err_msg)
                    if api_client.API_LOGGING_ENABLED:
                        api_client.api_logger.error(f"Update failed: {err_msg}")
                        try:
                            api_client.write_connection_log(f"Update user ERROR - {err_msg}")
                        except Exception:
                            pass
                self.signals.progress.emit(i + 1, total)

        if api_client.API_LOGGING_ENABLED:
            api_client.api_logger.info(f"Bulk update completed: {updated}/{total} users updated")
            try:
                api_client.write_connection_log(f"Bulk update completed: {updated}/{total} users updated")
            except Exception:
                pass

        self.signals.finished.emit({"updated": updated, "total": total, "errors": errors})
