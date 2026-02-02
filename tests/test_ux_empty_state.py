import sys
import os
import unittest
from unittest.mock import MagicMock, patch

# 1. Mock dependencies BEFORE importing main
sys.modules["pystray"] = MagicMock()
sys.modules["PIL"] = MagicMock()
sys.modules["PIL.Image"] = MagicMock()
sys.modules["firebase_admin"] = MagicMock()
sys.modules["firebase_admin.credentials"] = MagicMock()
sys.modules["firebase_admin.firestore"] = MagicMock()
sys.modules["requests"] = MagicMock()
sys.modules["dotenv"] = MagicMock()

# 2. Define Dummy CustomTkinter Classes
class DummyWidget:
    def __init__(self, master=None, **kwargs):
        self.master = master
        self.kwargs = kwargs
        self.children = []
        if master and hasattr(master, 'children'):
            master.children.append(self)
        self.pack_args = {}

    def pack(self, **kwargs):
        self.pack_args = kwargs
    def grid(self, **kwargs):
        pass
    def pack_forget(self):
        pass
    def grid_forget(self):
        pass
    def destroy(self):
        if self.master and hasattr(self.master, 'children') and self in self.master.children:
            self.master.children.remove(self)
        # Clear own children
        for c in list(self.children):
            c.destroy()
    def winfo_children(self):
        return list(self.children)
    def configure(self, **kwargs):
        self.kwargs.update(kwargs)
    def cget(self, key):
        return self.kwargs.get(key)
    def bind(self, event, command, add=None):
        pass
    def lift(self): pass
    def attributes(self, *args): pass
    def state(self, *args): pass
    def wm_deiconify(self): pass
    def deiconify(self): pass
    def withdraw(self): pass
    def update_idletasks(self): pass
    def geometry(self, *args): pass
    def title(self, *args): pass
    def protocol(self, *args): pass
    def mainloop(self): pass
    def winfo_id(self): return 1
    def winfo_width(self): return 100
    def winfo_height(self): return 100
    def winfo_screenwidth(self): return 1920
    def winfo_screenheight(self): return 1080
    def overrideredirect(self, *args): pass
    def grab_set(self): pass
    def focus_force(self): pass
    def winfo_rootx(self): return 0
    def winfo_rooty(self): return 0
    def wm_overrideredirect(self, *args): pass
    def wm_geometry(self, *args): pass
    def wait(self, *args): pass
    def terminate(self): pass
    def kill(self): pass
    def columnconfigure(self, *args, **kwargs): pass
    def rowconfigure(self, *args, **kwargs): pass

class CTk(DummyWidget):
    def __init__(self, **kwargs):
        super().__init__(None, **kwargs)
    def after(self, ms, func=None):
        # execute immediately for testing if functional
        if func: func()

class CTkFrame(DummyWidget): pass
class CTkScrollableFrame(DummyWidget): pass
class CTkToplevel(DummyWidget): pass
class CTkLabel(DummyWidget):
    def __init__(self, master=None, **kwargs):
        super().__init__(master, **kwargs)
        self.text = kwargs.get("text", "")
class CTkButton(DummyWidget): pass
class CTkEntry(DummyWidget):
    def delete(self, *args): pass
    def insert(self, *args): pass
    def get(self): return ""
class CTkCheckBox(DummyWidget): pass
class CTkTextbox(DummyWidget):
    def insert(self, *args): pass
    def see(self, *args): pass
class CTkProgressBar(DummyWidget):
    def set(self, val): pass
class CTkOptionMenu(DummyWidget): pass
class CTkTabview(DummyWidget):
    def add(self, name): return CTkFrame(self)
class CTkInputDialog(DummyWidget):
    def get_input(self): return ""

# Mock Module
mock_ctk = MagicMock()
mock_ctk.CTk = CTk
mock_ctk.CTkFrame = CTkFrame
mock_ctk.CTkScrollableFrame = CTkScrollableFrame
mock_ctk.CTkToplevel = CTkToplevel
mock_ctk.CTkLabel = CTkLabel
mock_ctk.CTkButton = CTkButton
mock_ctk.CTkEntry = CTkEntry
mock_ctk.CTkCheckBox = CTkCheckBox
mock_ctk.CTkTextbox = CTkTextbox
mock_ctk.CTkProgressBar = CTkProgressBar
mock_ctk.CTkOptionMenu = CTkOptionMenu
mock_ctk.CTkTabview = CTkTabview
mock_ctk.CTkInputDialog = CTkInputDialog
mock_ctk.set_appearance_mode = MagicMock()
mock_ctk.set_default_color_theme = MagicMock()
mock_ctk.get_appearance_mode = MagicMock(return_value="Dark")
mock_ctk.BooleanVar = MagicMock()
mock_ctk.StringVar = MagicMock()

sys.modules["customtkinter"] = mock_ctk

# Helper to add src to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

# Now import main
from main import ProjectManagerApp

class TestUXEmptyState(unittest.TestCase):
    def setUp(self):
        # Patch load_registry globally or on the instance
        pass

    @patch('main.ProjectManagerApp._load_local_reg', return_value={})
    @patch('main.ProjectManagerApp._load_cloud_reg', return_value={})
    @patch('main.ProjectManagerApp._load_categories', return_value={})
    @patch('os.makedirs')
    @patch('os.path.exists', return_value=True)
    def test_empty_state_rendered(self, mock_exists, mock_makedirs, mock_cats, mock_cloud, mock_local):
        # Initialize app
        # We need to mock _start_remote_agent and others to avoid side effects
        with patch.object(ProjectManagerApp, '_start_remote_agent'), \
             patch.object(ProjectManagerApp, '_start_tray_icon'), \
             patch.object(ProjectManagerApp, '_init_firebase'), \
             patch.object(ProjectManagerApp, '_check_queue'), \
             patch('main.LoginWindow', MagicMock()): # Avoid login window

            app = ProjectManagerApp()

            # Ensure project list is clear
            app.project_list = CTkScrollableFrame(app)
            app.project_cards = {}
            app.category_frames = {}

            # Call refresh
            app._refresh_projects()

            # Check children of project_list
            children = app.project_list.winfo_children()

            # Search for welcome text
            found_welcome = False
            for child in children:
                # Need to traverse deep if wrapped in frames
                # But simple check: look at direct children or their text
                if isinstance(child, CTkLabel):
                    if "Welcome" in child.kwargs.get("text", ""):
                        found_welcome = True
                elif isinstance(child, CTkFrame):
                    # Check inside frame
                    for sub in child.winfo_children():
                        if isinstance(sub, CTkLabel):
                             if "Welcome" in sub.kwargs.get("text", ""):
                                found_welcome = True

            self.assertTrue(found_welcome, "Empty state 'Welcome' message should be displayed when no projects exist.")

if __name__ == '__main__':
    unittest.main()
