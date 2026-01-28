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

import remote_agent

class TestSoftwareOptimization(unittest.TestCase):
    @patch("subprocess.run")
    @patch("builtins.open", new_callable=mock_open, read_data='{"software": ["App.1", "App.2"]}')
    @patch("json.load")
    @patch("os.path.exists")
    def test_check_install_software_optimization(self, mock_exists, mock_json_load, mock_file, mock_run):
        """Test that check_install_software batches the check."""

        # Setup mocks
        mock_exists.return_value = True
        mock_json_load.return_value = {"software": ["App.1", "App.2"]}

        # Mock winget list output
        # App.1 is installed, App.2 is NOT.
        winget_output = """Name                               Id                           Version
-----------------------------------------------------------------------
Application One                    App.1                        1.0.0
Some Other App                     Other.App                    2.0.0
"""

        def side_effect(cmd, **kwargs):
            # Check for the optimized "list all" command
            if cmd == ["winget", "list"]:
                return MagicMock(stdout=winget_output, returncode=0)

            # Check for the old "list specific" command (to prevent crash if called)
            if "list" in cmd and "--id" in cmd:
                 # Logic for old behavior: check if ID is in our fake installed list
                 if "App.1" in cmd:
                      return MagicMock(stdout="App.1", returncode=0) # Found
                 else:
                      return MagicMock(stdout="No installed package found", returncode=0) # Not found

            # Check for install command
            if "install" in cmd:
                 return MagicMock(stdout="", returncode=0)

            return MagicMock(stdout="", returncode=0)

        mock_run.side_effect = side_effect

        # Call the function
        remote_agent.check_install_software("/tmp/project")

        # Verify calls

        # Filter calls
        # We look for the exact optimized call: ["winget", "list"]
        list_calls = [c for c in mock_run.call_args_list if c[0][0] == ["winget", "list"]]
        install_calls = [c for c in mock_run.call_args_list if "install" in c[0][0]]

        # Expect exactly 1 call to `winget list`
        self.assertEqual(len(list_calls), 1, f"Expected 1 batch 'winget list' call, got {len(list_calls)}")

        # Verify installs
        # App.1 should NOT be installed
        for call in install_calls:
            cmd = call[0][0]
            if "App.1" in cmd:
                self.fail("Should not install App.1 as it is already installed")

        # App.2 SHOULD be installed
        installed_app2 = False
        for call in install_calls:
            cmd = call[0][0]
            if "App.2" in cmd:
                installed_app2 = True
        self.assertTrue(installed_app2, "Should install App.2")

if __name__ == '__main__':
    unittest.main()
