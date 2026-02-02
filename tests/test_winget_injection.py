import sys
import os
import unittest
import json
import tempfile
import shutil
from unittest.mock import MagicMock, patch

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

class TestWingetInjection(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.project_path = os.path.join(self.test_dir, "project1")
        os.makedirs(self.project_path)
        self.manifest_path = os.path.join(self.project_path, "omni.json")

        self.env_patcher = patch.dict(os.environ, {
            "REMOTE_ACCESS_TOKEN": "test_token",
            "LOCAL_WORKSPACE_ROOT": self.test_dir
        })
        self.env_patcher.start()

    def tearDown(self):
        self.env_patcher.stop()
        shutil.rmtree(self.test_dir)

    @patch("subprocess.run")
    @patch("os.path.exists")
    def test_check_install_software_prevents_injection(self, mock_exists, mock_run):
        """Test that check_install_software prevents argument injection by skipping IDs starting with -"""
        # Setup manifest
        with open(self.manifest_path, "w") as f:
            json.dump({"software": ["-malicious_arg"]}, f)

        mock_exists.side_effect = lambda p: p == self.manifest_path or p == self.project_path

        # Mock winget list output (empty)
        mock_run.return_value = MagicMock(stdout="No installed package found")

        remote_agent.check_install_software(self.project_path)

        # We expect validation to prevent any subprocess call with install for this ID
        install_calls = [
            call for call in mock_run.call_args_list
            if call.args and len(call.args) > 0 and isinstance(call.args[0], list) and "install" in call.args[0]
        ]
        self.assertEqual(len(install_calls), 0)

if __name__ == '__main__':
    unittest.main()