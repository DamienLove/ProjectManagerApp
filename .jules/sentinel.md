## 2024-05-21 - [High] Permissive Path Validation Default
**Vulnerability:** `is_path_safe` in `remote_agent.py` defaulted to `True`, allowing access to any path not explicitly blacklisted (only Windows system folders were blacklisted).
**Learning:** Permissive defaults ("Allow All Except Bad") fail when new attack vectors or unexpected paths (like Linux paths in a Windows-centric app) are introduced.
**Prevention:** Always use "Deny by Default" (Allowlist) for security boundaries. Return `False` at the end of validation functions.

## 2024-05-22 - [Critical] Implementation of Default Deny
**Vulnerability:** Despite previous identification, `is_path_safe` still returned `True` by default because the allowlist check was conditional on `ABS_REMOTE_ALLOWED_ROOTS` being non-empty.
**Learning:** Conditional checks for allowlists must be structured to Fail Safe. If the allowlist is empty, it should probably match nothing (or default behavior must be explicit).
**Prevention:** Hardcode `return False` as the final statement of any security predicate. Do not rely on intermediate loops to catch "everything else" unless mathematically certain.
