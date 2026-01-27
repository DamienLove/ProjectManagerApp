import sys
import os
import unittest
from unittest.mock import MagicMock, patch

# Add src to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

# Mock dependencies
sys.modules["firebase_admin"] = MagicMock()
sys.modules["firebase_admin.credentials"] = MagicMock()
sys.modules["firebase_admin.firestore"] = MagicMock()
sys.modules["starlette.concurrency"] = MagicMock()
sys.modules["dotenv"] = MagicMock()
sys.modules["uvicorn"] = MagicMock()
sys.modules["fastapi"] = MagicMock()
sys.modules["fastapi.responses"] = MagicMock()

class TestIsPathSafe(unittest.TestCase):
    def setUp(self):
        if "remote_agent" in sys.modules:
            del sys.modules["remote_agent"]
        if "src.remote_agent" in sys.modules:
            del sys.modules["src.remote_agent"]

        # Setup environment variables for the test
        self.env_patcher = patch.dict(os.environ, {
            "REMOTE_ACCESS_TOKEN": "test_token",
            "LOCAL_WORKSPACE_ROOT": "/tmp/workspace",
            "REMOTE_ALLOWED_ROOTS": "", # Empty allowed roots
            # On Windows, PROTECTED_PATHS defaults to C:\...
            # We will patch ABS_PROTECTED_PATHS in the module to be platform agnostic for this test
        })
        self.env_patcher.start()

        import remote_agent
        self.remote_agent = remote_agent

        # Patch the constants to control the test environment
        self.remote_agent.ABS_LOCAL_WORKSPACE_ROOT = os.path.abspath("/tmp/workspace")
        self.remote_agent.ABS_REMOTE_ALLOWED_ROOTS = []
        self.remote_agent.ABS_PROTECTED_PATHS = [
            os.path.abspath("/protected"),
            os.path.abspath("/tmp/workspace/secret") # Protected path INSIDE workspace
        ]

    def tearDown(self):
        self.env_patcher.stop()

    def test_allow_workspace_root(self):
        self.assertTrue(self.remote_agent.is_path_safe("/tmp/workspace"))
        self.assertTrue(self.remote_agent.is_path_safe("/tmp/workspace/project"))

    def test_block_protected_paths(self):
        self.assertFalse(self.remote_agent.is_path_safe("/protected"))
        self.assertFalse(self.remote_agent.is_path_safe("/protected/file"))

    def test_block_protected_path_inside_workspace(self):
        # This checks that Blocklist overrides Allowlist
        self.assertFalse(self.remote_agent.is_path_safe("/tmp/workspace/secret"))
        self.assertFalse(self.remote_agent.is_path_safe("/tmp/workspace/secret/file"))

        # Sibling should be fine
        self.assertTrue(self.remote_agent.is_path_safe("/tmp/workspace/public"))

    def test_vulnerability_allow_arbitrary_paths(self):
        # This path is neither in workspace nor protected.
        # CURRENT BEHAVIOR: It should return False (Deny by Default)
        arbitrary_path = "/tmp/arbitrary/path"
        is_safe = self.remote_agent.is_path_safe(arbitrary_path)

        print(f"\n[Test] Checking arbitrary path {arbitrary_path}: Safe={is_safe}")

        # This asserts the fix: arbitrary paths must be blocked.
        self.assertFalse(is_safe, "Arbitrary path should be blocked by default.")

if __name__ == '__main__':
    unittest.main()
