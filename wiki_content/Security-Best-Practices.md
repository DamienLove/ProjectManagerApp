# Security Best Practices

Omni Project Remote is designed with a "Security First" mindset.

1.  **Cloudflare Tunnels**: Use a tunnel to avoid opening ports on your router.
2.  **Token Rotation**: Change your `REMOTE_ACCESS_TOKEN` in `secrets.env` regularly.
3.  **Path Sandboxing**: Use the `REMOTE_ALLOWED_ROOTS` setting in your `secrets.env` to restrict the agent's access to only specific development folders.
4.  **Authorized Email**: In the Android app, set the `expectedEmail` in the source (or config) to ensure only your Firebase account can access connection settings.
