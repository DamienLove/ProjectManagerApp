
import os
import sys
import unittest
from unittest.mock import patch

# Add src to sys.path
sys.path.append(os.path.join(os.getcwd(), 'src'))

# Mock environment variables before importing remote_agent
with patch.dict(os.environ, {
    "LOCAL_WORKSPACE_ROOT": "/opt/projects",
    "REMOTE_ALLOWED_ROOTS": "",
}):
    import remote_agent

class TestSecurityFix(unittest.TestCase):
    def test_is_path_safe_secure_by_default(self):
        """
        Verifies that is_path_safe is SECURE by default (returns False for unknown paths).
        """
        # Mocking config constants
        remote_agent.LOCAL_WORKSPACE_ROOT = "/opt/projects"
        remote_agent.REMOTE_ALLOWED_ROOTS = []
        remote_agent.PROTECTED_PATHS = ["/bin", "/usr"]

        # Inside workspace -> Should be True
        self.assertTrue(remote_agent.is_path_safe("/opt/projects/myapp"))

        # Outside workspace, not whitelisted -> Should be False (FIXED)
        self.assertFalse(remote_agent.is_path_safe("/home/user/secret_file"))

        # Protected -> Should be False
        self.assertFalse(remote_agent.is_path_safe("/bin/sh"))

    def test_explicit_allowlist(self):
        """
        Verifies that we can still allow paths explicitly.
        """
        remote_agent.LOCAL_WORKSPACE_ROOT = "/opt/projects"
        remote_agent.REMOTE_ALLOWED_ROOTS = ["/var/www"]

        # Explicitly allowed -> Should be True
        self.assertTrue(remote_agent.is_path_safe("/var/www/html"))

        # Still denied
        self.assertFalse(remote_agent.is_path_safe("/home/user"))

if __name__ == '__main__':
    unittest.main()
