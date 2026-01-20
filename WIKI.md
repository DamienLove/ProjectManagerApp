# Omni Project Remote Wiki

## Installation Guide

### Omni Remote Agent (Windows)
The Remote Agent is the core of the system. It needs to be running on the computer where your projects are located.

#### Option A: Windows Installer (Recommended)
1. Download OmniRemoteAgentSetup.exe from the latest release.
2. Run the installer and follow the instructions.
3. Once installed, navigate to the installation directory (usually C:\Program Files (x86)\OmniRemoteAgent).
4. Copy secrets.env.template to secrets.env and fill in your REMOTE_ACCESS_TOKEN.

#### Option B: Portable Executable
1. Download OmniRemoteAgentPortable.exe.
2. Place it in a folder of your choice.
3. Place a secrets.env file in the same folder.
4. Run the executable.

#### Option C: From Source
1. Clone the repository.
2. Install dependencies: pip install -r requirements.txt.
3. Configure secrets.env.
4. Run python src/remote_agent.py.

### Omni Remote Android App
1. Download OmniProjectRemote.APK.
2. Enable "Install from Unknown Sources" on your device if necessary.
3. Open the APK to install.
4. Upon launching, navigate to the **Setup** screen.
5. Enter your PC's IP address (or Cloudflare Tunnel URL), port, and the access token defined in your secrets.env.

### Android Studio Plugin
1. Download AndroidStudioPlugin.ZIP.
2. In Android Studio, go to File > Settings (or Android Studio > Settings on macOS).
3. Select Plugins.
4. Click the gear icon and select Install Plugin from Disk....
5. Select the downloaded ZIP file and restart the IDE.

## Usage Instructions

### Connecting the App
- Ensure the Remote Agent is running on your PC.
- In the Android app, use the **Test Connection** button to verify the link.
- You can use **Fetch Cloud** if you have configured Firebase sync (see REMOTE_AGENT.md for details).

### Managing Projects
- Once connected, the app will list all projects managed by OmniProjectSync.
- You can activate/deactivate projects with a single tap.

### Remote Terminal
- Access the terminal tab in the Android app to execute CLI commands on your PC remotely.
- This is useful for triggering builds, running scripts, or interacting with the Gemini/Claude CLI.

## Troubleshooting
- **Connection Failed**: Check if your firewall is blocking the port (default 8765). Ensure you are on the same network or using a tunnel.
- **Unauthorized**: Double-check that the REMOTE_ACCESS_TOKEN in the app matches the one in your secrets.env.
