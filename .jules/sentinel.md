# Sentinel's Journal

## 2025-02-14 - Constant-time Token Comparison
**Vulnerability:** The remote agent used simple string comparison (`token != REMOTE_ACCESS_TOKEN`) for authentication tokens. This is vulnerable to timing attacks, where an attacker can deduce the token byte-by-byte by measuring response times.
**Learning:** Even internal or "local" tools can be exposed via tunnels (like the Cloudflare tunnel used here), making them accessible over the internet. Standard Python comparisons are not constant-time.
**Prevention:** Always use `secrets.compare_digest()` for comparing sensitive strings like passwords, API keys, and tokens.
