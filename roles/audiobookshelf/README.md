# Audiobookshelf Ansible Role

Deploy Audiobookshelf (audiobook/ebook management server) on a Docker standalone host with integrated Nginx Proxy Manager routing and storage tiering.

## Features

- ✅ **Docker Compose V2** - No Swarm dependencies, pure standalone Docker
- ✅ **Dual Networking** - Flat LAN access (port 13378) + NPM reverse proxy integration
- ✅ **Storage Tiering** - Fast NVMe for config/metadata, bulk USB SSD for media
- ✅ **Full Idempotency** - Safe to re-run without duplicate proxy hosts
- ✅ **WebSocket Support** - Enables real-time Audiobookshelf library syncing
- ✅ **HTTPS Enforcement** - Auto-configured Let's Encrypt wildcard SSL
- ✅ **User Permission Mapping** - Respects PUID/PGID for volume access

## Role Variables

### Required

None — all variables have sensible defaults.

### Important (typically set in `vars.yml`)

```yaml
# Global variables
monolith_ip: "192.168.1.17"
local_domain: "chadbartel.duckdns.org"
proxy_host_port: 8181
admin_email: "admin@example.com"
vault_npm_admin_password: "your_npm_password"

# Audiobookshelf role will use defaults
audiobookshelf_container_name: "audiobookshelf"
audiobookshelf_image: "ghcr.io/advplyr/audiobookshelf:latest"
audiobookshelf_host_port: 13378
audiobookshelf_config_path: "/opt/audiobookshelf"
audiobookshelf_media_source: "/mnt/ssd_media"
```

### Optional

```yaml
# Storage configuration
audiobookshelf_puid: 1000           # User ID for volume permissions
audiobookshelf_pgid: 1000           # Group ID for volume permissions
audiobookshelf_memory_limit: "2GB"  # Optional memory limit

# Network and DNS
audiobookshelf_network: "homelab-bridge"
audiobookshelf_timezone: "America/Los_Angeles"
```

## Task Files

### Main Tasks (`tasks/main.yml`)

1. **Display Information** - Log deployment configuration
2. **Create Directories** - Initialize `/opt/audiobookshelf` with correct permissions
3. **Template Compose** - Generate `audiobookshelf-compose.yml` from Jinja2 template
4. **Deploy Stack** - Use `community.docker.docker_compose_v2` to start containers
5. **Health Check** - Poll HTTP port until service responds
6. **Configure NPM** - Call `npm_proxy.yml` to set up reverse proxy routing

### NPM Proxy Tasks (`tasks/npm_proxy.yml`)

1. **Authenticate** - Obtain JWT token from NPM API
2. **Fetch Certificates** - Resolve Let's Encrypt wildcard SSL cert ID
3. **Check Idempotency** - Compare existing domains against new configuration
4. **Create Proxy Host** - POST to `/api/nginx/proxy-hosts` (skips if domain exists)
5. **Display Summary** - Show access URLs and next steps

## Storage Architecture

```
Host Storage (Monolith - 192.168.1.17):
├─ /opt/audiobookshelf (NVMe - Fast, small, config-tier)
│  ├─ config/          → /config (Audiobookshelf internal state)
│  └─ metadata/        → /metadata (Database & library metadata)
│
└─ /mnt/ssd_media (USB SSD - Slow, large, media-tier)
   ├─ audiobooks/      → /audiobooks (Bulk audiobook files)
   └─ books/           → /ebooks (Bulk e-book files)
```

## Network Topology

```
Internet (Let's Encrypt wildcard DNS: *.chadbartel.duckdns.org)
    ↓
Router NAT Port 443 → 192.168.1.17:8181 (NPM admin port)
    ↓
Nginx Proxy Manager (proxy container on homelab-bridge)
    ├─ books.chadbartel.duckdns.org → http://audiobookshelf:80 (bridge network)
    └─ Forward Port: 80 (internal to container)
    ↓
Audiobookshelf Container (audiobookshelf on homelab-bridge)
    ├─ Listens: 0.0.0.0:80 (internal)
    ├─ Exposed: 192.168.1.17:13378 (flat LAN)
    └─ Media: /audiobooks, /ebooks (bind mounts to USB SSD)
```

## Playbook Integration

Add to your `main.yml` or a dedicated playbook:

```yaml
---
- name: Deploy Audiobookshelf media server
  hosts: monolith
  gather_facts: false
  become: true
  vars_files:
    - vars.yml
    - vault.yml
  
  roles:
    - audiobookshelf
  
  tags:
    - deploy
    - media
```

Or import as a task:

```yaml
- name: Deploy Audiobookshelf
  ansible.builtin.import_role:
    name: audiobookshelf
```

## Docker Compose Template

The role automatically templates `roles/audiobookshelf/templates/audiobookshelf-compose.yml.j2` with:

- Image: `ghcr.io/advplyr/audiobookshelf:latest`
- Container Name: `audiobookshelf` (explicit)
- Ports: `13378:80` (host:container)
- Networks: External `homelab-bridge` for NPM routing
- Volumes:
  - `/opt/audiobookshelf/config:/config`
  - `/opt/audiobookshelf/metadata:/metadata`
  - `/mnt/ssd_media/audiobooks:/audiobooks`
  - `/mnt/ssd_media/books:/ebooks`
- Environment: `PUID=1000`, `PGID=1000`, `TZ=America/Los_Angeles`

## Usage Examples

### Deploy via Ansible

```bash
# Deploy just Audiobookshelf
ansible-playbook main.yml --tags deploy -e "deploy_role=audiobookshelf"

# Deploy with other stacks
ansible-playbook main.yml --tags deploy
```

### Manual Docker Inspect

```bash
# Check container status
docker ps | grep audiobookshelf

# View logs
docker logs -f audiobookshelf

# Access shell
docker exec -it audiobookshelf sh

# Check disk usage
docker exec audiobookshelf du -sh /config /metadata /audiobooks /ebooks
```

### Add Media

```bash
# Copy audiobooks to mounted SSD
cp /path/to/audiobooks/* /mnt/ssd_media/audiobooks/

# Set permissions (if needed)
sudo chown -R 1000:1000 /mnt/ssd_media/audiobooks
sudo chmod -R 0775 /mnt/ssd_media/audiobooks

# Audiobookshelf will auto-discover on next scan
```

## Troubleshooting

### "502 Bad Gateway" via Proxy

**Cause:** Container name not resolvable on bridge network.
**Fix:** Check if Audiobookshelf container is running and on `homelab-bridge`.

```bash
docker network inspect homelab-bridge | grep audiobookshelf
```

### Container won't start

**Check logs:**

```bash
docker logs audiobookshelf
```

**Common issues:**
- Directory permissions: `chown -R 1000:1000 /opt/audiobookshelf`
- Media mount missing: `ls -la /mnt/ssd_media/{audiobooks,books}`
- Port conflict: `ss -tlnp | grep 13378`

### NPM Proxy Not Created

**Check NPM container:**

```bash
docker logs proxy  # NPM container is named 'proxy'
```

**Re-run proxy configuration:**

```bash
ansible-playbook main.yml -t npm_config
```

### Permission Denied on Media

**Ensure USB SSD volumes have correct ownership:**

```bash
sudo chown -R 1000:1000 /mnt/ssd_media/audiobooks /mnt/ssd_media/books
sudo chmod -R 0775 /mnt/ssd_media/audiobooks /mnt/ssd_media/books
```

## Performance Tuning

### Optimize NVMe Config Path

If `/opt/audiobookshelf` is on a slower device, move to faster storage:

```bash
# Stop container
docker stop audiobookshelf

# Migrate config
sudo rsync -av /opt/audiobookshelf/ /path/to/faster/storage/audiobookshelf/

# Update volume mount in compose template and re-deploy
ansible-playbook main.yml -t deploy
```

### Increase Memory for Large Libraries

```yaml
# In vars.yml
audiobookshelf_memory_limit: "4GB"
```

Then re-deploy:

```bash
ansible-playbook main.yml -t deploy
```

## Related Roles

- `stack_deployer` - Orchestrates Docker Compose deployment
- `nginx_proxy_manager_config` - Configures NPM reverse proxy (called by this role)
- `pihole_config` - DNS resolution for local services

## License

MIT
