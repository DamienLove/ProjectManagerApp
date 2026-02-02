import unittest
import sys
from unittest.mock import MagicMock, patch

# Mock dependencies
sys.modules["pystray"] = MagicMock()
sys.modules["PIL"] = MagicMock()
sys.modules["PIL.Image"] = MagicMock()
sys.modules["firebase_admin"] = MagicMock()
sys.modules["firebase_admin.credentials"] = MagicMock()
sys.modules["firebase_admin.firestore"] = MagicMock()
sys.modules["requests"] = MagicMock()
sys.modules["dotenv"] = MagicMock()

# Import main after mocking
import src.main as main

class TestProjectCardTooltips(unittest.TestCase):
    def setUp(self):
        self.mock_app = MagicMock()
        self.mock_app.icons = {}

        # Mock ToolTip class to verify instantiation
        self.patcher = patch('src.main.ToolTip')
        self.mock_tooltip = self.patcher.start()
        
        # Mock ctk components used in ProjectCard
        self.ctk_patcher = patch('src.main.ctk')
        self.mock_ctk = self.ctk_patcher.start()

    def tearDown(self):
        self.patcher.stop()
        self.ctk_patcher.stop()

    def test_btn_accepts_tooltip(self):
        """Test that _btn accepts a tooltip argument and creates a ToolTip."""
        # Mock parent frame
        mock_parent = MagicMock()
        
        # We need to mock ProjectCard's parent class CTkFrame
        with patch('src.main.ctk.CTkFrame'):
            card = main.ProjectCard(mock_parent, self.mock_app, "TestProject", "Local")
            # Clear previous calls from __init__
            self.mock_ctk.CTkButton.reset_mock()
            
            # Call _btn with tooltip
            card._btn("Test Button", lambda: None, tooltip="Helpful text")

            # Verify ToolTip was instantiated
            self.assertTrue(self.mock_tooltip.called, "ToolTip class was not instantiated")
            
            args, _ = self.mock_tooltip.call_args
            tooltip_text = args[1]
            self.assertEqual(tooltip_text, "Helpful text")

    def test_btn_no_tooltip(self):
        """Test that _btn works without tooltip."""
        mock_parent = MagicMock()
        
        with patch('src.main.ctk.CTkFrame'):
            card = main.ProjectCard(mock_parent, self.mock_app, "TestProject", "Local")
            
            self.mock_tooltip.reset_mock()
            card._btn("Test Button", lambda: None)

            # ToolTip should NOT be called if no tooltip provided
            self.mock_tooltip.assert_not_called()

if __name__ == "__main__":
    unittest.main()
