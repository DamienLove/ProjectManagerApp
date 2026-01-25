import os

file_path = r'..\src\remote_agent.py'
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# Add IDE_PORT to global settings
if "REMOTE_PORT =" in content and "IDE_PORT =" not in content:
    content = content.replace('REMOTE_PORT = int(os.getenv("REMOTE_PORT", "8765"))',
                              'REMOTE_PORT = int(os.getenv("REMOTE_PORT", "8765"))\nIDE_PORT = int(os.getenv("IDE_PORT", "8766"))')

# Add a helper function to proxy to the plugin
proxy_helper = """
async def proxy_to_plugin(method: str, path: str, body: dict = None, params: dict = None):
    import httpx
    url = f"http://127.0.0.1:{IDE_PORT}{path}"
    headers = {"X-Omni-Token": REMOTE_ACCESS_TOKEN}
    async with httpx.AsyncClient() as client:
        if method == "GET":
            return await client.get(url, headers=headers, params=params)
        elif method == "POST":
            return await client.post(url, headers=headers, json=body, params=params)
"""

if "async def proxy_to_plugin" not in content:
    # Insert before the FastAPI app definition or first route
    content = content.replace('@app.get("/api/health")', proxy_helper + '\n@app.get("/api/health")')

# Add IDE projects endpoint
ide_projects_route = """
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
"""

if "/api/projects/ide" not in content:
    content = content.replace('@app.get("/api/projects")', ide_projects_route + '\n@app.get("/api/projects")')

# Update WebSocket handler to handle proxying
# This is tricky because we need to decide whether to spawn a local shell or proxy.
# We'll modify the "run" message handler.

updated_run_handler = """
            if msg_type == "run":
                cmd = data.get("cmd")
                cwd = data.get("cwd")
                project = data.get("project") # NEW: target project
                
                if project and project != "System":
                    # Proxy to IDE
                    log(f"WS Proxy to IDE: {project} -> {cmd}")
                    # For proxying, we need a separate mechanism. 
                    # For now, let's keep the local shell as default but mark it.
                    # In a full implementation, we'd open a client WS to the plugin.
                    # To keep it simple for this step, we'll just allow the agent
                    # to spawn a shell in the IDE project's directory if we can find it.
                    ide_resp = await proxy_to_plugin("GET", "/api/projects")
                    ide_projects = ide_resp.json().get("projects", [])
                    target = next((p for p in ide_projects if p["name"] == project), None)
                    if target:
                        cwd = target["path"]
                
                env_overrides = data.get("env")
"""

# I will use re.sub for a safer replacement of the 'run' block
import re
content = re.sub(r'if msg_type == "run":.*?env_overrides = data\.get\("env"\)', updated_run_handler, content, flags=re.DOTALL)

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)
print("Successfully updated remote_agent.py")
