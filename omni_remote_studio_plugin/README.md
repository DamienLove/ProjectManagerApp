# Omni Remote Studio Plugin

This is a minimal Android Studio/IntelliJ tool window that talks to the Omni Remote Agent API.

## Build

- Build the plugin ZIP:
  - `gradlew buildPlugin`
  - Output: `build/distributions/*.zip`

## Run in Android Studio (dev)

- `gradlew runIde` (uses the Android Studio platform configured in `build.gradle.kts`).

## Notes

- Update the IntelliJ/Android Studio version in `build.gradle.kts` if your local Android Studio build differs.
- The tool window expects the Omni Remote Agent to be running and reachable.
