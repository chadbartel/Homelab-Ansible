# Manual Nginx Proxy Manager & Pi-hole Steps

This repository never automates changes to live Nginx Proxy Manager (`npm-stack`) or Pi-hole (`pihole-stack`) containers on `monolith` (`192.168.1.17`). Any reverse-proxy host or local DNS record required for AI stack services is documented here for manual configuration via the web UIs.

---

## Kokoro-FastAPI TTS (`kokoro-fastapi`) — Optional

> **Note:** Exposing Kokoro-FastAPI through Nginx Proxy Manager is **optional**. Open WebUI communicates directly with `http://kokoro-fastapi:8880/v1` over the internal `homelab-bridge` Docker network, so the Jarvis voice pipeline works without an NPM proxy host or public/LAN DNS route. Only add the entry below if you want direct HTTPS access to the TTS API or web UI from LAN clients.

### 1. Pi-hole Custom DNS Record (Required if NPM Route is Enabled)

In the Pi-hole admin UI (`Local DNS -> DNS Records`), add:

| Field | Value |
| --- | --- |
| **Domain** | `tts.chadbartel.duckdns.org` |
| **IP Address** | `192.168.1.17` |

### 2. Nginx Proxy Manager Proxy Host

In the Nginx Proxy Manager admin UI (`Hosts -> Proxy Hosts -> Add Proxy Host`), configure:

#### Details Tab
- **Domain Names:** `tts.chadbartel.duckdns.org`
- **Scheme:** `http`
- **Forward Hostname / IP:** `kokoro-fastapi` *(resolved internally over `homelab-bridge`)*
- **Forward Port:** `8880`
- **Cache Assets:** Disabled *(avoid caching dynamic TTS audio responses)*
- **Block Common Exploits:** Enabled
- **Websockets Support:** Disabled *(not required for REST/HTTP streaming endpoints)*
- **Access List:** `Internal Only` *(recommended so the TTS endpoint is restricted to LAN)*

#### SSL Tab
- **SSL Certificate:** Select the existing wildcard Let's Encrypt certificate (`*.chadbartel.duckdns.org`)
- **Force SSL:** Enabled
- **HTTP/2 Support:** Enabled
- **HSTS Enabled:** Match existing internal proxy host policy

### 3. Post-Setup Verification

```bash
# Direct health check on monolith
curl -fsS http://127.0.0.1:8880/health

# HTTPS health check via NPM (only after completing steps 1 and 2)
curl -fsS https://tts.chadbartel.duckdns.org/health
```
