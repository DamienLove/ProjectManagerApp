import sys
import os
import unittest
from unittest.mock import MagicMock, patch

# Add src to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

# Mock exception for FastAPI
class MockHTTPException(Exception):
    def __init__(self, status_code, detail=None):
        self.status_code = status_code
        self.detail = detail

# Mock dependencies
sys.modules["firebase_admin"] = MagicMock()
sys.modules["firebase_admin.credentials"] = MagicMock()
sys.modules["firebase_admin.firestore"] = MagicMock()
sys.modules["starlette.concurrency"] = MagicMock()
sys.modules["dotenv"] = MagicMock()
sys.modules["uvicorn"] = MagicMock()

mock_fastapi = MagicMock()
mock_fastapi.HTTPException = MockHTTPException

# Fix decorators for FastAPI app
mock_app_instance = MagicMock()
def identity_decorator(*args, **kwargs):
    def wrapper(func):
        return func
    return wrapper
mock_app_instance.get.side_effect = identity_decorator
mock_app_instance.post.side_effect = identity_decorator
mock_app_instance.websocket.side_effect = identity_decorator
mock_fastapi.FastAPI.return_value = mock_app_instance

sys.modules["fastapi"] = mock_fastapi
sys.modules["fastapi.responses"] = MagicMock()

class TestLogSanitization(unittest.TestCase):
    def setUp(self):
        # Force reload
        if "remote_agent" in sys.modules:
            del sys.modules["remote_agent"]
        if "src.remote_agent" in sys.modules:
            del sys.modules["src.remote_agent"]

        # Patch env
        self.env_patcher = patch.dict(os.environ, {
            "REMOTE_ACCESS_TOKEN": "test_token",
            "LOCAL_WORKSPACE_ROOT": "/tmp/ws"
        })
        self.env_patcher.start()

    def tearDown(self):
        self.env_patcher.stop()

    def test_sanitize_command_function(self):
        """Test that sanitize_command redacts sensitive info."""
        try:
            from remote_agent import sanitize_command
        except ImportError:
            # If function doesn't exist yet, we can't test it.
            # But for TDD, this failure is expected.
            self.fail("sanitize_command not implemented in remote_agent")

        cases = [
            ("echo hello world", "echo hello world"),
            ("login --password=secret123", "login --password=[REDACTED]"),
            ("login --password secret123", "login --password [REDACTED]"),
            ("export TOKEN=abcdef", "export TOKEN=[REDACTED]"),
            ("my-app --api_key 12345 --verbose", "my-app --api_key [REDACTED] --verbose"),
            # Note: The simple regex consumes the trailing quote if present as part of the value.
            # This is acceptable for logging purposes as the secret is redacted.
            ("echo 'password: secret'", "echo 'password: [REDACTED]"),
            # Ensure pipes stop redaction if used as delimiter (though regex excludes |)
            ("echo password=secret| grep foo", "echo password=[REDACTED]| grep foo"),
            # Semicolon
            ("export PWD=secret; ls", "export PWD=[REDACTED]; ls"),
        ]

        for original, expected in cases:
            sanitized = sanitize_command(original)
            self.assertEqual(sanitized, expected, f"Failed sanitization for: {original}")

    @patch("remote_agent.is_path_safe")
    @patch("remote_agent.log")
    def test_api_command_logs_sanitized(self, mock_log, mock_is_safe):
        """Test that api_command logs the sanitized command."""
        mock_is_safe.return_value = True

        import remote_agent
        from fastapi import Request
        import asyncio

        # We need to mock request.json()
        async def mock_json():
            return {"cmd": "login --password=secret"}

        mock_req = MagicMock()
        mock_req.headers.get.return_value = "test_token"
        mock_req.json = mock_json

        # Run api_command
        # We need an event loop for async
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        # We also need to mock create_subprocess_shell to avoid actual execution
        with patch("asyncio.create_subprocess_shell") as mock_proc:
            mock_proc.return_value.communicate.return_value = (b"", b"")
            mock_proc.return_value.returncode = 0

            loop.run_until_complete(remote_agent.api_command(mock_req))

        loop.close()

        # Check log call
        # Expected log message: "Command: login --password=[REDACTED] (cwd=...)"
        args, _ = mock_log.call_args
        log_msg = args[0]

        self.assertIn("Command:", log_msg)
        self.assertIn("[REDACTED]", log_msg)
        self.assertNotIn("secret", log_msg)
