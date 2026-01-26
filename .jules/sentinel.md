## 2025-02-18 - Prevent Command Injection in Remote Agent
**Vulnerability:** Unnecessary usage of `shell=True` in `subprocess` calls within `src/remote_agent.py` (`check_install_software` and `open_studio_project`).
**Learning:** `shell=True` was used for executing known executables (`winget`, `studio64.exe`) where direct execution is safer and sufficient. This exposes the application to command injection if the arguments (e.g., project paths or software IDs) contain shell metacharacters.
**Prevention:** Always default to `shell=False` (or omit the argument) when using `subprocess` functions unless shell features (pipes, redirection, wildcards) are explicitly required and inputs are strictly sanitized. For list arguments, `shell=False` is preferred.
