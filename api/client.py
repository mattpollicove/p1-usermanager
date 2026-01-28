import time
import json
import logging
import sys
from pathlib import Path
from typing import Optional
from datetime import datetime

# Ensure project root is on sys.path when running this module directly
_THIS_FILE = Path(__file__).resolve()
_PROJECT_ROOT = _THIS_FILE.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

import httpx
import asyncio
import atexit

"""API client utilities for PingOne interactions.

This module provides a focused HTTP client wrapper used by the UI and
background workers. It centralizes token management, exposes a runtime
toggle for detailed API logging, and offers a simple connection-level
log writer the UI can display for debugging.
"""

# --- 0. METADATA ---
LOG_FILE = Path("api_calls.log")

# Separate connection log for connection-related messages and API call/response snapshots
CONNECTION_LOG = Path("connection_errors.log")

# Credentials-specific log file (no secrets are written)
CREDENTIALS_LOG = Path("credentials.log")

# Global logging flag (can be toggled by UI)
API_LOGGING_ENABLED = False

# Live capture controls for UI-driven capture sessions
LIVE_CAPTURE_ENABLED = False
_LIVE_EVENTS = []

def enable_live_capture(enabled: bool):
    global LIVE_CAPTURE_ENABLED
    LIVE_CAPTURE_ENABLED = bool(enabled)
    try:
        api_logger.info("Live API capture %s", "enabled" if enabled else "disabled")
    except Exception:
        pass

def append_live_event(message: str):
    try:
        if LIVE_CAPTURE_ENABLED:
            _LIVE_EVENTS.append(f"{datetime.utcnow().isoformat()}Z {message}")
    except Exception:
        pass

def get_and_clear_live_events() -> list:
    global _LIVE_EVENTS
    ev = list(_LIVE_EVENTS)
    _LIVE_EVENTS = []
    return ev


def init_logger():
    """Initialize logger for API calls."""
    logger = logging.getLogger("PingOneAPI")
    logger.setLevel(logging.DEBUG)
    if not logger.handlers:
        handler = logging.FileHandler(LOG_FILE, mode='a', encoding='utf-8')
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    return logger


api_logger = init_logger()


def init_credential_logger():
    """Logger for credential-related events (token requests/results).

    This logger must NOT write secrets. It records attempts, successes,
    failures and timestamps to a separate file for auditing.
    """
    logger = logging.getLogger("PingOneCredentials")
    logger.setLevel(logging.INFO)
    if not logger.handlers:
        handler = logging.FileHandler(CREDENTIALS_LOG, mode='a', encoding='utf-8')
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    return logger


credential_logger = init_credential_logger()

# Control whether credential events are recorded (defaults to True)
CREDENTIALS_LOGGING_ENABLED = True


def set_credentials_logging(enabled: bool):
    global CREDENTIALS_LOGGING_ENABLED
    CREDENTIALS_LOGGING_ENABLED = bool(enabled)
    credential_logger.info("Credentials logging %s", "enabled" if enabled else "disabled")


def set_credentials_log_level(level_name: str):
    try:
        lvl = getattr(logging, level_name.upper(), None)
        if lvl is None:
            return
        credential_logger.setLevel(lvl)
        credential_logger.info(f"Credentials log level set to {level_name}")
    except Exception:
        pass


# Note: AsyncClient instances should not be shared across threads or
# event loops. Create short-lived AsyncClient instances per async
# operation (using `async with`) to avoid unsafe concurrent reuse.


def set_api_logging(enabled: bool):
    """Enable or disable API logging at runtime.

    This updates the module-level flag so other modules can check
    `api.client.API_LOGGING_ENABLED` at runtime, and ensures the
    logger is ready to receive messages.
    """
    global API_LOGGING_ENABLED
    API_LOGGING_ENABLED = bool(enabled)
    if API_LOGGING_ENABLED:
        # Record the toggle event so there is an audit trail of when logging
        # was enabled; the UI shows the path to the log files for user.
        api_logger.info("API logging enabled via set_api_logging()")
    else:
        api_logger.info("API logging disabled via set_api_logging()")


def close_async_client() -> None:
    """Compatibility helper: previously the module exposed a function to
    synchronously close a shared AsyncClient. The client was changed to
    use short-lived AsyncClient instances per operation; keep a no-op
    function so callers (e.g. `app.aboutToQuit.connect`) continue to work.
    """
    try:
        api_logger.info("close_async_client called (no-op)")
    except Exception:
        pass


def write_connection_log(message: str):
    """Append a connection-related message to `connection_errors.log`.

    This is used for both error traces and (optionally) for recording
    API request/response pairs when debugging connections.

    The function is intentionally simple and tolerant of IO errors so
    it will not interfere with normal app operation.
    """
    try:
        # Use UTC timestamp so logs are consistent regardless of user timezone
        ts = datetime.utcnow().isoformat() + "Z"
        with open(CONNECTION_LOG, "a", encoding="utf-8") as f:
            f.write(f"[{ts}] {message}\n")
        # Also append to live capture buffer when enabled
        try:
            append_live_event(message)
        except Exception:
            pass
    except Exception:
        # Intentionally ignore failures to avoid cascading errors in the app
        pass



class PingOneClient:
    """Client for interacting with PingOne API."""
    def __init__(self, env_id: str, client_id: str, client_secret: str):
        self.env_id = env_id
        self.client_id = client_id
        self.client_secret = client_secret
        self.base_url = f"https://api.pingone.com/v1/environments/{env_id}"
        self._token: Optional[str] = None
        self._token_expires = 0

    def _get_auth_headers(self, token: str) -> dict:
        """Helper method to create authorization headers."""
        # Centralize header creation so any future global headers (e.g.
        # Accept, tracing IDs) are added in a single place.
        return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    async def get_token(self) -> Optional[str]:
        """Retrieve and cache access token for API authentication."""
        now = time.time()
        if self._token and now < self._token_expires:
            return self._token

        auth_url = f"https://auth.pingone.com/{self.env_id}/as/token"
        # Execute the HTTP token request; callers rely on `None` return
        # value to indicate that authentication failed.
        try:
            append_live_event(f"TOKEN POST {auth_url}")
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(
                    auth_url,
                    data={"grant_type": "client_credentials"},
                    auth=(self.client_id, self.client_secret),
                )
            resp.raise_for_status()
            data = resp.json()
            self._token = data.get("access_token")
            self._token_expires = now + data.get("expires_in", 3600) - 60

            # Always log credential-related events (without secrets) to the
            # credential logger if enabled. API logging remains separate.
            if CREDENTIALS_LOGGING_ENABLED:
                try:
                    credential_logger.info(f"Token obtained for env={self.env_id}, client_id={self.client_id}, expires_in={data.get('expires_in', 3600)}s")
                except Exception:
                    pass
            if API_LOGGING_ENABLED:
                api_logger.info(f"Token obtained: expires_in={data.get('expires_in', 3600)}s")
                # Include request/response summary in the connection log as well
                try:
                    write_connection_log(f"POST {auth_url} - 200 OK - token_expires_in={data.get('expires_in', 3600)}")
                except Exception:
                    pass

            return self._token
        except Exception as e:
            # Log the exception to credential logger and API logger/connection log
            try:
                if CREDENTIALS_LOGGING_ENABLED:
                    credential_logger.error(f"Token request failed for env={self.env_id}, client_id={self.client_id} - {str(e)}")
            except Exception:
                pass
            if API_LOGGING_ENABLED:
                api_logger.error(f"Token request failed: {str(e)}")
                try:
                    write_connection_log(f"POST {auth_url} - ERROR - {str(e)}")
                except Exception:
                    pass
            return None

    async def update_user(self, user_id: str, data: dict) -> dict:
        """Update a user's information in PingOne."""
        token = await self.get_token()
        if not token:
            raise Exception("Auth Failed. Check credentials.")
        headers = self._get_auth_headers(token)
        update_url = f"{self.base_url}/users/{user_id}"
        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                # Optionally record request body/URL
                if API_LOGGING_ENABLED:
                    api_logger.info(f"PUT {update_url} - Request body: {json.dumps(data)}")
                    append_live_event(f"PUT {update_url}")
                    write_connection_log(f"PUT {update_url} - Request: {json.dumps(data)}")

                resp = await client.put(update_url, headers=headers, json=data)
                try:
                    resp.raise_for_status()
                except httpx.HTTPStatusError as he:
                    # Include response body for diagnostics
                    body = None
                    try:
                        body = he.response.text
                    except Exception:
                        body = str(he)
                    msg = f"{str(he)} - Response: {body}"
                    # Log the failing update including request body for debugging
                    try:
                        short_req = json.dumps(data) if isinstance(data, (dict, list)) else str(data)
                        if len(short_req) > 2000:
                            short_req = short_req[:2000] + '...'
                        write_connection_log(f"UPDATE FAILED for user={user_id} - Request: {short_req} - Response: {body}")
                        append_live_event(f"Update failed for {user_id}")
                        api_logger.error(f"PUT {update_url} failed: {msg}")
                    except Exception:
                        pass
                    raise Exception(msg)
                result = resp.json()

                # Record response status and a short preview in logs when enabled
                if API_LOGGING_ENABLED:
                    api_logger.info(f"PUT {update_url} - Status: {resp.status_code}")
                    # Write a compact response summary to the connection log.
                    try:
                        preview = json.dumps(result) if isinstance(result, (dict, list)) else str(result)
                        if len(preview) > 1000:
                            preview = preview[:1000] + '...'
                        write_connection_log(f"PUT {update_url} - {resp.status_code} - Response: {preview}")
                    except Exception:
                        pass
                return result
            except Exception as e:
                if API_LOGGING_ENABLED:
                    api_logger.error(f"PUT {update_url} failed: {str(e)}")
                    try:
                        write_connection_log(f"PUT {update_url} - ERROR - {str(e)}")
                    except Exception:
                        pass
                raise

    async def create_user(self, data: dict) -> dict:
        """Create a new user in PingOne.

        Returns the created user object on success.
        """
        token = await self.get_token()
        if not token:
            raise Exception("Auth Failed. Check credentials.")
        headers = self._get_auth_headers(token)
        create_url = f"{self.base_url}/users"
        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                params = None
                append_live_event(f"POST {create_url}")
                resp = await client.post(create_url, headers=headers, json=data)
                try:
                    resp.raise_for_status()
                except httpx.HTTPStatusError as he:
                    # Include response body for diagnostics
                    body = None
                    try:
                        body = he.response.text
                    except Exception:
                        body = str(he)
                    msg = f"{str(he)} - Response: {body}"
                    # Always write the request payload to the connection log
                    # on create failures to aid debugging of uniqueness errors.
                    try:
                        uname = data.get('username') if isinstance(data, dict) else None
                        short_req = json.dumps(data) if isinstance(data, (dict, list)) else str(data)
                        if len(short_req) > 2000:
                            short_req = short_req[:2000] + '...'
                        write_connection_log(f"CREATE FAILED for user={uname or '<unknown>'} - Request: {short_req} - Response: {body}")
                        append_live_event(f"Create failed for {uname or '<unknown>'}")
                        api_logger.error(f"Create failed for {uname or '<unknown>'}: {body}")
                    except Exception:
                        pass
                    raise Exception(msg)
                result = resp.json()

                if API_LOGGING_ENABLED:
                    api_logger.info(f"POST {create_url} - Status: {resp.status_code}")
                    try:
                        preview = json.dumps(result) if isinstance(result, (dict, list)) else str(result)
                        if len(preview) > 1000:
                            preview = preview[:1000] + '...'
                        write_connection_log(f"POST {create_url} - {resp.status_code} - Response: {preview}")
                    except Exception:
                        pass
                return result
            except Exception as e:
                if API_LOGGING_ENABLED:
                    api_logger.error(f"POST {create_url} failed: {str(e)}")
                    try:
                        write_connection_log(f"POST {create_url} - ERROR - {str(e)}")
                    except Exception:
                        pass
                raise

    async def validate_user(self, data: dict, dry_run: bool = True) -> dict:
        """Validate a user payload. If `dry_run` is True, POST to the
        create endpoint with `?dryRun=true` to let the server validate
        without creating. Returns the response JSON on success or raises
        an exception with the response body on validation failure.
        """
        token = await self.get_token()
        if not token:
            raise Exception("Auth Failed. Check credentials.")
        headers = self._get_auth_headers(token)
        create_url = f"{self.base_url}/users"
        params = {'dryRun': 'true'} if dry_run else None
        async with httpx.AsyncClient(timeout=10.0) as client:
            append_live_event(f"POST {create_url} (dryRun={dry_run})")
            resp = await client.post(create_url, headers=headers, json=data, params=params)
            try:
                resp.raise_for_status()
            except httpx.HTTPStatusError as he:
                body = None
                try:
                    body = he.response.text
                except Exception:
                    body = str(he)
                msg = f"{str(he)} - Response: {body}"
                # Diagnostic logging to help trace which payload caused a
                # validation failure. Include username (if present) and a
                # truncated request body in the connection log and live
                # capture buffer.
                try:
                    uname = data.get('username') if isinstance(data, dict) else None
                    short_req = json.dumps(data) if isinstance(data, (dict, list)) else str(data)
                    if len(short_req) > 2000:
                        short_req = short_req[:2000] + '...'
                    write_connection_log(f"VALIDATION FAILED for user={uname or '<unknown>'} - Request: {short_req} - Response: {body}")
                    append_live_event(f"Validation failed for {uname or '<unknown>'}")
                    api_logger.error(f"Validation failed for {uname or '<unknown>'}: {body}")
                except Exception:
                    pass
                raise Exception(msg)
            return resp.json()

    def local_validate_user(self, data: dict) -> None:
        """Perform local JSON Schema validation if `jsonschema` and a
        `user_schema.json` file are available. If validation fails an
        Exception is raised. If no schema or library is present this is a no-op.
        """
        try:
            import jsonschema
        except Exception:
            # jsonschema not installed; skip local validation
            return
        schema_file = Path(__file__).resolve().parent.parent / 'user_schema.json'
        if not schema_file.exists():
            return
        try:
            with open(schema_file, 'r', encoding='utf-8') as f:
                schema = json.load(f)
            jsonschema.validate(instance=data, schema=schema)
        except Exception as e:
            raise

    async def get_populations(self) -> dict:
        """Return a mapping of population names to IDs for the environment."""
        token = await self.get_token()
        if not token:
            raise Exception("Auth Failed. Check credentials.")
        headers = self._get_auth_headers(token)
        url = f"{self.base_url}/populations"
        async with httpx.AsyncClient(timeout=10.0) as client:
            append_live_event(f"GET {url}")
            resp = await client.get(url, headers=headers)
            resp.raise_for_status()
            data = resp.json()
            pops = {p['name']: p['id'] for p in data.get('_embedded', {}).get('populations', [])}
            return pops
