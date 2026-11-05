# Hosting after folder reorganisation

The existing live site still builds **codex/pest-hosting** using its old
`Local_Website` root. This reorganisation is on **codex/organize-device-folders**
and is not deployed. Before deliberately promoting it to the hosted service,
change Server Manager's build root to `Laptop/Dashboard`, then verify the
read-only hosted endpoints. No server setting was changed by this reorganisation.

The notes below describe the previous deployment and are retained as history.

# PEST on the 4byte server

Requested address: **https://pest.4bytedigi.com**.

Live and verified on **3 November 2026**. The dashboard, stylesheet, JavaScript,
health, state and port endpoints return HTTP 200 over public HTTPS. USB command
requests return HTTP 403. Desktop and mobile browser checks passed with no page
errors. Camera start/stop and image download were checked separately with
synthetic video; the physical camera was not accessed.

Use the existing 4byte Server Manager and its Docker network and gateway:

| Setting | Value |
| --- | --- |
| Project | `pest` |
| Repository | `Pskm12E/CEG2001-Sensor-Control-AND-CEG2002-Embedded-System-Design-Project` |
| Branch | `codex/pest-hosting` |
| Preset | Dockerfile |
| Root directory at that deployment | `Local_Website` |
| Container port | `8765` |
| Website address | `pest.4bytedigi.com` |

The image runs as a non-root user, contains only the dashboard files and its
pinned Python dependency, and has a local HTTP health check. No USB devices,
host folders, private network configuration or hardware credentials are mounted.
Source files are assigned to the runtime user during the image build so the
manager's restrictive checkout permissions do not prevent startup.
The hosting mode refuses all USB commands. The default laptop launcher keeps
its original local bench mode.

Public routing needs two independent settings: a hostname entry pointing to the
existing deployment gateway (`http://127.0.0.1:9080`) in the server's locally
managed Cloudflare tunnel, and a proxied DNS CNAME for `pest` pointing to that
tunnel. Preserve all existing tunnel routes and DNS records. No new server or
Cloudflare tunnel is needed.

The `pest` proxied CNAME now targets the existing
`dc054a50-d5b1-4c37-b12a-b2c89d11ca56.cfargotunnel.com` tunnel. The tunnel's
hostname entry points to the existing gateway. GitHub updates on the selected
hosting branch automatically rebuild this app through Server Manager.

Verify `/`, `/styles.css`, `/app.js`, `/api/health` and `/api/state` over public
HTTPS after publication. State must report `mode: hosted`, no live telemetry and
no robot connection; command POSTs must be rejected. Check desktop/mobile
layout and camera behavior using synthetic video. A working gateway alone does
not establish that public DNS and HTTPS are live.

The laptop-to-server telemetry bridge, remote camera streaming, pest detection
and robot jobs are separate future integrations.
