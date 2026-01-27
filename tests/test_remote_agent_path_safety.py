import sys
import os
import unittest
from unittest.mock import MagicMock, patch

# Add src to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

class TestRemoteAgentPathSafety(unittest.TestCase):

    def _reload_agent(self, env_vars, protected_paths=None):
        # Clean up sys.modules to force re-import
        if "remote_agent" in sys.modules:
            del sys.modules["remote_agent"]
        if "src.remote_agent" in sys.modules:
            del sys.modules["src.remote_agent"]

        # Mock dependencies safely using patch.dict
        # We need to mock all top-level imports of remote_agent
        mocks = {
            "firebase_admin": MagicMock(),
            "firebase_admin.credentials": MagicMock(),
            "firebase_admin.firestore": MagicMock(),
            "starlette.concurrency": MagicMock(),
            "dotenv": MagicMock(),
            "uvicorn": MagicMock(),
            "fastapi": MagicMock(),
            "fastapi.responses": MagicMock(),
        }
        # Ensure HTTPException is an Exception so it can be raised if needed (though not used in these tests)
        mocks["fastapi"].HTTPException = Exception

        with patch.dict(os.environ, env_vars), patch.dict(sys.modules, mocks):
            import remote_agent
            # Patch protected paths to be relevant for Linux test env
            if protected_paths:
                remote_agent.ABS_PROTECTED_PATHS = [os.path.abspath(p) for p in protected_paths]
            return remote_agent

    def test_is_path_safe_default_deny(self):
        """
        Verify that arbitrary paths are denied by default (Fix verification).
        """
        env = {
            "LOCAL_WORKSPACE_ROOT": "/tmp/workspace",
            "REMOTE_ALLOWED_ROOTS": "", # Empty
        }
        # Hardcode protected paths for test
        protected = ["/bin", "/usr"]

        agent = self._reload_agent(env, protected)

        # Workspace should be safe
        self.assertTrue(agent.is_path_safe("/tmp/workspace/project1"), "Workspace should be safe")

        # Protected should be unsafe
        self.assertFalse(agent.is_path_safe("/bin/ls"), "Protected path should be unsafe")

        # Arbitrary path (VULNERABILITY CHECK)
        self.assertFalse(agent.is_path_safe("/tmp/secret"), "Arbitrary path should be unsafe (Deny by Default)")

    def test_is_path_safe_with_allowlist(self):
        """Verify behavior when ALLOWED_ROOTS is set."""
        env = {
            "LOCAL_WORKSPACE_ROOT": "/tmp/workspace",
            "REMOTE_ALLOWED_ROOTS": "/tmp/allowed;/var/log",
        }
        protected = ["/bin"]
        agent = self._reload_agent(env, protected)

        # Allowed roots
        self.assertTrue(agent.is_path_safe("/tmp/allowed/file.txt"))
        self.assertTrue(agent.is_path_safe("/var/log/syslog"))

        # Workspace
        self.assertTrue(agent.is_path_safe("/tmp/workspace/p1"))

        # Arbitrary
        self.assertFalse(agent.is_path_safe("/tmp/other"))

if __name__ == '__main__':
    unittest.main()
