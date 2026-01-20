# Omni Project Remote

A comprehensive suite for managing and accessing your projects remotely. This project consists of three main components:

1.  **Omni Remote Agent (Python/Windows)**: A backend service that runs on your workstation, providing a secure API to manage projects and a remote terminal.
2.  **Omni Remote Android App (Kotlin)**: A mobile client that connects to the Remote Agent, allowing you to manage projects and run commands from your phone.
3.  **Omni Remote Studio Plugin (IntelliJ/Android Studio)**: A plugin for your IDE to integrate remote management directly into your development workflow.

## 📥 Downloads (V2 Alpha)

| Component | Asset | Description |
| :--- | :--- | :--- |
| **Android App** | [OmniProjectRemote.apk](https://github.com/DamienLove/ProjectManagerApp/releases/download/V2/OmniProjectRemote.apk) | Mobile Client |
| **Remote Agent** | [OmniRemoteAgentSetup.exe](https://github.com/DamienLove/ProjectManagerApp/releases/download/V2/OmniRemoteAgentSetup.exe) | **Recommended** Installer |
| **Remote Agent** | [OmniRemoteAgentPortable.exe](https://github.com/DamienLove/ProjectManagerApp/releases/download/V2/OmniRemoteAgentPortable.exe) | No-install Portable version |
| **Remote Agent** | [OmniRemoteAgent.exe](https://github.com/DamienLove/ProjectManagerApp/releases/download/V2/OmniRemoteAgent.exe) | Standalone Executable |
| **IDE Plugin** | [AndroidStudioPlugin.zip](https://github.com/DamienLove/ProjectManagerApp/releases/download/V2/AndroidStudioPlugin.zip) | For Android Studio / IntelliJ |
| **Config** | [secrets.env.template](https://github.com/DamienLove/ProjectManagerApp/releases/download/V2/secrets.env.template) | Required Configuration Template |

## Quick Start

### 1. Remote Agent (Workstation)
- **Installer**: Download `OmniRemoteAgentSetup.exe` and follow the prompts.
- **Config**: Create a `secrets.env` file in the same directory as the executable (use `secrets.env.template` as a base).

### 2. Android App (Mobile)
- Download `OmniProjectRemote.apk` and install it on your Android device.
- Configure the Host, Port, and Access Token in the app settings.

### 3. IDE Plugin
- In Android Studio/IntelliJ, go to `Settings` -> `Plugins` -> `Install Plugin from Disk...` and select `AndroidStudioPlugin.zip`.

## Documentation
For detailed installation and usage instructions, please refer to the [Wiki](https://github.com/DamienLove/ProjectManagerApp/wiki).
