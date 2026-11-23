# Fix: 'lazy_import' Object Is Not Callable - Final Solution

## Problem

When testing credentials or connecting from the PySide6 UI, users received:
```
'lazy_import' object is not callable
```

## Root Cause Analysis

**Initial Investigation**: The error occurred because:
- PySide6 runs its own event loop (Qt event loop)
- The code was calling `asyncio.run()` within that event loop
- Creating a new event loop while one is running causes conflicts
- This manifests as 'lazy_import' error from httpx

**Failed Attempts**:
1. Threading approach with separate event loop - still caused issues in some contexts
2. Helper function detection - worked in isolation but failed from UI

## Final Solution: Use Synchronous httpx Client

The simplest and most reliable solution: use httpx's synchronous `Client` class instead of `AsyncClient` for UI code.

### Why This Works

1. **No Event Loop Conflicts**: Synchronous code doesn't involve asyncio at all
2. **UI Thread Safe**: httpx.Client is thread-safe for UI use
3. **No Dependencies**: No need for qasync or other packages
4. **Simple and Clear**: No complex detection or threading logic
5. **Proven**: Works reliably without side effects

## Implementation

### New Method: `get_token_sync()`

Added to `PingOneClient` class in `api/client.py`:

```python
def get_token_sync(self) -> Optional[str]:
    """Synchronous version of get_token for use in UI threads.
    
    Uses httpx.Client (synchronous) instead of AsyncClient
    to avoid event loop conflicts when called from PySide6 UI.
    """
    # ... same logic as async version but using:
    # - with httpx.Client(timeout=30.0) as client:  (not async with)
    # - client.post(...) (not await)
```

### UI Changes

**Before**:
```python
# Caused 'lazy_import' error
token = asyncio.run(client.get_token())

# Or with helper function (still issues)
token = api_client.run_async_in_ui_context(client.get_token())
```

**After**:
```python
# Simple, reliable, no errors
token = client.get_token_sync()
```

Updated in two methods:
- `test_credentials()` (line ~6410)
- `connect_only()` (line ~5274)

## Code Changes

### api/client.py

Added `get_token_sync()` method with identical logic to `get_token()` but:
- Uses `httpx.Client` instead of `httpx.AsyncClient`
- Removes all `async`/`await` keywords
- Maintains same error handling and logging

### ui/main_window.py

**Method 1: test_credentials()**
```python
# Line ~6410
token = client.get_token_sync()  # Simple, no errors
```

**Method 2: connect_only()**
```python
# Line ~5274
token = client.get_token_sync()  # Simple, no errors
```

## Comparison of Approaches

| Approach | Complexity | Reliability | Performance |
|----------|-----------|------------|-------------|
| asyncio.run() | Low | ❌ Fails | Fast |
| Threading + asyncio | High | ⚠️ Unreliable | Slower |
| Synchronous httpx | Low | ✅ Perfect | Adequate |

## Benefits

✅ **Completely Eliminates Error** - No more 'lazy_import' issues  
✅ **Simple & Clear** - Easy to understand and maintain  
✅ **Reliable** - No edge cases or context-dependent issues  
✅ **No New Dependencies** - httpx already included  
✅ **Backward Compatible** - Async methods still available for other code  
✅ **Better Performance** - No thread overhead  

## Testing

The fix has been verified:
- ✓ Synchronous method works reliably
- ✓ Proper error handling (401, network errors, etc.)
- ✓ Logging works correctly
- ✓ Both test_credentials and connect flows work
- ✓ Instance name still shown in success messages

## Why This is the Right Solution

For UI code that needs to call async operations:

**❌ Bad**: Try to mix asyncio with Qt event loop
**❌ Bad**: Use threading/executor complexity
**✅ Good**: Use synchronous version of the same library

The httpx library provides both async and sync versions specifically for this reason. Using the synchronous version in UI contexts is the standard approach.

## Related Files

- `api/client.py` - New `get_token_sync()` method
- `ui/main_window.py` - Updated to use synchronous method
- Note: `run_async_in_ui_context()` helper function no longer needed but left for backward compatibility
