import sys
import os
import unittest
import tempfile
import shutil
import json
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
    def __init__(self, **kwargs): super().__init__(None, **kwargs)
    def after(self, ms, func=None):
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
from main import ProjectConfigWindow

class TestUXConfigEmptyState(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.project_name = "TestProject"
        self.project_path = os.path.join(self.test_dir, self.project_name)
        os.makedirs(self.project_path, exist_ok=True)
        # Create empty manifest
        with open(os.path.join(self.project_path, "omni.json"), "w") as f:
            json.dump({}, f)

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def test_config_empty_states(self):
        # Initialize window
        # We need a dummy parent
        parent = MagicMock()

        # Instantiate window
        # This calls _init_ui and _load_manifest -> _refresh
        win = ProjectConfigWindow(parent, self.project_name, self.test_dir)

        # Helper to check for label with text in a frame
        def has_empty_label(frame, keyword):
            for child in frame.winfo_children():
                if isinstance(child, CTkLabel):
                    if keyword.lower() in child.text.lower():
                        return True
            return False

        # 1. External Files
        # By default empty
        self.assertTrue(
            has_empty_label(win.scroll_files, "synced"),
            "External Files tab should show empty state label when empty"
        )

        # 2. Software
        self.assertTrue(
            has_empty_label(win.scroll_soft, "software"),
            "Software tab should show empty state label when empty"
        )

        # 3. App State
        self.assertTrue(
            has_empty_label(win.scroll_app_state, "app state"),
            "App State tab should show empty state label when empty"
        )

if __name__ == '__main__':
    unittest.main()
