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

# Mock fastapi
mock_fastapi = MagicMock()
sys.modules["fastapi"] = mock_fastapi
sys.modules["fastapi.responses"] = MagicMock()

# Define Mock exceptions and classes
class MockHTTPException(Exception):
    def __init__(self, status_code, detail):
        self.status_code = status_code
        self.detail = detail

mock_fastapi.HTTPException = MockHTTPException
mock_fastapi.Request = MagicMock
mock_fastapi.WebSocket = MagicMock
mock_fastapi.WebSocketDisconnect = Exception
mock_fastapi.FastAPI = MagicMock

import remote_agent

class TestSoftwareOptimization(unittest.TestCase):
    def setUp(self):
        self.test_dir = "C:\\Projects\\TestProject"

    @patch("subprocess.run")
    @patch("builtins.open", new_callable=mock_open, read_data='{"software": ["App.A", "App.B", "App.C"]}')
    @patch("json.load")
    @patch("os.path.exists", return_value=True)
    def test_check_install_software_calls(self, mock_exists, mock_json_load, mock_file, mock_subprocess):
        # Setup mock json data
        mock_json_load.return_value = {"software": ["App.A", "App.B", "App.C"]}

        # Setup subprocess mock behavior
        def side_effect(args, **kwargs):
            cmd = args
            # Simulate "winget list" (batch check)
            if cmd[0] == "winget" and cmd[1] == "list" and len(cmd) == 2:
                # Returns App.A and App.B, but not App.C
                return MagicMock(returncode=0, stdout="""
Name      Id      Version
-------------------------
App A     App.A   1.0
App B     App.B   2.0
""")
            # Simulate "winget install ..."
            if cmd[0] == "winget" and cmd[1] == "install":
                 return MagicMock(returncode=0)

            return MagicMock(returncode=0)

        mock_subprocess.side_effect = side_effect

        # Run the function
        remote_agent.check_install_software(self.test_dir)

        # Assertions
        # Current behavior: 3 list calls + 1 install call = 4 calls
        # Optimization goal: 1 list call + 1 install call = 2 calls

        # Count list calls
        list_calls = 0
        install_calls = 0
        for call in mock_subprocess.call_args_list:
            args = call[0][0]
            if args[1] == "list":
                list_calls += 1
            if args[1] == "install":
                install_calls += 1

        print(f"List calls: {list_calls}, Install calls: {install_calls}")

        # We expect 1 list call (batch) + 1 install call (for App.C)
        self.assertEqual(list_calls, 1, "Expected 1 winget list call in optimized code")
        self.assertEqual(install_calls, 1, "Expected 1 install call for missing App.C")

if __name__ == '__main__':
    unittest.main()
