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

# Mock fastapi
mock_fastapi = MagicMock()
sys.modules["fastapi"] = mock_fastapi
sys.modules["fastapi.responses"] = MagicMock()

# Define Mock exceptions and classes
class MockHTTPException(Exception):
    def __init__(self, status_code, detail):
        self.status_code = status_code
        self.detail = detail

mock_fastapi.HTTPException = MockHTTPException
mock_fastapi.Request = MagicMock
mock_fastapi.WebSocket = MagicMock
mock_fastapi.WebSocketDisconnect = Exception
mock_fastapi.FastAPI = MagicMock

class TestRemoteAgentAuth(unittest.TestCase):
    def setUp(self):
        # Force reload of remote_agent
        if "remote_agent" in sys.modules:
            del sys.modules["remote_agent"]
        if "src.remote_agent" in sys.modules:
            del sys.modules["src.remote_agent"]

        self.env_patcher = patch.dict(os.environ, {"REMOTE_ACCESS_TOKEN": "secret_token_123"})
        self.env_patcher.start()

        import remote_agent
        self.remote_agent = remote_agent

    def tearDown(self):
        self.env_patcher.stop()

    def test_auth_uses_compare_digest(self):
        """Verify that authentication uses constant-time comparison."""
        request = MagicMock()
        request.headers = {"X-Omni-Token": "secret_token_123"}

        with patch('secrets.compare_digest', return_value=True) as mock_compare:
            try:
                self.remote_agent.require_token_from_request(request)
            except Exception as e:
                self.fail(f"require_token_from_request raised exception: {e}")

            # This assertion is expected to FAIL initially
            self.assertTrue(mock_compare.called, "secrets.compare_digest should be used for token verification")

    def test_auth_logic_valid(self):
        """Verify that correct token passes."""
        request = MagicMock()
        request.headers = {"X-Omni-Token": "secret_token_123"}
        try:
            self.remote_agent.require_token_from_request(request)
        except Exception:
            self.fail("Valid token rejected")

    def test_auth_logic_invalid(self):
        """Verify that incorrect token fails."""
        request = MagicMock()
        request.headers = {"X-Omni-Token": "wrong_token"}
        with self.assertRaises(MockHTTPException):
            self.remote_agent.require_token_from_request(request)

if __name__ == '__main__':
    unittest.main()
