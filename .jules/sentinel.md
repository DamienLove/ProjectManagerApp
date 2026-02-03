## 2024-05-21 - [High] Permissive Path Validation Default
**Vulnerability:** `is_path_safe` in `remote_agent.py` defaulted to `True`, allowing access to any path not explicitly blacklisted (only Windows system folders were blacklisted).
**Learning:** Permissive defaults ("Allow All Except Bad") fail when new attack vectors or unexpected paths (like Linux paths in a Windows-centric app) are introduced.
**Prevention:** Always use "Deny by Default" (Allowlist) for security boundaries. Return `False` at the end of validation functions.

## 2026-02-01 - [Critical] Path Traversal in Project Backups
**Vulnerability:** `backup_external_resources` trusted `omni.json` to define "external paths" for backup, which, combined with a permissive `is_path_safe` check, allowed malicious projects to steal files from outside the workspace.
**Learning:** Features that allow "importing" or "backing up" external files defined by project metadata are inherent SSRF/Path Traversal risks. Context-aware validation (is this path part of the project?) is crucial.
**Prevention:** Enforce strict Allow-list policies for filesystem access. Only allow `LOCAL_WORKSPACE_ROOT` by default. Require explicit user configuration (`REMOTE_ALLOWED_ROOTS`) to access external paths.

## 2026-02-03 - [High] Sensitive Command Logging
**Vulnerability:** The `remote_agent` logged full command strings, including arguments like `--password` or `token=`, exposing secrets in `remote_agent.log` in plaintext.
**Learning:** Logging is a common source of data leaks. Any system that executes user-supplied commands must assume the input contains secrets.
**Prevention:** Implement automatic redaction/sanitization for all logged commands using regex to catch common secret patterns (password, token, key).
