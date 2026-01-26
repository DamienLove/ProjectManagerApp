## 2025-02-18 - [Unnecessary Shell Execution with Untrusted Inputs]
**Vulnerability:** `subprocess.run(list, shell=True)` was used to invoke `winget` and Android Studio, passing inputs derived from `omni.json` or API parameters. On Windows, `shell=True` allows command injection even if arguments are passed as a list, because the list is converted to a command string.
**Learning:** Developers often assume `shell=True` is needed for CLI tools or that passing a list protects against injection on Windows. Neither is true.
**Prevention:** Avoid `shell=True` unless explicitly invoking shell features (like pipes). When using `subprocess`, prefer passing arguments as a list with `shell=False`.

## 2025-02-18 - [Timing Attack in Token Verification]
**Vulnerability:** The `require_token_from_request` and `require_token_from_ws` functions in `src/remote_agent.py` used direct string comparison (`!=`) for validating the `X-Omni-Token`.
**Learning:** This exposes the application to timing attacks where an attacker can deduce the token byte-by-byte by measuring the time it takes for the comparison to fail. While difficult to exploit over a network with jitter, it is a bad practice.
**Prevention:** Always use `secrets.compare_digest()` for comparing sensitive strings like passwords, tokens, or hashes to ensure constant-time comparison.
# Sentinel's Journal

## 2024-05-24 - Timing Attack on Token Verification
**Vulnerability:** Direct string comparison (`!=`) was used for checking the `X-Omni-Token`. This allows an attacker to potentially deduce the token byte-by-byte by measuring the time it takes for the server to respond.
**Learning:** Even simple authentication checks must be constant-time. Developers often overlook this detail when using high-level languages like Python.
**Prevention:** Always use `secrets.compare_digest()` for comparing sensitive strings like passwords, tokens, or API keys.
