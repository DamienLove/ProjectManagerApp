## 2024-10-24 - Async Operation Feedback
**Learning:** Blocking operations in background threads (like `winget list` which takes >5s) create a "broken" appearance if the UI remains empty during execution.
**Action:** Always implement an explicit "Scanning..." or "Loading..." state for any list population that depends on external processes, and ensure it persists until data is ready.
