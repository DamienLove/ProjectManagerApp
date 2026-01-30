import os
import sys
import unittest
from unittest.mock import patch, MagicMock

# Mock dependencies to avoid import errors
sys.modules["firebase_admin"] = MagicMock()
sys.modules["firebase_admin.credentials"] = MagicMock()
sys.modules["firebase_admin.firestore"] = MagicMock()
sys.modules["starlette.concurrency"] = MagicMock()
sys.modules["dotenv"] = MagicMock()
sys.modules["uvicorn"] = MagicMock()
sys.modules["fastapi"] = MagicMock()
sys.modules["fastapi.responses"] = MagicMock()

# Set env vars BEFORE importing remote_agent
# Using a fixed workspace for testing
TEST_WORKSPACE = "/tmp/workspace" if os.name != 'nt' else r"C:\tmp\workspace"
os.environ["LOCAL_WORKSPACE_ROOT"] = TEST_WORKSPACE
os.environ["REMOTE_ALLOWED_ROOTS"] = ""

# Add src to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

import remote_agent

class TestIsPathSafeStrict(unittest.TestCase):
    def test_strict_deny_by_default(self):
        """
        Verify that is_path_safe strictly denies paths outside workspace
        when REMOTE_ALLOWED_ROOTS is empty.
        """
        # Determine an "outside" path that is NOT in the old PROTECTED_PATHS blacklist
        if os.name == 'nt':
            outside_path = r"D:\Secret.txt" # D: drive was allowed by old code
        else:
            outside_path = "/tmp/outside_secret.txt" # /tmp/outside was allowed by old code

        is_safe = remote_agent.is_path_safe(outside_path)

        # We expect this to be FALSE now (it was True in vulnerable version)
        self.assertFalse(is_safe, f"VULNERABILITY: Path {outside_path} should be blocked!")

    def test_allow_workspace_files(self):
        """Verify that files INSIDE the workspace are still allowed."""
        safe_path = os.path.join(TEST_WORKSPACE, "my_project", "omni.json")
        self.assertTrue(remote_agent.is_path_safe(safe_path))

    def test_allow_workspace_root(self):
        """Verify that workspace root itself is allowed."""
        self.assertTrue(remote_agent.is_path_safe(TEST_WORKSPACE))

    def test_explicit_allowed_roots(self):
        """Verify that REMOTE_ALLOWED_ROOTS works as a whitelist if set."""
        # This requires reloading the module or patching ABS_REMOTE_ALLOWED_ROOTS
        # Since ABS_REMOTE_ALLOWED_ROOTS is computed at module level, we must patch it directly.

        allowed_extra = "/var/www" if os.name != 'nt' else r"E:\www"

        # Patch the module-level variable
        with patch("remote_agent.ABS_REMOTE_ALLOWED_ROOTS", [os.path.abspath(allowed_extra)]):
            self.assertTrue(remote_agent.is_path_safe(os.path.join(allowed_extra, "index.html")))
            self.assertFalse(remote_agent.is_path_safe("/etc/passwd" if os.name != 'nt' else r"C:\Windows\System32"))

if __name__ == '__main__':
    unittest.main()
