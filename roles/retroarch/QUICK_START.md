# RetroArch Quick Start & NPM Configuration

Get RetroArch online in 5 minutes.

## TL;DR Deployment

### 1. Create Playbook
```yaml
---
- name: Deploy RetroArch
  hosts: monolith
  roles:
    - retroarch
```

### 2. Run Deployment
```bash
ansible-playbook -i inventory.yml playbooks/deploy_retroarch.yml
```

### 3. Access Directly
```
LAN:  http://192.168.1.17:3000
```

### 4. Configure NPM (Optional - for external/remote access)
Follow the **NPM Configuration** section below.

---

## NPM Configuration for Nginx Proxy Manager

To access RetroArch via `retroarch.chadbartel.duckdns.org` and enable HTTPS:

### Prerequisites
- RetroArch deployed and running (port 3000 responding)
- Nginx Proxy Manager accessible at `http://192.168.1.17:8181`
- Valid SSL certificate configured in NPM

### Step-by-Step NPM Setup

#### Step 1: Add New Proxy Host

1. Open **Nginx Proxy Manager** admin panel
   ```
   http://192.168.1.17:8181
   ```

2. Navigate to **Proxy Hosts** → **Add Proxy Host**

#### Step 2: Domain Configuration

| Field | Value |
|-------|-------|
| **Domain Names** | `retroarch.chadbartel.duckdns.org` |
| **Scheme** | `http` |
| **Forward Hostname / IP** | `retroarch` |
| **Forward Port** | `3000` |
| **Cache Assets** | `OFF` |
| **Block Exploits** | `ON` |

**Example screenshot layout:**
```
┌─ Details Tab ────────────────────────┐
│ Domain Names:                         │
│ ┌─────────────────────────────────┐  │
│ │ retroarch.chadbartel.duckdns.org│  │
│ └─────────────────────────────────┘  │
│                                       │
│ Scheme:  [http]  ▼                   │
│                                       │
│ Forward Hostname / IP:                │
│ ┌─────────────────────────────────┐  │
│ │ retroarch                        │  │
│ └─────────────────────────────────┘  │
│                                       │
│ Forward Port: [3000]                  │
│                                       │
│ ☑ Cache Assets                        │
│ ☑ Block Exploits                      │
│ ☐ Deny Access                         │
└───────────────────────────────────────┘
```

#### Step 3: Enable Advanced Features (CRITICAL for KasmVNC)

1. Click **Advanced** tab

2. Enable **Websockets Support**
   - Toggle: **ON**
   - Why: KasmVNC streams video via WebSocket protocol

3. Optional: Add custom upstream headers if needed

**Example advanced config:**
```
┌─ Advanced Tab ────────────────────────┐
│ Websockets Support:                   │
│ ☑ Enabled                             │
│                                       │
│ Custom Locations: (leave empty)       │
│ HTTP Authentications: (none)          │
│ Custom Headers:                       │
│ (leave empty - RetroArch handles it)  │
└───────────────────────────────────────┘
```

#### Step 4: SSL Certificate

1. Click **SSL** tab

2. Select certificate:
   - **SSL Certificate:** Choose your existing wildcard or domain cert
     - Example: `*.chadbartel.duckdns.org` (wildcard)
     - Or: `chadbartel.duckdns.org` (specific domain)
   
   - **Force SSL:** `ON` (redirect HTTP to HTTPS)
   - **HTTP/2 Support:** `ON` (for better performance)
   - **HSTS:** `ON` (security best practice)

**Example SSL config:**
```
┌─ SSL Tab ─────────────────────────────┐
│ SSL Certificate: [*.chadbartel.duckd…▼ │
│ Force SSL: ☑                          │
│ HTTP/2 Support: ☑                     │
│ HSTS Enabled: ☑                       │
│ HSTS Subdomains: ☑                    │
│ HSTS Max-Age: [63072000]              │
│ Use Mozilla Recommendations: [On]     │
└───────────────────────────────────────┘
```

#### Step 5: Save Proxy Host

1. Click **Save** button
2. Wait for NPM to reload (typically 2-3 seconds)
3. Verify the proxy host appears in the **Proxy Hosts** list

#### Step 6: Verify DNS Resolution

Ensure Pi-hole has the DNS entry:

1. Open **Pi-hole admin panel**
   ```
   http://192.168.1.17:8081/admin
   ```

2. Navigate to **Local DNS Records**

3. Verify entry exists:
   ```
   retroarch.chadbartel.duckdns.org  →  192.168.1.17
   ```

   **If missing, add manually:**
   - Domain: `retroarch.chadbartel.duckdns.org`
   - IP: `192.168.1.17`
   - Save

### Step 7: Test Access

#### From LAN
```bash
# Resolve via Pi-hole DNS
nslookup retroarch.chadbartel.duckdns.org 192.168.1.1

# Access via proxy
https://retroarch.chadbartel.duckdns.org
```

#### From WAN
```bash
# Should resolve and route through DuckDNS and NPM
https://retroarch.chadbartel.duckdns.org
```

---

## Troubleshooting NPM Integration

### 502 Bad Gateway

**Cause:** NPM cannot reach the backend container.

**Debug:**
1. **Verify container is running:**
   ```bash
   docker ps | grep retroarch
   ```

2. **Verify port 3000 is open:**
   ```bash
   docker exec retroarch nc -zv retroarch 3000
   ```

3. **Verify bridge network:**
   ```bash
   docker network inspect homelab-bridge | grep retroarch
   ```

4. **Check NPM logs:**
   ```bash
   docker logs nginx-proxy-manager | grep retroarch
   ```

**Solution:**
- Ensure `Forward Hostname / IP` is set to container name: `retroarch`
- Do NOT use `192.168.1.17` (that's for host-network services only)
- Verify both NPM and RetroArch are on `homelab-bridge` network

### WebSocket Connection Fails / Video Stream Stalls

**Cause:** WebSocket upgrade not enabled in NPM.

**Debug:**
1. Open browser Developer Tools (F12)
2. Check **Network** tab for WebSocket connections
3. Look for failed `ws://` or `wss://` connections

**Solution:**
- Verify **Websockets Support** is **ON** in NPM Advanced tab
- Check NPM logs: `docker logs nginx-proxy-manager`

### SSL Certificate Error

**Cause:** Certificate doesn't match domain or is expired.

**Debug:**
```bash
curl -v https://retroarch.chadbartel.duckdns.org
```

**Solution:**
- Verify certificate in NPM includes `*.chadbartel.duckdns.org` or `chadbartel.duckdns.org`
- Check certificate expiration
- If using Let's Encrypt, verify auto-renewal is working

### DNS Not Resolving

**Cause:** Pi-hole DNS entry missing or incorrect.

**Debug:**
```bash
# From monolith
nslookup retroarch.chadbartel.duckdns.org 192.168.1.1

# Check Pi-hole logs
docker logs pihole | grep retroarch
```

**Solution:**
- Add DNS entry to Pi-hole (see Step 6)
- Verify Pi-hole is listening on port 53: `docker ps | grep pihole`
- Flush local DNS cache on client device

---

## NPM Configuration via Ansible (Advanced)

Instead of manual GUI configuration, automate NPM setup:

```yaml
- name: Configure NPM reverse proxy for RetroArch
  ansible.builtin.include_role:
    name: nginx_proxy_manager_config
  vars:
    npm_config_proxy_hosts:
      - domain: "retroarch.chadbartel.duckdns.org"
        forward_scheme: "http"
        forward_host: "retroarch"
        forward_port: 3000
        ssl_certificate_id: 1  # Replace with your cert ID
        ssl_forced: true
        websocket_upgrade: true
        block_exploits: true
        caching_enabled: false
```

---

## Quick Reference: Configuration Summary

```
┌─ RetroArch Infrastructure Map ────────────────────┐
│                                                   │
│  WAN / Remote Users                              │
│  ├─ retroarch.chadbartel.duckdns.org (HTTPS)    │
│  │  └─ [DuckDNS] → [Router] → [NPM Port 8181]   │
│  │                            ↓                  │
│  │     [Nginx Proxy Manager]                    │
│  │     ├─ Domain: retroarch.chadbartel.duck… │
│  │     ├─ Scheme: HTTP                         │
│  │     ├─ Forward: retroarch:3000              │
│  │     ├─ Websockets: ON                       │
│  │     └─ SSL Cert: *.chadbartel.duckdns.org  │
│  │                            ↓                 │
│  │     [homelab-bridge Network]                 │
│  │     ├─ retroarch (port 3000)                 │
│  │     └─ (container name resolution)           │
│  │                                              │
│  └─────────────────────────────────────────────│
│                                                   │
│  LAN / Local Access                              │
│  └─ http://192.168.1.17:3000                    │
│     (Direct to RetroArch, no proxy needed)      │
│                                                   │
└───────────────────────────────────────────────────┘
```

---

## Common NPM Settings for Reference

**Typical proxy host values across the homelab:**

| Service | Domain | Forward Host | Port | Scheme | WebSocket |
|---------|--------|--------------|------|--------|-----------|
| Jellyfin | jellyfin.local | `jellyfin` | 8096 | http | ❌ |
| Portainer | portainer.local | `portainer` | 9000 | http | ✅ |
| Pi-hole | pihole.local | `pihole` | 80 | http | ❌ |
| RetroArch | retroarch.local | `retroarch` | 3000 | http | ✅ |
| OpenVPN-AS | vpn.local | `172.18.0.1` | 943 | https | ❌ |

**Key Pattern:**
- Bridge-network services use **container name** (e.g., `retroarch`)
- Host-network services use **gateway IP** (e.g., `172.18.0.1`)
- WebSocket-heavy services (streaming, realtime) enable it

---

## Next Steps

1. ✅ Deploy RetroArch (see TL;DR above)
2. ✅ Test direct LAN access: `http://192.168.1.17:3000`
3. ✅ Configure NPM reverse proxy (this guide)
4. ✅ Add ROMs to `/mnt/ssd_media/roms`
5. ✅ Access from WAN: `https://retroarch.chadbartel.duckdns.org`

Enjoy retro gaming! 🎮
