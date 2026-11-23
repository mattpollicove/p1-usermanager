# Fix: 'lazy_import' Object Is Not Callable Error

## Problem

When testing credentials or connecting to PingOne from the UI, users received the error:
```
'lazy_import' object is not callable
```

## Root Cause

The error occurred because:

1. PySide6 runs its own event loop (Qt event loop)
2. The UI was calling `asyncio.run(client.get_token())` to execute async code
3. `asyncio.run()` tries to create a NEW event loop
4. When an event loop is already running (the Qt loop), creating another one causes conflicts
5. This manifests as a 'lazy_import' error from httpx's internal lazy import mechanism

## Solution

Created a new helper function `run_async_in_ui_context()` in `api/client.py` that:

1. **Detects** if an event loop is already running
2. **If running** (Qt context):
   - Runs the async code in a **separate thread** with its own event loop
   - Avoids conflicts with the Qt event loop
   - Uses `concurrent.futures.ThreadPoolExecutor` for clean thread management
3. **If not running** (command-line or non-UI context):
   - Uses the standard `asyncio.run()` as before
   - Maintains backward compatibility with existing code

## Code Changes

### api/client.py

Added helper function (before PingOneClient class):
```python
def run_async_in_ui_context(coro):
    """Run an async coroutine safely in a Qt UI context."""
    try:
        # Check if event loop already running
        loop = asyncio.get_running_loop()
        # If we get here, we're in a Qt context - use separate thread
        import concurrent.futures
        
        def run_in_thread():
            new_loop = asyncio.new_event_loop()
            asyncio.set_event_loop(new_loop)
            try:
                return new_loop.run_until_complete(coro)
            finally:
                new_loop.close()
        
        with concurrent.futures.ThreadPoolExecutor() as executor:
            future = executor.submit(run_in_thread)
            return future.result()
    except RuntimeError:
        # No event loop running - safe to use asyncio.run()
        return asyncio.run(coro)
```

### ui/main_window.py

Updated two methods to use the helper:

**In `test_credentials()` method (line ~6410):**
```python
# Before:
token = asyncio.run(client.get_token())

# After:
token = api_client.run_async_in_ui_context(client.get_token())
```

**In `connect_only()` method (line ~5274):**
```python
# Before:
token = asyncio.run(client.get_token())

# After:
token = api_client.run_async_in_ui_context(client.get_token())
```

## Benefits

✅ **Fixes the error** - No more 'lazy_import' errors when testing credentials  
✅ **Thread-safe** - Each async operation runs in its own thread context  
✅ **Backward compatible** - Non-UI code (CLI, scripts) continues to work normally  
✅ **Clean** - Uses standard library only (no extra dependencies)  
✅ **Efficient** - ThreadPoolExecutor automatically manages thread lifecycle  

## Testing

The fix has been verified to:
- ✓ Work with both test credentials and connect flows
- ✓ Handle errors properly (401 Unauthorized, network errors, etc.)
- ✓ Support optional profile names in success messages
- ✓ Maintain all existing functionality

## Related Files

- `api/client.py` - Helper function + better error logging with traceback
- `ui/main_window.py` - Updated test_credentials() and connect_only() methods
- `CONNECTION_SUCCESS_MESSAGES.md` - Feature enhancements for showing instance names
