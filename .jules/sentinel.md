## 2025-02-18 - [Command Injection via shell=True]
**Vulnerability:** The functions `check_install_software` and `open_studio_project` in `src/remote_agent.py` used `subprocess.run(..., shell=True)` and `subprocess.Popen(..., shell=True)` with list arguments. On Windows, this converts the list to a string, potentially allowing command injection if arguments (like `app_id` or `project_path`) contain shell metacharacters (e.g., `&`).
**Learning:** Using `shell=True` with `subprocess` functions is dangerous when handling user or external input, especially on Windows where argument quoting rules are complex. Passing a list of arguments with `shell=False` (the default) is safer as it invokes the executable directly.
**Prevention:** Avoid `shell=True` unless absolutely necessary (e.g., needing shell built-ins). When launching executables, always pass arguments as a list with `shell=False`.

## 2025-02-18 - [Timing Attack in Token Verification]
**Vulnerability:** The `require_token_from_request` and `require_token_from_ws` functions in `src/remote_agent.py` used direct string comparison (`!=`) for validating the `X-Omni-Token`.
**Learning:** This exposes the application to timing attacks where an attacker can deduce the token byte-by-byte by measuring the time it takes for the comparison to fail. While difficult to exploit over a network with jitter, it is a bad practice.
**Prevention:** Always use `secrets.compare_digest()` for comparing sensitive strings like passwords, tokens, or hashes to ensure constant-time comparison.
# Sentinel's Journal

## 2024-05-24 - Timing Attack on Token Verification
**Vulnerability:** Direct string comparison (`!=`) was used for checking the `X-Omni-Token`. This allows an attacker to potentially deduce the token byte-by-byte by measuring the time it takes for the server to respond.
**Learning:** Even simple authentication checks must be constant-time. Developers often overlook this detail when using high-level languages like Python.
**Prevention:** Always use `secrets.compare_digest()` for comparing sensitive strings like passwords, tokens, or API keys.
