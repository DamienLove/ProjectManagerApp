import unittest
from unittest.mock import MagicMock, patch
import sys
import os
import secrets
from fastapi import Request, WebSocket, HTTPException

# Adjust path so we can import src.remote_agent
sys.path.append(os.path.abspath("src"))

# Mock global side effects if any.
# We patch os.getenv before import to control globals, but reload might be needed.
# Instead, we will patch 'src.remote_agent.REMOTE_ACCESS_TOKEN' in setUp.

import src.remote_agent as remote_agent

class TestRemoteAgentSecurity(unittest.TestCase):

    def setUp(self):
        self.valid_token = "secret_token_123"
        remote_agent.REMOTE_ACCESS_TOKEN = self.valid_token

        # Mock secrets.compare_digest
        self.compare_digest_mock = MagicMock(wraps=secrets.compare_digest)
        # We'll patch secrets.compare_digest in the module where it is used.
        # However, since remote_agent imports secrets, we should check if it uses it.
        # Currently it doesn't use compare_digest, so we can't patch it in remote_agent context effectively
        # unless we patch 'secrets.compare_digest' globally or where it's imported.
        # But wait, remote_agent imports `secrets`. So `src.remote_agent.secrets.compare_digest` is what we'd want to patch
        # IF we want to spy on it. But right now it's NOT used.

        # To verify it IS NOT used (vulnerability check), we can't easily spy on "direct string comparison".
        # But we can verify it IS used (fix check) later.
        pass

    def test_require_token_from_request_success(self):
        request = MagicMock(spec=Request)
        request.headers = {"X-Omni-Token": self.valid_token}

        # Should not raise
        remote_agent.require_token_from_request(request)

    def test_require_token_from_request_failure(self):
        request = MagicMock(spec=Request)
        request.headers = {"X-Omni-Token": "wrong_token"}

        with self.assertRaises(HTTPException) as cm:
            remote_agent.require_token_from_request(request)
        self.assertEqual(cm.exception.status_code, 401)

    def test_require_token_from_request_bearer_success(self):
        request = MagicMock(spec=Request)
        request.headers = {"Authorization": f"Bearer {self.valid_token}"}

        # Should not raise
        remote_agent.require_token_from_request(request)

    def test_require_token_from_ws_success(self):
        ws = MagicMock(spec=WebSocket)
        ws.headers = {"X-Omni-Token": self.valid_token}
        ws.query_params = {}

        # Should not raise
        remote_agent.require_token_from_ws(ws)

    def test_require_token_from_ws_query_success(self):
        ws = MagicMock(spec=WebSocket)
        ws.headers = {}
        ws.query_params = {"token": self.valid_token}

        # Should not raise
        remote_agent.require_token_from_ws(ws)

    @patch('src.remote_agent.secrets.compare_digest')
    def test_vulnerability_fix_verification(self, mock_compare):
        """
        This test expects secrets.compare_digest to be called.
        It will fail on the current code (demonstrating vulnerability/lack of security best practice),
        and pass after the fix.
        """
        mock_compare.return_value = True

        request = MagicMock(spec=Request)
        request.headers = {"X-Omni-Token": self.valid_token}

        remote_agent.require_token_from_request(request)

        if not mock_compare.called:
            print("\n[VULNERABILITY CONFIRMED] secrets.compare_digest was NOT called.")
            self.fail("secrets.compare_digest was not used for token comparison")
        else:
            mock_compare.assert_called()

if __name__ == '__main__':
    unittest.main()
