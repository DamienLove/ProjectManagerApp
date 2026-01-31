import sys
import os
import unittest
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

class TestIsPathSafeStrict(unittest.TestCase):
    def setUp(self):
        if "remote_agent" in sys.modules:
            del sys.modules["remote_agent"]
        if "src.remote_agent" in sys.modules:
            del sys.modules["src.remote_agent"]

        # Default environment: No allowed roots, standard workspace
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

    def test_path_safety_behavior(self):
        # 1. Inside workspace -> SHOULD BE TRUE
        self.assertTrue(self.remote_agent.is_path_safe("/tmp/workspace/project1"))

        # 2. Outside workspace (e.g. system file) -> SHOULD BE FALSE
        # FIXED BEHAVIOR: Returns False (Deny by Default)
        self.assertFalse(self.remote_agent.is_path_safe("/etc/passwd"), "Vulnerability fixed: /etc/passwd is blocked!")

        # 3. Another arbitrary path -> SHOULD BE FALSE
        self.assertFalse(self.remote_agent.is_path_safe("/var/log/syslog"))

if __name__ == '__main__':
    unittest.main()
