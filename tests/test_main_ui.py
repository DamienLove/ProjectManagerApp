import sys
import os
import unittest
from unittest.mock import MagicMock, patch

# Mock modules BEFORE importing main
sys.modules['customtkinter'] = MagicMock()
sys.modules['dotenv'] = MagicMock()
sys.modules['firebase_admin'] = MagicMock()
sys.modules['firebase_admin.credentials'] = MagicMock()
sys.modules['firebase_admin.firestore'] = MagicMock()
sys.modules['pystray'] = MagicMock()
sys.modules['PIL'] = MagicMock()
sys.modules['requests'] = MagicMock()

# Configure specific mocks for CTK structure
import customtkinter as ctk

# We need these to be classes so inheritance works
class MockCTk:
    def __init__(self, *args, **kwargs): pass
    def title(self, *args): pass
    def geometry(self, *args): pass
    def withdraw(self, *args): pass
    def deiconify(self, *args): pass
    def protocol(self, *args): pass
    def mainloop(self, *args): pass
    def after(self, *args, **kwargs): pass
    def lift(self, *args): pass
    def attributes(self, *args): pass
    def winfo_width(self): return 100
    def winfo_height(self): return 100
    def winfo_screenwidth(self): return 1000
    def winfo_screenheight(self): return 1000
    def winfo_id(self): return 123
    def state(self, *args): pass
    def wm_deiconify(self, *args): pass
    def update_idletasks(self, *args): pass
    def bind(self, *args): pass

ctk.CTk = MockCTk
ctk.CTkToplevel = MockCTk
ctk.CTkFrame = MagicMock()
ctk.CTkScrollableFrame = MagicMock()
ctk.CTkLabel = MagicMock()
ctk.CTkButton = MagicMock()
ctk.CTkEntry = MagicMock()
ctk.CTkTextbox = MagicMock()
ctk.CTkProgressBar = MagicMock()
ctk.CTkOptionMenu = MagicMock()
ctk.CTkCheckBox = MagicMock()
ctk.BooleanVar = MagicMock
ctk.StringVar = MagicMock
ctk.set_appearance_mode = MagicMock()
ctk.set_default_color_theme = MagicMock()
ctk.get_appearance_mode = MagicMock(return_value="Dark")

# Add src to path
sys.path.append(os.path.join(os.getcwd(), 'src'))

# Now import main
try:
    from main import ProjectManagerApp
except ImportError as e:
    print(f"ImportError: {e}")
    sys.exit(1)

class TestEmptyState(unittest.TestCase):
    @patch('main.load_dotenv')
    @patch('main.log_startup')
    def test_empty_state_rendering(self, mock_log, mock_dotenv):
        # Setup app
        # We need to bypass some of __init__ or ensure it doesn't fail
        # ProjectManagerApp.__init__ checks sys.frozen. We can mock sys.frozen = False (default)

        # We need to mock LoginWindow creation or it might fail if Toplevel mocks aren't perfect
        with patch('main.LoginWindow') as MockLogin:
            app = ProjectManagerApp()

            # Reset mocks for clean state verification
            ctk.CTkLabel.reset_mock()
            ctk.CTkButton.reset_mock()
            ctk.CTkFrame.reset_mock()

            # Setup for _refresh_projects
            app.project_list = MagicMock()
            app.project_list.winfo_children.return_value = []

            # Mock scans to ensure "Empty" result
            app._scan_folders = MagicMock(return_value=set())
            app._load_cloud_reg = MagicMock(return_value={})
            app._load_local_reg = MagicMock(return_value={})
            app._load_categories = MagicMock(return_value={})
            app.sync_to_firestore = MagicMock()
            app._save_reg = MagicMock()

            print("Running _refresh_projects with empty registry...")
            app._refresh_projects()

            # Verification
            # 1. Check if a frame was created inside project_list
            # CTKFrame is a class mock (MagicMock). instantiation is a call.
            # We expect ctk.CTkFrame(self.project_list, fg_color="transparent")

            # Filter calls to find the one with project_list
            frame_created = False
            for call in ctk.CTkFrame.call_args_list:
                args, kwargs = call
                if args and args[0] == app.project_list:
                    frame_created = True
                    break

            if not frame_created:
                # Debug info
                print("Frame calls:", ctk.CTkFrame.call_args_list)
                print("ProjectList:", app.project_list)

            self.assertTrue(frame_created, "An empty state frame should be created in project_list")

            # 2. Check for "Welcome" label
            welcome_text_found = False
            for call in ctk.CTkLabel.call_args_list:
                kwargs = call[1]
                if "Welcome to OmniProjectSync" in kwargs.get('text', ''):
                    welcome_text_found = True
                    break

            self.assertTrue(welcome_text_found, "Welcome text label should be created")

            # 3. Check for "Create First Project" button
            button_found = False
            for call in ctk.CTkButton.call_args_list:
                kwargs = call[1]
                if "Create First Project" in kwargs.get('text', ''):
                    button_found = True
                    break

            self.assertTrue(button_found, "Create Project button should be created")
            print("✅ Empty State verified successfully.")

if __name__ == '__main__':
    unittest.main()
