## 2024-05-21 - [High] Permissive Path Validation Default
**Vulnerability:** `is_path_safe` in `remote_agent.py` defaulted to `True`, allowing access to any path not explicitly blacklisted (only Windows system folders were blacklisted).
**Learning:** Permissive defaults ("Allow All Except Bad") fail when new attack vectors or unexpected paths (like Linux paths in a Windows-centric app) are introduced.
**Prevention:** Always use "Deny by Default" (Allowlist) for security boundaries. Return `False` at the end of validation functions.

## 2026-01-29 - [Critical] Argument Injection in Subprocess
**Vulnerability:** `check_install_software` passed unvalidated `app_id` from `omni.json` to `winget` subprocess. IDs starting with `-` were treated as flags (e.g., `-m URL`), allowing installation of arbitrary software manifests (RCE/Arbitrary Install).
**Learning:** Even with `shell=False`, passing untrusted input as the first character of an argument can lead to "Argument Injection" if the invoked program parses flags (like `-m` or `--option`).
**Prevention:** Validate that user-provided arguments do not start with `-` (or use `--` delimiter if supported by the tool) before passing them to `subprocess`.
