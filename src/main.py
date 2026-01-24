import customtkinter as ctk
import os
import requests
import threading
import time
from dotenv import load_dotenv
import datetime
import shutil
import pystray
from PIL import Image
import sys
import stat
import subprocess
import json
import hashlib
import tempfile
import queue
import re
import traceback
import firebase_admin
from firebase_admin import credentials, firestore

# --- CONFIG ---
APP_NAME = "OmniProjectSync"
VERSION = "4.6.0"
OWNER_EMAILS = {"me@damiennichols.com", "damien@dmnlat.com"}

def get_base_dir() -> str:
    # When packaged (PyInstaller), anchor config next to the executable.
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

BASE_DIR = get_base_dir()
STARTUP_LOG = os.path.join(BASE_DIR, "omnisync_startup.log")

ENV_PATH = os.path.join(BASE_DIR, "secrets.env")
CONFIG_DIR = os.path.join(BASE_DIR, "config")
LOCAL_REGISTRY_PATH = os.path.join(CONFIG_DIR, "project_registry.json")
ASSET_PATH = os.path.join(BASE_DIR, "assets")
ICON_PATH = os.path.join(ASSET_PATH, "app_icon.png")

DEFAULT_WORKSPACE = "C:\\Projects"
PROTECTED_PATHS = ["C:\\Windows", "C:\\Program Files", "C:\\Program Files (x86)", "C:\\Users", "C:\\"]   

# Cloud/portable behavior
CLOUD_META_DIRNAME = "_omni_sync"
CLOUD_REGISTRY_FILENAME = "project_registry.json"
CLOUD_APP_DIRNAME = "OmniProjectSync"
CLOUD_LAUNCHER_PS1 = "Launch-OmniProjectSync.ps1"
CLOUD_LAUNCHER_CMD = "Launch-OmniProjectSync.cmd"
PORTABLE_MODE_ENV = "PORTABLE_MODE"
PORTABLE_ROOT_ENV = "PORTABLE_ROOT"
PORTABLE_AUTO_CLEAN_ENV = "PORTABLE_AUTO_CLEANUP"

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

# Hidden projects list (loaded from env, used by sync_to_firestore)
HIDDEN_PROJECTS = [h.strip().lower() for h in os.getenv("HIDDEN_PROJECTS", "").split(",") if h.strip()]

# --- UTILS ---
def force_remove_readonly(func, path, excinfo):
    """Handler for shutil.rmtree to unlock Git/Read-only files."""
    os.chmod(path, stat.S_IWRITE)
    func(path)

def bring_to_front(win, parent=None):
    """Best-effort: keep popups visible above the main window."""
    try:
        if parent: win.transient(parent)
    except Exception:
        pass
    try:
        win.lift()
    except Exception:
        pass
    try:
        win.attributes("-topmost", True)
        win.after(200, lambda: win.attributes("-topmost", False))
    except Exception:
        pass
    try:
        win.focus_force()
    except Exception:
        pass

def load_registry(app):
    """Load merged registry without relying on instance attr lookup quirks."""
    try:
        local = app._load_local_reg()
    except Exception:
        local = {}
    try:
        cloud = app._load_cloud_reg()
    except Exception:
        cloud = {}
    merged = {}
    merged.update(cloud)
    merged.update(local)
    return merged

def log_startup(message: str):
    try:
        os.makedirs(os.path.dirname(STARTUP_LOG), exist_ok=True)
        with open(STARTUP_LOG, "a", encoding="utf-8") as f:
            ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            f.write(f"[{ts}] {message}\n")
    except Exception:
        pass

def hide_console_window():
    try:
        if sys.platform != "win32":
            return
        import ctypes
        hwnd = ctypes.windll.kernel32.GetConsoleWindow()
        if hwnd:
            ctypes.windll.user32.ShowWindow(hwnd, 0)  # SW_HIDE
    except Exception:
        pass

def parse_winget_list_output(output: str):
    apps = []
    lines = output.splitlines()
    start = 0
    for i, line in enumerate(lines):
        if line.strip().startswith("---"):
            start = i + 1
            break
    for line in lines[start:]:
        if not line.strip():
            continue
        if "No installed package found" in line:
            continue
        parts = re.split(r"\s{2,}", line.strip())
        if len(parts) < 2:
            continue
        name = parts[0].strip()
        app_id = parts[1].strip()
        if not name or not app_id or app_id.lower() == "id":
            continue
        apps.append((name, app_id))
    # Deduplicate by id, keep first name.
    seen = set()
    deduped = []
    for name, app_id in apps:
        if app_id in seen:
            continue
        seen.add(app_id)
        deduped.append((name, app_id))
    return deduped

def resolve_credentials_path(path: str | None) -> str | None:
    if not path:
        return None
    cleaned = path.strip().strip('"')
    if not cleaned:
        return None
    if os.path.isfile(cleaned):
        return cleaned
    if os.path.isdir(cleaned):
        try:
            for name in os.listdir(cleaned):
                if not name.lower().endswith(".json"):
                    continue
                candidate = os.path.join(cleaned, name)
                if not os.path.isfile(candidate):
                    continue
                try:
                    with open(candidate, "r", encoding="utf-8") as f:
                        text = f.read()
                    if "\"type\": \"service_account\"" in text:
                        return candidate
                except Exception:
                    continue
        except Exception:
            return None
    return None

# --- UI WINDOWS ---

class LoginWindow(ctk.CTkToplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.title("Login")
        self.geometry("350x380+100+100")
        bring_to_front(self, parent)
        try:
            self.update_idletasks()
            self.state("normal")
            self.wm_deiconify()
            self.deiconify()
            self.lift()
            self.attributes("-topmost", True)
            self.after(500, lambda: self.attributes("-topmost", False))
            try:
                import ctypes
                hwnd = self.winfo_id()
                ctypes.windll.user32.ShowWindow(hwnd, 5)  # SW_SHOW
                ctypes.windll.user32.SetForegroundWindow(hwnd)
            except Exception:
                pass
        except Exception:
            pass
        try:
            self.deiconify()
        except Exception:
            pass
        self.main_app = parent
        self.protocol("WM_DELETE_WINDOW", self.main_app.on_close)

        ctk.CTkLabel(self, text="Email").pack(pady=(10,0))
        self.email_entry = ctk.CTkEntry(self, placeholder_text="Enter your email")
        self.email_entry.pack(fill="x", padx=20)
        email_saved = os.getenv("FIREBASE_EMAIL", "")
        if email_saved: self.email_entry.insert(0, email_saved)

        ctk.CTkLabel(self, text="Password").pack(pady=(10,0))
        self.password_entry = ctk.CTkEntry(self, placeholder_text="Enter your password", show="*")
        self.password_entry.pack(fill="x", padx=20)

        self.status_lbl = ctk.CTkLabel(self, text="", text_color="red", font=("", 10))
        self.status_lbl.pack(pady=(5,0))

        btn_row = ctk.CTkFrame(self, fg_color="transparent")
        btn_row.pack(pady=10)
        ctk.CTkButton(btn_row, text="Login", width=100, command=self.login).pack(side="left", padx=5)
        ctk.CTkButton(btn_row, text="Register", width=100, fg_color="#22c55e", command=self.register).pack(side="left", padx=5)
        
        ctk.CTkButton(self, text="Forgot Password / Reset", fg_color="transparent", text_color="gray", command=self.reset_password).pack(pady=5)

    def register(self):
        email = self.email_entry.get().strip()
        password = self.password_entry.get().strip()
        if not email or not password:
            self.status_lbl.configure(text="Email and password required")
            return
        self.status_lbl.configure(text="Registering...", text_color="white")
        api_key = "AIzaSyD4mFl_Qal_mi5mxWvi5jEEHwxszzCq1CU"
        url = f"https://identitytoolkit.googleapis.com/v1/accounts:signUp?key={api_key}"
        try:
            resp = requests.post(url, json={"email": email, "password": password, "returnSecureToken": True})
            if resp.status_code == 200:
                self.status_lbl.configure(text="Account created! Logging in...", text_color="green")
                self.login()
            else:
                err = resp.json().get("error", {}).get("message", "Registration failed")
                self.status_lbl.configure(text=f"Error: {err}")
        except:
            self.status_lbl.configure(text="Connection error")

    def reset_password(self):
        email = self.email_entry.get().strip()
        if not email:
            self.status_lbl.configure(text="Enter email first", text_color="orange")
            return
        api_key = "AIzaSyD4mFl_Qal_mi5mxWvi5jEEHwxszzCq1CU"
        url = f"https://identitytoolkit.googleapis.com/v1/accounts:sendOobCode?key={api_key}"
        try:
            resp = requests.post(url, json={"email": email, "requestType": "PASSWORD_RESET"})
            if resp.status_code == 200:
                self.status_lbl.configure(text="Reset email sent!", text_color="green")
            else:
                err = resp.json().get("error", {}).get("message", "Error")
                self.status_lbl.configure(text=f"Error: {err}")
        except:
            self.status_lbl.configure(text="Connection failed")

    def login(self):
        # Find the actual ProjectManagerApp instance
        app = self.main_app
        if not hasattr(app, "save_setting"):
            # Try to find it in global scope if self.main_app is just the tk interpreter
            import __main__
            if hasattr(__main__, "app"):
                app = __main__.app

        email = self.email_entry.get().strip()
        password = self.password_entry.get().strip()
        if not email or not password:
            self.status_lbl.configure(text="Missing email/password")
            return
        self.status_lbl.configure(text="Authenticating...", text_color="white")
        api_key = "AIzaSyD4mFl_Qal_mi5mxWvi5jEEHwxszzCq1CU"
        url = f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={api_key}"
        try:
            resp = requests.post(url, json={"email": email, "password": password, "returnSecureToken": True}, timeout=10)
            data = resp.json()
            if resp.status_code == 200:
                uid = data["localId"]
                is_owner = email.lower() in OWNER_EMAILS
                app.save_setting("FIREBASE_UID", uid)
                app.save_setting("FIREBASE_EMAIL", email)
                app.save_setting("FIREBASE_DOCUMENT_PATH", f"users/{uid}")
                if is_owner: app.save_setting("DEVELOPER_MODE", "1")
                os.environ["FIREBASE_UID"] = uid
                app.firebase_uid = uid
                db = app.__dict__.get("db", None)
                if db:
                    try:
                        db.collection("users").document(uid).set({
                            "email": email, "role": "owner" if is_owner else "user", "last_login": firestore.SERVER_TIMESTAMP
                        }, merge=True)
                    except: pass
                app.show_main_app()
                self.destroy()
            else:
                err = data.get("error", {}).get("message", "Login failed")
                self.status_lbl.configure(text="Invalid email or password" if err == "INVALID_LOGIN_CREDENTIALS" else f"Error: {err}", text_color="red")
        except Exception as e:
            self.status_lbl.configure(text=f"System error: {str(e)[:30]}", text_color="red")


class SoftwareBrowserWindow(ctk.CTkToplevel):
    def __init__(self, parent, callback):
        super().__init__(parent); bring_to_front(self, parent); self.title("Browse Software"); self.geometry("700x650"); self.callback = callback; self.apps = []; self.selected_ids = set()
        self.search_var = ctk.StringVar(); self.search_var.trace("w", self._filter_list)
        ctk.CTkEntry(self, textvariable=self.search_var, placeholder_text="🔍 Search...").pack(fill="x", padx=10, pady=5)
        self.scroll = ctk.CTkScrollableFrame(self); self.scroll.pack(fill="both", expand=True, padx=10, pady=10)
        self.is_scanning = True
        ctk.CTkLabel(self.scroll, text="⏳ Scanning installed software...\n(This usually takes 10-20 seconds)", font=("", 14), text_color="gray").pack(pady=20)
        self.btn_confirm = ctk.CTkButton(self, text="Add Selected (0)", command=self.confirm, state="disabled", fg_color="#22c55e", height=40)
        self.btn_confirm.pack(fill="x", padx=20, pady=10)
        threading.Thread(target=self._scan, daemon=True).start()
    def _scan(self):
        try:
            res = subprocess.run(["winget", "list"], capture_output=True, text=True, encoding='utf-8', errors='ignore')
            self.apps = parse_winget_list_output(res.stdout)
        except: pass
        finally:
            self.is_scanning = False
            self.after(0, self._filter_list)
    def _filter_list(self, *a):
        q = self.search_var.get().lower(); [w.destroy() for w in self.scroll.winfo_children()]
        if getattr(self, "is_scanning", False):
            ctk.CTkLabel(self.scroll, text="⏳ Scanning installed software...\n(This usually takes 10-20 seconds)", font=("", 14), text_color="gray").pack(pady=20)
            return
        count = 0
        for n, i in self.apps:
            if q in n.lower() or q in i.lower():
                if count > 200: break
                self._create_row(n, i); count += 1
    def _create_row(self, n, i):
        f = ctk.CTkFrame(self.scroll, fg_color="transparent"); f.pack(fill="x", pady=2)
        sel = i in self.selected_ids
        btn = ctk.CTkButton(f, text="✅" if sel else "➕", width=40, fg_color="#22c55e" if sel else "#3b82f6", command=lambda: self.tog(i))
        btn.pack(side="left"); ctk.CTkLabel(f, text=n, font=("",12,"bold")).pack(side="left", padx=5); ctk.CTkLabel(f, text=i, text_color="gray").pack(side="left")
    def tog(self, i):
        self.selected_ids.remove(i) if i in self.selected_ids else self.selected_ids.add(i)
        self.btn_confirm.configure(text=f"Add Selected ({len(self.selected_ids)})", state="normal" if self.selected_ids else "disabled"); self._filter_list()
    def confirm(self): self.callback(list(self.selected_ids)); self.destroy()

class InstalledAppsWindow(ctk.CTkToplevel):
    def __init__(self, parent):
        super().__init__(parent)
        bring_to_front(self, parent)
        self.title("Installed Apps")
        self.geometry("1000x650")
        self.app = parent
        self.apps = []
        self.filtered_apps = []
        self.selected_app_id = None
        self.selected_app_name = None
        self.app_buttons = {}
        self.project_checks = {}

        # Search + list (left)
        left = ctk.CTkFrame(self)
        left.pack(side="left", fill="both", expand=True, padx=10, pady=10)

        self.search_var = ctk.StringVar()
        self.search_var.trace("w", self._filter_apps)
        ctk.CTkEntry(left, textvariable=self.search_var, placeholder_text="Search installed apps...").pack(fill="x", pady=(0, 8))
        self.app_scroll = ctk.CTkScrollableFrame(left)
        self.app_scroll.pack(fill="both", expand=True)

        self.is_scanning = True
        ctk.CTkLabel(self.app_scroll, text="⏳ Scanning installed software...\n(This usually takes 10-20 seconds)", font=("", 14), text_color="gray").pack(pady=20)

        # Projects (right)
        right = ctk.CTkFrame(self)
        right.pack(side="right", fill="both", expand=True, padx=10, pady=10)

        self.selected_label = ctk.CTkLabel(right, text="Select an app to manage projects", font=("", 14, "bold"))
        self.selected_label.pack(anchor="w")
        self.auto_label = ctk.CTkLabel(right, text="Auto-uninstall: enabled (when unused by any project)", text_color="gray")
        self.auto_label.pack(anchor="w", pady=(0, 5))

        self.project_scroll = ctk.CTkScrollableFrame(right)
        self.project_scroll.pack(fill="both", expand=True, pady=(5, 0))

        self.status_label = ctk.CTkLabel(right, text="", text_color="gray")
        self.status_label.pack(anchor="w", pady=(5, 0))

        threading.Thread(target=self._scan_apps, daemon=True).start()

    def _scan_apps(self):
        try:
            res = subprocess.run(["winget", "list"], capture_output=True, text=True, encoding='utf-8', errors='ignore')
            self.apps = parse_winget_list_output(res.stdout)
            self.filtered_apps = list(self.apps)
        except Exception as e:
            self.after(0, lambda: self.status_label.configure(text=f"Failed to load apps: {e}"))
        finally:
            self.is_scanning = False
            self.after(0, self._render_apps)

    def _filter_apps(self, *a):
        q = self.search_var.get().lower().strip()
        if not q:
            self.filtered_apps = list(self.apps)
        else:
            self.filtered_apps = [(n, i) for n, i in self.apps if q in n.lower() or q in i.lower()]
        self._render_apps()

    def _render_apps(self):
        for w in self.app_scroll.winfo_children():
            w.destroy()

        if getattr(self, "is_scanning", False):
            ctk.CTkLabel(self.app_scroll, text="⏳ Scanning installed software...\n(This usually takes 10-20 seconds)", font=("", 14), text_color="gray").pack(pady=20)
            return

        self.app_buttons.clear()

        for name, app_id in self.filtered_apps[:300]:
            is_selected = app_id == self.selected_app_id
            btn = ctk.CTkButton(
                self.app_scroll,
                text=f"{name}  ({app_id})",
                anchor="w",
                fg_color="#2563eb" if is_selected else "transparent",
                text_color="white" if is_selected else "gray90",
                command=lambda n=name, i=app_id: self._select_app(n, i)
            )
            btn.pack(fill="x", pady=2)
            self.app_buttons[app_id] = btn

    def _select_app(self, name, app_id):
        self.selected_app_id = app_id
        self.selected_app_name = name
        self.selected_label.configure(text=f"{name}  ({app_id})")
        self._render_apps()
        self._render_projects_for_app(app_id)

    def _render_projects_for_app(self, app_id):
        for w in self.project_scroll.winfo_children():
            w.destroy()
        self.project_checks.clear()

        projects = self.app._get_projects_snapshot()
        count = 0
        for proj in projects:
            name = proj["name"]
            status = proj["status"]
            exists = proj["exists"]
            manifest_path = proj.get("manifest_path")

            row = ctk.CTkFrame(self.project_scroll, fg_color="transparent")
            row.pack(fill="x", pady=2)

            if status == "Cloud" and not exists:
                label_text = f"{name} [{status}] (not downloaded)"
            else:
                label_text = f"{name} [{status}]" + ("" if exists else " (missing)")
            label = ctk.CTkLabel(row, text=label_text, anchor="w")
            label.pack(side="left", padx=(0, 5), fill="x", expand=True)

            var = ctk.BooleanVar(value=self.app._project_has_software(manifest_path, app_id))
            chk = ctk.CTkCheckBox(
                row,
                text="",
                variable=var,
                state="normal" if manifest_path else "disabled",
                command=lambda n=name, s=status, v=var: self._toggle_project(n, s, app_id, v)
            )
            chk.pack(side="right")

            self.project_checks[name] = var
            count += 1

        self.status_label.configure(text=f"{count} projects loaded.")

    def _toggle_project(self, name, status, app_id, var):
        enabled = bool(var.get())
        changed = self.app._update_project_software(name, status, app_id, enabled)
        if changed:
            self.status_label.configure(text=f"Saved: {name} -> {'enabled' if enabled else 'disabled'}")
        else:
            self.status_label.configure(text=f"No change: {name}")

class ProjectConfigWindow(ctk.CTkToplevel):
    def __init__(self, parent, name, root):
        super().__init__(parent); bring_to_front(self, parent); self.title(f"Config: {name}"); self.geometry("700x600")
        self.project_path = os.path.join(root, name)
        self.manifest_path = os.path.join(self.project_path, "omni.json")
        self.data = {"external_paths":[], "software":[], "app_state_paths":[]}
        self._init_ui(); self._load_manifest()
    def _init_ui(self):
        t = ctk.CTkTabview(self); t.pack(fill="both", expand=True, padx=10, pady=10)
        tf = t.add("📁 External Files"); ts = t.add("💾 Software"); ta = t.add("⚙️ App State")
        self.scroll_files = ctk.CTkScrollableFrame(tf); self.scroll_files.pack(fill="both", expand=True)  
        f_add = ctk.CTkFrame(tf); f_add.pack(fill="x", pady=5)
        self.entry_path = ctk.CTkEntry(f_add, placeholder_text="C:\\Path\\To\\External\\Folder"); self.entry_path.pack(side="left", expand=True, fill="x", padx=5)
        ctk.CTkButton(f_add, text="Add", width=80, command=self.add_path).pack(side="right")
        self.scroll_soft = ctk.CTkScrollableFrame(ts); self.scroll_soft.pack(fill="both", expand=True)    
        s_add = ctk.CTkFrame(ts); s_add.pack(fill="x", pady=5)
        self.entry_soft = ctk.CTkEntry(s_add, placeholder_text="Software ID..."); self.entry_soft.pack(side="left", expand=True, fill="x", padx=5)
        ctk.CTkButton(s_add, text="Browse", width=80, command=lambda: SoftwareBrowserWindow(self, self.add_software_batch)).pack(side="right", padx=5)
        ctk.CTkButton(s_add, text="Add ID", width=80, command=self.add_software_id).pack(side="right")    
        self.scroll_app_state = ctk.CTkScrollableFrame(ta); self.scroll_app_state.pack(fill="both", expand=True)
        a_add = ctk.CTkFrame(ta); a_add.pack(fill="x", pady=5)
        self.entry_app_state_path = ctk.CTkEntry(a_add, placeholder_text="C:\\Users\\...\\AppData\\Roaming\\..._profile"); self.entry_app_state_path.pack(side="left", expand=True, fill="x", padx=5)
        ctk.CTkButton(a_add, text="Add", width=80, command=self.add_app_state_path).pack(side="right")    

    def _load_manifest(self):
        if os.path.exists(self.manifest_path):
            try:
                with open(self.manifest_path, "r") as f: self.data = json.load(f)
            except: pass
        if "app_state_paths" not in self.data:
            self.data["app_state_paths"] = []
        self._refresh()

    def _refresh(self):
        for w in self.scroll_files.winfo_children(): w.destroy()
        for w in self.scroll_soft.winfo_children(): w.destroy()
        for w in self.scroll_app_state.winfo_children(): w.destroy()
        for p in self.data.get("external_paths",[]):
            r=ctk.CTkFrame(self.scroll_files, fg_color="transparent"); r.pack(fill="x")
            ctk.CTkLabel(r, text=p).pack(side="left"); ctk.CTkButton(r, text="🗑️", width=30, fg_color="red", command=lambda x=p: self.remove_path(x)).pack(side="right")
        for s in self.data.get("software",[]):
            r=ctk.CTkFrame(self.scroll_soft, fg_color="transparent"); r.pack(fill="x")
            ctk.CTkLabel(r, text=s).pack(side="left"); ctk.CTkButton(r, text="🗑️", width=30, fg_color="red", command=lambda x=s: self.remove_software(x)).pack(side="right")
        for p in self.data.get("app_state_paths", []):
            r = ctk.CTkFrame(self.scroll_app_state, fg_color="transparent"); r.pack(fill="x")
            ctk.CTkLabel(r, text=p).pack(side="left")
            ctk.CTkButton(r, text="🗑️", width=30, fg_color="red", command=lambda x=p: self.remove_app_state_path(x)).pack(side="right")

    def add_path(self):
        p=self.entry_path.get().strip()
        if p and p not in self.data["external_paths"]: self.data["external_paths"].append(p); self.save_manifest()
    def remove_path(self, p): self.data["external_paths"].remove(p); self.save_manifest()
    def add_software_id(self):
        s=self.entry_soft.get().strip()
        if s and s not in self.data["software"]: self.data["software"].append(s); self.save_manifest()    
    def add_software_batch(self, ids):
        for i in ids:
            if i not in self.data["software"]: self.data["software"].append(i)
        self.save_manifest()
    def remove_software(self, s): self.data["software"].remove(s); self.save_manifest()
    def add_app_state_path(self):
        p = self.entry_app_state_path.get().strip()
        if p and p not in self.data["app_state_paths"]:
            self.data["app_state_paths"].append(p)
            self.save_manifest()
    def remove_app_state_path(self, p):
        self.data["app_state_paths"].remove(p)
        self.save_manifest()
    def save_manifest(self):
        with open(self.manifest_path, "w") as f: json.dump(self.data, f, indent=4)
        self._refresh()

class SettingsWindow(ctk.CTkToplevel):
    def __init__(self, parent, env):
        super().__init__(parent); bring_to_front(self, parent); self.env=env; self.parent=parent; self.title("Settings"); self.geometry("600x750"); self.entries={}
        self.fields = [
            ("Backup Drive Path","DRIVE_ROOT_FOLDER_ID"),
            ("Local Workspace Root","LOCAL_WORKSPACE_ROOT"),
            ("GitHub Token","GITHUB_TOKEN"),
            ("Hidden Projects","HIDDEN_PROJECTS"),
            ("Firebase Project ID", "FIREBASE_PROJECT_ID"),
            ("Firebase Doc Path", "FIREBASE_DOCUMENT_PATH"),
            ("Google App Credentials Path", "GOOGLE_APPLICATION_CREDENTIALS")
        ]
        self.remote_fields = [
            ("Remote Access Token", "REMOTE_ACCESS_TOKEN"),
            ("Public Host (for Android)", "REMOTE_PUBLIC_HOST"),
            ("Bind Host", "REMOTE_BIND_HOST"),
            ("Remote Port", "REMOTE_PORT"),
        ]
        self.scroll = ctk.CTkScrollableFrame(self); self.scroll.pack(fill="both", expand=True, padx=10, pady=10)

        # General settings section
        ctk.CTkLabel(self.scroll, text="General Settings", font=("", 14, "bold")).pack(anchor="w", pady=(0,5))
        for l,k in self.fields:
            f=ctk.CTkFrame(self.scroll, fg_color="transparent"); f.pack(fill="x", pady=5); ctk.CTkLabel(f, text=l, width=200, anchor="w").pack(side="left")
            e=ctk.CTkEntry(f); e.pack(side="left", fill="x", expand=True); self.entries[k]=e

        # Remote Agent section
        ctk.CTkLabel(self.scroll, text="Remote Agent (Android)", font=("", 14, "bold")).pack(anchor="w", pady=(20,5))

        # Token field with generate button
        f=ctk.CTkFrame(self.scroll, fg_color="transparent"); f.pack(fill="x", pady=5)
        ctk.CTkLabel(f, text="Remote Access Token", width=200, anchor="w").pack(side="left")
        e=ctk.CTkEntry(f, show="*"); e.pack(side="left", fill="x", expand=True); self.entries["REMOTE_ACCESS_TOKEN"]=e
        ctk.CTkButton(f, text="Generate", width=80, command=self._generate_token, fg_color="#6366f1").pack(side="left", padx=(5,0))

        # Public host field with auto-detect buttons
        f=ctk.CTkFrame(self.scroll, fg_color="transparent"); f.pack(fill="x", pady=5)
        ctk.CTkLabel(f, text="Public Host (Android)", width=200, anchor="w").pack(side="left")
        e=ctk.CTkEntry(f); e.pack(side="left", fill="x", expand=True); self.entries["REMOTE_PUBLIC_HOST"]=e
        ctk.CTkButton(f, text="Tunnel", width=70, command=self._detect_tunnel_url, fg_color="#f97316").pack(side="left", padx=(5,0))
        ctk.CTkButton(f, text="LAN", width=50, command=self._detect_lan_ip, fg_color="#0ea5e9").pack(side="left", padx=(5,0))

        # Bind host
        f=ctk.CTkFrame(self.scroll, fg_color="transparent"); f.pack(fill="x", pady=5)
        ctk.CTkLabel(f, text="Bind Host", width=200, anchor="w").pack(side="left")
        e=ctk.CTkEntry(f); e.pack(side="left", fill="x", expand=True); self.entries["REMOTE_BIND_HOST"]=e
        e.insert(0, "127.0.0.1")  # Default

        # Port
        f=ctk.CTkFrame(self.scroll, fg_color="transparent"); f.pack(fill="x", pady=5)
        ctk.CTkLabel(f, text="Remote Port", width=200, anchor="w").pack(side="left")
        e=ctk.CTkEntry(f); e.pack(side="left", fill="x", expand=True); self.entries["REMOTE_PORT"]=e
        e.insert(0, "8765")  # Default

        # Help text
        help_text = """Use your Cloudflare tunnel URL (e.g., omni.yourdomain.com) for remote access.
LAN IP only works on same network. 127.0.0.1 will NOT work!"""
        ctk.CTkLabel(self.scroll, text=help_text, text_color="#f97316", font=("", 11)).pack(anchor="w", pady=(5,10))

        # Restart agent checkbox
        self.restart_agent_var = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(self.scroll, text="Restart remote agent after save", variable=self.restart_agent_var).pack(anchor="w", pady=5)

        ctk.CTkButton(self, text="💾 Save Configuration", command=self.save, fg_color="#22c55e", height=40).pack(fill="x", padx=20, pady=20)
        self.load()

    def _generate_token(self):
        import secrets as sec
        token = sec.token_urlsafe(32)
        entry = self.entries.get("REMOTE_ACCESS_TOKEN")
        if entry:
            entry.delete(0, "end")
            entry.insert(0, token)

    def _detect_lan_ip(self):
        import socket
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            entry = self.entries.get("REMOTE_PUBLIC_HOST")
            if entry:
                entry.delete(0, "end")
                entry.insert(0, ip)
        except Exception:
            pass

    def _detect_tunnel_url(self):
        """Try to detect Cloudflare tunnel URL from config file."""
        import yaml
        config_paths = [
            os.path.expanduser("~/.cloudflared/config.yml"),
            os.path.expanduser("~/.cloudflared/config.yaml"),
        ]
        for config_path in config_paths:
            if os.path.exists(config_path):
                try:
                    with open(config_path, "r") as f:
                        config = yaml.safe_load(f)
                    ingress = config.get("ingress", [])
                    for rule in ingress:
                        hostname = rule.get("hostname", "")
                        if hostname and not hostname.startswith("*"):
                            entry = self.entries.get("REMOTE_PUBLIC_HOST")
                            if entry:
                                entry.delete(0, "end")
                                entry.insert(0, hostname)
                            return
                except Exception:
                    continue
        from tkinter import messagebox
        messagebox.showinfo(
            "Cloudflare Tunnel",
            """No tunnel config found.

"
            "Paste your tunnel URL directly (e.g., omni.yourdomain.com)"""
        )

    def load(self):
        if os.path.exists(self.env):
            with open(self.env) as f:
                d = {l.split("=",1)[0].strip():l.split("=",1)[1].strip() for l in f if "=" in l and not l.startswith("#")}
                all_fields = self.fields + self.remote_fields
                for l,k in all_fields:
                    if k in self.entries:
                        self.entries[k].delete(0, "end")
                        self.entries[k].insert(0, d.get(k,""))

    def save(self):
        with open(self.env, "w") as f: f.write("\n".join([f"{k}={e.get().strip()}" for k,e in self.entries.items()]))
        load_dotenv(self.env, override=True)
        if hasattr(self.parent, '_sync_settings_to_cloud'):
            self.parent._sync_settings_to_cloud()
        if hasattr(self.parent, 'reload_config'):
            self.parent.reload_config()
        if self.restart_agent_var.get() and hasattr(self.parent, '_restart_remote_agent'):
            self.parent._restart_remote_agent()
        self.destroy()

class PopupMenu(ctk.CTkToplevel):
    def __init__(self, parent, widget, menu_items):
        super().__init__(parent)
        self.widget = widget
        self.withdraw()  # Hide initially

        # Remove decorations and set on top
        self.overrideredirect(True)
        self.attributes("-topmost", True)

        # Colors (Light, Dark)
        bg_color = ("#ffffff", "#1f2937")
        border_color = ("#3b82f6", "#3b82f6")

        self.frame = ctk.CTkFrame(self, fg_color=bg_color, corner_radius=6, border_width=2, border_color=border_color)
        self.frame.pack(fill="both", expand=True)

        for item in menu_items:
            # item format: (text, command, fg_color, text_color)
            text = item[0]
            cmd = item[1]
            fg = item[2] if len(item) > 2 else "transparent"
            tc = item[3] if len(item) > 3 else ("black", "white")

            # Hover color logic
            hover = ("#e5e7eb", "#374151") if fg == "transparent" else None

            btn = ctk.CTkButton(
                self.frame,
                text=text,
                command=lambda c=cmd: self._invoke(c),
                fg_color=fg,
                text_color=tc,
                anchor="w",
                width=180,
                height=35,
                corner_radius=4,
                hover_color=hover
            )

            btn.pack(fill="x", padx=5, pady=3)

        self.update_idletasks()
        self._position_window()
        self.deiconify()

        # Capture clicks
        self.after(10, self._set_grab)

    def _set_grab(self):
        try:
            self.grab_set()
            self.focus_force()
            self.bind("<Button-1>", self._check_click_outside)
            self.bind("<Escape>", lambda e: self.destroy())
        except Exception:
            pass

    def _position_window(self):
        try:
            root_x = self.widget.winfo_rootx()
            root_y = self.widget.winfo_rooty()
            btn_w = self.widget.winfo_width()
            btn_h = self.widget.winfo_height()

            req_w = self.winfo_reqwidth()
            req_h = self.winfo_reqheight()

            # Align right edge of menu with right edge of button
            x = (root_x + btn_w) - req_w
            # Ensure it doesn't go off the left side of the screen
            if x < 0: x = root_x

            y = root_y + btn_h + 5

            self.geometry(f"{req_w}x{req_h}+{x}+{y}")
        except Exception:
            self.geometry("+0+0")

    def _invoke(self, cmd):
        self.destroy()
        if cmd: cmd()

    def _check_click_outside(self, event):
        x = event.x_root
        y = event.y_root

        wx = self.winfo_rootx()
        wy = self.winfo_rooty()
        ww = self.winfo_width()
        wh = self.winfo_height()

        if not (wx <= x <= wx + ww and wy <= y <= wy + wh):
             self.destroy()

# --- MAIN APPLICATION ---

class CollapsibleFrame(ctk.CTkFrame):
    def __init__(self, parent, title="Title"):
        super().__init__(parent)
        self.columnconfigure(0, weight=1)
        self.expanded = False

        self.header = ctk.CTkFrame(self, fg_color="transparent")
        self.header.grid(row=0, column=0, sticky="ew")
        self.header.bind("<Button-1>", self.toggle)

        self.lbl_title = ctk.CTkLabel(self.header, text=f"▶ {title}", font=("", 12, "bold"))
        self.lbl_title.pack(side="left", padx=5)
        self.lbl_title.bind("<Button-1>", self.toggle)

        self.content = ctk.CTkFrame(self)

    def toggle(self, event=None):
        self.expanded = not self.expanded
        self.lbl_title.configure(text=f"{'▼' if self.expanded else '▶'} {self.lbl_title.cget('text')[2:]}")
        if self.expanded: self.content.grid(row=1, column=0, sticky="ew", padx=5, pady=5)
        else: self.content.grid_forget()

class ProjectCard(ctk.CTkFrame):
    def __init__(self, parent, app, name, status):
        super().__init__(parent, fg_color=("gray85", "gray25"))
        self.app = app
        self.name = name
        self.status = status
        self.expanded = False
        self.busy = False

        self.pack(fill="x", pady=2, padx=2)

        # Header
        self.header = ctk.CTkFrame(self, fg_color="transparent")
        self.header.pack(fill="x", padx=5, pady=5)
        self.header.bind("<Button-1>", self.toggle)

        self.update_visual_state()

        # Controls (Hidden by default)
        self.controls = ctk.CTkFrame(self, fg_color="transparent")

    def toggle(self, event=None):
        if self.busy:
            return
        self.expanded = not self.expanded
        if self.expanded:
            self.controls.pack(fill="x", padx=5, pady=5)
            self._populate_controls()
        else:
            self.controls.pack_forget()
            for w in self.controls.winfo_children(): w.destroy()

    def _populate_controls(self):
        # Re-create buttons every time to ensure fresh state/bindings
        if self.status == "Local":
            self._btn("📂 Folder", lambda: os.startfile(os.path.join(os.getenv("LOCAL_WORKSPACE_ROOT", DEFAULT_WORKSPACE), self.name)), "gray")
            self._btn("🤖 Studio", lambda: self.app.open_studio(self.name), "#3DDC84", "black")
            self._btn("🌌 AntiG", lambda: self.app.open_antigravity(self.name), "#9333ea")
            self._btn("⚙️ Config", lambda: ProjectConfigWindow(self.app, self.name, os.getenv("LOCAL_WORKSPACE_ROOT", DEFAULT_WORKSPACE)), "#64748b")
            self._btn("☁️ Deactivate", lambda: self.app.deactivate_project(self.name), "#ef4444")
        else:
            self._btn("🚀 Activate", lambda: self.app.activate_project(self.name), "#3b82f6")
            self._btn("❌ Forget", lambda: self.app.forget_project(self.name), "transparent", "red", border=1)

    def _btn(self, txt, cmd, bg="transparent", fg="white", border=0):
        btn = ctk.CTkButton(self.controls, text=txt, command=cmd, fg_color=bg, text_color=fg, border_width=border, height=25)
        btn.pack(fill="x", pady=2)
        if self.busy:
            btn.configure(state="disabled")

    def set_busy(self, is_busy):
        self.busy = is_busy
        self.update_visual_state()
        if self.expanded:
            for w in self.controls.winfo_children(): w.destroy()
            self._populate_controls()

    def update_visual_state(self):
        if hasattr(self, 'lbl'):
            self.lbl.destroy()

        if self.busy:
            icon = "⏳"
            col = "gray"
            text = f"{icon} {self.name} (Working...)"
        else:
            icon = "☁️" if self.status == "Cloud" else "📂"
            col = "#facc15" if self.status == "Cloud" else "#4ade80"
            text = f"{icon} {self.name}"

        self.lbl = ctk.CTkLabel(self.header, text=text, font=("", 14, "bold"), text_color=col)
        self.lbl.pack(side="left")
        self.lbl.bind("<Button-1>", self.toggle)

class ProjectManagerApp(ctk.CTk):

    def _init_firebase(self):
        self.db = None
        firebase_id = os.getenv("FIREBASE_PROJECT_ID", "omniremote-e7afd")
        cred_path = resolve_credentials_path(os.getenv("GOOGLE_APPLICATION_CREDENTIALS"))
        
        try:
            if cred_path:
                cred = credentials.Certificate(cred_path)
                firebase_admin.initialize_app(cred, {'projectId': firebase_id})
                self.db = firestore.client()
                self.log("📡 Firebase initialized.")
                self._ensure_user_doc()
            else:
                self.log("⚠️ Firebase credentials not found. Cloud sync disabled.")
        except Exception as e:
            self.log(f"⚠️ Firebase init failed: {e}")

    def _ensure_user_doc(self):
        if not self.db:
            return
        uid = self.firebase_uid or os.getenv("FIREBASE_UID")
        email = os.getenv("FIREBASE_EMAIL", "").strip()
        if not uid:
            return
        data = {"last_login": firestore.SERVER_TIMESTAMP}
        if email:
            data["email"] = email
            data["role"] = "owner" if email.lower() in OWNER_EMAILS else "user"
        try:
            self.db.collection("users").document(uid).set(data, merge=True)
        except Exception as e:
            self.log(f"⚠️ Failed to save user profile: {e}")

    def sync_to_firestore(self):
        if not self.db:
            return
        uid = self.firebase_uid or os.getenv("FIREBASE_UID")
        if not uid:
            return
            
        def worker():
            try:
                # 1. Sync connection info
                # (Desktop doesn't usually host the agent, but it might have its own token)
                # For now, let's focus on projects.
                
                # 2. Sync projects
                root = os.getenv("LOCAL_WORKSPACE_ROOT", DEFAULT_WORKSPACE)
                drive_root = self._drive_root()
                
                registry = load_registry(self)
                projects_ref = self.db.collection("users").document(uid).collection("projects")
                
                batch = self.db.batch()
                for name, status in registry.items():
                    if name.lower() in HIDDEN_PROJECTS: continue
                    
                    project_path = os.path.join(root, name) if status == "Local" else os.path.join(drive_root or "", name)
                    manifest_path = os.path.join(project_path, "omni.json")
                    
                    project_data = {
                        "name": name,
                        "status": status,
                        "updated_at": firestore.SERVER_TIMESTAMP
                    }
                    
                    if os.path.exists(manifest_path):
                        try:
                            with open(manifest_path, "r", encoding="utf-8") as f:
                                manifest = json.load(f)
                            project_data.update(manifest)
                        except Exception: pass
                        
                    doc_ref = projects_ref.document(name)
                    batch.set(doc_ref, project_data, merge=True)
                
                batch.commit()
                self.log(f"✅ Synced {len(registry)} projects to Firestore.")
            except Exception as e:
                self.log(f"⚠️ Firestore sync failed: {e}")

        threading.Thread(target=worker, daemon=True).start()

    def save_setting(self, key, value):
        lines = []
        found = False
        value = str(value).replace('\0', '').strip()
        if os.path.exists(ENV_PATH):
            try:
                with open(ENV_PATH, 'rb') as f:
                    raw = f.read().replace(b'\x00', b'')
                text = raw.decode('utf-8', errors='ignore')
                for line in text.splitlines():
                    if line.strip().startswith(f"{key}="):
                        lines.append(f"{key}={value}")
                        found = True
                    else:
                        lines.append(line)
            except: pass
        if not found:
            lines.append(f"{key}={value}")
        with open(ENV_PATH, 'w', encoding='utf-8') as f:
            f.write("\n".join(lines) + "\n")
        load_dotenv(ENV_PATH, override=True)

    def _init_login_inline(self):
        self.login_frame = ctk.CTkFrame(self)
        self.login_frame.pack(fill="both", expand=True, padx=20, pady=20)
        log_startup("Inline login created")

        ctk.CTkLabel(self.login_frame, text="Email").pack(pady=(10, 0))
        self.login_email_entry = ctk.CTkEntry(self.login_frame, placeholder_text="Enter your email")
        self.login_email_entry.pack(fill="x", padx=10)
        email_saved = os.getenv("FIREBASE_EMAIL", "")
        if email_saved:
            self.login_email_entry.insert(0, email_saved)

        ctk.CTkLabel(self.login_frame, text="Password").pack(pady=(10, 0))
        self.login_password_entry = ctk.CTkEntry(self.login_frame, placeholder_text="Enter your password", show="*")
        self.login_password_entry.pack(fill="x", padx=10)

        self.login_status_lbl = ctk.CTkLabel(self.login_frame, text="", text_color="red", font=("", 10))
        self.login_status_lbl.pack(pady=(5, 0))

        btn_row = ctk.CTkFrame(self.login_frame, fg_color="transparent")
        btn_row.pack(pady=10)
        ctk.CTkButton(btn_row, text="Login", width=100, command=self._login_inline).pack(side="left", padx=5)
        ctk.CTkButton(btn_row, text="Register", width=100, fg_color="#22c55e", command=self._register_inline).pack(side="left", padx=5)

        ctk.CTkButton(self.login_frame, text="Forgot Password / Reset", fg_color="transparent", text_color="gray", command=self._reset_inline).pack(pady=5)

    def _register_inline(self):
        email = self.login_email_entry.get().strip()
        password = self.login_password_entry.get().strip()
        if not email or not password:
            self.login_status_lbl.configure(text="Email and password required")
            return
        self.login_status_lbl.configure(text="Registering...", text_color="white")
        api_key = "AIzaSyD4mFl_Qal_mi5mxWvi5jEEHwxszzCq1CU"
        url = f"https://identitytoolkit.googleapis.com/v1/accounts:signUp?key={api_key}"
        try:
            resp = requests.post(url, json={"email": email, "password": password, "returnSecureToken": True})
            if resp.status_code == 200:
                self.login_status_lbl.configure(text="Account created! Logging in...", text_color="green")
                self._login_inline()
            else:
                err = resp.json().get("error", {}).get("message", "Registration failed")
                self.login_status_lbl.configure(text=f"Error: {err}")
        except Exception:
            self.login_status_lbl.configure(text="Connection error")

    def _reset_inline(self):
        email = self.login_email_entry.get().strip()
        if not email:
            self.login_status_lbl.configure(text="Enter email first", text_color="orange")
            return
        api_key = "AIzaSyD4mFl_Qal_mi5mxWvi5jEEHwxszzCq1CU"
        url = f"https://identitytoolkit.googleapis.com/v1/accounts:sendOobCode?key={api_key}"
        try:
            resp = requests.post(url, json={"email": email, "requestType": "PASSWORD_RESET"})
            if resp.status_code == 200:
                self.login_status_lbl.configure(text="Reset email sent!", text_color="green")
            else:
                err = resp.json().get("error", {}).get("message", "Error")
                self.login_status_lbl.configure(text=f"Error: {err}")
        except Exception:
            self.login_status_lbl.configure(text="Connection failed")

    def _login_inline(self):
        email = self.login_email_entry.get().strip()
        password = self.login_password_entry.get().strip()
        if not email or not password:
            self.login_status_lbl.configure(text="Missing email/password")
            return
        self.login_status_lbl.configure(text="Authenticating...", text_color="white")
        api_key = "AIzaSyD4mFl_Qal_mi5mxWvi5jEEHwxszzCq1CU"
        url = f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={api_key}"
        try:
            resp = requests.post(url, json={"email": email, "password": password, "returnSecureToken": True}, timeout=10)
            data = resp.json()
            if resp.status_code == 200:
                uid = data["localId"]
                is_owner = email.lower() in OWNER_EMAILS
                self.save_setting("FIREBASE_UID", uid)
                self.save_setting("FIREBASE_EMAIL", email)
                self.save_setting("FIREBASE_DOCUMENT_PATH", f"users/{uid}")
                if is_owner:
                    self.save_setting("DEVELOPER_MODE", "1")
                os.environ["FIREBASE_UID"] = uid
                self.firebase_uid = uid
                if self.db:
                    try:
                        self.db.collection("users").document(uid).set({
                            "email": email, "role": "owner" if is_owner else "user", "last_login": firestore.SERVER_TIMESTAMP
                        }, merge=True)
                    except Exception:
                        pass
                self.show_main_app()
            else:
                err = data.get("error", {}).get("message", "Login failed")
                self.login_status_lbl.configure(text="Invalid email or password" if err == "INVALID_LOGIN_CREDENTIALS" else f"Error: {err}", text_color="red")
        except Exception as e:
            self.login_status_lbl.configure(text=f"System error: {str(e)[:30]}", text_color="red")

    def __init__(self):
        super().__init__()
        log_startup("ProjectManagerApp init started")
        # Bind to instance to avoid Tk __getattr__ fallback on missing attrs.
        self._load_reg = lambda: load_registry(self)
        # Ensure attributes exist before login flow touches them.
        self.db = None
        self.firebase_uid = None
        self.title(APP_NAME)
        self.geometry("360x800+80+80")
        self.tray_icon = None
        self._cloud_meta_error_logged = False
        self._portable_cleanup_scheduled = False
        self.queue = queue.Queue()
        self.agent_process = None
        self.login_window = None
        if not getattr(sys, "frozen", False):
            self.withdraw() # Hide main window initially for source runs
            try:
                self.login_window = LoginWindow(self)
                log_startup("LoginWindow created")
            except Exception as e:
                log_startup(f"LoginWindow failed: {e}")
                log_startup(traceback.format_exc())
                raise
        else:
            self._init_login_inline()
        if getattr(sys, "frozen", False):
            try:
                self.state("normal")
                self.wm_deiconify()
                self.deiconify()
                self.lift()
                if self.login_window:
                    self.after(100, lambda: bring_to_front(self.login_window, self))
                    self.after(200, lambda: self.login_window.focus_force())
                log_startup("Forced login window to front (frozen)")
                try:
                    import ctypes
                    hwnd = self.winfo_id()
                    ctypes.windll.user32.ShowWindow(hwnd, 5)  # SW_SHOW
                    ctypes.windll.user32.SetForegroundWindow(hwnd)
                except Exception:
                    pass
                def _nudge_login(attempt=0):
                    if attempt >= 5:
                        return
                    try:
                        if self.login_window:
                            self.login_window.deiconify()
                            self.login_window.lift()
                            self.login_window.attributes("-topmost", True)
                            self.login_window.after(200, lambda: self.login_window.attributes("-topmost", False))
                    except Exception:
                        pass
                    self.after(400, lambda: _nudge_login(attempt + 1))
                self.after(300, _nudge_login)
            except Exception as e:
                log_startup(f"LoginWindow bring-to-front failed: {e}")
        self._check_queue()
        if getattr(sys, "frozen", False):
            self.after(200, self._ensure_visible)
        log_startup("ProjectManagerApp init finished")

    def _check_queue(self):
        try:
            while True:
                task = self.queue.get_nowait()
                if task == "deiconify":
                    self.deiconify()
                    bring_to_front(self)
                elif task == "quit":
                    self.on_close()
        except queue.Empty:
            pass
        self.after(200, self._check_queue)

    def show_main_app(self):
        if getattr(self, "login_window", None):
            try:
                self.login_window.destroy()
            except Exception:
                pass
        if getattr(self, "login_frame", None):
            try:
                self.login_frame.destroy()
            except Exception:
                pass
        self.deiconify() # Show main window
        self._init_compact_ui()
        self._start_tray_icon()
        self._start_remote_agent()

        if not os.path.exists(CONFIG_DIR): os.makedirs(CONFIG_DIR)
        self._init_firebase()
        self.reload_config()

    def _init_compact_ui(self):
        # 1. Header
        header = ctk.CTkFrame(self, height=50, corner_radius=0)
        header.pack(fill="x", side="top")

        ctk.CTkLabel(header, text=APP_NAME, font=("", 16, "bold")).pack(side="left", padx=15, pady=10)    

        # Menu Button (Settings/Quit)
        self.menu_btn = ctk.CTkButton(header, text="☰", width=40, command=self.show_menu)
        self.menu_btn.pack(side="right", padx=10)

        # 2. Main List
        self.project_list = ctk.CTkScrollableFrame(self)
        self.project_list.pack(fill="both", expand=True, padx=5, pady=5)
        self.project_cards = {}

        # 3. Footer
        footer = ctk.CTkFrame(self, fg_color="transparent")
        footer.pack(fill="x", side="bottom", padx=5, pady=5)

        ctk.CTkButton(footer, text="➕ New Project", command=self.show_new_project).pack(fill="x", pady=2)

        # Activity Log (Collapsible)
        self.log_container = CollapsibleFrame(footer, title="Activity Log")
        self.log_container.pack(fill="x", pady=2)

        self.log_box = ctk.CTkTextbox(self.log_container.content, height=100, font=("Consolas", 10))      
        self.log_box.pack(fill="x", padx=2, pady=2)
        self.log_box.configure(state="disabled")

        self.progress_bar = ctk.CTkProgressBar(footer, height=10, progress_color="#22c55e")
        self.progress_bar.set(0)
        self.progress_bar.pack(fill="x", pady=(5,0))

    def show_menu(self):
        menu_items = [
            ("⚙️ Settings", lambda: SettingsWindow(self, ENV_PATH)),
            ("🧩 Installed Apps", lambda: InstalledAppsWindow(self)),
            ("📦 Export Launcher", self.export_portable_bundle),
            ("☁️ Deactivate All", self.deactivate_all_projects),
        ]

        if self._is_portable_mode():
            menu_items.append(("🧹 Deactivate + Cleanup", lambda: self.deactivate_all_projects(cleanup=True, quit_after=True), "#f59e0b", "black"))

        menu_items.append(("🚪 Quit", self.on_close, "red", "white"))

        PopupMenu(self, self.menu_btn, menu_items)

    def _get_projects_snapshot(self):
        root = os.getenv("LOCAL_WORKSPACE_ROOT", DEFAULT_WORKSPACE)
        drive_root = self._drive_root()

        # Scan folders to keep registry fresh without touching UI.
        local_folders = {f for f in os.listdir(root) if os.path.isdir(os.path.join(root, f))} if os.path.exists(root) else set()
        cloud_folders = set()
        if drive_root and os.path.exists(drive_root):
            try:
                cloud_folders = {f for f in os.listdir(drive_root) if os.path.isdir(os.path.join(drive_root, f))}
            except Exception:
                cloud_folders = set()

        registry = {}
        registry.update(self._load_cloud_reg())
        registry.update(self._load_local_reg())
        for f in local_folders:
            registry[f] = "Local"
        for f in cloud_folders:
            if registry.get(f) != "Local":
                registry[f] = "Cloud"

        projects = []
        for name, status in sorted(registry.items()):
            if name.lower() in HIDDEN_PROJECTS:
                continue
            path = self._project_path_for_status(name, status)
            manifest_path = self._project_manifest_path(name, status, path)
            projects.append({
                "name": name,
                "status": status,
                "path": path,
                "manifest_path": manifest_path,
                "exists": bool(path and os.path.exists(path)),
            })
        return projects

    def _project_path_for_status(self, name, status):
        root = os.getenv("LOCAL_WORKSPACE_ROOT", DEFAULT_WORKSPACE)
        drive_root = self._drive_root()
        if status == "Local":
            return os.path.join(root, name)
        if not drive_root:
            return None
        return os.path.join(drive_root, name)

    def _project_manifest_path(self, name, status, project_path):
        if project_path and os.path.exists(project_path):
            return os.path.join(project_path, "omni.json")
        if status == "Cloud":
            meta = self._cloud_meta_dir()
            if meta:
                try:
                    project_meta = os.path.join(meta, "projects", name)
                    os.makedirs(project_meta, exist_ok=True)
                    return os.path.join(project_meta, "omni.json")
                except Exception:
                    return None
        return None

    def _load_project_manifest(self, manifest_path):
        data = {"external_paths": [], "software": [], "app_state_paths": []}
        if manifest_path and os.path.exists(manifest_path):
            try:
                with open(manifest_path, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
                if isinstance(loaded, dict):
                    data.update(loaded)
            except Exception:
                pass
        if "software" not in data:
            data["software"] = []
        if "external_paths" not in data:
            data["external_paths"] = []
        if "app_state_paths" not in data:
            data["app_state_paths"] = []
        return data

    def _save_project_manifest(self, manifest_path, data):
        if not manifest_path:
            return False
        try:
            os.makedirs(os.path.dirname(manifest_path), exist_ok=True)
            with open(manifest_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4)
            return True
        except Exception as e:
            self.log(f"⚠️ Failed to save manifest: {e}", "red")
            return False

    def _project_has_software(self, manifest_path, app_id):
        if not manifest_path:
            return False
        data = self._load_project_manifest(manifest_path)
        return app_id in data.get("software", [])

    def _update_project_software(self, name, status, app_id, enabled):
        project_path = self._project_path_for_status(name, status)
        manifest_path = self._project_manifest_path(name, status, project_path)
        if not manifest_path:
            return False
        data = self._load_project_manifest(manifest_path)
        software = list(data.get("software", []))
        changed = False

        if enabled and app_id not in software:
            software.append(app_id)
            changed = True
        if not enabled and app_id in software:
            software.remove(app_id)
            changed = True

        if not changed:
            return False

        data["software"] = software
        if not self._save_project_manifest(manifest_path, data):
            return False

        # Auto-uninstall when unused by any project.
        if not enabled:
            self._uninstall_app_if_unused(app_id)

        self.sync_to_firestore()
        return True

    def _is_app_used_by_any_projects(self, app_id):
        for proj in self._get_projects_snapshot():
            manifest_path = proj.get("manifest_path")
            if self._project_has_software(manifest_path, app_id):
                return True
        return False

    def _uninstall_app_if_unused(self, app_id):
        if self._is_app_used_by_any_projects(app_id):
            return
        try:
            self.log(f"🧹 Uninstalling unused app: {app_id}")
            subprocess.run(["winget", "uninstall", "-e", "--id", app_id, "--silent"], shell=True)
        except Exception as e:
            self.log(f"⚠️ Uninstall failed for {app_id}: {e}", "red")

    def reload_config(self):
        self._sync_settings_from_cloud()
        load_dotenv(ENV_PATH, override=True)
        self.log("🔄 Reloaded.")
        self._refresh_projects()

    def _drive_root(self):
        p = os.getenv("DRIVE_ROOT_FOLDER_ID", "").strip()
        return p if p else None

    def _cloud_meta_dir(self):
        root = self._drive_root()
        if not root:
            return None
        try:
            meta = os.path.join(root, CLOUD_META_DIRNAME)
            os.makedirs(meta, exist_ok=True)
            return meta
        except Exception as e:
            if not self._cloud_meta_error_logged:
                self.log(f"⚠️ Cloud meta unavailable: {e}")
                self._cloud_meta_error_logged = True
            return None

    def _cloud_registry_path(self):
        meta = self._cloud_meta_dir()
        if not meta:
            return None
        return os.path.join(meta, CLOUD_REGISTRY_FILENAME)

    def _load_json(self, path):
        if path and os.path.exists(path):
            try:
                with open(path, "r") as f:
                    return json.load(f)
            except Exception:
                return {}
        return {}

    def _save_json(self, path, data):
        if not path:
            return
        try:
            with open(path, "w") as f:
                json.dump(data, f, indent=4)
        except Exception:
            pass

    def _load_local_reg(self):
        return self._load_json(LOCAL_REGISTRY_PATH)

    def _save_local_reg(self, data):
        self._save_json(LOCAL_REGISTRY_PATH, data)

    def _load_cloud_reg(self):
        return self._load_json(self._cloud_registry_path())

    def _save_cloud_reg(self, data):
        self._save_json(self._cloud_registry_path(), data)

    def _load_reg(self):
        local = self._load_local_reg()
        cloud = self._load_cloud_reg()
        merged = {}
        merged.update(cloud)
        merged.update(local)
        return merged

    def _save_reg(self, data):
        self._save_local_reg(data)
        self._save_cloud_reg(data)

    def _sync_settings_from_cloud(self):
        if os.path.exists(ENV_PATH):
            return
        meta = self._cloud_meta_dir()
        if not meta:
            return
        cloud_env = os.path.join(meta, "secrets.env")
        if os.path.exists(cloud_env):
            try:
                shutil.copy2(cloud_env, ENV_PATH)
                self.log("🔑 Pulled settings from cloud.")
            except Exception:
                pass

    def _sync_settings_to_cloud(self):
        meta = self._cloud_meta_dir()
        if not meta or not os.path.exists(ENV_PATH):
            return
        try:
            shutil.copy2(ENV_PATH, os.path.join(meta, "secrets.env"))
        except Exception:
            pass

    def _copy_tree(self, src, dst):
        if not os.path.exists(src):
            return
        ignore = shutil.ignore_patterns(
            "__pycache__", "*.pyc", ".venv", ".git", ".genkit", "launch_log*.txt"
        )
        shutil.copytree(src, dst, dirs_exist_ok=True, ignore=ignore)

    def _write_portable_launchers(self, target_root):
        ps1_path = os.path.join(target_root, CLOUD_LAUNCHER_PS1)
        cmd_path = os.path.join(target_root, CLOUD_LAUNCHER_CMD)
        ps1 = (
            '$ErrorActionPreference = "Stop"\n'
            '$root = Split-Path -Parent $MyInvocation.MyCommand.Path\n'
            'Set-Location $root\n'
            '$env:PORTABLE_MODE = "1"\n'
            '$env:PORTABLE_ROOT = $root\n'
            '$venv = Join-Path $root ".venv"\n'
            '$python = Join-Path $venv "Scripts\\python.exe"\n'
            'if (-not (Test-Path $python)) {\n'
            '    Write-Host "Creating portable venv..."\n'
            '    $py = Get-Command py -ErrorAction SilentlyContinue\n'
            '    if ($py) { & py -3 -m venv $venv } else { & python -m venv $venv }\n'
            '    & $python -m pip install --upgrade pip\n'
            '    & $python -m pip install -r (Join-Path $root "requirements.txt")\n'
            '}\n'
            '& $python (Join-Path $root "src\\main.py")\n'
        )
        cmd = (
            "@echo off\n"
            "powershell -ExecutionPolicy Bypass -File \"%~dp0\\Launch-OmniProjectSync.ps1\"\n"
        )
        with open(ps1_path, "w", newline="\n") as f:
            f.write(ps1)
        with open(cmd_path, "w", newline="\n") as f:
            f.write(cmd)

    def export_portable_bundle(self):
        drive_root = self._drive_root()
        if not drive_root:
            self.log("❌ Error: No Drive Path set in settings.", "red")
            return
        meta = self._cloud_meta_dir()
        if not meta:
            self.log("❌ Error: Cloud meta folder unavailable.", "red")
            return
        # Ensure cloud registry + settings are up to date
        self._save_reg(load_registry(self))
        self._sync_settings_to_cloud()

        target_root = os.path.join(meta, CLOUD_APP_DIRNAME)
        os.makedirs(target_root, exist_ok=True)
        self._copy_tree(os.path.join(BASE_DIR, "src"), os.path.join(target_root, "src"))
        self._copy_tree(os.path.join(BASE_DIR, "assets"), os.path.join(target_root, "assets"))
        self._copy_tree(os.path.join(BASE_DIR, "config"), os.path.join(target_root, "config"))

        for fname in ["requirements.txt", "secrets.env", "secrets.env.template"]:
            src = os.path.join(BASE_DIR, fname)
            if os.path.exists(src):
                shutil.copy2(src, os.path.join(target_root, fname))

        self._write_portable_launchers(target_root)
        self.log(f"✅ Portable bundle updated at {target_root}")

    def _is_portable_mode(self):
        if os.getenv(PORTABLE_MODE_ENV, "").strip() == "1":
            return True
        pr = os.getenv(PORTABLE_ROOT_ENV, "").strip()
        if pr:
            try:
                base = os.path.abspath(BASE_DIR)
                root = os.path.abspath(pr)
                return os.path.commonpath([base, root]) == root
            except Exception:
                return False
        drive_root = self._drive_root()
        if drive_root:
            try:
                base = os.path.abspath(BASE_DIR)
                root = os.path.abspath(drive_root)
                if os.path.commonpath([base, root]) == root and CLOUD_META_DIRNAME.lower() in base.lower():
                    return True
            except Exception:
                pass
        return False

    def _portable_root(self):
        pr = os.getenv(PORTABLE_ROOT_ENV, "").strip()
        if pr:
            return pr
        return BASE_DIR if self._is_portable_mode() else None

    def _schedule_self_cleanup(self):
        if self._portable_cleanup_scheduled:
            return
        root = self._portable_root()
        if not root:
            self.log("⚠️ Portable cleanup skipped (not in portable mode).")
            return
        self._portable_cleanup_scheduled = True
        script_path = os.path.join(tempfile.gettempdir(), f"omni_cleanup_{os.getpid()}.cmd")
        with open(script_path, "w", newline="\n") as f:
            f.write("@echo off\n")
            f.write("timeout /t 3 /nobreak >nul\n")
            f.write(f"rmdir /s /q \"{root}\"\n")
        subprocess.Popen(["cmd", "/c", script_path], shell=True)

    def deactivate_all_projects(self, cleanup=False, quit_after=False):
        threading.Thread(target=self._deactivate_all_worker, args=(cleanup, quit_after), daemon=True).start()

    def _deactivate_all_worker(self, cleanup, quit_after):
        drive_root = self._drive_root()
        if not drive_root:
            self.log("❌ Error: No Drive Path set in settings.", "red")
            return
        try:
            os.makedirs(drive_root, exist_ok=True)
        except Exception as e:
            self.log(f"❌ Error: Drive Path unavailable ({e})", "red")
            return

        root = os.getenv("LOCAL_WORKSPACE_ROOT", DEFAULT_WORKSPACE)
        reg = load_registry(self)
        local_names = [n for n, s in reg.items() if s == "Local"]
        if not local_names:
            self.log("ℹ️ No local projects to deactivate.")
        for name in local_names:
            local_path = os.path.join(root, name)
            dest_path = os.path.join(drive_root, name)
            if os.path.exists(local_path):
                self.log(f"☁️ Deactivating {name}...")
                self._robust_move_to_backup(local_path, dest_path, name)

        if cleanup and self._is_portable_mode():
            self.log("🧹 Scheduling self-cleanup...")
            self._schedule_self_cleanup()

        if quit_after:
            # Adding a small delay to ensure the cleanup script has time to be created
            self.after(1000, self.on_close)

    
    def _refresh_projects(self):
        for w in self.project_list.winfo_children(): w.destroy()

        root = os.getenv("LOCAL_WORKSPACE_ROOT", DEFAULT_WORKSPACE)
        if not os.path.exists(root): os.makedirs(root)
        
        drive_root = self._drive_root()
        hidden = [h.strip().lower() for h in os.getenv("HIDDEN_PROJECTS", "").split(",") if h.strip()]
        hidden.extend(["$recycle.bin", CLOUD_META_DIRNAME.lower()])

        # 1. Scan Local
        local_folders = {f for f in os.listdir(root) if os.path.isdir(os.path.join(root, f))}

        # 2. Scan Cloud (Drive)
        cloud_folders = set()
        if drive_root and os.path.exists(drive_root):
            try:
                cloud_folders = {f for f in os.listdir(drive_root) if os.path.isdir(os.path.join(drive_root, f))}
            except: pass

        # 3. Build Registry
        registry = {}
        # Start with what's in the saved registry files
        registry.update(self._load_cloud_reg())
        registry.update(self._load_local_reg())

        # Merge in actual folders found
        for f in local_folders:
            registry[f] = "Local"
        
        for f in cloud_folders:
            # If not already Local, it's Cloud
            if registry.get(f) != "Local":
                registry[f] = "Cloud"

        # Cleanup registry: if it's in registry but doesn't exist in either place, remove it
        # (Or keep it as 'Cloud' if you expect it might come back, but let's be clean)
        for name in list(registry.keys()):
            if name not in local_folders and name not in cloud_folders:
                # If it's not local and not in drive, it's effectively "Forgotten" unless manually added
                # But for now, let's keep everything found in the scan.
                pass

        self._save_reg(registry)

        for name in sorted(registry.keys()):
            if name.lower() in hidden: continue
            status = registry[name]
            # Create Card
            card = ProjectCard(self.project_list, self, name, status)
            self.project_cards[name] = card
        self.sync_to_firestore()


    def deactivate_project(self, name):
        card = self.project_cards.get(name)
        if card and card.busy:
            self.log(f"⚠️ Operation already in progress for {name}.")
            return

        if card:
            card.set_busy(True)

        def task():
            try:
                self.log(f"☁️ Deactivating {name}...")
                root = os.getenv("LOCAL_WORKSPACE_ROOT", DEFAULT_WORKSPACE)
                local_path = os.path.join(root, name)

                backup_path = self._drive_root()
                if not backup_path:
                    self.log("❌ Error: No Drive Path set in settings.", "red")
                    return
                try:
                    os.makedirs(backup_path, exist_ok=True)
                except Exception as e:
                    self.log(f"❌ Error: Drive Path unavailable ({e})", "red")
                    return

                dest_path = os.path.join(backup_path, name)
                self._robust_move_to_backup(local_path, dest_path, name)
            finally:
                if card:
                    self.after(0, lambda: card.set_busy(False))

        threading.Thread(target=task, daemon=True).start()

    def _copy_with_progress(self, src, dst):
        # Count files first for progress
        total_files = 0
        for root, dirs, files in os.walk(src):
            total_files += len(files)

        copied_files = 0

        def copy_progress(s, d):
            nonlocal copied_files
            shutil.copy2(s, d)
            copied_files += 1

            # Update visual progress bar and log text
            pct = copied_files / total_files if total_files > 0 else 0
            self.after(0, lambda: self.progress_bar.set(pct))

            if copied_files % max(1, int(total_files / 10)) == 0:
                 pct_int = int(pct * 100)
                 self.after(0, lambda: self.log(f"   ⏳ Syncing... {pct_int}% ({copied_files}/{total_files})"))

        shutil.copytree(src, dst, dirs_exist_ok=True, copy_function=copy_progress)
        self.after(0, lambda: self.progress_bar.set(0)) # Reset when done

    def _robust_move_to_backup(self, src, dst, name):
        try:
            # 1. Process External Resources (Move into project Assets folder)
            self._backup_project_resources(src)

            # 1.5 Uninstall unused software
            self._uninstall_software_if_unused(src, name)

            # 2. Copy Tree (Safely across drives)
            self.log(f"📤 Syncing to backup: {dst}")
            self._copy_with_progress(src, dst)

            # 3. Force Delete Local
            self.log(f"🗑️ Cleaning local storage (Force unlocking Git)...")
            shutil.rmtree(src, onerror=force_remove_readonly)

            self.log(f"✅ {name} Offloaded Successfully.")
            reg = load_registry(self); reg[name] = "Cloud"; self._save_reg(reg)
            self.after(0, self._refresh_projects)
            self.sync_to_firestore()
        except Exception as e:
            self.log(f"❌ Transfer Failed: {e}", "red")

    def activate_project(self, name):
        card = self.project_cards.get(name)
        if card and card.busy:
            self.log(f"⚠️ Operation already in progress for {name}.")
            return

        if card:
            card.set_busy(True)

        def task():
            try:
                self.log(f"🚀 Activating {name}...")
                root = os.getenv("LOCAL_WORKSPACE_ROOT", DEFAULT_WORKSPACE)
                local_path = os.path.join(root, name)
                root_backup = self._drive_root()
                if not root_backup:
                    self.log("❌ Error: No Drive Path set in settings.", "red")
                    return
                backup_path = os.path.join(root_backup, name)

                if not os.path.exists(backup_path):
                    self.log(f"❌ Backup not found at {backup_path}", "red")
                    return

                self._robust_move_to_local(backup_path, local_path, name)
            finally:
                if card:
                    self.after(0, lambda: card.set_busy(False))

        threading.Thread(target=task, daemon=True).start()

    def _robust_move_to_local(self, src, dst, name):
        try:
            self.log(f"⬇️ Restoring from {src}...")
            # We can use the same progress copy here
            self._copy_with_progress(src, dst)

            # Restore resources/installs
            self._restore_project_resources(dst)
            self._check_install_software(dst)

            # Delete Backup (Only if you want it moved, otherwise comment this)
            # shutil.rmtree(src, onerror=force_remove_readonly)

            self.log(f"✅ {name} Restored & Ready.")
            reg = load_registry(self); reg[name] = "Local"; self._save_reg(reg)
            self.after(0, self._refresh_projects)
            self.sync_to_firestore()
        except Exception as e:
            self.log(f"❌ Restore Failed: {e}", "red")

    # --- RESOURCE HANDLERS ---
    def _backup_project_resources(self, project_path):
        manifest = os.path.join(project_path, "omni.json")
        if not os.path.exists(manifest): return
        with open(manifest, "r") as f: data = json.load(f)
        assets_dir = os.path.join(project_path, "_omni_assets")
        if not os.path.exists(assets_dir): os.makedirs(assets_dir)

        # Load existing restore map or create a new one
        map_file = os.path.join(assets_dir, "restore_map.json")
        restore_map = self._load_json(map_file)

        paths_to_backup = []
        paths_to_backup.extend([(p, "External") for p in data.get("external_paths", [])])
        paths_to_backup.extend([(p, "App State") for p in data.get("app_state_paths", [])])

        for p, resource_type in paths_to_backup:
            if os.path.exists(p):
                pid = hashlib.md5(p.encode()).hexdigest()
                dest = os.path.join(assets_dir, pid)
                self.log(f"   > Moving {resource_type}: {p}")
                if os.path.isdir(p):
                    shutil.move(p, dest)
                else:
                    shutil.copy2(p, dest)
                    os.remove(p)
                restore_map[pid] = p

        self._save_json(map_file, restore_map)

    def _restore_project_resources(self, project_path):
        assets_dir = os.path.join(project_path, "_omni_assets")
        map_file = os.path.join(assets_dir, "restore_map.json")
        if not os.path.exists(map_file): return

        restore_map = self._load_json(map_file)

        for pid, original_path in restore_map.items():
            stored_path = os.path.join(assets_dir, pid)
            if os.path.exists(stored_path):
                self.log(f"   > Restoring resource: {original_path}")
                parent = os.path.dirname(original_path)
                try:
                    if not os.path.exists(parent): os.makedirs(parent)
                    shutil.move(stored_path, original_path)
                except Exception as e:
                    fallback_dir = os.path.join(assets_dir, "_restored")
                    os.makedirs(fallback_dir, exist_ok=True)
                    fallback_path = os.path.join(fallback_dir, pid)
                    shutil.move(stored_path, fallback_path)
                    self.log(f"   ⚠️ Restore failed, kept at {fallback_path} ({e})", "red")

        # Clean up the map so we don't restore twice.
        self._save_json(map_file, {})

        try:
            if not os.listdir(assets_dir) or os.listdir(assets_dir) == ["restore_map.json"]:
                shutil.rmtree(assets_dir)
        except Exception:
            pass

    def _check_install_software(self, project_path):
        manifest = os.path.join(project_path, "omni.json")
        if not os.path.exists(manifest): return
        with open(manifest, "r") as f: data = json.load(f)
        for app in data.get("software", []):
            self.log(f"   > Checking Software: {app}")
            try:
                res = subprocess.run(["winget", "list", "-e", "--id", app], capture_output=True, text=True)
                if "No installed package found" in res.stdout:
                    self.log(f"   ⬇️ Auto-Installing {app}...")
                    subprocess.run(["winget", "install", "-e", "--id", app, "--silent"], shell=True)      
            except: pass

    def _uninstall_software_if_unused(self, project_path, name):
        manifest_path = os.path.join(project_path, "omni.json")
        if not os.path.exists(manifest_path):
            return

        with open(manifest_path, "r") as f:
            data = json.load(f)

        software_to_uninstall = data.get("software", [])
        if not software_to_uninstall:
            return

        # Get all other active projects
        root = os.getenv("LOCAL_WORKSPACE_ROOT", DEFAULT_WORKSPACE)
        all_projects = load_registry(self)
        other_active_projects = [p for p, s in all_projects.items() if s == "Local" and p != name]        

        # Get all software dependencies from other active projects
        other_dependencies = set()
        for project_name in other_active_projects:
            other_manifest_path = os.path.join(root, project_name, "omni.json")
            if os.path.exists(other_manifest_path):
                with open(other_manifest_path, "r") as f:
                    other_data = json.load(f)
                for s in other_data.get("software", []):
                    other_dependencies.add(s)

        # Uninstall software if it's not a dependency of any other active project
        for app in software_to_uninstall:
            if app not in other_dependencies:
                self.log(f"   > Uninstalling {app}...")
                try:
                    subprocess.run(["winget", "uninstall", "-e", "--id", app, "--silent"], shell=True)    
                except Exception as e:
                    self.log(f"   > Failed to uninstall {app}: {e}", "red")
            else:
                self.log(f"   > Skipping uninstall for {app} (in use by another project).")


    def _restart_remote_agent(self):
        """Stop the current agent and start a new one with updated config."""
        self.log("🔄 Restarting Remote Agent...")
        if self.agent_process:
            try:
                self.agent_process.terminate()
                self.agent_process.wait(timeout=5)
            except Exception:
                try:
                    self.agent_process.kill()
                except Exception:
                    pass
            self.agent_process = None
        self._start_remote_agent()

    def _start_remote_agent(self):
        agent_cmd = None

        # Prefer packaged agent when running from a bundled exe.
        if getattr(sys, "frozen", False):
            agent_candidates = [
                os.path.join(BASE_DIR, "OmniRemoteAgent.exe"),
                os.path.join(BASE_DIR, "OmniRemoteAgentPortable.exe"),
            ]
            for candidate in agent_candidates:
                if os.path.exists(candidate):
                    agent_cmd = [candidate]
                    break

        # Fallback to Python script in source mode.
        if agent_cmd is None:
            agent_script = os.path.join(BASE_DIR, "src", "remote_agent.py")
            if os.path.exists(agent_script):
                agent_cmd = [sys.executable, agent_script]

        if agent_cmd:
            self.log("🚀 Starting Remote Agent...")
            threading.Thread(target=self._run_agent_worker, args=(agent_cmd,), daemon=True).start()
        else:
            self.log("⚠️ Remote Agent not found.", "red")

    def _run_agent_worker(self, agent_cmd):
        try:
            import subprocess
            # Start the agent as a subprocess
            self.agent_process = subprocess.Popen(
                agent_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1
            )
            # Log output in real-time
            for line in self.agent_process.stdout:
                if "listening on" in line or "error" in line.lower():
                    self.log(f"📡 Agent: {line.strip()}")
            self.agent_process.wait()
        except Exception as e:
            self.log(f"⚠️ Remote Agent error: {e}", "red")

    # --- GUI ACTIONS ---
    def open_studio(self, n):
        p = os.path.join(os.getenv("LOCAL_WORKSPACE_ROOT", DEFAULT_WORKSPACE), n)
        for s in [r"C:\\Program Files\\Android\\Android Studio\\bin\\studio64.exe", os.path.expandvars(r"%LOCALAPPDATA%\\Android\\Android Studio\\bin\\studio64.exe")]:
            if os.path.exists(s): subprocess.Popen([s, p], shell=True); return
        self.log("❌ Studio not found.", "red")

    def open_antigravity(self, n):
        try: subprocess.Popen(["python", "-m", "antigravity"], shell=True)
        except: pass

    def forget_project(self, name):
        reg = load_registry(self); reg.pop(name, None); self._save_reg(reg); self._refresh_projects()        

    def log(self, m, col=None):
        self.log_box.configure(state="normal"); self.log_box.insert("end", f"[{datetime.datetime.now().strftime('%H:%M:%S')}] {m}\n"); self.log_box.see("end"); self.log_box.configure(state="disabled")

    def on_close(self):
        if os.getenv(PORTABLE_AUTO_CLEAN_ENV, "").strip() == "1":
            self._schedule_self_cleanup()
        if self.tray_icon: self.tray_icon.stop()
        self.quit()

    def _start_tray_icon(self):
        try:
            img = Image.open(ICON_PATH)
            items = [pystray.MenuItem("Show", lambda i, it: self.queue.put("deiconify"))]
            if self._is_portable_mode():
                items.append(pystray.MenuItem("Deactivate + Cleanup", lambda i, it: self.deactivate_all_projects(cleanup=True, quit_after=True)))
            items.append(pystray.MenuItem("Quit", lambda i, it: self.queue.put("quit")))
            self.tray_icon = pystray.Icon("OmniSync", img, menu=pystray.Menu(*items))
            import threading
            threading.Thread(target=self.tray_icon.run, daemon=True).start()
        except: pass
    def show_new_project(self):
        d=ctk.CTkInputDialog(text="Name:", title="New Project"); bring_to_front(d, self); n=d.get_input() 
        if n: os.makedirs(os.path.join(os.getenv("LOCAL_WORKSPACE_ROOT", DEFAULT_WORKSPACE), n), exist_ok=True); self._refresh_projects()

    def _ensure_visible(self):
        try:
            self.update_idletasks()
            self.state("normal")
            self.deiconify()
            self.attributes("-alpha", 1.0)
            w = max(self.winfo_width(), 360)
            h = max(self.winfo_height(), 800)
            sw = self.winfo_screenwidth()
            sh = self.winfo_screenheight()
            x = max(0, int((sw - w) / 2))
            y = max(0, int((sh - h) / 2))
            self.geometry(f"{w}x{h}+{x}+{y}")
            self.lift()
            self.attributes("-topmost", True)
            self.after(200, lambda: self.attributes("-topmost", False))
            log_startup("Ensured main window visible")
        except Exception as e:
            log_startup(f"Ensure visible failed: {e}")

if __name__ == "__main__":
    try:
        if getattr(sys, "frozen", False):
            hide_console_window()
        log_startup("Starting OmniProjectSync...")
        app = ProjectManagerApp()
        app.protocol("WM_DELETE_WINDOW", app.on_close)
        app.mainloop()
    except Exception as e:
        log_startup(f"FATAL: {e}")
        log_startup(traceback.format_exc())
        try:
            import tkinter.messagebox as mb
            mb.showerror("OmniProjectSync Error", str(e))
        except Exception:
            pass

