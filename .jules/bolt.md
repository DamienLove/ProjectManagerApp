## 2024-10-24 - Pre-calculation of invariant paths
**Learning:** `os.path.abspath` can be a significant overhead in hot paths (like security checks) if called repeatedly on constant values.
**Action:** Pre-calculate absolute paths for static configurations at module level.
