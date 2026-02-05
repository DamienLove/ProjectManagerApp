import sys
import os
import unittest
import time
import shutil
import tempfile
from unittest.mock import MagicMock, patch

# --- MOCKING DEPENDENCIES START ---
sys.modules["pystray"] = MagicMock()
sys.modules["PIL"] = MagicMock()
sys.modules["PIL.Image"] = MagicMock()
sys.modules["firebase_admin"] = MagicMock()
sys.modules["firebase_admin.credentials"] = MagicMock()
sys.modules["firebase_admin.firestore"] = MagicMock()
sys.modules["requests"] = MagicMock()
sys.modules["dotenv"] = MagicMock()

# Define Dummy CustomTkinter Classes (Minimal for this test)
class DummyWidget:
    def __init__(self, master=None, **kwargs):
        self.master = master
        self.children = []
        if master and hasattr(master, 'children'):
            master.children.append(self)
    def pack(self, **kwargs): pass
    def grid(self, **kwargs): pass
    def destroy(self):
        if self.master and hasattr(self.master, 'children') and self in self.master.children:
            self.master.children.remove(self)
    def winfo_children(self): return list(self.children)
    def configure(self, **kwargs): pass
    def cget(self, key): return ""
    def bind(self, event, command, add=None): pass
    def after(self, ms, func=None):
        # For benchmark, we don't want to execute 'after' callbacks immediately
        # if they are meant for UI updates, or maybe we do to ensure full flow?
        # Since we want to test that the MAIN thread is free, we assume 'after' schedules it.
        # But in a synchronous test, 'after' is usually mocked to run immediately or ignored.
        # Here we will just ignore it or run it if provided to simulate main thread work if needed.
        pass
    def columnconfigure(self, *args, **kwargs): pass
    def rowconfigure(self, *args, **kwargs): pass
    def toggle(self): pass
    def title(self, *args): pass
    def geometry(self, *args): pass
    def withdraw(self): pass
    def deiconify(self): pass
    def lift(self): pass
    def attributes(self, *args): pass
    def state(self, *args): pass
    def wm_deiconify(self): pass
    def protocol(self, *args): pass
    def mainloop(self): pass
    def overrideredirect(self, *args): pass
    def grab_set(self): pass
    def focus_force(self): pass
    def wait(self, *args): pass
    def terminate(self): pass
    def kill(self): pass
    def winfo_id(self): return 1
    def winfo_width(self): return 100
    def winfo_height(self): return 100
    def winfo_screenwidth(self): return 1920
    def winfo_screenheight(self): return 1080
    def winfo_rootx(self): return 0
    def winfo_rooty(self): return 0
    def winfo_exists(self): return 1
    def update_idletasks(self): pass

class CTk(DummyWidget):
    def after(self, ms, func=None): pass
class CTkFrame(DummyWidget): pass
class CTkScrollableFrame(DummyWidget): pass
class CTkToplevel(DummyWidget): pass
class CTkLabel(DummyWidget): pass
class CTkButton(DummyWidget): pass
class CTkEntry(DummyWidget):
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
mock_ctk.get_appearance_mode = MagicMock(return_value="Dark")

sys.modules["customtkinter"] = mock_ctk
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

from main import ProjectManagerApp
# --- MOCKING DEPENDENCIES END ---

class BenchmarkRefresh(unittest.TestCase):
    def test_mro(self):
        print("MRO:", ProjectManagerApp.mro())
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.drive_dir = tempfile.mkdtemp()

        # Create some fake project folders
        for i in range(5):
            os.makedirs(os.path.join(self.test_dir, f"Project_Local_{i}"))
            os.makedirs(os.path.join(self.drive_dir, f"Project_Cloud_{i}"))

    def tearDown(self):
        shutil.rmtree(self.test_dir)
        shutil.rmtree(self.drive_dir)

    def test_refresh_performance(self):
        # We simulate a slow scandir using a side_effect
        original_scandir = os.scandir

        def slow_scandir(path):
            time.sleep(0.5) # Simulate 0.5s delay (e.g. network drive)
            return original_scandir(path)

        with patch('os.scandir', side_effect=slow_scandir), \
             patch.object(ProjectManagerApp, '_start_remote_agent'), \
             patch.object(ProjectManagerApp, '_start_tray_icon'), \
             patch.object(ProjectManagerApp, '_init_firebase'), \
             patch.object(ProjectManagerApp, '_check_queue'), \
             patch.dict(os.environ, {"LOCAL_WORKSPACE_ROOT": self.test_dir, "DRIVE_ROOT_FOLDER_ID": self.drive_dir}), \
             patch('main.LoginWindow', MagicMock()):

            app = ProjectManagerApp()
            app.project_list = CTkScrollableFrame(app)
            app.project_cards = {}
            app.category_frames = {}

            print("\n--- Starting Benchmark ---")
            start_time = time.time()
            app._refresh_projects()
            end_time = time.time()

            duration = end_time - start_time
            print(f"Refresh took: {duration:.4f} seconds")

            # This assertion will fail if optimization works (it should be fast)
            # But for now, we expect it to be slow (> 1.0s because we call scandir at least twice with 0.5s delay)
            if duration < 0.1:
                print("Status: FAST (Non-blocking)")
            else:
                print(f"Status: SLOW (Blocking) - Took {duration:.4f}s")
                self.fail("Method _refresh_projects blocked the main thread for too long!")

if __name__ == '__main__':
    unittest.main()
