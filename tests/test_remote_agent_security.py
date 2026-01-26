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

# We need to ensure we can import remote_agent
# The mock setup above should handle external deps.

class TestRemoteAgentSecurity(unittest.TestCase):
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
    @patch("builtins.open", new_callable=mock_open, read_data='{"software": ["bad_app & hack"]}')
    @patch("json.load")
    @patch("os.path.exists")
    def test_check_install_software_no_shell(self, mock_exists, mock_json_load, mock_file, mock_run):
        """Test that check_install_software does NOT use shell=True for winget install."""

        # Setup mocks
        mock_exists.return_value = True
        mock_json_load.return_value = {"software": ["bad_app & hack"]}

        # Mock the "winget list" response to say package is missing, triggering install
        mock_run.return_value.stdout = "No installed package found"

        # Call the function
        self.remote_agent.check_install_software("/tmp/workspace/project1")

        # Verify subprocess.run calls
        # We expect two calls.
        # 1. winget list
        # 2. winget install

        # Check all calls
        for call in mock_run.call_args_list:
            args, kwargs = call
            # args[0] is the command list
            cmd_list = args[0]
            self.assertIsInstance(cmd_list, list)

            # CRITICAL CHECK: shell must NOT be True
            if kwargs.get("shell") is True:
                # If shell=True, verify it is NOT the install command
                # But our goal is to enforce NO shell=True for winget
                if "install" in cmd_list:
                    self.fail(f"VULNERABILITY: shell=True detected in subprocess call: {cmd_list}")

    @patch("subprocess.Popen")
    @patch("remote_agent.find_android_studio")
    @patch("remote_agent.is_path_safe")
    @patch("os.path.exists")
    def test_open_studio_project_no_shell(self, mock_exists, mock_is_safe, mock_find_studio, mock_popen):
        """Test that open_studio_project does NOT use shell=True."""

        # Setup mocks
        mock_exists.return_value = True
        mock_is_safe.return_value = True
        mock_find_studio.return_value = "/path/to/studio64.exe"

        # Call the function
        self.remote_agent.open_studio_project("test_project")

        # Verify Popen call
        self.assertTrue(mock_popen.called)
        args, kwargs = mock_popen.call_args

        # CRITICAL CHECK: shell must NOT be True
        if kwargs.get("shell") is True:
            self.fail("VULNERABILITY: shell=True detected in open_studio_project Popen call")

if __name__ == '__main__':
    unittest.main()
