import asyncio
import datetime
import hashlib
import json
import os
import secrets
import shutil
import stat
import subprocess
import threading
import uuid
import sys
from typing import Dict, Optional

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
import firebase_admin
from firebase_admin import credentials, firestore
from starlette.concurrency import run_in_threadpool

APP_NAME = "OmniProjectSync Remote Agent"
VERSION = "4.4.0"
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

REMOTE_BIND_HOST = os.getenv("REMOTE_BIND_HOST", "127.0.0.1")
REMOTE_PUBLIC_HOST = os.getenv("REMOTE_PUBLIC_HOST", "")  # External host for Android (tunnel URL or LAN IP)
REMOTE_PORT = int(os.getenv("REMOTE_PORT", "8765"))
REMOTE_ACCESS_TOKEN = os.getenv("REMOTE_ACCESS_TOKEN", "")
REMOTE_SHELL = os.getenv("REMOTE_SHELL", "powershell.exe")
REMOTE_DEFAULT_CWD = os.getenv("REMOTE_DEFAULT_CWD", BASE_DIR)
REMOTE_ALLOWED_ROOTS = [p.strip() for p in os.getenv("REMOTE_ALLOWED_ROOTS", "").split(";") if p.strip()] 

LOCAL_WORKSPACE_ROOT = os.getenv("LOCAL_WORKSPACE_ROOT", DEFAULT_WORKSPACE)
DRIVE_ROOT_FOLDER_ID = os.getenv("DRIVE_ROOT_FOLDER_ID", "")
HIDDEN_PROJECTS = [h.strip().lower() for h in os.getenv("HIDDEN_PROJECTS", "").split(",") if h.strip()]   

if not REMOTE_ACCESS_TOKEN:
    REMOTE_ACCESS_TOKEN = secrets.token_urlsafe(32)
    print("[remote-agent] REMOTE_ACCESS_TOKEN is not set. Temporary token generated:")
    print(REMOTE_ACCESS_TOKEN)
    print("Set REMOTE_ACCESS_TOKEN in secrets.env for a stable token.")

# Initialize Firebase
FIREBASE_PROJECT_ID = os.getenv("FIREBASE_PROJECT_ID", "omniremote-e7afd") 

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
    print(f"[remote-agent] Firebase initialization failed: {e}")


def sync_to_firestore():
    if not db:
        return
    uid = os.getenv("FIREBASE_UID")
    if not uid:
        doc_path = os.getenv("FIREBASE_DOCUMENT_PATH", "")
        if doc_path.startswith("users/") and "/" in doc_path:
            uid = doc_path.split("/", 2)[1]
    if not uid:
        print("[remote-agent] FIREBASE_UID not set. Skipping sync.")
        return
    try:
        # 1. Sync connection info
        # Use REMOTE_PUBLIC_HOST if set (tunnel URL or LAN IP), otherwise fall back to bind host
        public_host = REMOTE_PUBLIC_HOST or (REMOTE_BIND_HOST if REMOTE_BIND_HOST != "0.0.0.0" else "")

        # Validate host - warn if it looks like localhost or won't work remotely
        is_localhost = public_host in ("127.0.0.1", "localhost", "0.0.0.0", "")
        is_private_ip = public_host.startswith(("192.168.", "10.", "172.16.", "172.17.", "172.18.", "172.19.", "172.20.", "172.21.", "172.22.", "172.23.", "172.24.", "172.25.", "172.26.", "172.27.", "172.28.", "172.29.", "172.30.", "172.31."))

        if is_localhost:
            print("[remote-agent] ERROR: REMOTE_PUBLIC_HOST is localhost - Android cannot connect!")
            print("[remote-agent] Set REMOTE_PUBLIC_HOST to your Cloudflare tunnel URL in secrets.env")
            print("[remote-agent] Skipping Firestore sync to prevent bad config from being saved.")
            return

        if is_private_ip:
            print(f"[remote-agent] Warning: REMOTE_PUBLIC_HOST is a private IP ({public_host})")
            print("[remote-agent] This only works if Android is on the same network.")
            print("[remote-agent] For remote access, use a Cloudflare tunnel URL instead.")

        # Auto-detect secure: true for tunnel URLs (they use HTTPS), false for IPs
        is_likely_tunnel = public_host and not public_host[0].isdigit() and "." in public_host
        use_secure = is_likely_tunnel or REMOTE_PUBLIC_HOST.startswith("https://")

        conn_data = {
            "host": public_host,
            "pmPort": REMOTE_PORT,
            "idePort": REMOTE_PORT,
            "token": REMOTE_ACCESS_TOKEN,
            "secure": use_secure,
            "updated_at": firestore.SERVER_TIMESTAMP,
            "agent": "python-agent",
            "version": VERSION
        }
        user_ref = db.collection("users").document(uid)
        user_ref.set(conn_data, merge=True)
        user_ref.collection("config").document("connection").set(conn_data, merge=True)
        
        # 2. Sync projects
        registry = compute_registry()
        projects_ref = user_ref.collection("projects")
        
        # We'll use a batch for efficiency
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
            
            # Load extra info from omni.json if it exists
            if os.path.exists(manifest_path):
                try:
                    with open(manifest_path, "r", encoding="utf-8") as f:
                        manifest = json.load(f)
                    # Merge manifest data (software, external paths, etc)
                    project_data.update(manifest)
                except Exception:
                    pass
            
            doc_ref = projects_ref.document(name)
            batch.set(doc_ref, project_data, merge=True)
            
        batch.commit()
        print(f"[remote-agent] Synced connection info and {len(registry)} projects to Firestore for UID: {uid}")
    except Exception as e:
        print(f"[remote-agent] Firestore sync failed: {e}")




app = FastAPI(title=APP_NAME, version=VERSION)

_sessions_lock = threading.Lock()
_sessions: Dict[str, "CommandSession"] = {}

_project_locks_lock = threading.Lock()
_project_locks: Dict[str, threading.Lock] = {}

_registry_lock = threading.Lock()


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
    if token != REMOTE_ACCESS_TOKEN:
        raise HTTPException(status_code=401, detail="Unauthorized")


def require_token_from_ws(ws: WebSocket) -> None:
    token = ws.headers.get("X-Omni-Token") or ws.query_params.get("token")
    if token != REMOTE_ACCESS_TOKEN:
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
    ws_root = os.path.abspath(LOCAL_WORKSPACE_ROOT)
    if abs_path == ws_root or abs_path.startswith(ws_root + os.sep):
        return True
    # If allowed roots are defined, enforce them.
    if REMOTE_ALLOWED_ROOTS:
        for root in REMOTE_ALLOWED_ROOTS:
            root_abs = os.path.abspath(root)
            if abs_path == root_abs or abs_path.startswith(root_abs + os.sep):
                return True
        return False
    # Otherwise block only obviously dangerous roots.
    for p in PROTECTED_PATHS:
        p_abs = os.path.abspath(p)
        if abs_path == p_abs or abs_path.startswith(p_abs + os.sep):
            return False
    return True

def load_registry() -> Dict[str, str]:
    if os.path.exists(LOCAL_REGISTRY_PATH):
        try:
            with open(LOCAL_REGISTRY_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def save_registry(registry: Dict[str, str]) -> None:
    os.makedirs(CONFIG_DIR, exist_ok=True)
    with open(LOCAL_REGISTRY_PATH, "w", encoding="utf-8") as f:
        json.dump(registry, f, indent=2)

def compute_registry() -> Dict[str, str]:
    with _registry_lock:
        os.makedirs(LOCAL_WORKSPACE_ROOT, exist_ok=True)
        local_folders = {
            f for f in os.listdir(LOCAL_WORKSPACE_ROOT)
            if os.path.isdir(os.path.join(LOCAL_WORKSPACE_ROOT, f))
        }
        registry = load_registry()
        for name in local_folders:
            registry[name] = "Local"
        for name in list(registry.keys()):
            if name not in local_folders:
                registry[name] = "Cloud"
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
                ], shell=True)
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
        subprocess.Popen([studio, project_path], shell=True)
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
    def __init__(self, session_id: str, proc: subprocess.Popen, ws: WebSocket):
        self.session_id = session_id
        self.proc = proc
        self.ws = ws
        self.started = datetime.datetime.now()


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

    session = CommandSession(session_id, proc, ws)
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


@app.get("/api/health")
async def health(request: Request):
    require_token_from_request(request)
    return {
        "status": "ok",
        "app": APP_NAME,
        "version": VERSION,
        "time": datetime.datetime.now().isoformat(),
    }


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
    sync_to_firestore()
    return result


@app.post("/api/projects/{name}/deactivate")
async def api_deactivate_project(name: str, request: Request):
    require_token_from_request(request)
    result = await run_in_threadpool(deactivate_project, name)
    if result.get("status") != "ok":
        raise HTTPException(status_code=400, detail=result.get("message"))
    sync_to_firestore()
    return result


@app.post("/api/projects/{name}/open-studio")
async def api_open_studio_project(name: str, request: Request):
    require_token_from_request(request)
    result = open_studio_project(name)
    if result.get("status") != "ok":
        raise HTTPException(status_code=400, detail=result.get("message"))
    sync_to_firestore()
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
        stdout_str = stdout.decode("utf-8", errors="replace")
        stderr_str = stderr.decode("utf-8", errors="replace")
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
                    if session.proc.stdin:
                        session.proc.stdin.write(text)
                        session.proc.stdin.flush()
                except Exception:
                    await send_ws(ws, {"type": "error", "message": "stdin failed"})
            elif msg_type == "cancel":
                session_id = data.get("sessionId")
                with _sessions_lock:
                    session = _sessions.get(session_id)
                if session:
                    try:
                        session.proc.terminate()
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


if __name__ == "__main__":
    import uvicorn

    # sync_to_firestore() # Not defined
    print(f"{APP_NAME} listening on {REMOTE_BIND_HOST}:{REMOTE_PORT}")
    sync_to_firestore()
    uvicorn.run(app, host=REMOTE_BIND_HOST, port=REMOTE_PORT, reload=False)
