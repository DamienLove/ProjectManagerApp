
import unittest
from unittest.mock import MagicMock, patch
from fastapi import HTTPException, Request, WebSocket
import secrets
import sys
import os

# Add src to sys.path to allow importing remote_agent
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

# Mock modules that might cause issues during import if dependencies are missing or environment is not set up
sys.modules['firebase_admin'] = MagicMock()
sys.modules['firebase_admin.credentials'] = MagicMock()
sys.modules['firebase_admin.firestore'] = MagicMock()

import remote_agent

class TestRemoteAgentSecurity(unittest.TestCase):
    def setUp(self):
        remote_agent.REMOTE_ACCESS_TOKEN = "secret_token"

    @patch('secrets.compare_digest')
    def test_require_token_from_request_usage(self, mock_compare):
        # Setup mock request
        request = MagicMock(spec=Request)
        request.headers = {"X-Omni-Token": "secret_token"}

        # Configure mock to behave like real compare_digest (return True for match)
        mock_compare.return_value = True

        # Call function
        remote_agent.require_token_from_request(request)

        # Verify compare_digest was called
        # If the code uses `!=` or `==`, this mock won't be called, and this assertion will fail.
        mock_compare.assert_called_with("secret_token", "secret_token")

    @patch('secrets.compare_digest')
    def test_require_token_from_ws_usage(self, mock_compare):
        # Setup mock websocket
        ws = MagicMock(spec=WebSocket)
        ws.headers = {"X-Omni-Token": "secret_token"}
        ws.query_params = {}

        # Configure mock
        mock_compare.return_value = True

        # Call function
        remote_agent.require_token_from_ws(ws)

        # Verify compare_digest was called
        mock_compare.assert_called_with("secret_token", "secret_token")

    def test_require_token_from_request_invalid(self):
        request = MagicMock(spec=Request)
        request.headers = {"X-Omni-Token": "wrong_token"}

        with self.assertRaises(HTTPException) as cm:
            remote_agent.require_token_from_request(request)
        self.assertEqual(cm.exception.status_code, 401)

    def test_require_token_from_ws_invalid(self):
        ws = MagicMock(spec=WebSocket)
        ws.headers = {"X-Omni-Token": "wrong_token"}
        ws.query_params = {}

        with self.assertRaises(HTTPException) as cm:
            remote_agent.require_token_from_ws(ws)
        self.assertEqual(cm.exception.status_code, 401)

if __name__ == '__main__':
    unittest.main()
