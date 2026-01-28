## 2024-05-21 - [High] Permissive Path Validation Default
**Vulnerability:** `is_path_safe` in `remote_agent.py` defaulted to `True`, allowing access to any path not explicitly blacklisted (only Windows system folders were blacklisted).
**Learning:** Permissive defaults ("Allow All Except Bad") fail when new attack vectors or unexpected paths (like Linux paths in a Windows-centric app) are introduced.
**Prevention:** Always use "Deny by Default" (Allowlist) for security boundaries. Return `False` at the end of validation functions.

## 2024-10-24 - [Critical] Inconsistent Mocking causing Test Pollution
**Vulnerability:** `test_remote_agent_security.py` mocked `fastapi.HTTPException` as a `MagicMock` (global side effect), while `test_remote_agent_auth.py` expected it to be a class inheriting from `Exception`. This caused unrelated tests to fail or pass incorrectly depending on execution order.
**Learning:** Global state modification in tests (like `sys.modules`) without precise restoration or consistent definitions creates fragile test suites that hide bugs.
**Prevention:** Always define mock classes consistently across test files if modifying global modules, or ensure `setUp` strictly restores the expected state for that specific test file.
