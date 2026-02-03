import sys
import os
import unittest
import threading
import importlib
from unittest.mock import MagicMock, patch

# Define Dummy CustomTkinter Classes (Reused structure)
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
    def grid(self, **kwargs): pass
    def pack_forget(self): pass
    def grid_forget(self): pass
    def destroy(self):
        if self.master and hasattr(self.master, 'children') and self in self.master.children:
            self.master.children.remove(self)
        for c in list(self.children):
            c.destroy()
    def winfo_children(self):
        return list(self.children)
    def configure(self, **kwargs):
        self.kwargs.update(kwargs)
    def cget(self, key):
        return self.kwargs.get(key)
    def bind(self, event, command, add=None): pass
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
    def winfo_exists(self): return True

class CTk(DummyWidget):
    def __init__(self, **kwargs):
        super().__init__(None, **kwargs)
    def after(self, ms, func=None):
        if not hasattr(self, '_callbacks'): self._callbacks = []
        if func: self._callbacks.append(func)

class CTkFrame(DummyWidget): pass
class CTkScrollableFrame(DummyWidget): pass
class CTkToplevel(DummyWidget):
    def after(self, ms, func=None):
        if not hasattr(self, '_callbacks'): self._callbacks = []
        if func: self._callbacks.append(func)
class CTkLabel(DummyWidget):
    def __init__(self, master=None, **kwargs):
        super().__init__(master, **kwargs)
        self.text = kwargs.get("text", "")
class CTkButton(DummyWidget): pass
class CTkEntry(DummyWidget):
    def __init__(self, master=None, **kwargs):
        super().__init__(master, **kwargs)
        self._text = ""
    def delete(self, *args): pass
    def insert(self, *args):
        if len(args) > 1: self._text = args[1]
    def get(self): return self._text
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

class TestUXAsyncLogin(unittest.TestCase):
    def setUp(self):
        # Patch sys.modules to inject mocks
        self.modules_patcher = patch.dict(sys.modules, {
            "customtkinter": mock_ctk,
            "pystray": MagicMock(),
            "PIL": MagicMock(),
            "PIL.Image": MagicMock(),
            "firebase_admin": MagicMock(),
            "firebase_admin.credentials": MagicMock(),
            "firebase_admin.firestore": MagicMock(),
            "requests": MagicMock(),
            "dotenv": MagicMock(),
        })
        self.modules_patcher.start()

        # Add src to path if needed (though it seems it is already)
        src_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '../src'))
        if src_path not in sys.path:
            sys.path.insert(0, src_path)

        # Import main securely
        self.old_main = sys.modules.get('main')
        import main
        importlib.reload(main)
        self.main = main

        self.app_mock = MagicMock()
        self.app_mock.on_close = MagicMock()

    def tearDown(self):
        self.modules_patcher.stop()
        # Restore old main if it existed, otherwise clean up
        if self.old_main:
            sys.modules['main'] = self.old_main
        elif 'main' in sys.modules:
            del sys.modules['main']

    @patch('threading.Thread')
    def test_login_starts_thread(self, mock_thread):
        # Use classes from the reloaded main module
        LoginWindow = self.main.LoginWindow

        # We need to access the requests mock that main is using
        # Since main imported requests, and we patched sys.modules['requests'],
        # main.requests should be our mock.
        mock_post = self.main.requests.post

        login_window = LoginWindow(self.app_mock)

        # Simulate user input
        login_window.email_entry._text = "test@example.com"
        login_window.password_entry._text = "password123"

        # Call login
        login_window.login()

        # Assert buttons are disabled
        self.assertEqual(login_window.btn_login.kwargs.get("state"), "disabled")
        self.assertEqual(login_window.btn_register.kwargs.get("state"), "disabled")
        self.assertEqual(login_window.status_lbl.kwargs.get("text"), "Authenticating...")

        # Assert thread started
        mock_thread.assert_called_once()
        args, kwargs = mock_thread.call_args
        target = kwargs.get('target')
        thread_args = kwargs.get('args')

        self.assertEqual(thread_args, ("test@example.com", "password123"))
        self.assertTrue(kwargs.get('daemon'))

        # Assert requests.post NOT called yet
        mock_post.assert_not_called()

        # Now simulate thread execution
        target(*thread_args)

        # Assert requests.post called
        mock_post.assert_called_once()

        # Simulate main thread processing 'after' callbacks
        for callback in login_window._callbacks:
            callback()

        # Check if buttons re-enabled
        self.assertEqual(login_window.btn_login.kwargs.get("state"), "normal")
        self.assertEqual(login_window.btn_register.kwargs.get("state"), "normal")

if __name__ == '__main__':
    unittest.main()
