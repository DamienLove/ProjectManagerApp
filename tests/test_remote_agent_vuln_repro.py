import unittest
import os
import sys
from unittest.mock import patch, MagicMock

# Mock necessary modules for remote_agent import
sys.modules['firebase_admin'] = MagicMock()
sys.modules['firebase_admin.credentials'] = MagicMock()
sys.modules['firebase_admin.firestore'] = MagicMock()
sys.modules['fastapi'] = MagicMock()
sys.modules['fastapi.responses'] = MagicMock()
sys.modules['uvicorn'] = MagicMock()
sys.modules['starlette'] = MagicMock()
sys.modules['starlette.concurrency'] = MagicMock()
sys.modules['dotenv'] = MagicMock()

# Now import the module under test
from src import remote_agent

class TestPathSafetyVuln(unittest.TestCase):
    def setUp(self):
        # Setup specific paths for testing
        self.original_workspace = remote_agent.ABS_LOCAL_WORKSPACE_ROOT
        self.original_allowed = remote_agent.ABS_REMOTE_ALLOWED_ROOTS

        # Simulate Windows paths behavior even on Linux for logic check
        # We rely on os.path.abspath which is platform dependent, so we must rely on
        # the platform we are running on.
        # However, the vulnerability is logic-based: "If not in allowlist, check blocklist."

        # We will set workspace to a temp dir
        self.workspace = os.path.abspath("/tmp/workspace")
        remote_agent.ABS_LOCAL_WORKSPACE_ROOT = self.workspace

        # Set allowed roots to EMPTY (Default configuration)
        remote_agent.ABS_REMOTE_ALLOWED_ROOTS = []

    def tearDown(self):
        remote_agent.ABS_LOCAL_WORKSPACE_ROOT = self.original_workspace
        remote_agent.ABS_REMOTE_ALLOWED_ROOTS = self.original_allowed

    def test_path_traversal_default_allow(self):
        """
        Vulnerability Reproduction:
        If REMOTE_ALLOWED_ROOTS is empty, the agent should NOT allow access to arbitrary paths
        that are not explicitly protected.
        """
        # Path outside workspace, and not in protected paths.
        # E.g. /etc/passwd or /home/user/secret (if /protected is /usr)

        # /tmp/secret_outside_workspace
        outside_path = os.path.abspath("/tmp/secret_outside_workspace")

        # Ensure it is not workspace or child
        self.assertFalse(outside_path.startswith(self.workspace))

        # Ensure it is not protected
        self.assertFalse(outside_path.startswith(os.path.abspath("/protected")))

        # NEW SECURE BEHAVIOR: Returns False
        is_safe = remote_agent.is_path_safe(outside_path)
        print(f"Path: {outside_path}, Is Safe: {is_safe}")

        # We expect this to be False now (Fixed).
        self.assertFalse(is_safe, "Vulnerability NOT fixed: Path was allowed.")

if __name__ == '__main__':
    unittest.main()
