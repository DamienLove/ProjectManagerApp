# Installation Guide

## 1. Remote Agent (Windows)
The Remote Agent is the core of the system. It needs to be running on the computer where your projects are located.

### Option A: Windows Installer (Recommended)
1. Download `OmniRemoteAgentSetup.exe` from the latest release.
2. Run the installer and follow the instructions.
3. Once installed, navigate to the installation directory (usually `C:\Program Files (x86)\OmniRemoteAgent`).
4. Copy `secrets.env.template` to `secrets.env` and fill in your `REMOTE_ACCESS_TOKEN`.

### Option B: Portable Executable
1. Download `OmniRemoteAgentPortable.exe`.
2. Place it in a folder of your choice.
3. Place a `secrets.env` file in the same folder.
4. Run the executable.

---

## 2. Android App
1. Download `OmniProjectRemote.APK`.
2. Enable "Install from Unknown Sources" on your device if necessary.
3. Open the APK to install.
4. Upon launching, navigate to the **Setup** screen.
5. Enter your PC's IP address, both the PM Port (8765) and IDE Port (8766), and the access token defined in your `secrets.env`.

---

## 3. IDE Plugin (Android Studio / IntelliJ)
1. Download `AndroidStudioPlugin.ZIP`.
2. In Android Studio, go to `Settings` -> `Plugins`.
3. Click the gear icon and select `Install Plugin from Disk...`.
4. Select the downloaded ZIP file and restart the IDE.

