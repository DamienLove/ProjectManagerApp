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

import customtkinter
# Define Mock classes
class MockWidget:
    def __init__(self, master=None, **kwargs):
        self.master = master
        self.pack = MagicMock()
        self.pack_forget = MagicMock()
        self.grid = MagicMock()
        self.grid_forget = MagicMock()
        self.bind = MagicMock()
        self.configure = MagicMock()
        self.winfo_children = lambda: []
        self.destroy = MagicMock()

# Patch ctk before import
with patch('customtkinter.CTkFrame', MockWidget), \
     patch('customtkinter.CTkButton', MockWidget), \
     patch('customtkinter.CTkLabel', MockWidget):
    
    from src import main

class TestProjectCardTooltips(unittest.TestCase):
    def setUp(self):
        self.mock_app = MagicMock()
        self.mock_app.icons = {}

        # Mock ToolTip class to verify instantiation
        self.original_tooltip = main.ToolTip
        self.mock_tooltip = MagicMock()
        main.ToolTip = self.mock_tooltip

    def tearDown(self):
        main.ToolTip = self.original_tooltip

    def test_btn_accepts_tooltip(self):
        """Test that _btn accepts a tooltip argument and creates a ToolTip."""
        # Mock parent frame
        mock_parent = MockWidget()
        # Mock the controls frame which is created in __init__
        with patch('customtkinter.CTkFrame', MockWidget):
            card = main.ProjectCard(mock_parent, self.mock_app, "TestProject", "Local")
            # card.controls is created in __init__

            # Call _btn with tooltip
            card._btn("Test Button", lambda: None, tooltip="Helpful text")

            # Verify ToolTip was instantiated
            self.assertTrue(self.mock_tooltip.called, "ToolTip class was not instantiated")

            # Check arguments: ToolTip(widget, text)
            args, _ = self.mock_tooltip.call_args
            tooltip_text = args[1]

            self.assertEqual(tooltip_text, "Helpful text")

    def test_btn_no_tooltip(self):
        """Test that _btn works without tooltip."""
        mock_parent = MockWidget()
        with patch('customtkinter.CTkFrame', MockWidget):
            card = main.ProjectCard(mock_parent, self.mock_app, "TestProject", "Local")

            self.mock_tooltip.reset_mock()
            card._btn("Test Button", lambda: None)

            # ToolTip should NOT be called if no tooltip provided
            self.mock_tooltip.assert_not_called()

if __name__ == "__main__":
    unittest.main()