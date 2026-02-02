## 2024-05-21 - [High] Permissive Path Validation Default
**Vulnerability:** `is_path_safe` in `remote_agent.py` defaulted to `True`, allowing access to any path not explicitly blacklisted (only Windows system folders were blacklisted).
**Learning:** Permissive defaults ("Allow All Except Bad") fail when new attack vectors or unexpected paths (like Linux paths in a Windows-centric app) are introduced.
**Prevention:** Always use "Deny by Default" (Allowlist) for security boundaries. Return `False` at the end of validation functions.

## 2026-02-01 - [Critical] Path Traversal in Project Backups
**Vulnerability:** `backup_external_resources` trusted `omni.json` to define "external paths" for backup, which, combined with a permissive `is_path_safe` check, allowed malicious projects to steal files from outside the workspace.
**Learning:** Features that allow "importing" or "backing up" external files defined by project metadata are inherent SSRF/Path Traversal risks. Context-aware validation (is this path part of the project?) is crucial.
**Prevention:** Enforce strict Allow-list policies for filesystem access. Only allow `LOCAL_WORKSPACE_ROOT` by default. Require explicit user configuration (`REMOTE_ALLOWED_ROOTS`) to access external paths.

## 2026-02-02 - [Medium] Sensitive Data Leak in Command Logs
**Vulnerability:** The `api_command` endpoint in `remote_agent.py` logged the full command string, including arguments. This leaked sensitive information (passwords, tokens) if they were passed as CLI arguments (CWE-532).
**Learning:** Generic logging of user input or system commands often inadvertently captures secrets. "Debuggability" features often conflict with security requirements.
**Prevention:** Implement context-aware sanitization for all command logs. Use regex to identify and redact values associated with sensitive keywords (password, token, key) before writing to logs.
