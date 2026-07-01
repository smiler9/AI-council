# Tunnel Security Checklist

Use this checklist before considering Cloudflare Tunnel, ngrok, Tailscale, or any public/reachable tunnel.

- Do not commit tunnel tokens or API keys.
- Use HTTPS where applicable.
- Require webhook secret validation.
- Prefer IP allowlists or identity-aware access.
- Log only metadata, not secrets or account values.
- Rotate tunnel credentials.
- Test with `normalize-preview` before read-only review mode.
- Never connect AI Council output to live order paths.
- Keep `order_execution_allowed=false`.

Tunnels are convenient, but they increase operational and secret-management burden.
