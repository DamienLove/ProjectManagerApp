import sys
import os
import unittest
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

class TestRegistryOptimization(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.original_workspace = remote_agent.LOCAL_WORKSPACE_ROOT
        remote_agent.LOCAL_WORKSPACE_ROOT = self.test_dir

        # Create some dummy folders and files
        os.makedirs(os.path.join(self.test_dir, "project1"))
        os.makedirs(os.path.join(self.test_dir, "project2"))
        with open(os.path.join(self.test_dir, "file1.txt"), "w") as f:
            f.write("content")

    def tearDown(self):
        shutil.rmtree(self.test_dir)
        remote_agent.LOCAL_WORKSPACE_ROOT = self.original_workspace

    def test_compute_registry_scandir(self):
        """Test that compute_registry correctly identifies folders using scandir optimization."""
        # Mock load_registry to return empty
        with patch('remote_agent.load_registry', return_value={}):
             with patch('remote_agent.save_registry') as mock_save:
                registry = remote_agent.compute_registry()

                self.assertIn("project1", registry)
                self.assertIn("project2", registry)
                self.assertNotIn("file1.txt", registry)
                self.assertEqual(registry["project1"], "Local")
                self.assertEqual(registry["project2"], "Local")

if __name__ == '__main__':
    unittest.main()
