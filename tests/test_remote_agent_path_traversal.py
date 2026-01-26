import sys
import os
import unittest
import json
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

class TestRemoteAgentPathTraversal(unittest.TestCase):
    def setUp(self):
        # Force reload to apply fresh mocks
        if "src.remote_agent" in sys.modules:
            del sys.modules["src.remote_agent"]
        if "remote_agent" in sys.modules:
            del sys.modules["remote_agent"]

        self.env_patcher = patch.dict(os.environ, {
            "REMOTE_ACCESS_TOKEN": "test",
            "LOCAL_WORKSPACE_ROOT": "/tmp/workspace"
        })
        self.env_patcher.start()

        import remote_agent
        self.remote_agent = remote_agent

        # Mock ABS_PROTECTED_PATHS for testing regardless of OS
        self.remote_agent.ABS_PROTECTED_PATHS = [os.path.abspath("/protected")]
        self.remote_agent.ABS_LOCAL_WORKSPACE_ROOT = os.path.abspath("/tmp/workspace")
        self.remote_agent.ABS_REMOTE_ALLOWED_ROOTS = []

    def tearDown(self):
        self.env_patcher.stop()

    @patch("shutil.move")
    @patch("os.makedirs")
    @patch("os.path.exists")
    @patch("builtins.open", new_callable=mock_open)
    @patch("json.load")
    def test_restore_external_resources_path_traversal(self, mock_json_load, mock_file, mock_exists, mock_makedirs, mock_move):
        """Test that restore_external_resources prevents writing to protected paths."""

        # Setup: restore_map points to a protected path
        unsafe_path = os.path.abspath("/protected/system32/malware.exe")
        mock_json_load.return_value = {
            "hash123": unsafe_path
        }

        # Mock existence checks
        # 1. map_file exists
        # 2. stored_path exists
        mock_exists.side_effect = [True, True]

        # Call function
        self.remote_agent.restore_external_resources("/tmp/workspace/project1")

        # Assert: shutil.move should NOT be called for the unsafe path
        # If it IS called, we have a vulnerability.
        for call in mock_move.call_args_list:
            args, _ = call
            dest = args[1]
            if dest == unsafe_path:
                self.fail(f"VULNERABILITY: restore_external_resources attempted to write to protected path: {dest}")

    @patch("shutil.move")
    @patch("shutil.copy2")
    @patch("os.remove")
    @patch("os.makedirs")
    @patch("os.path.exists")
    @patch("builtins.open", new_callable=mock_open)
    @patch("json.load")
    def test_backup_external_resources_path_traversal(self, mock_json_load, mock_file, mock_exists, mock_makedirs, mock_remove, mock_copy2, mock_move):
        """Test that backup_external_resources prevents deleting protected paths."""

        # Setup: omni.json points to a protected path
        unsafe_path = os.path.abspath("/protected/important_file.txt")
        mock_json_load.return_value = {
            "external_paths": [unsafe_path]
        }

        # Mock existence: file exists
        mock_exists.return_value = True

        # Call function
        self.remote_agent.backup_external_resources("/tmp/workspace/project1")

        # Assert: os.remove should NOT be called for the unsafe path
        for call in mock_remove.call_args_list:
            args, _ = call
            target = args[0]
            if target == unsafe_path:
                self.fail(f"VULNERABILITY: backup_external_resources attempted to delete protected file: {target}")

if __name__ == '__main__':
    unittest.main()
