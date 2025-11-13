# Fix: Relative Redirect Handling in SSRF Protection

## Problem

After implementing SSRF protection, authentication to `www.fomento-vi.es` was failing with this error:

```
ERROR - SSRF protection blocked redirect from https://www.fomento-vi.es/ to /Inicio.aspx:
Invalid URL scheme ''. Only http and https are allowed.
```

## Root Cause

The SSRF validation code was not handling **relative redirects** correctly.

### What Happened

1. Site redirects: `POST https://www.fomento-vi.es/` → `302 Found` with `Location: /Inicio.aspx`
2. The redirect URL `/Inicio.aspx` is **relative** (no scheme, no domain)
3. Our validator tried to parse `/Inicio.aspx` as a complete URL
4. `urlparse('/Inicio.aspx')` returns `ParseResult(scheme='', netloc='', path='/Inicio.aspx', ...)`
5. Empty scheme `''` is not in `["http", "https"]` → **Validation fails**

### Why This Is Common

Many websites use relative redirects:
- `/login` → `/dashboard`
- `/` → `/home`
- `/api/auth` → `/api/profile`

These are **safe redirects** on the same domain, but our validator was treating them as invalid.

## The Fix

### Changes Made

**File:** `src/checkers/base_checker.py`

1. **Import `urljoin`** for resolving relative URLs:
```python
from urllib.parse import urlparse, urljoin
```

2. **Updated `_validate_redirect_url()` signature** to accept base URL:
```python
def _validate_redirect_url(self, redirect_url: str, base_url: str) -> bool:
```

3. **Added relative URL resolution logic:**
```python
# Check if redirect_url is relative (no scheme)
parsed = urlparse(redirect_url)
if not parsed.scheme:
    # Relative URL - resolve against base URL
    absolute_redirect_url = urljoin(base_url, redirect_url)
    self.logger.debug(f"Resolved relative redirect: {redirect_url} -> {absolute_redirect_url}")
    redirect_url = absolute_redirect_url
```

4. **Updated redirect chain handling** in `_make_request()`:
```python
# Track the base URL for resolving relative redirects
current_url = url

for hist_response in response.history:
    if hist_response.is_redirect:
        redirect_url = hist_response.headers.get('location')
        if redirect_url:
            # Validate redirect (handles both absolute and relative URLs)
            self._validate_redirect_url(redirect_url, current_url)

            # Update current_url for next redirect in chain
            parsed = urlparse(redirect_url)
            if parsed.scheme:
                current_url = redirect_url  # Absolute URL
            else:
                current_url = urljoin(current_url, redirect_url)  # Relative URL
```

### How It Works Now

**Example 1: Relative Redirect (Safe)**
```
Initial URL: https://www.fomento-vi.es/
Redirect: /Inicio.aspx
Resolved: https://www.fomento-vi.es/Inicio.aspx
Validation: ✓ Pass (public domain)
Result: ✓ Redirect allowed
```

**Example 2: Absolute Redirect to Private IP (Blocked)**
```
Initial URL: https://evil.com/
Redirect: http://192.168.1.1/admin
Resolved: http://192.168.1.1/admin (already absolute)
Validation: ✗ Fail (private IP)
Result: ✗ Redirect blocked
```

**Example 3: Relative Redirect Chain**
```
URL 1: https://example.com/page
Redirect 1: /step2 → Resolved to https://example.com/step2
Redirect 2: /final → Resolved to https://example.com/final
Result: ✓ All redirects allowed (same public domain)
```

**Example 4: Malicious Relative Redirect (Blocked)**
```
Initial URL: http://192.168.1.1/page
Redirect: /admin
Resolved: http://192.168.1.1/admin
Validation: ✗ Fail (private IP)
Result: ✗ Redirect blocked
```

## Security Implications

### Still Protected Against:

✅ **Absolute redirects to private IPs:**
```
https://evil.com/ → http://192.168.1.1/
```

✅ **Absolute redirects to localhost:**
```
https://evil.com/ → http://localhost/admin
```

✅ **Absolute redirects to cloud metadata:**
```
https://evil.com/ → http://169.254.169.254/latest/meta-data/
```

✅ **Relative redirects from private IPs** (if initial URL was private, it's blocked at startup):
```
http://10.0.0.1/ → /admin  (blocked because 10.0.0.1 blocked in config)
```

### New Capability:

✅ **Relative redirects on public domains** (now properly supported):
```
https://www.example.com/ → /dashboard
https://inforuta-rce.es/ → /usuario/perfil
https://www.fomento-vi.es/ → /Inicio.aspx
```

## Testing

### New Tests Added

**File:** `tests/test_ssrf_protection.py`

1. **`test_validate_redirect_relative_url`**
   - Tests that relative redirects on public domains are allowed
   - Example: `https://www.example.com/path` → `/new-path`

2. **`test_validate_redirect_relative_to_private_blocked`**
   - Tests that relative redirects on private IPs are still blocked
   - Example: `http://192.168.1.1/page` → `/admin`

### Test Results

```bash
$ pytest tests/test_ssrf_protection.py -v
============================== 35 passed in 0.19s ==============================
```

**Before fix:** 33 tests
**After fix:** 35 tests (2 new tests for relative redirects)

## Verification

### Before Fix
```bash
$ python main.py --config config/config.yaml --check-once
[Fomento VI] ✗ AUTHENTICATION: FAILURE
  Error: SSRF protection blocked request: Invalid URL scheme ''.
```

### After Fix
```bash
$ python main.py --config config/config.yaml --check-once
[Fomento VI] ✓ UPTIME: SUCCESS (135ms) HTTP 200
[Fomento VI] ✓ AUTHENTICATION: SUCCESS (259ms)
```

## Impact

- **Fixed:** Authentication now works for sites using relative redirects
- **Security:** No security regression - all SSRF protections still in place
- **Compatibility:** Better compatibility with real-world HTTP redirect patterns

## Files Modified

1. `src/checkers/base_checker.py`
   - Added `urljoin` import
   - Updated `_validate_redirect_url()` method
   - Updated `_make_request()` redirect handling
   - ~30 lines changed

2. `tests/test_ssrf_protection.py`
   - Added 2 new tests for relative redirects
   - ~25 lines added

## Conclusion

The fix correctly handles both absolute and relative HTTP redirects while maintaining full SSRF protection. The authentication system now works with all common redirect patterns used by modern web applications.

---

*Fix Date:* 2025-11-13
*Version:* 1.1.1
*Status:* ✅ Tested and Verified
