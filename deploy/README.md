# PEST on the 4byte server

Requested address: **https://pest.4bytedigi.com**.

Use the existing 4byte Server Manager and its Docker network and gateway:

| Setting | Value |
| --- | --- |
| Project | `pest` |
| Repository | `Pskm12E/CEG2001-Sensor-Control-AND-CEG2002-Embedded-System-Design-Project` |
| Branch | `codex/pest-hosting` |
| Preset | Dockerfile |
| Root directory | `Local_Website` |
| Container port | `8765` |
| Website address | `pest.4bytedigi.com` |

The image runs as a non-root user, contains only the dashboard files and its
pinned Python dependency, and has a local HTTP health check. No USB devices,
host folders, private network configuration or hardware credentials are mounted.
The hosting mode refuses all USB commands. The default laptop launcher keeps
its original local bench mode.

Public routing needs two independent settings: a hostname entry pointing to the
existing deployment gateway (`http://127.0.0.1:9080`) in the server's locally
managed Cloudflare tunnel, and a proxied DNS CNAME for `pest` pointing to that
tunnel. Preserve all existing tunnel routes and DNS records. No new server or
Cloudflare tunnel is needed.

Verify `/`, `/styles.css`, `/app.js`, `/api/health` and `/api/state` over public
HTTPS after publication. State must report `mode: hosted`, no live telemetry and
no robot connection; command POSTs must be rejected. Check desktop/mobile
layout and camera behavior using synthetic video. A working gateway alone does
not establish that public DNS and HTTPS are live.

The laptop-to-server telemetry bridge, remote camera streaming, pest detection
and robot jobs are separate future integrations.
