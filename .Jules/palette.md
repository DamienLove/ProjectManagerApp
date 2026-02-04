# Jules Design Palette: Learnings & Guidelines

## 2024-05-23 - Abbreviated Button Labels
**Learning:** Abbreviated buttons (Gen, Tun, LAN) save space but confuse new users.
**Action:** Always attach a `ToolTip` to explain the full function of abbreviated actions.

## 2024-05-24 - Empty State Onboarding
**Learning:** Dynamic lists without empty states leave new users guessing what to do next.
**Action:** When a list (like projects) is empty, always display a friendly welcome message and a primary Call to Action button.

## 2024-05-24 - Context-Aware Tooltips
**Learning:** Adding tooltips to icon-only buttons (like "AntiG" or "Config") significantly clarifies their purpose without cluttering the UI. `ToolTip` class logic is reusable and effective.
**Action:** Use `ToolTip` for any action button that uses an icon or an abbreviated label to improve discoverability.

## 2024-05-27 - Async Action Feedback
**Learning:** Blocking the UI thread during network requests (login/register) looks like a crash and allows double-submissions.
**Action:** Always wrap network calls in a background thread and use a `_set_loading` helper to disable buttons and update status text immediately.
