## 2024-05-22 - Login Password Visibility
**Learning:** `customtkinter` Entry widgets support dynamic `show` attribute updates, allowing for seamless password visibility toggling.
**Action:** When implementing password fields, always wrap them in a frame with a toggle button to improve usability and reduce input errors.

## 2024-05-23 - Abbreviated Button Labels
**Learning:** Abbreviated buttons (Gen, Tun, LAN) save space but confuse new users.
**Action:** Always attach a `ToolTip` to explain the full function of abbreviated actions.

## 2024-05-24 - Empty States for Lists
**Learning:** `customtkinter` scrollable frames can feel broken when empty.
**Action:** Always verify if a dynamic list is empty and inject a friendly "Empty State" frame with an action button to guide the user.
