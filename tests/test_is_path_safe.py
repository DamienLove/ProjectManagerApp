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

# Mock fastapi consistently with other tests
mock_fastapi = MagicMock()
sys.modules["fastapi"] = mock_fastapi
sys.modules["fastapi.responses"] = MagicMock()

class MockHTTPException(Exception):
    def __init__(self, status_code, detail):
        self.status_code = status_code
        self.detail = detail

mock_fastapi.HTTPException = MockHTTPException
mock_fastapi.Request = MagicMock
mock_fastapi.WebSocket = MagicMock
mock_fastapi.WebSocketDisconnect = Exception
mock_fastapi.FastAPI = MagicMock


class TestIsPathSafeDefaults(unittest.TestCase):
    """Test behavior when REMOTE_ALLOWED_ROOTS is NOT set (Default)."""
    def setUp(self):
        if "remote_agent" in sys.modules:
            del sys.modules["remote_agent"]
        if "src.remote_agent" in sys.modules:
            del sys.modules["src.remote_agent"]

        self.workspace_root = os.path.abspath("/tmp/workspace")

        self.env_patcher = patch.dict(os.environ, {
            "REMOTE_ACCESS_TOKEN": "test_token",
            "LOCAL_WORKSPACE_ROOT": self.workspace_root,
            "REMOTE_ALLOWED_ROOTS": "" # Empty by default
        })
        self.env_patcher.start()

        import remote_agent
        self.remote_agent = remote_agent

    def tearDown(self):
        self.env_patcher.stop()

    def test_workspace_path_allowed(self):
        safe_path = os.path.join(self.workspace_root, "project", "file.txt")
        self.assertTrue(self.remote_agent.is_path_safe(safe_path))

    def test_arbitrary_path_denied_default(self):
        unsafe_path = os.path.abspath("/tmp/secret.txt")
        self.assertFalse(self.remote_agent.is_path_safe(unsafe_path),
                         "Arbitrary path should be denied by default")

    def test_system_path_denied_default(self):
        unsafe_path = os.path.abspath("/etc/passwd")
        self.assertFalse(self.remote_agent.is_path_safe(unsafe_path),
                         "System path should be denied by default")


class TestIsPathSafeWithConfig(unittest.TestCase):
    """Test behavior when REMOTE_ALLOWED_ROOTS IS set."""
    def setUp(self):
        if "remote_agent" in sys.modules:
            del sys.modules["remote_agent"]
        if "src.remote_agent" in sys.modules:
            del sys.modules["src.remote_agent"]

        self.workspace_root = os.path.abspath("/tmp/workspace")
        self.allowed_root = os.path.abspath("/tmp/allowed")

        self.env_patcher = patch.dict(os.environ, {
            "REMOTE_ACCESS_TOKEN": "test_token",
            "LOCAL_WORKSPACE_ROOT": self.workspace_root,
            "REMOTE_ALLOWED_ROOTS": self.allowed_root
        })
        self.env_patcher.start()

        import remote_agent
        self.remote_agent = remote_agent

    def tearDown(self):
        self.env_patcher.stop()

    def test_allowed_root_path_allowed(self):
        safe_path = os.path.join(self.allowed_root, "config.json")
        self.assertTrue(self.remote_agent.is_path_safe(safe_path))

    def test_arbitrary_path_denied_with_config(self):
        unsafe_path = os.path.abspath("/tmp/secret.txt")
        self.assertFalse(self.remote_agent.is_path_safe(unsafe_path))

if __name__ == '__main__':
    unittest.main()
