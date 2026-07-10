# RetroArch Emulator Frontend Role

Deploy the **LinuxServer.io RetroArch** container on a headless Ubuntu monolith using Docker Compose V2.

RetroArch is a frontend for emulators, game engines, and media players that enables you to run classic games from a wide range of computer and console systems via a web-based KasmVNC interface.

## Features

✅ **LinuxServer.io Official Image**  
Maintained, hardened container with automatic updates

✅ **NVIDIA GPU Acceleration**  
Hardware-accelerated rendering and encoding via NVIDIA RTX 2070 SUPER

✅ **Wayland Stack**  
Modern compositing environment with zero-copy encoding to reduce CPU load

✅ **KasmVNC Web UI**  
Stream RetroArch via KasmVNC on port 3000 (HTTP) / 3001 (HTTPS)

✅ **Nginx Proxy Manager Integration**  
Reverse proxy routing to `retroarch.chadbartel.duckdns.org` with WebSocket support

✅ **Storage Tiering**  
- Config/saves on fast NVMe (Docker named volume)
- ROM library on bulk external USB storage (bind mount)

✅ **Idempotent Deployment**  
Uses `community.docker.docker_compose_v2` via stack_deployer role

## Architecture Overview

### Network
- **Container Network:** `homelab-bridge` (shared Docker bridge)
- **Host Access:** Direct port binding `192.168.1.17:3000` for flat LAN access
- **Reverse Proxy:** NPM routes `retroarch.chadbartel.duckdns.org` → `retroarch:3000` (bridge network container name)

### Storage
```
Host                          Container
─────────────────────────────────────────
/mnt/nvme_primary/...
  └─ retroarch_config   →     /config      (Docker volume, fast I/O)
  
/mnt/ssd_media/roms    →     /roms        (Bind mount, bulk storage)
```

### GPU
```
Host                          Container
─────────────────────────────────────────
NVIDIA RTX 2070 SUPER
  ├─ /dev/dri/renderD128  ─→  Rendering (DRINODE)
  └─ /dev/dri/renderD128  ─→  Encoding (DRI_NODE)
                              (Zero-copy when both identical)
```

## Prerequisites

### Host Requirements
- **Ubuntu 24.04 LTS** (tested) or 22.04+
- **NVIDIA Driver:** Proprietary drivers 580+ (install from nvidia.com .run file)
- **nvidia-container-toolkit:** Installed and configured
- **Docker Engine:** 20.10+ with Compose V2
- **Docker Runtime:** nvidia runtime configured

### Kernel Parameters (NVIDIA GPU)
Edit `/etc/default/grub` and add to `GRUB_CMDLINE_LINUX_DEFAULT`:
```bash
nvidia-drm.modeset=1 nvidia_drm.fbdev=1
```

Then apply:
```bash
sudo update-grub
```

### Hardware (Headless Systems)
On headless systems without a physical display, insert a **dummy plug into the NVIDIA GPU** so that DRM initializes properly.

### Volumes & Directories
- **Create ROM directory on host:**
  ```bash
  mkdir -p /mnt/ssd_media/roms
  chmod 755 /mnt/ssd_media/roms
  ```

- **Ensure `homelab-bridge` network exists:**  
  Created automatically by other stack deployments; verify:
  ```bash
  docker network ls | grep homelab-bridge
  ```

## Role Variables

### Essential Configuration
| Variable | Default | Description |
|----------|---------|-------------|
| `retroarch_container_name` | `retroarch` | Docker container name |
| `retroarch_http_port` | `3000` | KasmVNC HTTP port (LAN & proxy) |
| `retroarch_https_port` | `3001` | KasmVNC HTTPS port (self-signed) |
| `retroarch_puid` / `retroarch_pgid` | `1000` / `1000` | User/Group ID for volume permissions |

### Storage
| Variable | Default | Description |
|----------|---------|-------------|
| `retroarch_config_volume_name` | `retroarch_config` | Docker volume name for `/config` |
| `retroarch_roms_source` | `/mnt/ssd_media/roms` | Host path where ROMs are stored |
| `retroarch_roms_target` | `/roms` | Mount point inside container |

### GPU
| Variable | Default | Description |
|----------|---------|-------------|
| `retroarch_gpu_enabled` | `true` | Enable NVIDIA GPU passthrough |
| `retroarch_gpu_driver` | `nvidia` | GPU driver for Compose |
| `retroarch_drinode` | `/dev/dri/renderD128` | GPU rendering device |
| `retroarch_dri_node` | `/dev/dri/renderD128` | GPU encoding device |
| `retroarch_pixelflux_wayland` | `true` | Enable Wayland GPU acceleration |

### Nginx Proxy Manager
| Variable | Default | Description |
|----------|---------|-------------|
| `retroarch_npm_domain` | `retroarch.chadbartel.duckdns.org` | NPM domain (DNS entry created automatically) |
| `retroarch_npm_forward_host` | `retroarch` | Container name (bridge network) |
| `retroarch_npm_forward_port` | `3000` | Container HTTP port |
| `retroarch_npm_websocket_upgrade` | `true` | Enable WebSocket for KasmVNC |

See [defaults/main.yml](defaults/main.yml) for all configurable options.

## Deployment

### Option 1: Direct Ansible Playbook (Recommended)

Create a playbook that includes the role:

```yaml
---
- name: Deploy RetroArch
  hosts: monolith
  gather_facts: false
  roles:
    - role: retroarch
      vars:
        retroarch_gpu_enabled: true
        retroarch_roms_source: "/mnt/ssd_media/roms"
  tags: [deploy, retroarch]
```

Run it:
```bash
ansible-playbook -i inventory.yml playbooks/deploy_retroarch.yml
```

### Option 2: Include in Existing Main Playbook

Add to `main.yml`:
```yaml
- name: Deploy RetroArch
  import_tasks: tasks/deploy_retroarch.yml
```

Create `tasks/deploy_retroarch.yml`:
```yaml
---
- name: Deploy RetroArch container
  import_role:
    name: retroarch
  vars:
    retroarch_gpu_enabled: true
```

## Usage

### Direct LAN Access
After deployment, access RetroArch from any device on `192.168.1.x` subnet:
```
http://192.168.1.17:3000
https://192.168.1.17:3001  (self-signed cert)
```

### Via Nginx Proxy Manager (WAN/Remote Access)
See [QUICK_START.md](QUICK_START.md) for NPM configuration.

### First Launch with GPU
When running with NVIDIA GPU, you may need to:
1. Right-click the desktop inside KasmVNC
2. Re-launch RetroArch from the menu

This is a one-time initialization for GPU rendering.

### Adding ROMs
Place emulator ROM files in `/mnt/ssd_media/roms` on the host. RetroArch will auto-scan and import them.

Supported directories:
```
/roms/
├── nes/          → NES games
├── snes/         → Super Nintendo
├── genesis/      → Sega Genesis
├── gameboy/      → Game Boy
├── playstation/  → PS1 / PS2
└── ...           → Other systems
```

### Container Management

**View logs:**
```bash
docker logs -f retroarch
```

**Execute command in container:**
```bash
docker exec -it retroarch bash
```

**Restart container:**
```bash
docker restart retroarch
```

**Stop container:**
```bash
docker stop retroarch
```

## Troubleshooting

### Web UI Does Not Respond
- **Verify container is running:**
  ```bash
  docker ps | grep retroarch
  ```
- **Check port binding:**
  ```bash
  sudo netstat -tlnp | grep 3000
  ```
- **View logs:**
  ```bash
  docker logs retroarch | tail -50
  ```

### GPU Not Detected
- **Verify NVIDIA runtime:**
  ```bash
  docker run --rm --runtime=nvidia nvidia/cuda:11.8.0-runtime-ubuntu22.04 nvidia-smi
  ```
- **Check kernel parameters:**
  ```bash
  cat /proc/cmdline | grep nvidia-drm
  ```
- **Verify dummy plug is inserted (headless systems)**

### Poor Performance / Blurry Text
- **Enable FullColor 4:4:4 encoding in RetroArch settings**
  - Note: NVIDIA GPU supports zero-copy; Intel/AMD will fall back to CPU encoding
- **Ensure GPU is properly initialized:**
  ```bash
  docker exec retroarch nvidia-smi
  ```

### ROM Library Not Loading
- **Verify ROM directory exists on host:**
  ```bash
  ls -la /mnt/ssd_media/roms
  ```
- **Check container can access ROMs:**
  ```bash
  docker exec retroarch ls /roms
  ```
- **Ensure PUID/PGID match ROM ownership:**
  ```bash
  stat -c "%U:%G" /mnt/ssd_media/roms
  ```

### WebSocket Connection Issues (NPM Proxy)
- **Verify NPM has WebSocket upgrade enabled**  
  See [QUICK_START.md](QUICK_START.md) for configuration
- **Test direct port access works:**
  ```
  http://192.168.1.17:3000
  ```
- **Check NPM logs for upstream errors:**
  ```bash
  docker logs nginx-proxy-manager
  ```

## Security Considerations

⚠️ **WARNING:** The RetroArch container includes:
- Passwordless terminal access with `sudo` capability
- No default authentication
- Self-signed HTTPS certificate

### Recommendations
- **Local Network Only:** Deploy on trusted LANs only
- **Enable HTTP Auth:** Set `retroarch_custom_user` and `retroarch_password` for basic authentication
- **Use NPM:** Let Nginx Proxy Manager handle external access with SSL certificates
- **Firewall:** Restrict port 3000 to LAN only:
  ```bash
  sudo ufw allow from 192.168.1.0/24 to any port 3000
  ```

## Related Documentation

- **LinuxServer.io RetroArch:** https://docs.linuxserver.io/images/docker-retroarch/
- **RetroArch Official:** https://retroarch.com/
- **KasmVNC:** https://kasmweb.com/
- **NVIDIA Container Toolkit:** https://github.com/NVIDIA/nvidia-container-toolkit

## Support

For issues:
1. Check logs: `docker logs retroarch`
2. Verify prerequisites in this README
3. Review [QUICK_START.md](QUICK_START.md) for NPM integration
4. Consult LinuxServer.io documentation for container-specific issues
