import asyncio
import datetime
import hashlib
import json
import os
import re
import secrets
import shutil
import socket
import stat
import subprocess
import threading
import time
import uuid
import sys
from typing import Callable, Dict, Optional
from urllib.parse import urlparse

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
import firebase_admin
from firebase_admin import credentials, firestore
from starlette.concurrency import run_in_threadpool

APP_NAME = "OmniProjectSync Remote Agent"
VERSION = "4.7.0"
def get_base_dir() -> str:
    # When packaged (PyInstaller), anchor config next to the executable.
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


BASE_DIR = get_base_dir()
ENV_PATH = os.path.join(BASE_DIR, "secrets.env")
CONFIG_DIR = os.path.join(BASE_DIR, "config")
LOCAL_REGISTRY_PATH = os.path.join(CONFIG_DIR, "project_registry.json")

DEFAULT_WORKSPACE = r"C:\\Projects"
PROTECTED_PATHS = [r"C:\\Windows", r"C:\\Program Files", r"C:\\Program Files (x86)", r"C:\\"]

CLOUD_META_DIRNAME = "_omni_sync"
CLOUD_REGISTRY_FILENAME = "project_registry.json"

LOG_PATH = os.path.join(CONFIG_DIR, "remote_agent.log")

load_dotenv(ENV_PATH)


def _int_env(name: str, default: int) -> int:
    """Read integer env var with safe fallback for blank/invalid values."""
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def save_env_setting(key: str, value: str) -> None:
    """Persist env setting to secrets.env for other modules (sync UI, plugin)."""
    try:
        value = str(value).replace('\0', '').strip()
        lines = []
        found = False
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
            except Exception:
                pass
        if not found:
            lines.append(f"{key}={value}")
        os.makedirs(os.path.dirname(ENV_PATH), exist_ok=True)
        with open(ENV_PATH, 'w', encoding='utf-8') as f:
            f.write("\n".join(lines) + "\n")
        os.environ[key] = value
    except Exception:
        pass

REMOTE_BIND_HOST = os.getenv("REMOTE_BIND_HOST", "0.0.0.0")  # Default to all interfaces
REMOTE_PUBLIC_HOST = os.getenv("REMOTE_PUBLIC_HOST", "")  # Will be auto-set by tunnel
REMOTE_PORT = _int_env("REMOTE_PORT", 8765)
IDE_PORT = _int_env("IDE_PORT", 8766)
REMOTE_ACCESS_TOKEN = os.getenv("REMOTE_ACCESS_TOKEN", "")  # Will be fetched from Firebase
REMOTE_SHELL = os.getenv("REMOTE_SHELL", "powershell.exe")
REMOTE_DEFAULT_CWD = os.getenv("REMOTE_DEFAULT_CWD", BASE_DIR)
REMOTE_ALLOWED_ROOTS = [p.strip() for p in os.getenv("REMOTE_ALLOWED_ROOTS", "").split(";") if p.strip()] 

LOCAL_WORKSPACE_ROOT = os.getenv("LOCAL_WORKSPACE_ROOT", DEFAULT_WORKSPACE)
DRIVE_ROOT_FOLDER_ID = os.getenv("DRIVE_ROOT_FOLDER_ID", "")
HIDDEN_PROJECTS = [h.strip().lower() for h in os.getenv("HIDDEN_PROJECTS", "").split(",") if h.strip()]   

# Performance Optimization: Pre-calculate absolute paths
ABS_LOCAL_WORKSPACE_ROOT = os.path.abspath(LOCAL_WORKSPACE_ROOT)
ABS_REMOTE_ALLOWED_ROOTS = [os.path.abspath(p) for p in REMOTE_ALLOWED_ROOTS]
ABS_PROTECTED_PATHS = [os.path.abspath(p) for p in PROTECTED_PATHS]

# Initialize Firebase
FIREBASE_PROJECT_ID = os.getenv("FIREBASE_PROJECT_ID", "omniremote-e7afd")

# ============================================================================
# CLOUDFLARE TUNNEL MANAGER
# ============================================================================

class CloudflareTunnel:
    """Manages cloudflared quick tunnel for zero-config remote access"""

    def __init__(self, port: int):
        self.port = port
        self.process: Optional[subprocess.Popen] = None
        self.tunnel_url: Optional[str] = None
        self._stop_event = threading.Event()
        self._output_thread: Optional[threading.Thread] = None
        self._ready_event = threading.Event()
        self._on_ready: Optional[Callable[[str], None]] = None
        self._url_pattern = re.compile(r'https://[a-z0-9-]+\.trycloudflare\.com')

    def find_cloudflared(self) -> Optional[str]:
        """Find cloudflared executable in common locations"""
        locations = [
            r"C:\Program Files (x86)\cloudflared\cloudflared.exe",
            r"C:\Program Files\cloudflared\cloudflared.exe",
            os.path.expandvars(r"%LOCALAPPDATA%\cloudflared\cloudflared.exe"),
            os.path.expandvars(r"%USERPROFILE%\cloudflared\cloudflared.exe"),
            os.path.join(BASE_DIR, "cloudflared.exe"),
            "cloudflared",  # Try PATH
        ]

        for loc in locations:
            try:
                expanded = os.path.expandvars(loc)
                result = subprocess.run(
                    [expanded, "version"],
                    capture_output=True,
                    timeout=5,
                    creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0
                )
                if result.returncode == 0:
                    print(f"[tunnel] Found cloudflared at: {expanded}")
                    return expanded
            except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
                continue
        return None

    def start(self, on_ready: Optional[Callable[[str], None]] = None, wait_timeout: int = 30) -> Optional[str]:
        """Start tunnel and return URL when available (non-blocking beyond wait_timeout)."""
        cloudflared = self.find_cloudflared()
        if not cloudflared:
            print("[tunnel] ERROR: cloudflared not found!")
            print("[tunnel] Install: winget install Cloudflare.cloudflared")
            return None

        try:
            print(f"[tunnel] Starting cloudflared tunnel for port {self.port}...")
            creationflags = subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0
            self.process = subprocess.Popen(
                [cloudflared, "tunnel", "--url", f"http://localhost:{self.port}"],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                creationflags=creationflags
            )
            self._on_ready = on_ready
            self._output_thread = threading.Thread(target=self._read_output, daemon=True)
            self._output_thread.start()

            # Wait briefly for the URL (but keep tunnel alive even if it takes longer).
            if self._ready_event.wait(timeout=wait_timeout):
                return self.tunnel_url
            print(f"[tunnel] Waiting for URL... (continuing in background)")
            return None
        except Exception as e:
            print(f"[tunnel] ERROR: {e}")
            return None

    def _read_output(self):
        try:
            for line in self.process.stdout:
                if self._stop_event.is_set():
                    break
                line = line.strip()
                if not line:
                    continue
                print(f"[tunnel] {line}")
                if self.tunnel_url is None:
                    match = self._url_pattern.search(line)
                    if match:
                        self.tunnel_url = match.group(0)
                        print(f"[tunnel] SUCCESS: Tunnel at {self.tunnel_url}")
                        self._ready_event.set()
                        if self._on_ready:
                            try:
                                self._on_ready(self.tunnel_url)
                            except Exception:
                                pass
                        continue
                if ("ERR" in line or "error" in line.lower()):
                    # Already printed above; no extra action needed.
                    pass
        except Exception:
            pass

    def stop(self):
        self._stop_event.set()
        if self.process:
            try:
                print("[tunnel] Stopping tunnel...")
                self.process.terminate()
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
            except Exception:
                pass
            self.process = None
            self.tunnel_url = None
            print("[tunnel] Tunnel stopped")

    @property
    def is_running(self) -> bool:
        return self.process is not None and self.process.poll() is None


# Global tunnel instance
_tunnel: Optional[CloudflareTunnel] = None

# ============================================================================
# FIREBASE INITIALIZATION
# ============================================================================

def resolve_credentials_path(path: Optional[str]) -> Optional[str]:
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

try:
    cred_path = resolve_credentials_path(os.getenv("GOOGLE_APPLICATION_CREDENTIALS"))
    if cred_path:
        cred = credentials.Certificate(cred_path)
        firebase_admin.initialize_app(cred, {'projectId': FIREBASE_PROJECT_ID})
        db = firestore.client()
        print("[remote-agent] Firebase initialized.")
    else:
        db = None
        print("[remote-agent] Firebase not initialized (Credentials path not set).")
except Exception as e:
    db = None
    print(f"[firebase] Firebase initialization failed: {e}")


def get_firebase_uid() -> Optional[str]:
    """Get Firebase UID from environment"""
    uid = os.getenv("FIREBASE_UID")
    if not uid:
        doc_path = os.getenv("FIREBASE_DOCUMENT_PATH", "")
        if doc_path.startswith("users/") and "/" in doc_path:
            uid = doc_path.split("/", 2)[1]
    return uid


def get_or_create_shared_token(uid: str) -> Optional[str]:
    """Get existing shared token from Firebase or create new one"""
    global REMOTE_ACCESS_TOKEN

    if not db:
        print("[firebase] Cannot get token - Firebase not initialized")
        return None

    try:
        doc_ref = db.collection("users").document(uid)
        doc = doc_ref.get()

        if doc.exists:
            data = doc.to_dict()
            existing_token = data.get("token")
            if existing_token:
                print("[firebase] Using existing shared token from Firebase")
                REMOTE_ACCESS_TOKEN = existing_token
                return existing_token

        # No token exists - create new one
        new_token = secrets.token_urlsafe(32)
        doc_ref.set({"token": new_token}, merge=True)
        print("[firebase] Generated new shared token and saved to Firebase")
        REMOTE_ACCESS_TOKEN = new_token
        return new_token

    except Exception as e:
        print(f"[firebase] Failed to get/create token: {e}")
        if not REMOTE_ACCESS_TOKEN:
            REMOTE_ACCESS_TOKEN = secrets.token_urlsafe(32)
            print("[firebase] Using locally generated token (not synced)")
        return REMOTE_ACCESS_TOKEN


def get_local_ip() -> str:
    """Get local network IP address"""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"

def is_port_available(host: str, port: int) -> bool:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind((host, port))
        return True
    except Exception:
        return False

def pick_available_port(host: str, preferred: int) -> int:
    if is_port_available(host, preferred):
        return preferred
    for offset in range(1, 20):
        candidate = preferred + offset
        if is_port_available(host, candidate):
            return candidate
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind((host, 0))
            return int(s.getsockname()[1])
    except Exception:
        return preferred


def sync_to_firestore():
    """Sync connection info and projects to Firestore"""
    global REMOTE_ACCESS_TOKEN

    if not db:
        return

    uid = get_firebase_uid()
    if not uid:
        print("[firebase] FIREBASE_UID not set. Skipping sync.")
        return

    try:
        # Determine host and connection mode
        tunnel_url = _tunnel.tunnel_url if _tunnel else None
        local_ip = get_local_ip()

        if tunnel_url:
            # Use tunnel - extract hostname
            parsed = urlparse(tunnel_url)
            public_host = parsed.netloc
            use_port = 443
            use_secure = True
            print(f"[firebase] Syncing tunnel URL: {tunnel_url}")
        elif REMOTE_PUBLIC_HOST:
            # Manual public host configured
            public_host = REMOTE_PUBLIC_HOST
            use_port = REMOTE_PORT
            use_secure = not public_host[0].isdigit()
            print(f"[firebase] Syncing manual host: {public_host}")
        else:
            # Local IP only
            public_host = local_ip
            use_port = REMOTE_PORT
            use_secure = False
            print(f"[firebase] Syncing local IP: {local_ip}:{REMOTE_PORT}")

        # Connection data
        conn_data = {
            "host": public_host,
            "pmPort": use_port,
            "idePort": use_port,
            "token": REMOTE_ACCESS_TOKEN,
            "secure": use_secure,
            "tunnelUrl": tunnel_url or "",
            "localIp": local_ip,
            "localPort": REMOTE_PORT,
            "online": True,
            "updated_at": firestore.SERVER_TIMESTAMP,
            "agent": "python-agent",
            "version": VERSION
        }

        user_ref = db.collection("users").document(uid)
        user_ref.set(conn_data, merge=True)
        user_ref.collection("config").document("connection").set(conn_data, merge=True)

        # Sync projects
        registry = compute_registry()
        projects_ref = user_ref.collection("projects")
        batch = db.batch()

        for name, status in registry.items():
            if name.lower() in HIDDEN_PROJECTS:
                continue

            project_path = os.path.join(LOCAL_WORKSPACE_ROOT, name) if status == "Local" else os.path.join(DRIVE_ROOT_FOLDER_ID or "", name)
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
                except Exception:
                    pass

            doc_ref = projects_ref.document(name)
            batch.set(doc_ref, project_data, merge=True)

        batch.commit()
        print(f"[firebase] Synced: host={public_host}, secure={use_secure}, projects={len(registry)}")

    except Exception as e:
        print(f"[firebase] Firestore sync failed: {e}")


def set_offline_status():
    """Mark agent as offline in Firebase"""
    if not db:
        return

    uid = get_firebase_uid()
    if not uid:
        return

    try:
        offline_data = {
            "online": False,
            "updated_at": firestore.SERVER_TIMESTAMP
        }
        user_ref = db.collection("users").document(uid)
        user_ref.set(offline_data, merge=True)
        user_ref.collection("config").document("connection").set(offline_data, merge=True)
        print("[firebase] Marked as offline")
    except Exception as e:
        print(f"[firebase] Failed to set offline status: {e}")




app = FastAPI(title=APP_NAME, version=VERSION)

_sessions_lock = threading.Lock()
_sessions: Dict[str, "CommandSession"] = {}

_project_locks_lock = threading.Lock()
_project_locks: Dict[str, threading.Lock] = {}

_registry_lock = threading.Lock()
_registry_cache: Optional[Dict[str, str]] = None
_registry_mtime: float = 0.0


def log(msg: str) -> None:
    os.makedirs(CONFIG_DIR, exist_ok=True)
    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}\n"
    try:
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write(line)
    except Exception:
        pass


def require_token_from_request(request: Request) -> None:
    token = request.headers.get("X-Omni-Token")
    if not token:
        auth = request.headers.get("Authorization", "")
        if auth.lower().startswith("bearer "):
            token = auth.split(" ", 1)[1].strip()
    if token is None or not secrets.compare_digest(token, REMOTE_ACCESS_TOKEN):
        raise HTTPException(status_code=401, detail="Unauthorized")


def require_token_from_ws(ws: WebSocket) -> None:
    token = ws.headers.get("X-Omni-Token") or ws.query_params.get("token")
    if token is None or not secrets.compare_digest(token, REMOTE_ACCESS_TOKEN):
        raise HTTPException(status_code=401, detail="Unauthorized")


def get_project_lock(name: str) -> threading.Lock:
    with _project_locks_lock:
        if name not in _project_locks:
            _project_locks[name] = threading.Lock()
        return _project_locks[name]

def is_path_safe(path: str) -> bool:
    if not path:
        return False
    abs_path = os.path.abspath(path)
    # Always allow the workspace root and its children.
    if abs_path == ABS_LOCAL_WORKSPACE_ROOT or abs_path.startswith(ABS_LOCAL_WORKSPACE_ROOT + os.sep):
        return True
    # If allowed roots are defined, enforce them.
    if ABS_REMOTE_ALLOWED_ROOTS:
        for root_abs in ABS_REMOTE_ALLOWED_ROOTS:
            if abs_path == root_abs or abs_path.startswith(root_abs + os.sep):
                return True
        return False
    # Otherwise block only obviously dangerous roots.
    for p_abs in ABS_PROTECTED_PATHS:
        if abs_path == p_abs or abs_path.startswith(p_abs + os.sep):
            return False
    return True

def load_registry() -> Dict[str, str]:
    global _registry_cache, _registry_mtime
    if not os.path.exists(LOCAL_REGISTRY_PATH):
        return {}
    try:
        mtime = os.path.getmtime(LOCAL_REGISTRY_PATH)
        if _registry_cache is not None and mtime == _registry_mtime:
            return _registry_cache.copy()

        with open(LOCAL_REGISTRY_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
            _registry_cache = data
            _registry_mtime = mtime
            return data.copy()
    except Exception:
        return {}

def save_registry(registry: Dict[str, str]) -> None:
    global _registry_cache, _registry_mtime
    os.makedirs(CONFIG_DIR, exist_ok=True)
    with open(LOCAL_REGISTRY_PATH, "w", encoding="utf-8") as f:
        json.dump(registry, f, indent=2)

    _registry_cache = registry.copy()
    try:
        _registry_mtime = os.path.getmtime(LOCAL_REGISTRY_PATH)
    except Exception:
        _registry_mtime = 0.0

def compute_registry() -> Dict[str, str]:
    with _registry_lock:
        os.makedirs(LOCAL_WORKSPACE_ROOT, exist_ok=True)
        local_folders = set()
        # Optimization: Use os.scandir to avoid multiple system calls for isdir checks
        with os.scandir(LOCAL_WORKSPACE_ROOT) as it:
            for entry in it:
                if entry.is_dir():
                    local_folders.add(entry.name)

        registry = load_registry()
        original_registry = registry.copy()

        for name in local_folders:
            registry[name] = "Local"
        for name in list(registry.keys()):
            if name not in local_folders:
                registry[name] = "Cloud"

        if registry != original_registry:
            save_registry(registry)
        return registry

def force_remove_readonly(func, path, excinfo):
    try:
        os.chmod(path, stat.S_IWRITE)
    except Exception:
        pass
    func(path)

def backup_external_resources(project_path: str) -> None:
    manifest = os.path.join(project_path, "omni.json")
    if not os.path.exists(manifest):
        return
    try:
        with open(manifest, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return
    assets_dir = os.path.join(project_path, "_omni_assets")
    os.makedirs(assets_dir, exist_ok=True)
    restore_map = {}
    for p in data.get("external_paths", []):
        if os.path.exists(p):
            pid = hashlib.md5(p.encode()).hexdigest()
            dest = os.path.join(assets_dir, pid)
            log(f"Backup external resource: {p}")
            if os.path.isdir(p):
                shutil.move(p, dest)
            else:
                shutil.copy2(p, dest)
                os.remove(p)
            restore_map[pid] = p
    with open(os.path.join(assets_dir, "restore_map.json"), "w", encoding="utf-8") as f:
        json.dump(restore_map, f, indent=2)

def restore_external_resources(project_path: str) -> None:
    assets_dir = os.path.join(project_path, "_omni_assets")
    map_file = os.path.join(assets_dir, "restore_map.json")
    if not os.path.exists(map_file):
        return
    try:
        with open(map_file, "r", encoding="utf-8") as f:
            restore_map = json.load(f)
    except Exception:
        return
    for pid, original_path in restore_map.items():
        stored_path = os.path.join(assets_dir, pid)
        if os.path.exists(stored_path):
            log(f"Restore external resource: {original_path}")
            parent = os.path.dirname(original_path)
            try:
                os.makedirs(parent, exist_ok=True)
                shutil.move(stored_path, original_path)
            except Exception as e:
                fallback_dir = os.path.join(assets_dir, "_restored")
                os.makedirs(fallback_dir, exist_ok=True)
                fallback_path = os.path.join(fallback_dir, pid)
                shutil.move(stored_path, fallback_path)
                log(f"Restore failed; kept at {fallback_path} ({e})")
    try:
        remaining = os.listdir(assets_dir)
        if not remaining or remaining == ["restore_map.json"]:
            shutil.rmtree(assets_dir)
    except Exception:
        pass

def check_install_software(project_path: str) -> None:
    manifest = os.path.join(project_path, "omni.json")
    if not os.path.exists(manifest):
        return
    try:
        with open(manifest, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return
    for app_id in data.get("software", []):
        log(f"Check software: {app_id}")
        try:
            res = subprocess.run([
                "winget", "list", "-e", "--id", app_id
            ], capture_output=True, text=True)
            if "No installed package found" in res.stdout:
                log(f"Auto-install software: {app_id}")
                subprocess.run([
                    "winget", "install", "-e", "--id", app_id, "--silent"
                ])
        except Exception:
            pass

def copy_tree(src: str, dst: str) -> None:
    shutil.copytree(src, dst, dirs_exist_ok=True)

def find_android_studio() -> Optional[str]:
    candidates = [
        r"C:\\Program Files\\Android\\Android Studio\\bin\\studio64.exe",
        os.path.expandvars(r"%LOCALAPPDATA%\\Android\\Android Studio\\bin\\studio64.exe"),
    ]
    for path in candidates:
        if os.path.exists(path):
            return path
    return None

def open_studio_project(name: str) -> Dict[str, str]:
    project_path = os.path.join(LOCAL_WORKSPACE_ROOT, name)
    if not os.path.exists(project_path):
        return {"status": "error", "message": "Project not found"}
    if not is_path_safe(project_path):
        return {"status": "error", "message": "Unsafe project path"}
    studio = find_android_studio()
    if not studio:
        return {"status": "error", "message": "Android Studio not found"}
    try:
        subprocess.Popen([studio, project_path])
    except Exception as e:
        return {"status": "error", "message": str(e)}
    return {"status": "ok", "message": "Studio launched"}

def deactivate_project(name: str) -> Dict[str, str]:
    lock = get_project_lock(name)
    with lock:
        local_path = os.path.join(LOCAL_WORKSPACE_ROOT, name)
        if not os.path.exists(local_path):
            return {"status": "error", "message": "Project not found locally"}
        if not DRIVE_ROOT_FOLDER_ID:
            return {"status": "error", "message": "DRIVE_ROOT_FOLDER_ID not configured"}
        if not is_path_safe(local_path):
            return {"status": "error", "message": "Unsafe project path"}
        dest_path = os.path.join(DRIVE_ROOT_FOLDER_ID, name)
        os.makedirs(DRIVE_ROOT_FOLDER_ID, exist_ok=True)
        log(f"Deactivate project: {name}")
        backup_external_resources(local_path)
        copy_tree(local_path, dest_path)
        shutil.rmtree(local_path, onerror=force_remove_readonly)
        reg = compute_registry()
        reg[name] = "Cloud"
        save_registry(reg)
        return {"status": "ok", "message": "Deactivated"}

def activate_project(name: str) -> Dict[str, str]:
    lock = get_project_lock(name)
    with lock:
        if not DRIVE_ROOT_FOLDER_ID:
            return {"status": "error", "message": "DRIVE_ROOT_FOLDER_ID not configured"}
        backup_path = os.path.join(DRIVE_ROOT_FOLDER_ID, name)
        local_path = os.path.join(LOCAL_WORKSPACE_ROOT, name)
        if not os.path.exists(backup_path):
            return {"status": "error", "message": "Backup not found"}
        if not is_path_safe(local_path):
            return {"status": "error", "message": "Unsafe project path"}
        os.makedirs(LOCAL_WORKSPACE_ROOT, exist_ok=True)
        log(f"Activate project: {name}")
        copy_tree(backup_path, local_path)
        restore_external_resources(local_path)
        check_install_software(local_path)
        reg = compute_registry()
        reg[name] = "Local"
        save_registry(reg)
        return {"status": "ok", "message": "Activated"}


class CommandSession:
    def __init__(self, session_id: str, ws: WebSocket):
        self.session_id = session_id
        self.ws = ws
        self.started = datetime.datetime.now()

class LocalSession(CommandSession):
    def __init__(self, session_id: str, proc: subprocess.Popen, ws: WebSocket):
        super().__init__(session_id, ws)
        self.proc = proc

class IDESession(CommandSession):
    def __init__(self, session_id: str, ws: WebSocket, ide_ws):
        super().__init__(session_id, ws)
        self.ide_ws = ide_ws
        self.ide_session_id = None


async def start_ide_proxy_session(loop: asyncio.AbstractEventLoop, ws: WebSocket, run_data: dict) -> str:
    import websockets
    session_id = str(uuid.uuid4())
    
    ide_ws = await websockets.connect(f"ws://127.0.0.1:{IDE_PORT}/ws/terminal?token={REMOTE_ACCESS_TOKEN}")
    await ide_ws.send(json.dumps(run_data))
    
    session = IDESession(session_id, ws, ide_ws)
    with _sessions_lock:
        _sessions[session_id] = session

    async def relay():
        try:
            async for msg in ide_ws:
                try:
                    data = json.loads(msg)
                except Exception:
                    await ws.send_text(msg)
                    continue

                msg_type = data.get("type")
                if msg_type == "started":
                    session.ide_session_id = data.get("sessionId")
                    # Agent already emitted a "started" with its own sessionId.
                    continue

                if "sessionId" in data:
                    data["sessionId"] = session_id

                await ws.send_text(json.dumps(data))

                if msg_type == "exit":
                    break
        except Exception:
            pass
        finally:
            with _sessions_lock:
                _sessions.pop(session_id, None)
            try:
                await ide_ws.close()
            except Exception:
                pass

    asyncio.create_task(relay())
    return session_id


async def send_ws(ws: WebSocket, payload: Dict[str, str]) -> None: 
    try:
        await ws.send_text(json.dumps(payload))
    except Exception:
        pass

def start_command(loop: asyncio.AbstractEventLoop, ws: WebSocket, cmd: str, cwd: Optional[str], env_overrides: Optional[Dict[str, str]]) -> str:
    session_id = str(uuid.uuid4())
    safe_cwd = cwd or REMOTE_DEFAULT_CWD
    if safe_cwd and not is_path_safe(safe_cwd):
        raise HTTPException(status_code=400, detail="Unsafe working directory")

    env = os.environ.copy()
    if env_overrides:
        env.update(env_overrides)

    proc = subprocess.Popen(
        cmd,
        cwd=safe_cwd,
        env=env,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        shell=True,
    )

    session = LocalSession(session_id, proc, ws)
    with _sessions_lock:
        _sessions[session_id] = session

    def reader():
        try:
            for line in proc.stdout:
                asyncio.run_coroutine_threadsafe(
                    send_ws(ws, {"type": "output", "sessionId": session_id, "data": line}),
                    loop,
                )
        except Exception:
            pass
        finally:
            code = proc.poll()
            asyncio.run_coroutine_threadsafe(
                send_ws(ws, {"type": "exit", "sessionId": session_id, "code": str(code) if code is not None else ""}),
                loop,
            )
            with _sessions_lock:
                _sessions.pop(session_id, None)

    thread = threading.Thread(target=reader, daemon=True)
    thread.start()
    return session_id



async def proxy_to_plugin(method: str, path: str, body: dict = None, params: dict = None):
    import httpx
    url = f"http://127.0.0.1:{IDE_PORT}{path}"
    headers = {"X-Omni-Token": REMOTE_ACCESS_TOKEN}
    async with httpx.AsyncClient() as client:
        if method == "GET":
            return await client.get(url, headers=headers, params=params)
        elif method == "POST":
            return await client.post(url, headers=headers, json=body, params=params)

@app.get("/api/health")
async def health(request: Request):
    require_token_from_request(request)
    return {
        "status": "ok",
        "app": APP_NAME,
        "version": VERSION,
        "time": datetime.datetime.now().isoformat(),
        "tunnel": _tunnel.tunnel_url if _tunnel else None,
    }



@app.get("/api/projects/ide")
async def api_ide_projects(request: Request):
    require_token_from_request(request)
    try:
        resp = await proxy_to_plugin("GET", "/api/projects")
        return resp.json()
    except Exception as e:
        return {"projects": [], "error": str(e)}

@app.post("/api/projects/ide/close")
async def api_ide_close_project(request: Request):
    require_token_from_request(request)
    data = await request.json()
    name = data.get("name")
    try:
        resp = await proxy_to_plugin("POST", "/api/close-project", params={"name": name})
        return resp.json()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/projects")
async def get_projects(request: Request):
    require_token_from_request(request)
    registry = await run_in_threadpool(compute_registry)
    projects = []
    for name, status in sorted(registry.items()):
        if name.lower() in HIDDEN_PROJECTS:
            continue
        projects.append({"name": name, "status": status})
    return {"projects": projects}


@app.post("/api/projects/{name}/activate")
async def api_activate_project(name: str, request: Request):
    require_token_from_request(request)
    loop = asyncio.get_running_loop()
    result = await loop.run_in_executor(None, activate_project, name)
    if result.get("status") != "ok":
        raise HTTPException(status_code=400, detail=result.get("message"))
    await run_in_threadpool(sync_to_firestore)
    return result


@app.post("/api/projects/{name}/deactivate")
async def api_deactivate_project(name: str, request: Request):
    require_token_from_request(request)
    result = await run_in_threadpool(deactivate_project, name)
    if result.get("status") != "ok":
        raise HTTPException(status_code=400, detail=result.get("message"))
    await run_in_threadpool(sync_to_firestore)
    return result


@app.post("/api/projects/{name}/open-studio")
async def api_open_studio_project(name: str, request: Request):
    require_token_from_request(request)
    result = open_studio_project(name)
    if result.get("status") != "ok":
        raise HTTPException(status_code=400, detail=result.get("message"))
    await run_in_threadpool(sync_to_firestore)
    return result


@app.post("/api/command")
async def api_command(request: Request):
    require_token_from_request(request)
    payload = await request.json()
    cmd = payload.get("cmd")
    cwd = payload.get("cwd") or REMOTE_DEFAULT_CWD
    if not cmd:
        raise HTTPException(status_code=400, detail="cmd is required")
    if cwd and not is_path_safe(cwd):
        raise HTTPException(status_code=400, detail="Unsafe working directory")
    log(f"Command: {cmd} (cwd={cwd})")
    try:
        proc = await asyncio.create_subprocess_shell(
            cmd,
            cwd=cwd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        stdout_str = stdout.decode("utf-8", errors="replace") if stdout else ""
        stderr_str = stderr.decode("utf-8", errors="replace") if stderr else ""

        output = stdout_str + ("\n" + stderr_str if stderr_str else "")
        if len(output) > 20000:
            output = output[:20000] + "\n...truncated..."
        return {"status": "ok", "code": proc.returncode, "output": output}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.websocket("/ws/terminal")
async def ws_terminal(ws: WebSocket):
    try:
        require_token_from_ws(ws)
    except HTTPException:
        await ws.close(code=1008)
        return

    await ws.accept()
    loop = asyncio.get_running_loop()
    log("WebSocket connected")

    try:
        while True:
            msg = await ws.receive_text()
            try:
                data = json.loads(msg)
            except Exception:
                await send_ws(ws, {"type": "error", "message": "Invalid JSON"})
                continue

            msg_type = data.get("type")
            
            if msg_type == "run":
                cmd = data.get("cmd")
                cwd = data.get("cwd")
                project = data.get("project")
                tab = data.get("tab")
                
                if project and project != "System":
                    log(f"Starting IDE proxy session: {project} (tab={tab})")
                    try:
                        session_id = await start_ide_proxy_session(loop, ws, data)
                        await send_ws(ws, {"type": "started", "sessionId": session_id})
                    except Exception as e:
                        log(f"IDE Proxy start error: {e}")
                        await send_ws(ws, {"type": "error", "message": f"IDE proxy failed: {e}"})
                    continue
                
                env_overrides = data.get("env")

                if not cmd:
                    await send_ws(ws, {"type": "error", "message": "cmd is required"})
                    continue
                log(f"WS run: {cmd}")
                try:
                    session_id = start_command(loop, ws, cmd, cwd, env_overrides)
                    await send_ws(ws, {"type": "started", "sessionId": session_id})
                except HTTPException as e:
                    await send_ws(ws, {"type": "error", "message": str(e.detail)})
            elif msg_type == "stdin":
                session_id = data.get("sessionId")
                text = data.get("data", "")
                if not session_id:
                    await send_ws(ws, {"type": "error", "message": "sessionId is required"})
                    continue
                with _sessions_lock:
                    session = _sessions.get(session_id)
                if not session:
                    await send_ws(ws, {"type": "error", "message": "session not found"})
                    continue
                
                try:
                    if isinstance(session, LocalSession):
                        if session.proc.stdin:
                            session.proc.stdin.write(text)
                            session.proc.stdin.flush()
                    elif isinstance(session, IDESession):
                        if session.ide_session_id:
                            await session.ide_ws.send(json.dumps({
                                "type": "stdin",
                                "sessionId": session.ide_session_id,
                                "data": text
                            }))
                except Exception:
                    await send_ws(ws, {"type": "error", "message": "stdin failed"})
            elif msg_type == "cancel":
                session_id = data.get("sessionId")
                with _sessions_lock:
                    session = _sessions.get(session_id)
                if session:
                    try:
                        if isinstance(session, LocalSession):
                            session.proc.terminate()
                        elif isinstance(session, IDESession):
                            await session.ide_ws.send(json.dumps({
                                "type": "cancel",
                                "sessionId": session.ide_session_id
                            }))
                    except Exception:
                        pass
            else:
                await send_ws(ws, {"type": "error", "message": "Unknown message type"})
    except WebSocketDisconnect:
        log("WebSocket disconnected")
    finally:
        # Cleanup any sessions tied to this websocket.
        with _sessions_lock:
            for sid, session in list(_sessions.items()):
                if session.ws == ws:
                    try:
                        session.proc.terminate()
                    except Exception:
                        pass
                    _sessions.pop(sid, None)


# ============================================================================
# STARTUP
# ============================================================================

def startup_sequence():
    """Run startup sequence: tunnel + Firebase sync"""
    global _tunnel, REMOTE_ACCESS_TOKEN

    print("=" * 60)
    print(f"{APP_NAME} v{VERSION}")
    print("=" * 60)

    # Ensure we can bind the port before starting services.
    global REMOTE_PORT
    chosen_port = pick_available_port(REMOTE_BIND_HOST, REMOTE_PORT)
    if chosen_port != REMOTE_PORT:
        print(f"[startup] Port {REMOTE_PORT} unavailable, using {chosen_port} instead.")
        REMOTE_PORT = chosen_port
        os.environ["REMOTE_PORT"] = str(REMOTE_PORT)

    uid = get_firebase_uid()
    if not uid:
        print("[startup] WARNING: FIREBASE_UID not set - cannot sync to Firebase")
        if not REMOTE_ACCESS_TOKEN:
            REMOTE_ACCESS_TOKEN = secrets.token_urlsafe(32)
            print(f"[startup] Generated local token: {REMOTE_ACCESS_TOKEN}")
    else:
        print(f"[startup] Firebase UID: {uid}")
        # Get or create shared token from Firebase
        get_or_create_shared_token(uid)

    # Start cloudflared tunnel
    def _on_tunnel_ready(url: str):
        global REMOTE_PUBLIC_HOST
        try:
            parsed = urlparse(url)
            host = parsed.netloc or url
            save_env_setting("REMOTE_PUBLIC_HOST", host)
            save_env_setting("REMOTE_TUNNEL_URL", url)
            REMOTE_PUBLIC_HOST = host
            print(f"[startup] Tunnel ready: {url}")
        except Exception:
            pass
        # Re-sync with tunnel info
        try:
            sync_to_firestore()
        except Exception:
            pass

    _tunnel = CloudflareTunnel(REMOTE_PORT)
    tunnel_url = _tunnel.start(on_ready=_on_tunnel_ready, wait_timeout=30)

    if tunnel_url:
        print(f"[startup] Remote access: {tunnel_url}")
    else:
        local_ip = get_local_ip()
        print(f"[startup] Tunnel pending - local access only: http://{local_ip}:{REMOTE_PORT}")

    # Initial sync to Firebase (will be re-synced when tunnel is ready)
    sync_to_firestore()

    print("=" * 60)
    print(f"Server ready on port {REMOTE_PORT}")
    if _tunnel and _tunnel.tunnel_url:
        print(f"Connect from anywhere: {_tunnel.tunnel_url}")
    print("=" * 60)


def shutdown_sequence():
    """Clean shutdown: stop tunnel, mark offline"""
    global _tunnel

    print("[shutdown] Shutting down...")

    if _tunnel:
        _tunnel.stop()
        _tunnel = None

    set_offline_status()
    print("[shutdown] Goodbye!")


if __name__ == "__main__":
    import uvicorn
    import atexit
    import signal

    # Register shutdown handlers
    atexit.register(shutdown_sequence)

    def signal_handler(signum, frame):
        shutdown_sequence()
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Run startup sequence
    startup_sequence()

    # Start server
    uvicorn.run(app, host=REMOTE_BIND_HOST, port=REMOTE_PORT, reload=False)
