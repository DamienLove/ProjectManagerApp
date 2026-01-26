## 2024-05-22 - [Timing Attack Prevention in Authentication]
**Vulnerability:** The remote agent used standard string comparison (`!=`) to verify authentication tokens in `require_token_from_request` and `require_token_from_ws`.
**Learning:** Standard string comparison returns as soon as a mismatch is found, allowing an attacker to deduce the token byte-by-byte by measuring response times.
**Prevention:** Always use `secrets.compare_digest()` for comparing secrets (passwords, tokens, HMACs) to ensure constant-time comparison.
