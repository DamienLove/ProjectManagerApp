## 2024-05-23 - Async Loading States
**Learning:** Users perceive the application as broken when long-running background processes (like `winget list`) occur without visual feedback.
**Action:** Always initialize UI with a "Scanning..." or "Loading..." state for any operation that takes >1s, and explicitly clear it only when data is ready.
