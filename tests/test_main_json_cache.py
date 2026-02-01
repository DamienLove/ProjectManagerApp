import unittest
from unittest.mock import MagicMock, patch, mock_open
import sys
import os
import json
import copy

# --- MOCKING ---
sys.modules["customtkinter"] = MagicMock()
sys.modules["pystray"] = MagicMock()
sys.modules["PIL"] = MagicMock()
sys.modules["PIL.Image"] = MagicMock()
sys.modules["firebase_admin"] = MagicMock()
sys.modules["firebase_admin.credentials"] = MagicMock()
sys.modules["firebase_admin.firestore"] = MagicMock()

class MockCTk:
    def __init__(self, *args, **kwargs): pass
    def title(self, *args): pass
    def geometry(self, *args): pass
    def withdraw(self): pass
    def protocol(self, *args): pass
    def mainloop(self): pass
    def after(self, *args): pass
    def update_idletasks(self): pass
    def state(self, *args): pass
    def deiconify(self): pass
    def lift(self): pass
    def attributes(self, *args): pass
    def winfo_id(self): return 1
    def winfo_width(self): return 100
    def winfo_height(self): return 100
    def winfo_screenwidth(self): return 1000
    def winfo_screenheight(self): return 1000
    def winfo_exists(self): return True

sys.modules["customtkinter"].CTk = MockCTk
sys.modules["customtkinter"].CTkToplevel = MockCTk
sys.modules["customtkinter"].CTkFrame = MagicMock()
sys.modules["customtkinter"].CTkLabel = MagicMock()
sys.modules["customtkinter"].CTkEntry = MagicMock()
sys.modules["customtkinter"].CTkButton = MagicMock()
sys.modules["customtkinter"].CTkScrollableFrame = MagicMock()
sys.modules["customtkinter"].CTkTextbox = MagicMock()
sys.modules["customtkinter"].CTkProgressBar = MagicMock()
sys.modules["customtkinter"].CTkInputDialog = MagicMock()

from src.main import ProjectManagerApp

class TestJsonCaching(unittest.TestCase):
    def setUp(self):
        with patch("src.main.LoginWindow"):
            with patch("src.main.ProjectManagerApp._start_tray_icon"):
                with patch("src.main.ProjectManagerApp._start_remote_agent"):
                    self.app = ProjectManagerApp()

    def test_load_json_caching_and_immutability(self):
        test_path = "test_registry.json"
        # Nested data to test deep copy
        test_data = {"project1": {"status": "Local", "config": [1, 2]}}

        m = mock_open(read_data=json.dumps(test_data))

        with patch("builtins.open", m):
            with patch("os.path.exists", return_value=True):
                with patch("os.path.getmtime") as mock_mtime:
                    mock_mtime.return_value = 100.0

                    # 1. First Load
                    data1 = self.app._load_json(test_path)
                    self.assertEqual(data1, test_data)
                    self.assertEqual(m.call_count, 1)

                    # 2. Modify returned data
                    data1["project1"]["config"].append(3)

                    # 3. Second Load (Same mtime)
                    data2 = self.app._load_json(test_path)

                    # Expectation: Cache should NOT be polluted
                    self.assertEqual(data2["project1"]["config"], [1, 2], "Cache should be isolated from modifications")
                    self.assertNotEqual(data2, data1)
                    self.assertEqual(m.call_count, 1)

if __name__ == "__main__":
    unittest.main()
