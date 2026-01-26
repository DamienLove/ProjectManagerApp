## 2024-05-21 - [High] Permissive Path Validation Default
**Vulnerability:** `is_path_safe` in `remote_agent.py` defaulted to `True`, allowing access to any path not explicitly blacklisted (only Windows system folders were blacklisted).
**Learning:** Permissive defaults ("Allow All Except Bad") fail when new attack vectors or unexpected paths (like Linux paths in a Windows-centric app) are introduced.
**Prevention:** Always use "Deny by Default" (Allowlist) for security boundaries. Return `False` at the end of validation functions.

## 2024-05-24 - [Critical] Path Traversal in File Restoration
**Vulnerability:** `restore_external_resources` and `backup_external_resources` blindly trusted paths from `restore_map.json` and `omni.json`, allowing arbitrary file writes and deletions outside the workspace.
**Learning:** Even if a file format is internal (`omni.json` inside a project), it must be treated as untrusted input because it can be imported from external sources (Google Drive, user downloads).
**Prevention:** Always validate paths against the security boundary (`is_path_safe`) before performing file system operations, especially when those paths originate from data files.
