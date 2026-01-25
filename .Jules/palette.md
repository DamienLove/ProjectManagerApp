## 2024-05-23 - Async Loading States
**Learning:** Users perceive the application as broken when long-running background processes (like `winget list`) occur without visual feedback.
**Action:** Always initialize UI with a "Scanning..." or "Loading..." state for any operation that takes >1s, and explicitly clear it only when data is ready.
## 2024-10-24 - Async Operation Feedback
**Learning:** Blocking operations in background threads (like `winget list` which takes >5s) create a "broken" appearance if the UI remains empty during execution.
**Action:** Always implement an explicit "Scanning..." or "Loading..." state for any list population that depends on external processes, and ensure it persists until data is ready.

