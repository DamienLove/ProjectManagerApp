import sys
import os
import unittest
from unittest.mock import MagicMock, patch, mock_open

# Add src to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

# Mock dependencies
sys.modules["firebase_admin"] = MagicMock()
sys.modules["firebase_admin.credentials"] = MagicMock()
sys.modules["firebase_admin.firestore"] = MagicMock()
sys.modules["starlette.concurrency"] = MagicMock()
sys.modules["dotenv"] = MagicMock()
sys.modules["uvicorn"] = MagicMock()
sys.modules["fastapi"] = MagicMock()
sys.modules["fastapi.responses"] = MagicMock()

class TestLoggingRedaction(unittest.TestCase):
    def setUp(self):
        if "src.remote_agent" in sys.modules:
            del sys.modules["src.remote_agent"]
        if "remote_agent" in sys.modules:
            del sys.modules["remote_agent"]

        self.env_patcher = patch.dict(os.environ, {
            "REMOTE_ACCESS_TOKEN": "test_token",
            "LOCAL_WORKSPACE_ROOT": "/tmp/workspace"
        })
        self.env_patcher.start()

        import remote_agent
        self.remote_agent = remote_agent

    def tearDown(self):
        self.env_patcher.stop()

    def test_redaction_logic(self):
        """Verify that sanitize_command redacts sensitive info."""
        if not hasattr(self.remote_agent, "sanitize_command"):
            self.fail("sanitize_command not found")

        sanitize = self.remote_agent.sanitize_command

        cases = [
            ("echo hello", "echo hello"),
            ("export PASSWORD=secret123", "export PASSWORD=REDACTED"),
            ("login --token abcdef", "login --token REDACTED"),
            ("set API_KEY=12345", "set API_KEY=REDACTED"),
            ("echo 'my secret is safe'", "echo 'my secret is safe'"), # 'secret' alone should NOT be redacted now
            ("export CLIENT_SECRET=xyz", "export CLIENT_SECRET=REDACTED"),
            ("cat /etc/passwd | grep foo", "cat /etc/passwd | grep foo"), # Should NOT redact passwd here
            ("useradd --password mypass", "useradd --password REDACTED"),
            ('export PASSWORD="my secret phrase"', 'export PASSWORD=REDACTED'),
        ]

        for input_cmd, expected in cases:
            self.assertEqual(sanitize(input_cmd), expected)

if __name__ == '__main__':
    unittest.main()
