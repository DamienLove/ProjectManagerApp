import sys
import os
import unittest
import shutil
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

class MockHTTPException(Exception):
    def __init__(self, status_code, detail):
        self.status_code = status_code
        self.detail = detail

mock_fastapi = MagicMock()
mock_fastapi.HTTPException = MockHTTPException
sys.modules["fastapi"] = mock_fastapi
sys.modules["fastapi.responses"] = MagicMock()

class TestRemoteAgentPathTraversal(unittest.TestCase):
    def setUp(self):
        if "remote_agent" in sys.modules:
            del sys.modules["remote_agent"]
        if "src.remote_agent" in sys.modules:
            del sys.modules["src.remote_agent"]

        self.env_patcher = patch.dict(os.environ, {
            "REMOTE_ACCESS_TOKEN": "test_token",
            "LOCAL_WORKSPACE_ROOT": "/tmp/workspace",
            "REMOTE_ALLOWED_ROOTS": ""
        })
        self.env_patcher.start()

        import remote_agent
        self.remote_agent = remote_agent

    def tearDown(self):
        self.env_patcher.stop()

    @patch("remote_agent.is_path_safe")
    @patch("remote_agent.log")
    @patch("shutil.copy2")
    @patch("shutil.move")
    @patch("os.remove")
    @patch("os.path.exists")
    @patch("os.path.isdir")
    @patch("json.load")
    @patch("builtins.open", new_callable=mock_open)
    def test_backup_external_resources_path_traversal(self, mock_file, mock_json_load, mock_isdir, mock_exists, mock_remove, mock_move, mock_copy2, mock_log, mock_is_safe):
        """Test that backup_external_resources prevents accessing unsafe external paths."""

        # Setup: Manifest points to a sensitive system file
        unsafe_path = "/etc/passwd"
        mock_json_load.return_value = {"external_paths": [unsafe_path]}

        # Mock is_path_safe to return False for the unsafe path
        mock_is_safe.side_effect = lambda p: p != unsafe_path

        # Mock FS
        def side_effect_exists(path):
            if path == unsafe_path:
                return True
            if path.endswith("omni.json"):
                return True
            return False

        mock_exists.side_effect = side_effect_exists
        mock_isdir.return_value = False  # treat as file

        # Call function
        project_path = "/tmp/workspace/project1"
        self.remote_agent.backup_external_resources(project_path)

        # Verification
        # We check if copy2 was called with the unsafe path as source
        was_called = False
        for call in mock_copy2.call_args_list:
            args, _ = call
            if args[0] == unsafe_path:
                was_called = True
                break

        if was_called:
             self.fail(f"VULNERABILITY: Backup attempted on unsafe path: {unsafe_path}")

        # Verify is_path_safe was actually called
        mock_is_safe.assert_called_with(unsafe_path)

    @patch("remote_agent.is_path_safe")
    @patch("remote_agent.log")
    @patch("shutil.move")
    @patch("os.path.exists")
    @patch("json.load")
    @patch("builtins.open", new_callable=mock_open)
    def test_restore_external_resources_path_traversal(self, mock_file, mock_json_load, mock_exists, mock_move, mock_log, mock_is_safe):
        """Test that restore_external_resources prevents restoring to unsafe paths."""

        unsafe_target = "/etc/passwd"
        mock_json_load.return_value = {"somehash": unsafe_target}

        # Mock is_path_safe to return False for the unsafe path
        mock_is_safe.side_effect = lambda p: p != unsafe_target

        mock_exists.return_value = True # restore_map exists, stored file exists

        project_path = "/tmp/workspace/project1"
        self.remote_agent.restore_external_resources(project_path)

        # Verify move
        was_called = False
        for call in mock_move.call_args_list:
            args, _ = call
            # args[1] is destination
            if args[1] == unsafe_target:
                was_called = True
                break

        if was_called:
            self.fail(f"VULNERABILITY: Restore attempted to unsafe path: {unsafe_target}")

        # Verify is_path_safe was actually called
        mock_is_safe.assert_called_with(unsafe_target)

if __name__ == '__main__':
    unittest.main()
