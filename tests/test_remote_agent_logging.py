import sys
import os
import unittest
from unittest.mock import MagicMock, patch, AsyncMock
import asyncio

# Add src to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

# Mock dependencies
for mod in ["firebase_admin", "firebase_admin.credentials", "firebase_admin.firestore",
            "starlette.concurrency", "dotenv", "uvicorn", "fastapi.responses"]:
    sys.modules[mod] = MagicMock()

# Better FastAPI mock to preserve function logic through decorators
class MockFastAPI:
    def __init__(self, *args, **kwargs):
        pass
    def post(self, *args, **kwargs):
        return lambda func: func
    def get(self, *args, **kwargs):
        return lambda func: func
    def websocket(self, *args, **kwargs):
        return lambda func: func

mock_fastapi = MagicMock()
mock_fastapi.FastAPI = MockFastAPI
mock_fastapi.HTTPException = Exception
sys.modules["fastapi"] = mock_fastapi

class TestRemoteAgentLogging(unittest.TestCase):
    def setUp(self):
        if "remote_agent" in sys.modules:
            del sys.modules["remote_agent"]
        if "src.remote_agent" in sys.modules:
            del sys.modules["src.remote_agent"]

        self.env_patcher = patch.dict(os.environ, {
            "REMOTE_ACCESS_TOKEN": "test_token",
            "LOCAL_WORKSPACE_ROOT": "/tmp/workspace",
            "REMOTE_BIND_HOST": "127.0.0.1",
            "REMOTE_PORT": "8000"
        })
        self.env_patcher.start()

        import remote_agent
        self.remote_agent = remote_agent

    def tearDown(self):
        self.env_patcher.stop()

    def test_sanitize_command_logic(self):
        """Test the sanitize_command function directly."""
        if not hasattr(self.remote_agent, "sanitize_command"):
            print("sanitize_command not found (expected)")
            return

        sanitize = self.remote_agent.sanitize_command

        cases = [
            ("login --password MySecretPassword", "login --password ***"),
            ("set token=XYZ123", "set token=***"),
            ("my_command --key=12345 --verbose", "my_command --key=*** --verbose"),
            ("echo 'hello world'", "echo 'hello world'"),
        ]

        for input_cmd, expected in cases:
            self.assertEqual(sanitize(input_cmd), expected, f"Failed to sanitize: {input_cmd}")

    @patch("remote_agent.log")
    def test_api_command_logging_redacted(self, mock_log):
        """Test that api_command logs redacted commands."""

        # Mock Request
        mock_request = MagicMock()
        mock_request.headers.get.return_value = "test_token"

        # Async mock for json()
        mock_request.json = AsyncMock(return_value={"cmd": "login --password secret123", "cwd": "/tmp"})

        # We also need to mock create_subprocess_shell and is_path_safe
        with patch("asyncio.create_subprocess_shell", new_callable=AsyncMock) as mock_shell, \
             patch("remote_agent.is_path_safe", return_value=True):

             mock_proc = MagicMock()
             mock_proc.communicate = AsyncMock(return_value=(b"", b""))
             mock_proc.returncode = 0
             mock_shell.return_value = mock_proc

             # Run the function
             try:
                 asyncio.run(self.remote_agent.api_command(mock_request))
             except Exception as e:
                 self.fail(f"api_command raised exception: {e}")

             # Verify log call
             args, _ = mock_log.call_args
             log_msg = args[0]

             print(f"Logged message: {log_msg}")

             if "secret123" in log_msg:
                 self.fail("VULNERABILITY: Sensitive data leaked in logs!")

             self.assertIn("***", log_msg, "Redaction not applied")

if __name__ == '__main__':
    unittest.main()
