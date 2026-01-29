import sys
import os
import unittest
from unittest.mock import MagicMock, patch

# Add src to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

# Define Mock exceptions and classes compatible with remote_agent expectations
class MockHTTPException(Exception):
    def __init__(self, status_code, detail):
        self.status_code = status_code
        self.detail = detail

# Mock dependencies required to import remote_agent
sys.modules["firebase_admin"] = MagicMock()
sys.modules["firebase_admin.credentials"] = MagicMock()
sys.modules["firebase_admin.firestore"] = MagicMock()
sys.modules["starlette.concurrency"] = MagicMock()
sys.modules["dotenv"] = MagicMock()
sys.modules["uvicorn"] = MagicMock()

mock_fastapi = MagicMock()
mock_fastapi.HTTPException = MockHTTPException
sys.modules["fastapi"] = mock_fastapi
sys.modules["fastapi.responses"] = MagicMock()

class TestIsPathSafeStrict(unittest.TestCase):
    def setUp(self):
        # We need to reload remote_agent to reset module-level variables like ABS_PROTECTED_PATHS
        if "remote_agent" in sys.modules:
            del sys.modules["remote_agent"]
        if "src.remote_agent" in sys.modules:
            del sys.modules["src.remote_agent"]
        pass

    def test_deny_by_default_windows(self):
        """Test that paths outside workspace are denied by default (simulating Windows logic)."""

        with patch('os.path.abspath') as mock_abspath, \
             patch('os.sep', '\\'), \
             patch.dict(os.environ, {"LOCAL_WORKSPACE_ROOT": r"C:\Projects", "REMOTE_ALLOWED_ROOTS": ""}):

            def side_effect_abspath(path):
                path = str(path)
                # Handle drive letters generally
                if len(path) > 1 and path[1] == ":":
                    return path.replace("/", "\\")
                if path.startswith("\\"):
                    return "C:" + path.replace("/", "\\")
                return r"C:\Projects" + "\\" + path.replace("/", "\\")

            mock_abspath.side_effect = side_effect_abspath

            import remote_agent

            # Workspace should be safe
            self.assertTrue(remote_agent.is_path_safe(r"C:\Projects\MyProject"))
            self.assertTrue(remote_agent.is_path_safe(r"C:\Projects"))

            # Protected paths should be unsafe
            self.assertFalse(remote_agent.is_path_safe(r"C:\Windows\System32\cmd.exe"))

            # VULNERABILITY CHECK:
            # Secondary drive should be UNSAFE by default.
            self.assertFalse(remote_agent.is_path_safe(r"D:\Secret\Data.txt"), "D: drive access should be denied by default")

            # User profile on C: should be denied
            self.assertFalse(remote_agent.is_path_safe(r"C:\Users\Admin\Secret.txt"))

    def test_allow_list(self):
        """Test that explicit allow list works."""
        with patch('os.path.abspath') as mock_abspath, \
             patch('os.sep', '\\'), \
             patch.dict(os.environ, {"LOCAL_WORKSPACE_ROOT": r"C:\Projects", "REMOTE_ALLOWED_ROOTS": r"D:\Games;E:\Work"}):

            def side_effect_abspath(path):
                path = str(path)
                if len(path) > 1 and path[1] == ":":
                    return path.replace("/", "\\")
                return r"C:\Projects" + "\\" + path.replace("/", "\\")

            mock_abspath.side_effect = side_effect_abspath

            import remote_agent

            # Workspace safe
            self.assertTrue(remote_agent.is_path_safe(r"C:\Projects\MyProject"))

            # Allowed roots safe
            self.assertTrue(remote_agent.is_path_safe(r"D:\Games\Config.json"))
            self.assertTrue(remote_agent.is_path_safe(r"E:\Work\Project.doc"))

            # Other roots unsafe
            self.assertFalse(remote_agent.is_path_safe(r"F:\Other\File.txt"))
            self.assertFalse(remote_agent.is_path_safe(r"C:\Windows\System32"))


if __name__ == '__main__':
    unittest.main()
