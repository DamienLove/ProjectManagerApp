## 2024-05-22 - File Modification Resolution
**Learning:** When testing file-based caching mechanisms that rely on `os.path.getmtime`, simply calling `os.utime(path, None)` (which sets it to "now") might not be enough if the test runs extremely fast, as the resolution of the filesystem might yield the same timestamp.
**Action:** Always ensure a significant delta (e.g., `st_mtime + 2.0`) when forcing mtime updates in tests to guarantee change detection.
