# Omni Project Remote

A comprehensive suite for managing and accessing your projects remotely. This project consists of three main components:

1.  **Omni Remote Agent (Python/Windows)**: A backend service that runs on your workstation, providing a secure API to manage projects and a remote terminal.
2.  **Omni Remote Android App (Kotlin)**: A mobile client that connects to the Remote Agent, allowing you to manage projects and run commands from your phone.
3.  **Omni Remote Studio Plugin (IntelliJ/Android Studio)**: A plugin for your IDE to integrate remote management directly into your development workflow.

## Quick Start

### 1. Remote Agent (Workstation)
- **Installer**: Download OmniRemoteAgentSetup.exe and follow the prompts.
- **Portable**: Run OmniRemoteAgentPortable.exe for a no-install experience.
- **Config**: Create a secrets.env file in the same directory as the executable (use secrets.env.template as a base).

### 2. Android App (Mobile)
- Download OmniProjectRemote.APK and install it on your Android device.
- Configure the Host, Port, and Access Token in the app settings to match your Remote Agent.

### 3. IDE Plugin
- In Android Studio/IntelliJ, go to Settings -> Plugins -> Install Plugin from Disk... and select AndroidStudioPlugin.ZIP.

## Documentation
For detailed installation and usage instructions, please refer to the [Wiki](WIKI.md).
