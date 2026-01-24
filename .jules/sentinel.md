## 2025-02-18 - [Timing Attack in Token Verification]
**Vulnerability:** The `require_token_from_request` and `require_token_from_ws` functions in `src/remote_agent.py` used direct string comparison (`!=`) for validating the `X-Omni-Token`.
**Learning:** This exposes the application to timing attacks where an attacker can deduce the token byte-by-byte by measuring the time it takes for the comparison to fail. While difficult to exploit over a network with jitter, it is a bad practice.
**Prevention:** Always use `secrets.compare_digest()` for comparing sensitive strings like passwords, tokens, or hashes to ensure constant-time comparison.
