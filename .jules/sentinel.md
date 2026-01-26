# Sentinel Journal

This journal tracks critical security learnings and vulnerability patterns found in the codebase.

## Format
## YYYY-MM-DD - [Title]
**Vulnerability:** [What you found]
**Learning:** [Why it existed]
**Prevention:** [How to avoid next time]

## 2026-01-23 - Authentication Bypass via Empty Token
**Vulnerability:** The remote agent allowed authentication bypass when `REMOTE_ACCESS_TOKEN` was empty (due to configuration failure) by providing an empty `X-Omni-Token`. Additionally, token comparison was vulnerable to timing attacks.
**Learning:** Default empty strings for security-critical configuration variables can lead to fail-open scenarios. Relying on external services (Firebase) for token generation without a local fallback can leave the system insecure if the service fails.
**Prevention:** Always ensure security tokens are initialized to a secure default or fail startup if missing. Use constant-time comparison (`secrets.compare_digest`) for all secret verifications.
