import sys
import os
import unittest
from unittest.mock import MagicMock, patch, mock_open

# Add src to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

# Mock dependencies to prevent import errors and side effects
sys.modules["firebase_admin"] = MagicMock()
sys.modules["firebase_admin.credentials"] = MagicMock()
sys.modules["firebase_admin.firestore"] = MagicMock()
sys.modules["starlette.concurrency"] = MagicMock()
sys.modules["dotenv"] = MagicMock()
sys.modules["uvicorn"] = MagicMock()
sys.modules["fastapi"] = MagicMock()
sys.modules["fastapi.responses"] = MagicMock()

class TestWingetInjection(unittest.TestCase):
    def setUp(self):
        # Force reload of remote_agent to apply fresh mocks
        if "remote_agent" in sys.modules:
            del sys.modules["remote_agent"]
        if "src.remote_agent" in sys.modules:
            del sys.modules["src.remote_agent"]

        self.env_patcher = patch.dict(os.environ, {
            "REMOTE_ACCESS_TOKEN": "test_token",
            "LOCAL_WORKSPACE_ROOT": "/tmp/workspace"
        })
        self.env_patcher.start()

        import remote_agent
        self.remote_agent = remote_agent

    def tearDown(self):
        self.env_patcher.stop()

    @patch("subprocess.run")
    @patch("builtins.open", new_callable=mock_open, read_data='{"software": ["-malicious_arg"]}')
    @patch("json.load")
    @patch("os.path.exists")
    def test_check_install_software_prevents_injection(self, mock_exists, mock_json_load, mock_file, mock_run):
        """Test that check_install_software prevents argument injection by skipping IDs starting with -"""
        mock_exists.return_value = True
        mock_json_load.return_value = {"software": ["-malicious_arg"]}

        self.remote_agent.check_install_software("/tmp/workspace/project1")

        # We expect validation to prevent any subprocess call with this ID
        mock_run.assert_not_called()

if __name__ == '__main__':
    unittest.main()
