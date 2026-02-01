## 2024-05-21 - [High] Permissive Path Validation Default
**Vulnerability:** `is_path_safe` in `remote_agent.py` defaulted to `True`, allowing access to any path not explicitly blacklisted (only Windows system folders were blacklisted).
**Learning:** Permissive defaults ("Allow All Except Bad") fail when new attack vectors or unexpected paths (like Linux paths in a Windows-centric app) are introduced.
**Prevention:** Always use "Deny by Default" (Allowlist) for security boundaries. Return `False` at the end of validation functions.

## 2024-05-23 - [Critical] Incomplete Path Validation Fix
**Vulnerability:** The previous fix for `is_path_safe` still contained a fallback that allowed access to all paths (except a small blacklist) if the allowlist was empty. This allowed unauthorized access to non-C: drives or other sensitive paths.
**Learning:** "Deny by Default" must be absolute. Conditional fallbacks to permissive lists (even if intended to be "user friendly") undermine the security model.
**Prevention:** Validation functions should strictly return `False` by default. Only return `True` if an explicit allowlist condition is met. Do not mix allowlist and blacklist logic.
