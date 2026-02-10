
import unittest
import os
import shutil
import tempfile
from unittest.mock import MagicMock, patch
import sys
import importlib
import types

# Create a mock module structure for fastapi
mock_fastapi = types.ModuleType("fastapi")
sys.modules["fastapi"] = mock_fastapi

# Create mock for fastapi.responses
mock_fastapi_responses = types.ModuleType("fastapi.responses")
sys.modules["fastapi.responses"] = mock_fastapi_responses
mock_fastapi_responses.JSONResponse = MagicMock()

# Mock Exceptions
class MockHTTPException(Exception):
    def __init__(self, status_code, detail):
        self.status_code = status_code
        self.detail = detail
mock_fastapi.HTTPException = MockHTTPException

# Mock other components
mock_fastapi.FastAPI = MagicMock()
mock_fastapi.Request = MagicMock()
mock_fastapi.WebSocket = MagicMock()
mock_fastapi.WebSocketDisconnect = MagicMock()

# Mock external dependencies
sys.modules['firebase_admin'] = MagicMock()
sys.modules['firebase_admin.credentials'] = MagicMock()
sys.modules['firebase_admin.firestore'] = MagicMock()
sys.modules['starlette'] = MagicMock()
sys.modules['starlette.concurrency'] = MagicMock()
sys.modules['dotenv'] = MagicMock()

# Ensure src is in path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

class TestLoggingSecurity(unittest.TestCase):
    def setUp(self):
        # Force fresh import of remote_agent
        if "remote_agent" in sys.modules:
            del sys.modules["remote_agent"]
        if "src.remote_agent" in sys.modules:
            del sys.modules["src.remote_agent"]

        import src.remote_agent as remote_agent
        self.remote_agent = remote_agent

        self.test_dir = tempfile.mkdtemp()
        self.log_path = os.path.join(self.test_dir, "test_agent.log")

        # Patch the LOG_PATH in the module
        self.original_log_path = self.remote_agent.LOG_PATH
        self.original_config_dir = self.remote_agent.CONFIG_DIR
        self.remote_agent.LOG_PATH = self.log_path
        self.remote_agent.CONFIG_DIR = self.test_dir

    def tearDown(self):
        self.remote_agent.LOG_PATH = self.original_log_path
        self.remote_agent.CONFIG_DIR = self.original_config_dir
        shutil.rmtree(self.test_dir)

    def test_log_redacts_sensitive_info(self):
        # Test 1: sanitize_command unit test
        sensitive_cmd = "login --password=SECRET_PASSWORD_123"
        sanitized = self.remote_agent.sanitize_command(sensitive_cmd)
        self.assertIn("***REDACTED***", sanitized)
        self.assertNotIn("SECRET_PASSWORD_123", sanitized)

    def test_integration_api_command(self):
        inputs = [
            ("login --password=SECRET", "login --password=***REDACTED***"),
            ("export TOKEN='MyToken'", "export TOKEN=***REDACTED***"),
            ("echo key: secretvalue", "echo key=***REDACTED***"),
        ]

        for inp, expected_part in inputs:
            out = self.remote_agent.sanitize_command(inp)
            self.assertIn("***REDACTED***", out)
            # Verify the secret is gone
            secret = inp.split("=")[-1] if "=" in inp else inp.split(":")[-1].strip()
            secret = secret.strip("'").strip('"')
            if secret in inp:
                self.assertNotIn(secret, out, f"Failed to redact {secret} in {inp}")

    def test_no_false_positives(self):
        safe_cmd = "git commit -m 'added feature'"
        out = self.remote_agent.sanitize_command(safe_cmd)
        self.assertEqual(out, safe_cmd)

if __name__ == "__main__":
    unittest.main()
