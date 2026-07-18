# Audiobookshelf Ansible Role — Quick Start

## 1️⃣ Verify Prerequisites

Ensure these are running on the monolith before deploying Audiobookshelf:

```bash
# Check Docker is installed
docker --version

# Check Compose V2 is available
docker compose version

# Verify homelab-bridge network exists
docker network ls | grep homelab-bridge

# Verify NPM is running (if you want proxy auto-configuration)
docker ps | grep "proxy"  # NPM container named "proxy"

# Verify media mount exists
ls -la /mnt/ssd_media/{audiobooks,books}
```

## 2️⃣ Update Configuration Variables

Add Audiobookshelf to your `vars.yml`:

```yaml
# In vars.yml - already defined in defaults, just ensure you have these:
audiobookshelf_container_name: "audiobookshelf"
audiobookshelf_host_port: 13378
audiobookshelf_config_path: "/opt/audiobookshelf"
audiobookshelf_media_source: "/mnt/ssd_media"
```

Add Audiobookshelf to `group_vars/monolith.yml` proxy_hosts list:

```yaml
# In group_vars/monolith.yml - add this entry to proxy_hosts:
  # Audiobookshelf: audiobook/ebook management
  - domain: "books.{{ local_domain }}"
    host: "audiobookshelf"  # Container name on homelab-bridge
    port: 80  # Internal container port
    scheme: "http"
    block_exploits: true
    websocket_upgrade: true  # Required for library syncing
    ssl_forced: true
    http2_support: true
```

Update `vars.yml` to add DNS entry:

```yaml
# In vars.yml - add to pihole_config_custom_dns_entries:
pihole_config_custom_dns_entries:
  # ... existing entries ...
  - ip: "{{ monolith_ip }}"
    hostname: "audiobookshelf.{{ local_domain }}"
```

## 3️⃣ Create External Bridge Network (if not exists)

```bash
docker network create homelab-bridge
```

Or let Nginx Proxy Manager's deployment create it automatically.

## 4️⃣ Add Audiobookshelf Role to Playbook

Edit `main.yml` to include the `audiobookshelf` role:

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
    - audiobookshelf
```

Or add to an existing playbook section:

```yaml
  roles:
    - nginx_proxy_manager_config
    - pihole_config
    - jellyfin
    - audiobookshelf  # ← Add here
```

## 5️⃣ Deploy Audiobookshelf

Run the playbook:

```bash
# Deploy just Audiobookshelf
ansible-playbook main.yml -t audiobookshelf

# Or deploy all stacks including Audiobookshelf
ansible-playbook main.yml -t deploy
```

## 6️⃣ Verify Deployment

```bash
# Check container is running
docker ps | grep audiobookshelf

# Check connectivity
curl -I http://192.168.1.17:13378

# Check bridge network connection
docker network inspect homelab-bridge | grep audiobookshelf

# Check NPM proxy configuration
curl -I https://books.chadbartel.duckdns.org
```

## 7️⃣ Access Audiobookshelf

**Local Network (no auth required):**
```
http://192.168.1.17:13378
```

**Via Reverse Proxy (Let's Encrypt SSL):**
```
https://books.chadbartel.duckdns.org
```

## 8️⃣ Add Content

Copy audiobooks and ebooks to the media directories:

```bash
# Create subdirectories if they don't exist
mkdir -p /mnt/ssd_media/audiobooks
mkdir -p /mnt/ssd_media/books

# Copy audiobooks (m4b format recommended)
cp /path/to/*.m4b /mnt/ssd_media/audiobooks/

# Copy e-books (epub, pdf, etc.)
cp /path/to/*.epub /mnt/ssd_media/books/

# Set permissions (if needed)
sudo chown -R 1000:1000 /mnt/ssd_media/audiobooks /mnt/ssd_media/books
sudo chmod -R 0775 /mnt/ssd_media/audiobooks /mnt/ssd_media/books
```

Audiobookshelf will auto-discover media on the next scan or you can manually trigger it via the web UI.

## Troubleshooting

### Container fails to start

```bash
docker logs audiobookshelf
```

**Common causes:**
- Permission denied: `sudo chown -R 1000:1000 /opt/audiobookshelf`
- Port already in use: `sudo ss -tlnp | grep 13378`
- Missing media directory: `mkdir -p /mnt/ssd_media/{audiobooks,books}`

### Can't access via proxy domain

```bash
# Check if proxy is running
docker ps | grep proxy

# Verify NPM has the proxy host configured
curl -X GET http://192.168.1.17:8181/api/nginx/proxy-hosts \
  -H "Authorization: Bearer YOUR_NPM_TOKEN"

# Check DNS resolution
nslookup books.chadbartel.duckdns.org 192.168.1.17  # Pi-hole DNS IP
```

### Volumes not mounted

```bash
docker exec audiobookshelf mount | grep -E "audiobooks|ebooks"
```

### Library not scanning

- Check Audiobookshelf logs: `docker logs -f audiobookshelf`
- Verify file permissions: `ls -la /mnt/ssd_media/audiobooks/`
- Trigger manual scan via web UI: Settings → Library → Scan

## Advanced Configuration

### Change Host Port

```yaml
# In vars.yml
audiobookshelf_host_port: 13379  # Choose any available port
```

### Add Memory Limit

```yaml
# In vars.yml
audiobookshelf_memory_limit: "4GB"
```

### Use Different Media Directory

```yaml
# In vars.yml
audiobookshelf_media_source: "/mnt/ssd_media2"  # Different USB SSD
```

Then re-deploy:

```bash
ansible-playbook main.yml -t audiobookshelf
```

## Related Documentation

- [Audiobookshelf Official Docs](https://www.audiobookshelf.org/)
- [Ansible Role Best Practices](https://docs.ansible.com/ansible/latest/user_guide/playbooks_reuse_roles.html)
- [Docker Compose V2 Reference](https://docs.docker.com/compose/compose-file/)
