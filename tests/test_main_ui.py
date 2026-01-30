
import unittest
from unittest.mock import MagicMock, patch
import sys
import os

# Create dummy classes for inheritance to ensure ProjectManagerApp is a valid class
class DummyCTk:
    def __init__(self, *args, **kwargs): pass
    def mainloop(self): pass
    def withdraw(self): pass
    def geometry(self, *args): pass
    def title(self, *args): pass
    def iconbitmap(self, *args): pass
    def protocol(self, *args): pass
    def after(self, *args): pass
    def option_add(self, *args): pass
    def update_idletasks(self): pass
    def state(self, *args): pass
    def wm_deiconify(self): pass
    def deiconify(self): pass
    def lift(self): pass
    def attributes(self, *args): pass
    def winfo_width(self): return 100
    def winfo_height(self): return 100
    def winfo_screenwidth(self): return 1920
    def winfo_screenheight(self): return 1080
    def winfo_id(self): return 123
    def destroy(self): pass

class DummyToplevel(DummyCTk):
    def transient(self, master): pass
    def grab_set(self): pass
    def focus_force(self): pass
    def wm_overrideredirect(self, v): pass
    def wm_geometry(self, g): pass

class DummyFrame:
    def __init__(self, *args, **kwargs): pass
    def pack(self, *args, **kwargs): pass
    def grid(self, *args, **kwargs): pass
    def destroy(self): pass
    def winfo_children(self): return []
    def bind(self, *args): pass
    def pack_forget(self): pass
    def grid_forget(self): pass

# Setup mock module
mock_ctk = MagicMock()
mock_ctk.CTk = DummyCTk
mock_ctk.CTkToplevel = DummyToplevel
mock_ctk.CTkFrame = DummyFrame
mock_ctk.CTkScrollableFrame = DummyFrame
mock_ctk.CTkLabel = MagicMock()
mock_ctk.CTkButton = MagicMock()
mock_ctk.CTkEntry = MagicMock()
mock_ctk.CTkCheckBox = MagicMock()
mock_ctk.CTkProgressBar = MagicMock()
mock_ctk.CTkTextbox = MagicMock()
mock_ctk.CTkTabview = MagicMock()
mock_ctk.CTkOptionMenu = MagicMock()
mock_ctk.CTkInputDialog = MagicMock()
mock_ctk.set_appearance_mode = MagicMock()
mock_ctk.set_default_color_theme = MagicMock()

sys.modules["customtkinter"] = mock_ctk
sys.modules["pystray"] = MagicMock()
sys.modules["PIL"] = MagicMock()
sys.modules["firebase_admin"] = MagicMock()
sys.modules["firebase_admin.credentials"] = MagicMock()
sys.modules["firebase_admin.firestore"] = MagicMock()
sys.modules["requests"] = MagicMock()
sys.modules["dotenv"] = MagicMock()

# Ensure src is in path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.main import ProjectManagerApp

class TestMainUI(unittest.TestCase):
    def test_empty_state_trigger(self):
        # Patch dependencies on the class
        with patch.object(ProjectManagerApp, "_scan_folders", return_value=set()) as mock_scan, \
             patch.object(ProjectManagerApp, "_load_cloud_reg", return_value={}) as mock_cloud, \
             patch.object(ProjectManagerApp, "_load_local_reg", return_value={}) as mock_local, \
             patch.object(ProjectManagerApp, "_load_categories", return_value={}) as mock_cats, \
             patch.object(ProjectManagerApp, "sync_to_firestore") as mock_sync, \
             patch.object(ProjectManagerApp, "_save_reg") as mock_save, \
             patch.object(ProjectManagerApp, "_drive_root", return_value=None), \
             patch.object(ProjectManagerApp, "__init__", return_value=None), \
             patch.object(ProjectManagerApp, "_render_empty_state", create=True) as mock_render:

            # Create an instance
            app = ProjectManagerApp()
            app.project_list = MagicMock()
            app.project_list.winfo_children.return_value = []
            app.category_frames = {}
            app._get_project_category = MagicMock(return_value="Uncategorized")

            # Run the method under test
            ProjectManagerApp._refresh_projects(app)

            # Assertions
            mock_render.assert_called_once()

if __name__ == "__main__":
    unittest.main()
