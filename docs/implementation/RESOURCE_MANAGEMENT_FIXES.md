# Resource Management Fixes - Telegram Bot Response Time Degradation

## Problem Summary

After the monitoring program runs for several hours, the Telegram bot becomes increasingly slow to respond, taking several minutes to reply to commands.

## Root Causes Identified

### 1. **HTTP Client Resource Leak in Checkers** (Critical)

**Location**: `src/monitor.py:315` and checker lifecycle
**Issue**: Every 15 minutes, `perform_checks()` creates new checker instances via `_initialize_checkers_for_site()`. Each checker creates its own `httpx.Client`, but these clients were never explicitly closed. Over time, hundreds of unclosed HTTP connections, file descriptors, and memory accumulate, degrading system performance and making the bot thread sluggish.

### 2. **Unreliable TelegramNotifier Client Cleanup**

**Location**: `src/notifiers/telegram_notifier.py:68, 371-374`
**Issue**: The TelegramNotifier kept a persistent `httpx.Client` and relied on the unreliable `__del__` method for cleanup, which may never be called in Python.

### 3. **Thread Pool Exhaustion from Bot Commands**

**Location**: `src/bot/telegram_bot_handler.py:257-259`
**Issue**: The `/check` command used `run_in_executor(None, ...)` which blocks threads from the default thread pool. Multiple commands in succession could exhaust the pool, causing bot commands to queue up and respond slowly.

## Fixes Implemented

### Fix 1: Explicit Checker Cleanup (Critical Fix)

**File**: `src/monitor.py:341-453`

Added a `finally` block to `_perform_site_checks()` that explicitly calls `cleanup()` on all checkers after each check cycle:

```python
try:
    # ... perform checks ...
    return results
finally:
    # CRITICAL: Cleanup all checkers to prevent resource leaks
    for check_type, checker in checkers.items():
        try:
            checker.cleanup()
            self.logger.debug(f"[{site_name}] Cleaned up {check_type} checker")
        except Exception as e:
            self.logger.error(f"[{site_name}] Error cleaning up {check_type} checker: {e}")
```

**Impact**: Prevents accumulation of HTTP clients, connections, and file descriptors over time.

### Fix 2: Context Manager for TelegramNotifier HTTP Client

**Files**:
- `src/notifiers/telegram_notifier.py:62-68` (removed persistent client)
- `src/notifiers/telegram_notifier.py:329-375` (use context manager)

Changed from persistent HTTP client to fresh client per request with automatic cleanup:

```python
# Before: Persistent client (leak-prone)
self.http_client = httpx.Client(timeout=10.0)

# After: Context manager (proper cleanup)
with httpx.Client(timeout=10.0) as client:
    response = client.post(url, json=payload)
    # ... handle response ...
```

Removed unreliable `__del__` method.

**Impact**: Eliminates resource leaks from long-lived notifier instances.

### Fix 3: Connection Pool Limits for HTTP Clients

**File**: `src/checkers/base_checker.py:102-134`

Added explicit connection pool limits to prevent resource exhaustion:

```python
limits = httpx.Limits(
    max_connections=10,              # Maximum total connections in pool
    max_keepalive_connections=5,     # Maximum idle connections to keep alive
    keepalive_expiry=30.0            # Close idle connections after 30 seconds
)

self._client = httpx.Client(
    timeout=timeout,
    limits=limits,
    follow_redirects=True,
    http2=True,
    headers={...}
)
```

**Impact**: Prevents unbounded connection accumulation even if cleanup is delayed.

### Fix 4: Dedicated ThreadPoolExecutor for Bot Commands

**Files**:
- `src/monitor.py:9` (added import)
- `src/monitor.py:82-87` (created executor)
- `src/monitor.py:249-257` (pass executor to bot)
- `src/monitor.py:678-682` (shutdown executor)
- `src/bot/telegram_bot_handler.py:41, 52, 59` (accept executor)
- `src/bot/telegram_bot_handler.py:260-264` (use executor)

Created a dedicated ThreadPoolExecutor with limited workers (2) for bot commands:

```python
# In Monitor.__init__
self.bot_executor = ThreadPoolExecutor(
    max_workers=2,
    thread_name_prefix="bot_cmd"
)

# In TelegramBotHandler.cmd_check
loop = asyncio.get_event_loop()
await loop.run_in_executor(self.executor, self.monitor.perform_checks)
```

**Impact**: Prevents thread pool exhaustion when multiple `/check` commands are issued. Limits concurrent checks to avoid overwhelming the system.

## Tests Added

Created comprehensive test suite: `tests/test_resource_management.py` (14 tests)

### Test Coverage:

1. **TestCheckerCleanup** (4 tests)
   - Verifies `cleanup()` closes HTTP clients
   - Tests context manager usage
   - Validates multiple checker cleanup
   - Ensures cleanup is idempotent

2. **TestConnectionPoolLimits** (2 tests)
   - Verifies connection pool limits are configured
   - Validates timeout settings

3. **TestTelegramNotifierResourceManagement** (2 tests)
   - Confirms no persistent HTTP client
   - Verifies context manager usage for API calls

4. **TestMonitorCheckerCleanup** (2 tests)
   - Validates cleanup after check cycles
   - Ensures cleanup even when checks raise exceptions

5. **TestThreadPoolExecutor** (2 tests)
   - Confirms executor is created
   - Validates executor shutdown on stop

6. **TestMemoryLeakPrevention** (2 tests)
   - Tests repeated creation/cleanup cycles
   - Validates garbage collection

### Test Results:
```
14 tests passed (100% success rate)
All 75 tests in suite passed (14 new + 61 existing)
```

## Expected Performance Improvements

1. **Immediate Response Times**: Bot should maintain consistent response times regardless of uptime
2. **Stable Memory Usage**: Memory footprint should remain constant over time
3. **No Connection Accumulation**: File descriptors and network connections are properly released
4. **Graceful Degradation**: Under load, bot commands queue cleanly instead of hanging

## Deployment Notes

1. **No Breaking Changes**: All changes are backward compatible
2. **No Configuration Changes**: Existing configs work without modification
3. **Graceful Shutdown**: Monitor now properly cleans up all resources on exit
4. **Thread Safety**: Dedicated executor prevents bot command interference

## Monitoring Recommendations

After deployment, monitor these metrics:

1. **File Descriptors**: `lsof -p <pid> | wc -l` should remain stable
2. **Memory Usage**: RSS should not grow unbounded over time
3. **Bot Response Times**: Should remain under 2 seconds for simple commands
4. **Thread Count**: Should remain stable (not continuously growing)

## Files Modified

1. `src/monitor.py` - Added cleanup logic and thread pool executor
2. `src/checkers/base_checker.py` - Added connection pool limits
3. `src/notifiers/telegram_notifier.py` - Replaced persistent client with context manager
4. `src/bot/telegram_bot_handler.py` - Updated to use dedicated executor
5. `tests/test_resource_management.py` - New comprehensive test suite

## Verification Commands

```bash
# Run resource management tests
python -m pytest tests/test_resource_management.py -v

# Run all tests
python -m pytest tests/ -v

# Monitor file descriptors (while running)
watch -n 5 'lsof -p $(pgrep -f "python.*main.py") | wc -l'

# Monitor memory usage (while running)
watch -n 5 'ps aux | grep "python.*main.py"'
```

---

**Date**: 2025-11-14
**Author**: Claude Code
**Severity**: Critical (Production Issue)
**Status**: ✅ Fixed and Tested
