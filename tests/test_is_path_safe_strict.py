import sys
import os
import unittest
from unittest.mock import MagicMock, patch

# Add src to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

# Mock dependencies to allow importing remote_agent without side effects
sys.modules["firebase_admin"] = MagicMock()
sys.modules["firebase_admin.credentials"] = MagicMock()
sys.modules["firebase_admin.firestore"] = MagicMock()
sys.modules["starlette.concurrency"] = MagicMock()
sys.modules["dotenv"] = MagicMock()
sys.modules["uvicorn"] = MagicMock()
sys.modules["fastapi"] = MagicMock()
sys.modules["fastapi.responses"] = MagicMock()

class TestIsPathSafeStrict(unittest.TestCase):
    def setUp(self):
        # Clean up previous imports
        if "remote_agent" in sys.modules:
            del sys.modules["remote_agent"]
        if "src.remote_agent" in sys.modules:
            del sys.modules["src.remote_agent"]

        # Set up environment variables for the test
        self.workspace_root = os.path.abspath("/tmp/workspace")
        self.allowed_root = os.path.abspath("/tmp/allowed")

        self.env_patcher = patch.dict(os.environ, {
            "LOCAL_WORKSPACE_ROOT": self.workspace_root,
            "REMOTE_ALLOWED_ROOTS": self.allowed_root,
            # We don't set PROTECTED_PATHS here as they are hardcoded in the module,
            # but we can rely on the module's logic.
        })
        self.env_patcher.start()

        # Import the module under test
        import remote_agent
        self.remote_agent = remote_agent

    def tearDown(self):
        self.env_patcher.stop()

    def test_allowed_workspace_path(self):
        """Test that paths inside the workspace root are allowed."""
        safe_path = os.path.join(self.workspace_root, "project1", "omni.json")
        self.assertTrue(self.remote_agent.is_path_safe(safe_path), f"Should allow workspace path: {safe_path}")

    def test_allowed_root_path(self):
        """Test that paths inside REMOTE_ALLOWED_ROOTS are allowed."""
        safe_path = os.path.join(self.allowed_root, "config.json")
        self.assertTrue(self.remote_agent.is_path_safe(safe_path), f"Should allow explicitly allowed root: {safe_path}")

    def test_denied_system_path(self):
        """Test that system paths (outside workspace/allowed) are DENIED."""
        # On Linux, /etc/passwd. On Windows, maybe C:\Windows\System32 (which is protected by default logic anyway).
        # We want to test the "Deny by Default" for paths that are NOT protected but NOT allowed.

        if sys.platform == "win32":
            unsafe_path = "D:\\Secrets\\passwords.txt"
        else:
            unsafe_path = "/etc/passwd"

        # This assertions checks if the strict logic is working.
        # CURRENTLY: This is expected to FAIL because is_path_safe returns True for these.
        self.assertFalse(self.remote_agent.is_path_safe(unsafe_path), f"Should deny system path: {unsafe_path}")

    def test_denied_random_path(self):
        """Test that a random path outside of allowed roots is DENIED."""
        # A path that is not system, not protected, but also not allowed.
        unsafe_path = os.path.abspath("/tmp/random_folder/file.txt")
        # Ensure it doesn't accidentally fall into workspace or allowed
        if unsafe_path.startswith(self.workspace_root) or unsafe_path.startswith(self.allowed_root):
            self.skipTest("Random path collided with allowed paths")

        self.assertFalse(self.remote_agent.is_path_safe(unsafe_path), f"Should deny random path: {unsafe_path}")

class TestIsPathSafeVulnerableConfig(unittest.TestCase):
    """Test behavior when REMOTE_ALLOWED_ROOTS is NOT set (the default)."""

    def setUp(self):
        # Clean up previous imports
        if "remote_agent" in sys.modules:
            del sys.modules["remote_agent"]
        if "src.remote_agent" in sys.modules:
            del sys.modules["src.remote_agent"]

        self.workspace_root = os.path.abspath("/tmp/workspace")

        # Empty REMOTE_ALLOWED_ROOTS to simulate default insecure config
        self.env_patcher = patch.dict(os.environ, {
            "LOCAL_WORKSPACE_ROOT": self.workspace_root,
            "REMOTE_ALLOWED_ROOTS": "",
        })
        self.env_patcher.start()

        import remote_agent
        self.remote_agent = remote_agent

    def tearDown(self):
        self.env_patcher.stop()

    def test_default_config_should_deny_system_path(self):
        """
        With default config (no allowed roots), system paths should still be DENIED.
        This tests the fix for the vulnerability.
        """
        if sys.platform == "win32":
            unsafe_path = "D:\\Secrets\\passwords.txt"
        else:
            unsafe_path = "/etc/passwd"

        # This assertions checks if the strict logic is working even with empty allowed roots.
        # CURRENTLY: This is expected to FAIL (return True)
        self.assertFalse(self.remote_agent.is_path_safe(unsafe_path), f"Should deny system path even with empty allowed roots: {unsafe_path}")

if __name__ == '__main__':
    unittest.main()
