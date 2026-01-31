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

# Mock fastapi properly to avoid breaking other tests that expect HTTPException to be an Exception
mock_fastapi = MagicMock()
class MockHTTPException(Exception):
    def __init__(self, status_code, detail):
        self.status_code = status_code
        self.detail = detail
mock_fastapi.HTTPException = MockHTTPException
sys.modules["fastapi"] = mock_fastapi
sys.modules["fastapi.responses"] = MagicMock()

class TestIsPathSafeStrict(unittest.TestCase):
    def setUp(self):
        if "remote_agent" in sys.modules:
            del sys.modules["remote_agent"]
        if "src.remote_agent" in sys.modules:
            del sys.modules["src.remote_agent"]

        # We need to load remote_agent to get the function, but we want to control the constants.
        # Since constants are computed at load time, we can patch os.getenv before import,
        # OR we can patch the constants on the module after import.
        # Patching constants after import is safer for testing specific values without reloading every time.

        # Load module
        import remote_agent
        self.remote_agent = remote_agent

    def test_default_deny(self):
        """Test that paths outside workspace/allowed roots are denied by default."""
        # Setup: Workspace is /tmp/work, Protected is /tmp/prot.
        # We test /tmp/random.

        with patch.object(self.remote_agent, 'ABS_LOCAL_WORKSPACE_ROOT', "/tmp/work"), \
             patch.object(self.remote_agent, 'ABS_REMOTE_ALLOWED_ROOTS', []), \
             patch.object(self.remote_agent, 'ABS_PROTECTED_PATHS', ["/tmp/prot"]):

            # Using absolute paths for simulation
            # Note: The function uses os.path.abspath(path) internally.
            # We must mock os.path.abspath or pass absolute paths.

            # Case 1: Random path (should be denied, currently allowed)
            # In existing code, if not protected, it returns True.
            self.assertFalse(self.remote_agent.is_path_safe("/tmp/random"),
                             "VULNERABILITY: Random path was allowed! Should be default deny.")

    def test_allow_workspace(self):
        with patch.object(self.remote_agent, 'ABS_LOCAL_WORKSPACE_ROOT', "/tmp/work"), \
             patch.object(self.remote_agent, 'ABS_REMOTE_ALLOWED_ROOTS', []), \
             patch.object(self.remote_agent, 'ABS_PROTECTED_PATHS', ["/tmp/prot"]):

            self.assertTrue(self.remote_agent.is_path_safe("/tmp/work/project1"))

    def test_deny_protected(self):
        with patch.object(self.remote_agent, 'ABS_LOCAL_WORKSPACE_ROOT', "/tmp/work"), \
             patch.object(self.remote_agent, 'ABS_REMOTE_ALLOWED_ROOTS', []), \
             patch.object(self.remote_agent, 'ABS_PROTECTED_PATHS', ["/tmp/prot"]):

            self.assertFalse(self.remote_agent.is_path_safe("/tmp/prot/config"))

    def test_allow_explicit_root(self):
        with patch.object(self.remote_agent, 'ABS_LOCAL_WORKSPACE_ROOT', "/tmp/work"), \
             patch.object(self.remote_agent, 'ABS_REMOTE_ALLOWED_ROOTS', ["/tmp/extra"]), \
             patch.object(self.remote_agent, 'ABS_PROTECTED_PATHS', ["/tmp/prot"]):

            self.assertTrue(self.remote_agent.is_path_safe("/tmp/extra/data"))

    def test_protected_overrides_workspace(self):
        """Test that if workspace is root, protected paths are still denied."""
        # This tests the proposed improvement (moving protected check to top).
        # Workspace = /, Protected = /etc

        with patch.object(self.remote_agent, 'ABS_LOCAL_WORKSPACE_ROOT', "/"), \
             patch.object(self.remote_agent, 'ABS_REMOTE_ALLOWED_ROOTS', []), \
             patch.object(self.remote_agent, 'ABS_PROTECTED_PATHS', ["/etc"]):

            # Currently this will Fail (return True) because workspace check is first.
            # After fix, this should return False.
            self.assertFalse(self.remote_agent.is_path_safe("/etc/passwd"),
                             "VULNERABILITY: Protected path inside workspace was allowed!")

if __name__ == '__main__':
    unittest.main()
