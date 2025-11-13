# Circuit Breaker Analysis & Status Report

## Executive Summary

**Status:** ⚠️ **PARTIALLY IMPLEMENTED - NEEDS FIXES**

The circuit breaker system has a **sophisticated `CircuitBreaker` class that is completely unused**. Instead, the Monitor uses a **manual, simplified implementation** that is **incomplete and has critical bugs**.

---

## Current Implementation

### 1. The Sophisticated CircuitBreaker Class (UNUSED)

**File:** `src/utils/circuit_breaker.py`

**Features:**
- ✅ Three-state design: CLOSED → OPEN → HALF_OPEN → CLOSED
- ✅ Thread-safe with locks
- ✅ Automatic recovery attempts after timeout
- ✅ Configurable failure threshold and recovery timeout
- ✅ `call()` wrapper for protected function execution
- ✅ Manual reset capability
- ✅ State introspection methods

**Problem:** **This class is NEVER used in the codebase!**

```python
# CircuitBreaker imported but never instantiated
from .utils import CircuitBreaker  # ← Imported
# ... nowhere in the code is CircuitBreaker() called
```

### 2. The Manual Implementation (CURRENTLY USED)

**File:** `src/monitor.py` + `src/storage/state_manager.py`

**How it works:**

#### State Storage (StateManager)
```python
"circuit_breaker": {
    "is_open": False,        # Boolean flag
    "failure_count": 0,      # Consecutive failures
    "last_failure": None     # ISO timestamp
}
```

#### Check Before Monitoring (Monitor.py:216-226)
```python
# Check if circuit breaker is open
if cb_config.get("enabled", True) and circuit_breaker_state.get("is_open", False):
    self.logger.warning(f"[{site_name}] Circuit breaker is OPEN, skipping checks")
    continue  # Skip all checks for this site
```

#### Failure Tracking (StateManager.py:222-224)
```python
# On check failure
site_state["circuit_breaker"]["failure_count"] += 1
site_state["circuit_breaker"]["last_failure"] = result.timestamp.isoformat()
```

#### Success Reset (StateManager.py:235-236)
```python
# On check success
site_state["circuit_breaker"]["failure_count"] = 0
# Note: is_open NOT reset here!
```

#### Opening Circuit (Monitor.py:352-362)
```python
# In exception handler
if site_state["circuit_breaker"]["failure_count"] >= failure_threshold:
    site_state["circuit_breaker"]["is_open"] = True
    self.logger.warning(f"[{site_name}] Circuit breaker OPENED")
```

---

## Critical Problems

### Problem 1: Circuit Breaker Can Never Recover ❌

**Issue:** Once opened, the circuit breaker **stays open forever**.

**Why:**
1. Circuit opens after 5 failures: `is_open = True`
2. Next check cycle: `if is_open: skip checks` (monitor.py:220)
3. **No checks = no successes = circuit stays open**
4. **No HALF_OPEN state = no recovery testing**

**Current Behavior:**
```
Site fails 5 times → Circuit opens → Monitor skips site forever
```

**Expected Behavior:**
```
Site fails 5 times → Circuit opens → Wait 30 min → Try test request (HALF_OPEN) →
    If success: Close circuit, resume monitoring
    If failure: Stay open, wait 30 min more
```

**Evidence:**
```python
# State after 5 failures
"circuit_breaker": {
    "is_open": True,           # ← Set to true
    "failure_count": 5,
    "last_failure": "2025-11-13T10:00:00"
}

# 30 minutes later... nothing happens
# 1 hour later... nothing happens
# Circuit stays open forever until manual intervention
```

### Problem 2: State Not Persisted After Circuit Opens ❌

**Issue:** Circuit breaker opens but state is NOT saved.

**Location:** `monitor.py:361`
```python
site_state["circuit_breaker"]["is_open"] = True
self.logger.warning(f"[{site_name}] Circuit breaker OPENED")
# BUG: No call to state_manager.save_state()!
```

**Impact:** Monitor restart = circuit breaker state lost

### Problem 3: No HALF_OPEN State ❌

**Issue:** Manual implementation has no way to test if site recovered.

**Missing:**
- No automatic recovery attempt after timeout
- No test request before fully reopening
- No gradual recovery

### Problem 4: Inconsistent Failure Counting ⚠️

**Issue:** Failures counted in two different places with different logic.

**StateManager (for all results):**
```python
# Increments on every failed result.is_failure
site_state["circuit_breaker"]["failure_count"] += 1
```

**Monitor (only on exceptions):**
```python
# Checks if threshold exceeded, opens circuit
if site_state["circuit_breaker"]["failure_count"] >= failure_threshold:
    site_state["circuit_breaker"]["is_open"] = True
```

**Result:** Circuit only opens on exceptions, NOT on check failures

**Example:**
- Check returns `CheckStatus.FAILURE` (not exception) → Count increments but circuit doesn't open
- Check throws exception → Circuit opens

### Problem 5: Configuration Mismatch 🔧

**Config File (`config.yaml`):**
```yaml
circuit_breaker:
  enabled: true
  failure_threshold: 5
  recovery_timeout_minutes: 30  # ← Not used!
  half_open_attempts: 2          # ← Not used!
```

**Actual Usage:**
- `enabled` ✅ Used
- `failure_threshold` ✅ Used
- `recovery_timeout_minutes` ❌ **Ignored** (no recovery)
- `half_open_attempts` ❌ **Ignored** (no HALF_OPEN state)

---

## Current Status in Your System

**Checked all 5 sites:**
```
InfoRuta RCE:        is_open=False, failures=0 ✅
AEMET:               is_open=False, failures=0 ✅
DGT Traffic Cameras: is_open=False, failures=0 ✅
Vialidad ACP:        is_open=False, failures=0 ✅
Fomento VI:          is_open=False, failures=0 ✅
```

**Analysis:**
- All circuits are CLOSED (normal)
- All sites are healthy (0 failures)
- **If any site fails 5+ times, circuit will open and NEVER recover automatically**

---

## Comparison: Current vs. Sophisticated Class

| Feature | Manual Implementation | CircuitBreaker Class |
|---------|----------------------|---------------------|
| **States** | 2 (CLOSED, OPEN) | 3 (CLOSED, OPEN, HALF_OPEN) |
| **Auto Recovery** | ❌ None | ✅ Automatic after timeout |
| **Thread Safety** | ❌ No locks | ✅ Thread-safe with locks |
| **Test Requests** | ❌ None | ✅ HALF_OPEN allows testing |
| **Persistence** | ⚠️ Partial (buggy) | ❌ In-memory only |
| **Recovery Timeout** | ❌ Not implemented | ✅ Configurable |
| **Current Usage** | ✅ Active | ❌ Completely unused |

---

## What Happens When Circuit Opens (Current System)

### Scenario: InfoRuta Site Goes Down

**Timeline:**
```
12:00 PM - Check 1 fails → failure_count = 1
12:15 PM - Check 2 fails → failure_count = 2
12:30 PM - Check 3 fails → failure_count = 3
12:45 PM - Check 4 fails → failure_count = 4
1:00 PM  - Check 5 fails → failure_count = 5, is_open = True
1:15 PM  - Circuit OPEN → Checks skipped
1:30 PM  - Circuit OPEN → Checks skipped
1:45 PM  - Circuit OPEN → Checks skipped
...
2 hours later...
...forever...

RESULT: Site permanently excluded from monitoring until:
  1. Manual intervention (restart monitor)
  2. Manual state file edit
  3. Code fix to implement recovery
```

**What SHOULD happen:**
```
12:00 PM - Check 1 fails → failure_count = 1
12:15 PM - Check 2 fails → failure_count = 2
12:30 PM - Check 3 fails → failure_count = 3
12:45 PM - Check 4 fails → failure_count = 4
1:00 PM  - Check 5 fails → failure_count = 5, is_open = True
1:15 PM  - Circuit OPEN → Checks skipped (wait for timeout)
1:30 PM  - Circuit OPEN → Still waiting...
1:30 PM  - TIMEOUT REACHED (30 min) → Enter HALF_OPEN
1:30 PM  - Test request sent...
           → If success: Circuit CLOSED, resume normal monitoring
           → If failure: Stay OPEN, wait another 30 min

RESULT: Site automatically recovers when service is restored
```

---

## Why Current System Exists (vs. Using CircuitBreaker Class)

**Likely reasons:**

1. **Persistence:** CircuitBreaker class is in-memory only, StateManager persists to disk
2. **Per-site isolation:** StateManager already tracks per-site state
3. **Incremental development:** Manual implementation added quickly, class created but never integrated
4. **Missing integration layer:** No bridge between CircuitBreaker class and StateManager

---

## Recommendations

### Option 1: Fix Manual Implementation (Quick Fix) ⚡

**Time: 2-3 hours**

**Changes needed:**

1. **Add automatic recovery timeout check:**
```python
# In monitor.py before checking is_open
if circuit_breaker_state.get("is_open", False):
    last_failure = circuit_breaker_state.get("last_failure")
    if last_failure:
        last_failure_time = datetime.fromisoformat(last_failure)
        recovery_timeout = cb_config.get("recovery_timeout_minutes", 30) * 60
        time_since_failure = (datetime.now() - last_failure_time).total_seconds()

        if time_since_failure >= recovery_timeout:
            # Attempt recovery - enter HALF_OPEN
            self.logger.info(f"[{site_name}] Circuit breaker attempting recovery...")
            circuit_breaker_state["is_half_open"] = True
            circuit_breaker_state["is_open"] = False
        else:
            # Still in timeout period
            self.logger.debug(f"[{site_name}] Circuit breaker OPEN, skipping checks")
            continue
```

2. **Add HALF_OPEN state handling:**
```python
# After checks complete successfully
if circuit_breaker_state.get("is_half_open", False):
    self.logger.info(f"[{site_name}] Circuit breaker recovered, closing")
    circuit_breaker_state["is_half_open"] = False
    circuit_breaker_state["failure_count"] = 0
    self.state_manager.save_state()
```

3. **Fix state persistence bug:**
```python
# After setting is_open = True
site_state["circuit_breaker"]["is_open"] = True
self.logger.warning(f"[{site_name}] Circuit breaker OPENED")
self.state_manager.save_state()  # ← ADD THIS
```

4. **Open circuit on check failures (not just exceptions):**
```python
# After recording result in state_manager
if result.is_failure:
    site_state = self.state_manager._get_site_state(site_name)
    if site_state["circuit_breaker"]["failure_count"] >= failure_threshold:
        site_state["circuit_breaker"]["is_open"] = True
        self.logger.warning(f"[{site_name}] Circuit breaker OPENED")
        self.state_manager.save_state()
```

**Pros:**
- ✅ Minimal code changes
- ✅ Uses existing state management
- ✅ Backward compatible

**Cons:**
- ⚠️ Still not thread-safe
- ⚠️ Doesn't use sophisticated CircuitBreaker class
- ⚠️ Recovery logic scattered across files

### Option 2: Integrate CircuitBreaker Class (Proper Fix) 🏗️

**Time: 1-2 days**

**Changes needed:**

1. **Create per-site CircuitBreaker instances:**
```python
# In Monitor.__init__
self.circuit_breakers = {}
for site in self.sites:
    site_name = site.get("name")
    cb_config = self.config.get("circuit_breaker", {})
    self.circuit_breakers[site_name] = CircuitBreaker(
        failure_threshold=cb_config.get("failure_threshold", 5),
        recovery_timeout=cb_config.get("recovery_timeout_minutes", 30) * 60,
    )
```

2. **Wrap check calls:**
```python
# In _perform_site_checks
cb = self.circuit_breakers[site_name]
try:
    result = cb.call(checker.check)
except CircuitOpenError:
    self.logger.warning(f"[{site_name}] Circuit breaker is OPEN")
    continue
```

3. **Sync state with StateManager:**
```python
# After check
cb_state = cb.get_state()
site_state["circuit_breaker"] = {
    "is_open": cb_state["state"] == "open",
    "failure_count": cb_state["failure_count"],
    "last_failure": cb_state["last_failure_time"],
    "state": cb_state["state"]  # Include full state
}
self.state_manager.save_state()
```

4. **Restore state on startup:**
```python
# In Monitor.__init__ after creating CircuitBreaker
saved_state = self.state_manager._get_site_state(site_name)
cb_state = saved_state.get("circuit_breaker", {})
if cb_state.get("is_open"):
    # Restore circuit breaker state from disk
    cb.failure_count = cb_state.get("failure_count", 0)
    if cb_state.get("last_failure"):
        cb.last_failure_time = datetime.fromisoformat(cb_state["last_failure"])
    cb.state = CircuitState.OPEN
```

**Pros:**
- ✅ Uses battle-tested CircuitBreaker class
- ✅ Full HALF_OPEN support
- ✅ Thread-safe
- ✅ Automatic recovery
- ✅ Cleaner separation of concerns

**Cons:**
- ⚠️ More code changes required
- ⚠️ Need to handle state persistence carefully
- ⚠️ Requires testing of integration

### Option 3: Disable Circuit Breaker (If Not Needed) 🛑

**If circuit breaking is not critical:**

```yaml
# config/config.yaml
circuit_breaker:
  enabled: false  # ← Disable completely
```

**When this makes sense:**
- Short monitoring intervals (< 5 min)
- External alerting handles failures
- Sites rarely have prolonged outages
- Manual intervention is acceptable

---

## Current Need Assessment

### Is Circuit Breaker Needed?

**Your monitoring system:**
- ✅ Checks every 15 minutes
- ✅ Monitors 5 sites
- ✅ Has Telegram alerting
- ✅ Has healthcheck.io external monitoring
- ❓ Site failure patterns unknown

**Questions to determine need:**

1. **Do sites have frequent, temporary failures?**
   - Yes → Circuit breaker reduces noise, saves API calls
   - No → Circuit breaker overkill

2. **Are long outages common (> 1 hour)?**
   - Yes → Circuit breaker prevents wasted checks
   - No → Current implementation sufficient

3. **Is automatic recovery important?**
   - Yes → MUST fix current implementation
   - No → Can disable or use manual recovery

4. **Are API rate limits a concern?**
   - Yes → Circuit breaker prevents hitting limits
   - No → Less critical

### Based on Your Current Status

**Evidence from logs:**
- All sites: `failure_count = 0`
- All circuits: `is_open = False`
- No circuit breaker activations observed

**Conclusion:**
Sites are **highly stable**. Circuit breaker has **never triggered** in your monitoring history.

**Recommendation:**
- **Short term:** Disable circuit breaker (`enabled: false`) or leave as-is
- **Medium term:** Implement Option 1 (quick fix) for safety
- **Long term:** Consider Option 2 if you add more unstable sites

---

## Testing Circuit Breaker (If Implementing Fix)

### Manual Test

1. **Modify config to force failures:**
```yaml
sites:
  - name: "Test Site"
    url: "http://httpstat.us/500"  # Always returns 500 error
    checks_enabled: [uptime]
```

2. **Run monitor:**
```bash
python main.py --check-once
# Should fail and increment failure_count
```

3. **Run 5 times to open circuit:**
```bash
for i in {1..5}; do python main.py --check-once; sleep 2; done
# Circuit should open after 5th failure
```

4. **Verify circuit is open:**
```bash
python3 -c "import json; print(json.load(open('logs/monitor_state.json'))['sites']['Test Site']['circuit_breaker'])"
# Should show: is_open=True
```

5. **Test recovery (if implemented):**
```bash
# Wait 30 minutes or modify timeout in code
python main.py --check-once
# Should attempt recovery (HALF_OPEN)
```

---

## Summary & Action Items

### Current Status
- ❌ Manual circuit breaker implementation is **incomplete**
- ❌ **No automatic recovery** after circuit opens
- ❌ State persistence bug when opening circuit
- ✅ Sophisticated CircuitBreaker class exists but **unused**
- ✅ All monitored sites currently **healthy** (0 failures)

### Immediate Action (Choose One)

**Option A: Disable (Safest)**
```yaml
circuit_breaker:
  enabled: false
```
**Time: 1 minute**

**Option B: Quick Fix (Recommended)**
- Implement Option 1 fixes above
- **Time: 2-3 hours**

**Option C: Proper Integration (Best)**
- Integrate CircuitBreaker class
- **Time: 1-2 days**

**Option D: Leave As-Is (Current)**
- Acceptable if sites stay healthy
- **Risk: Sites stuck if circuit ever opens**

### My Recommendation

Given your current site stability (0 failures across all sites), I recommend:

1. **Immediate:** Leave circuit breaker enabled but document the limitation
2. **When you have time:** Implement Option 1 (quick fix) for safety
3. **Future:** Consider Option 2 if you add more sites or see instability

**Why:** The circuit breaker has never triggered, so the bug hasn't affected you. But it's a time bomb if a site goes down for extended periods.

---

*Analysis Date: 2025-11-13*
*System Health: Excellent (0 failures)*
*Circuit Breaker Status: Partially Implemented*
*Risk Level: Low (but grows if sites become unstable)*
