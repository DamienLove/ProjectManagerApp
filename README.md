# Omni Project Remote

A comprehensive suite for managing and accessing your projects remotely. This project consists of three main components that work together in a flexible, dual-host architecture.

## ??? Architecture
Omni Project Remote allows you to control your workstation from your phone using two different hosting methods:
1.  **Standalone Agent (Python)**: A background service for 24/7 access to your workstation.
2.  **IDE Integrated Host (Plugin)**: A server embedded directly in Android Studio / IntelliJ IDEA.

## ?? Downloads (v4.7.0)

| Component | Asset | Description |
| :--- | :--- | :--- |
| **Android App** | [OmniProjectRemote.apk](https://github.com/DamienLove/ProjectManagerApp/releases/download/v4.7.0/OmniProjectRemote.apk) | Mobile Client |
| **IDE Plugin** | [AndroidStudioPlugin.zip](https://github.com/DamienLove/ProjectManagerApp/releases/download/v4.7.0/AndroidStudioPlugin.zip) | **Includes Host Mode** |
| **Remote Agent** | [OmniRemoteAgentSetup.exe](https://github.com/DamienLove/ProjectManagerApp/releases/download/v4.7.0/OmniRemoteAgentSetup.exe) | Standalone Installer |
| **Remote Agent** | [OmniProjectSync.exe](https://github.com/DamienLove/ProjectManagerApp/releases/download/v4.7.0/OmniProjectSync.exe) | Main GUI (No-install) |

## What's new in 4.7.0
- **Unified Terminal Routing**: Android terminal now connects to OmniProjectSync by default and can switch into open Android Studio terminal tabs via the plugin.
- **Plugin Auto-Login + Auto-Host**: IDE plugin restores Firebase login and auto-starts the host after restart (securely stored in PasswordSafe).
- **Safer Defaults**: Blank ports auto-default to 8765/8766 instead of crashing the agent.

## Quick Start

### 1. IDE Host (Fastest)
- Install the AndroidStudioPlugin.zip in your IDE.
- Open the **Omni Remote** side panel.
- Go to the **Host Mode** tab, set a token, and click **Start Host**.

### 2. Standalone Agent
- Download OmniRemoteAgentSetup.exe and follow the prompts (or use OmniRemoteAgent.exe).
- Configure your secrets.env with a REMOTE_ACCESS_TOKEN. Cloudflare tunnels will auto-update the public host.

### 3. Android App
- Install OmniProjectRemote.apk on your phone.
- Enter the IP of your PC, both the PM Port (8765) and IDE Port (8766), and the token defined in your secrets.env.

## Documentation
For detailed technical info, visit the [Wiki](https://github.com/DamienLove/ProjectManagerApp/wiki).

