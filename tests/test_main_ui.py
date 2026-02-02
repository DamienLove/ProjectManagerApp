import unittest
import sys
from unittest.mock import MagicMock

# 1. Mock dependencies BEFORE importing src.main
sys.modules["customtkinter"] = MagicMock()
sys.modules["pystray"] = MagicMock()
sys.modules["PIL"] = MagicMock()
sys.modules["PIL.Image"] = MagicMock()
sys.modules["firebase_admin"] = MagicMock()
sys.modules["firebase_admin.credentials"] = MagicMock()
sys.modules["firebase_admin.firestore"] = MagicMock()
sys.modules["requests"] = MagicMock()
sys.modules["dotenv"] = MagicMock()

# Mock specific ctk classes
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

sys.modules["customtkinter"].CTkFrame = MockWidget
sys.modules["customtkinter"].CTkButton = MockWidget
sys.modules["customtkinter"].CTkLabel = MockWidget

# Now import src.main
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
        # Create ProjectCard (mocks parent and app)
        card = main.ProjectCard(MagicMock(), self.mock_app, "TestProject", "Local")

        # Call _btn with tooltip
        try:
            card._btn("Test Button", lambda: None, tooltip="Helpful text")
        except TypeError as e:
            self.fail(f"_btn raised TypeError, likely missing tooltip argument: {e}")

        # Verify ToolTip was instantiated
        self.assertTrue(self.mock_tooltip.called, "ToolTip class was not instantiated")

        # Check arguments: call_args returns (args, kwargs)
        # We expect ToolTip(widget, text)
        args, _ = self.mock_tooltip.call_args
        created_btn = args[0]
        tooltip_text = args[1]

        self.assertIsInstance(created_btn, MockWidget)
        self.assertEqual(tooltip_text, "Helpful text")

    def test_btn_no_tooltip(self):
        """Test that _btn works without tooltip (backward compatibility/default)."""
        card = main.ProjectCard(MagicMock(), self.mock_app, "TestProject", "Local")

        self.mock_tooltip.reset_mock()
        card._btn("Test Button", lambda: None)

        # ToolTip should NOT be called if no tooltip provided
        self.mock_tooltip.assert_not_called()

if __name__ == "__main__":
    unittest.main()
