import sys
import os
import unittest
import json
import tempfile
import shutil
from unittest.mock import MagicMock, patch, ANY

# Add src to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

# Mock dependencies strictly before import
sys.modules["firebase_admin"] = MagicMock()
sys.modules["firebase_admin.credentials"] = MagicMock()
sys.modules["firebase_admin.firestore"] = MagicMock()
sys.modules["starlette.concurrency"] = MagicMock()
sys.modules["dotenv"] = MagicMock()
sys.modules["uvicorn"] = MagicMock()
sys.modules["websockets"] = MagicMock()

# Mock fastapi
mock_fastapi = MagicMock()
sys.modules["fastapi"] = mock_fastapi
sys.modules["fastapi.responses"] = MagicMock()

# Define Mock exceptions
class MockHTTPException(Exception):
    def __init__(self, status_code, detail):
        self.status_code = status_code
        self.detail = detail

mock_fastapi.HTTPException = MockHTTPException
mock_fastapi.Request = MagicMock
mock_fastapi.WebSocket = MagicMock
mock_fastapi.WebSocketDisconnect = Exception
mock_fastapi.FastAPI = MagicMock

# Now import remote_agent
import remote_agent

class TestSoftwareOptimization(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.project_path = os.path.join(self.test_dir, "MyProject")
        os.makedirs(self.project_path)
        self.manifest_path = os.path.join(self.project_path, "omni.json")

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def test_parse_winget_list_output(self):
        """Test parsing of winget list output."""
        output = """
Name                  Id                  Version
-------------------------------------------------
Visual Studio Code    Microsoft.VSCode    1.90.0
Git                   Git.Git             2.45.0
        """
        parsed = remote_agent.parse_winget_list_output(output)
        self.assertEqual(len(parsed), 2)
        self.assertIn(("Visual Studio Code", "Microsoft.VSCode"), parsed)
        self.assertIn(("Git", "Git.Git"), parsed)

    @patch("subprocess.run")
    def test_check_install_software_missing(self, mock_run):
        """Test that missing software triggers installation."""
        # Setup manifest
        with open(self.manifest_path, "w") as f:
            json.dump({"software": ["Node.js"]}, f)

        # Mock winget list output
        mock_list_output = MagicMock()
        mock_list_output.stdout = """
Name                  Id                  Version
-------------------------------------------------
Git                   Git.Git             2.45.0
"""
        mock_run.return_value = mock_list_output

        remote_agent.check_install_software(self.project_path)

        # Check if list was called
        mock_run.assert_any_call(
            ["winget", "list"],
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='ignore',
            creationflags=ANY
        )

        # Check if install was called
        install_calls = [
            call for call in mock_run.call_args_list
            if call.args and len(call.args) > 0 and isinstance(call.args[0], list) and "install" in call.args[0]
        ]
        self.assertEqual(len(install_calls), 1)
        # call.args[0] is the command list
        self.assertIn("Node.js", install_calls[0].args[0])

    @patch("subprocess.run")
    def test_check_install_software_present(self, mock_run):
        """Test that present software skips installation."""
        # Setup manifest
        with open(self.manifest_path, "w") as f:
            json.dump({"software": ["Git.Git"]}, f)

        # Mock winget list output containing Git.Git
        mock_list_output = MagicMock()
        mock_list_output.stdout = """
Name                  Id                  Version
-------------------------------------------------
Git                   Git.Git             2.45.0
"""
        mock_run.return_value = mock_list_output

        remote_agent.check_install_software(self.project_path)

        # Check if install was NOT called
        install_calls = [
            call for call in mock_run.call_args_list
            if call.args and len(call.args) > 0 and isinstance(call.args[0], list) and "install" in call.args[0]
        ]
        self.assertEqual(len(install_calls), 0)

if __name__ == '__main__':
    unittest.main()
