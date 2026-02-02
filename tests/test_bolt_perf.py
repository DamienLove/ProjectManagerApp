import sys
import unittest
from unittest.mock import MagicMock, patch

# Mock UI libs
sys.modules["customtkinter"] = MagicMock()
sys.modules["pystray"] = MagicMock()
sys.modules["PIL"] = MagicMock()
sys.modules["PIL.Image"] = MagicMock()

# Mock dependencies
sys.modules["firebase_admin"] = MagicMock()
sys.modules["firebase_admin.credentials"] = MagicMock()
sys.modules["firebase_admin.firestore"] = MagicMock()

# Mock fastapi for remote_agent
mock_fastapi = MagicMock()
class MockHTTPException(Exception):
    def __init__(self, status_code, detail):
        self.status_code = status_code
        self.detail = detail
mock_fastapi.HTTPException = MockHTTPException
sys.modules["fastapi"] = mock_fastapi
sys.modules["fastapi.responses"] = MagicMock()
sys.modules["uvicorn"] = MagicMock()
sys.modules["websockets"] = MagicMock()
sys.modules["starlette.concurrency"] = MagicMock()

import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

import remote_agent
import main

class TestBoltPerf(unittest.TestCase):
    def test_remote_agent_regex(self):
        """Verify remote_agent uses pre-compiled regex."""
        self.assertTrue(hasattr(remote_agent, "_WINGET_SPLIT_PATTERN"))
        import re
        self.assertIsInstance(remote_agent._WINGET_SPLIT_PATTERN, re.Pattern)

        output = """
Name                  Id                  Version
-------------------------------------------------
Visual Studio Code    Microsoft.VSCode    1.90.0
Git                   Git.Git             2.45.0
        """
        parsed = remote_agent.parse_winget_list_output(output)
        self.assertEqual(len(parsed), 2)
        self.assertIn(("Visual Studio Code", "Microsoft.VSCode"), parsed)

    def test_main_regex(self):
        """Verify main uses pre-compiled regex."""
        self.assertTrue(hasattr(main, "_WINGET_SPLIT_PATTERN"))
        import re
        self.assertIsInstance(main._WINGET_SPLIT_PATTERN, re.Pattern)

        output = """
Name                  Id                  Version
-------------------------------------------------
Visual Studio Code    Microsoft.VSCode    1.90.0
Git                   Git.Git             2.45.0
        """
        parsed = main.parse_winget_list_output(output)
        self.assertEqual(len(parsed), 2)
        self.assertIn(("Visual Studio Code", "Microsoft.VSCode"), parsed)

    @patch("os.path.getmtime")
    @patch("builtins.open", new_callable=unittest.mock.mock_open, read_data='{"project1": "Local"}')
    def test_load_registry_optimization(self, mock_file, mock_mtime):
        """Verify load_registry works without explicit exists check."""
        mock_mtime.return_value = 1000.0

        # Reset global cache
        remote_agent._registry_cache = None
        remote_agent._registry_mtime = 0.0

        reg = remote_agent.load_registry()
        self.assertEqual(reg, {"project1": "Local"})

        # Verify getmtime was called
        mock_mtime.assert_called_with(remote_agent.LOCAL_REGISTRY_PATH)

    def test_is_path_safe_denies_by_default(self):
        """Verify is_path_safe still works safely."""
        # Mock workspace root
        with patch("remote_agent.ABS_LOCAL_WORKSPACE_ROOT", "/safe/workspace"), \
             patch("remote_agent.ABS_REMOTE_ALLOWED_ROOTS", []), \
             patch("os.path.abspath", side_effect=lambda p: p):

            self.assertTrue(remote_agent.is_path_safe("/safe/workspace/project"))
            self.assertFalse(remote_agent.is_path_safe("/unsafe/path"))
            self.assertFalse(remote_agent.is_path_safe("/etc/passwd"))

if __name__ == '__main__':
    unittest.main()
