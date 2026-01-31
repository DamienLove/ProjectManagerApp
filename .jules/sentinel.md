## 2024-05-21 - [High] Permissive Path Validation Default
**Vulnerability:** `is_path_safe` in `remote_agent.py` defaulted to `True`, allowing access to any path not explicitly blacklisted (only Windows system folders were blacklisted).
**Learning:** Permissive defaults ("Allow All Except Bad") fail when new attack vectors or unexpected paths (like Linux paths in a Windows-centric app) are introduced.
**Prevention:** Always use "Deny by Default" (Allowlist) for security boundaries. Return `False` at the end of validation functions.

## 2024-05-22 - [Medium] Test Pollution masking Security Verification
**Vulnerability:** Unit tests relying on global `sys.modules` patching for `fastapi` caused cross-test contamination. This led to `TypeError` when security tests tried to assert exception types, potentially hiding failures or making the suite fragile.
**Learning:** Global state mutation in tests (like `sys.modules`) is dangerous and requires strict cleanup or robust re-setup in `setUp()`.
**Prevention:** Always restore `sys.modules` state in `tearDown` or enforce correct mock state in `setUp` before importing the module under test.
