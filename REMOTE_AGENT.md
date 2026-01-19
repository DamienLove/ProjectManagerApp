# OmniProjectSync Remote Agent

This agent exposes a small, authenticated API and WebSocket terminal so your Android app can:
- List projects and activate/deactivate them (using the same paths as OmniProjectSync).
- Run CLI commands (including Codex/Gemini/Claude CLI) from your phone.

## Setup

1) Install dependencies:

   python -m pip install -r requirements.txt

2) Add these values to secrets.env (or copy from secrets.env.template):

   REMOTE_ACCESS_TOKEN=... (long random value)
   REMOTE_BIND_HOST=0.0.0.0  (for LAN access) or 127.0.0.1 (local only)
   REMOTE_PORT=8765
   REMOTE_DEFAULT_CWD=C:\Users\me\Projects\ProjectManagerApp

3) Start the agent:

   python src\remote_agent.py

4) In the Android app, set:
   - Host: your PC's LAN IP (e.g., 192.168.1.12) or Tailscale IP
   - Port: 8765 (or leave blank if using HTTPS/TLS)
   - Token: REMOTE_ACCESS_TOKEN

## Cloudflare Tunnel (free online access)

This keeps the agent bound to localhost but makes it reachable via HTTPS/WSS.

1) Install cloudflared and log in:

   cloudflared tunnel login

2) Create a tunnel:

   cloudflared tunnel create omni-remote

3) Create a config file at:
   C:\Users\me\.cloudflared\config.yml

   Example:

   tunnel: <TUNNEL_ID>
   credentials-file: C:\Users\me\.cloudflared\<TUNNEL_ID>.json
   ingress:
     - hostname: omni-remote.yourdomain.com
       service: http://127.0.0.1:8765
     - service: http_status:404

4) Create the DNS route:

   cloudflared tunnel route dns omni-remote omni-remote.yourdomain.com

5) Run the tunnel:

   cloudflared tunnel run omni-remote

6) Android app settings:
   - Host: omni-remote.yourdomain.com
   - Port: (blank) or 443
   - Secure (HTTPS/WSS): ON
   - Token: REMOTE_ACCESS_TOKEN

## Firebase config sync (optional)

The Android app can pull connection info from Firestore.

1) Create a Firestore document:
   - Collection: `omniremote`
   - Document: `connection`
   - Fields (string/bool):
     - `url` (optional) e.g. `https://your-tunnel.trycloudflare.com`
     - `host` (optional) e.g. `your-tunnel.trycloudflare.com`
     - `port` (optional) e.g. `443` or empty
     - `secure` (optional) true/false

2) In the app, sign in with Firebase Auth (email/password), then use **Fetch Cloud** on the Setup screen.

Token is intentionally not synced from Firestore. Keep it manual or stored locally.

## Security notes
- Do not expose the port directly to the public internet.
- Use a VPN like Tailscale/ZeroTier for remote access outside your LAN.
- Keep REMOTE_ACCESS_TOKEN private.

## API
- GET /api/health (auth required)
- GET /api/projects (auth required)
- POST /api/projects/{name}/activate (auth required)
- POST /api/projects/{name}/deactivate (auth required)
- POST /api/command (auth required)
- WS /ws/terminal?token=... (auth required)
