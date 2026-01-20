# Omni Project Remote: The Ultimate Mobile-to-Desktop Development Bridge

Omni Project Remote is a high-performance suite designed for developers who need to stay connected to their workstations without being tethered to a desk. Whether you're in a meeting, traveling, or just stepping away for coffee, Omni Project Remote puts your entire development environment in your pocket.

## Key Features

### 💻 Workstation Power, Mobile Convenience
Control your professional workstation from any Android device. Our lightweight Python agent exposes a secure, high-speed API that bridges the gap between your mobile device and your desktop.

### 📱 Full-Featured Android Client
- **Modern Jetpack Compose UI**: A sleek, dark-themed interface designed for efficiency.
- **Biometric & Firebase Security**: Authenticated access ensures only you can control your workstation.
- **Cloud Config Sync**: Automatically pull your connection settings (IP, Port, Secure Status) from the cloud using Firebase Firestore.

### 📁 Advanced Project Management
- **Instant Activation/Deactivation**: Move projects between your local high-speed workspace and cloud storage (Google Drive) with a single tap.
- **Smart Resource Management**: Automatically handles external assets, software dependencies (via WinGet), and project manifests during transitions.
- **Status Awareness**: See at a glance which projects are "Local" (ready for work) or "Cloud" (stored remotely).

### ⌨️ Integrated Remote Terminal
- **Live WebSocket Streaming**: Real-time terminal output with zero lag.
- **Interactive Stdin**: Send input to running processes, allowing you to interact with CLI tools (like Gemini/Claude CLI, git, or build scripts) directly from your phone.
- **CWD Control**: Execute commands in specific project directories.

### 🔌 Seamless IDE Integration
- **Android Studio / IntelliJ Plugin**: Manage your remote connections and project status without ever leaving your IDE.
- **One-Click Launch**: Open local projects in Android Studio remotely from your mobile device.

### 🛡️ Enterprise-Grade Security
- **Token-Based Authentication**: All API and WebSocket requests require a secure, private access token.
- **Encrypted Tunnels**: Seamless support for Cloudflare Tunnels (WSS/HTTPS) for secure internet access without port forwarding.
- **Path Sandboxing**: Fine-grained control over which directories the agent can access on your workstation.

## Why Omni Project Remote?
Stop waiting for builds to finish or being stuck at your desk to check project status. Omni Project Remote is built by developers, for developers, providing the most robust way to manage a professional Windows development environment from a mobile device.
