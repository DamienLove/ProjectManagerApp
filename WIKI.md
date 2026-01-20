# Omni Project Remote - Detailed Technical Wiki

Welcome to the comprehensive technical documentation for Omni Project Remote.

## 🏗️ System Architecture

Omni Project Remote consists of three decoupled components communicating over a secure REST and WebSocket API.

1.  **Remote Agent**: A FastAPI-based Python server running on Windows.
2.  **Android Client**: A native Kotlin application built with Jetpack Compose.
3.  **Studio Plugin**: A Kotlin-based IntelliJ IDEA / Android Studio plugin.

---

## 🖥️ Remote Agent Deep Dive

The agent is the brain of the operation. It manages the project lifecycle and provides the bridge to the Windows shell.

### Configuration (secrets.env)
The agent uses a .env file for all sensitive settings:
- REMOTE_ACCESS_TOKEN: The primary security key.
- LOCAL_WORKSPACE_ROOT: Where your "Local" projects live (e.g., C:\Projects).
- DRIVE_ROOT_FOLDER_ID: The local path to your synced Cloud storage (e.g., G:\My Drive\projects).
- REMOTE_ALLOWED_ROOTS: A whitelist of directory paths the agent is allowed to interact with.

### Project Lifecycle
When you **Activate** a project:
1.  The agent copies the project from the "Cloud" path to the "Local" path.
2.  It scans for an omni.json manifest.
3.  **External Resources**: Restores any assets that were moved out of the project folder to save sync space.
4.  **Auto-Software**: Checks for required software IDs in the manifest and installs them via winget if missing.

When you **Deactivate** a project:
1.  It identifies external resources and moves them to a local _omni_assets folder to prevent them from being uploaded to the cloud unnecessarily.
2.  The project folder is copied to the "Cloud" path.
3.  The local copy is safely removed.

### Remote Terminal
The terminal uses WebSockets for real-time interaction.
- **Output**: Captured from stdout and stderr and streamed to the client.
- **Stdin**: Allows sending input to interactive commands (like a "yes/no" prompt or an LLM CLI).
- **Sessions**: Each command runs in its own session, which can be monitored or cancelled.

---

## 📱 Android Client Usage

### Authentication
- **Firebase Auth**: The app requires a specific authorized email to sign in.
- **Fetch Cloud**: Once signed in, the app can pull your workstation's IP and connection settings from a Firestore document (omniremote/connection).

### Terminal Interactions
- **Run**: Starts a new command.
- **Send Input**: Sends the current text in the command field to the *active* session's stdin.
- **Clear**: Wipes the local terminal buffer.

### Projects View
- Lists all projects found in your local and cloud directories.
- **Open Studio**: Sends a request to the agent to launch the project in Android Studio on the PC.

---

## 🔌 IDE Plugin (Android Studio / IntelliJ)

The plugin provides a side-panel for managing the system without leaving your code.

### Installation
1.  Navigate to Settings -> Plugins.
2.  Click the ⚙️ icon -> Install Plugin from Disk....
3.  Select AndroidStudioPlugin.ZIP.

### Features
- **Project List**: Synchronized view of your projects.
- **Embedded Terminal**: Run remote commands directly from the IDE.
- **Quick-Test**: Verify connectivity to your remote agent with a single button.

---

## 🔒 Security Best Practices

1.  **Use a Tunnel**: We highly recommend **Cloudflare Tunnels**. It allows the agent to stay on 127.0.0.1 while being reachable via a secure https:// and wss:// URL.
2.  **Long Tokens**: Use a 32+ character string for REMOTE_ACCESS_TOKEN.
3.  **Whitelist Paths**: Only include paths in REMOTE_ALLOWED_ROOTS that you actually need to manage.
4.  **Firewall**: If not using a tunnel, ensure your Windows Firewall only allows the REMOTE_PORT on your LAN.

## 🛠️ Manifest File (omni.json)
Create an omni.json in your project root to enable advanced features:
`json
{
  "software": ["Git.Git", "NodeJS.LTS"],
  "external_paths": ["C:\\LargeAssets\\Project1"]
}
`
- software: List of WinGet IDs to ensure are installed.
- external_paths: Paths that should be "detached" during cloud sync to save space/time.
