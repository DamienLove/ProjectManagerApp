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

class TestRemoteAgentSoftwareOpt(unittest.TestCase):
    def setUp(self):
        # Force reload
        if "remote_agent" in sys.modules:
            del sys.modules["remote_agent"]
        if "src.remote_agent" in sys.modules:
            del sys.modules["src.remote_agent"]

        self.env_patcher = patch.dict(os.environ, {
            "REMOTE_ACCESS_TOKEN": "test",
            "LOCAL_WORKSPACE_ROOT": "/tmp/ws"
        })
        self.env_patcher.start()

        import remote_agent
        self.remote_agent = remote_agent

    def tearDown(self):
        self.env_patcher.stop()

    @patch("subprocess.run")
    @patch("builtins.open", new_callable=mock_open, read_data='{"software": ["App.One", "App.Two", "App.Three"]}')
    @patch("json.load")
    @patch("os.path.exists")
    def test_check_install_software_optimized(self, mock_exists, mock_json_load, mock_file, mock_run):
        """
        Verifies that check_install_software calls 'winget list' ONLY ONCE.
        """
        mock_exists.return_value = True
        mock_json_load.return_value = {"software": ["App.One", "App.Two", "App.Three"]}

        # Mock winget list output
        # Output format based on winget: Name <spaces> Id <spaces> Version
        # We simulate App.One and App.Three are installed. App.Two is missing.
        # Note: The parser looks for 2+ spaces separator.
        mock_run.return_value.stdout = """
Name      Id       Version
--------------------------
App One   App.One  1.0.0
App Three   App.Three   1.0.0
"""

        self.remote_agent.check_install_software("/tmp/ws/proj")

        # Verify calls
        list_calls = 0
        install_calls = 0

        for call in mock_run.call_args_list:
            args, _ = call
            cmd = args[0]
            if "winget" in cmd and "list" in cmd:
                list_calls += 1
                # Verify it is just "winget list"
                self.assertEqual(cmd, ["winget", "list"])
            if "winget" in cmd and "install" in cmd:
                install_calls += 1
                # Verify we are installing the missing one
                self.assertIn("App.Two", cmd)

        print(f"\nDEBUG: Winget list calls: {list_calls}")
        self.assertEqual(list_calls, 1, "Should optimize to 1 winget list call")
        self.assertEqual(install_calls, 1, "Should attempt to install missing App.Two")

if __name__ == '__main__':
    unittest.main()
