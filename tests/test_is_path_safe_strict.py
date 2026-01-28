import unittest
import os
import sys
from unittest.mock import MagicMock, patch

# Define Mock exceptions and classes
class MockHTTPException(Exception):
    def __init__(self, status_code, detail):
        self.status_code = status_code
        self.detail = detail

class TestIsPathSafeStrict(unittest.TestCase):
    def setUp(self):
        # Clean up modules to ensure fresh import
        if 'src.remote_agent' in sys.modules:
            del sys.modules['src.remote_agent']
        if 'remote_agent' in sys.modules:
            del sys.modules['remote_agent']

        # Mock dependencies
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

        # Add src to path if not there
        src_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '../src'))
        if src_path not in sys.path:
            sys.path.insert(0, src_path)

    def test_strict_validation_default(self):
        """Test that is_path_safe is strict by default (empty allowed roots)."""
        with patch.dict(os.environ, {
            "LOCAL_WORKSPACE_ROOT": "/tmp/workspace",
            "REMOTE_ALLOWED_ROOTS": "", # Empty
        }):
            import remote_agent

            # Safe path
            self.assertTrue(remote_agent.is_path_safe("/tmp/workspace/project1"))
            self.assertTrue(remote_agent.is_path_safe("/tmp/workspace"))

            # Unsafe paths - should be blocked even if not "Protected"
            self.assertFalse(remote_agent.is_path_safe("/tmp/secret.txt"), "Access to /tmp/secret.txt should be denied")
            self.assertFalse(remote_agent.is_path_safe("/etc/passwd"), "Access to /etc/passwd should be denied")
            self.assertFalse(remote_agent.is_path_safe("/"), "Access to / should be denied")

    def test_strict_validation_with_allowed_roots(self):
        """Test that is_path_safe respects allowed roots."""
        with patch.dict(os.environ, {
            "LOCAL_WORKSPACE_ROOT": "/tmp/workspace",
            "REMOTE_ALLOWED_ROOTS": "/opt/data;/var/log",
        }):
            import remote_agent

            self.assertTrue(remote_agent.is_path_safe("/tmp/workspace/p1"))
            self.assertTrue(remote_agent.is_path_safe("/opt/data/file.txt"))
            self.assertTrue(remote_agent.is_path_safe("/var/log/syslog"))

            self.assertFalse(remote_agent.is_path_safe("/etc/passwd"))
            self.assertFalse(remote_agent.is_path_safe("/tmp/other"))

if __name__ == "__main__":
    unittest.main()
