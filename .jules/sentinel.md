# Sentinel's Journal

## 2024-05-24 - Timing Attack on Token Verification
**Vulnerability:** Direct string comparison (`!=`) was used for checking the `X-Omni-Token`. This allows an attacker to potentially deduce the token byte-by-byte by measuring the time it takes for the server to respond.
**Learning:** Even simple authentication checks must be constant-time. Developers often overlook this detail when using high-level languages like Python.
**Prevention:** Always use `secrets.compare_digest()` for comparing sensitive strings like passwords, tokens, or API keys.
