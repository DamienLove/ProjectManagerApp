## 2024-05-23 - Async Loading States
**Learning:** Users perceive the application as broken when long-running background processes (like `winget list`) occur without visual feedback.
**Action:** Always initialize UI with a "Scanning..." or "Loading..." state for any operation that takes >1s, and explicitly clear it only when data is ready.

## 2024-05-23 - Icon-Only Button Context
**Learning:** Icon-only buttons (like the main settings gear or delete icons) are visually clean but can be ambiguous to new users or screen reader users.
**Action:** Implemented a reusable `ToolTip` class for CustomTkinter widgets to provide immediate context on hover and focus. This should be applied to all future icon-only interactions.
