## 2024-05-23 - Tooltip Implementation Strategy
**Learning:** Abbreviated buttons (like "AntiG") in dense UIs are a recurring pattern here. Users often hesitate to click them. The `ToolTip` class in `src/main.py` is a lightweight, reusable solution that doesn't require new dependencies.
**Action:** When adding or modifying compact button layouts, always attach the `ToolTip` class to provide context. The pattern `ToolTip(widget, text)` is simple and should be standard for all icon-only or abbreviated controls.
