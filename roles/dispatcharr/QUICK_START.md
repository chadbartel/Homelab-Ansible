# Dispatcharr Quick Start

## Deploy Dispatcharr to the Monolith

### 1. Add to main.yml

```yaml
---
- hosts: monolith
  roles:
    - dispatcharr
```

### 2. Configure (optional overrides in group_vars/monolith.yml)

```yaml
---
dispatcharr_port: 9191
dispatcharr_postgres_password: "your-secure-password"
dispatcharr_django_secret_key: "your-django-secret"
dispatcharr_enable_gpu: true
```

### 3. Deploy

```bash
ansible-playbook main.yml --tags dispatcharr
```

### 4. Verify

```bash
# Check containers
docker ps | grep dispatcharr

# Test web access
curl http://192.168.1.17:9191/api/

# Check GPU passthrough
docker exec dispatcharr-web nvidia-smi
```

### 5. Configure NPM Reverse Proxy

**Nginx Proxy Manager:**
- Domain: `dispatcharr.chadbartel.duckdns.org`
- Forward Host: `dispatcharr-web`
- Forward Port: `9191`
- SSL: Let's Encrypt wildcard

---

## Local LAN Access (Flat Architecture)

Local IoT devices can access Dispatcharr directly **without** going through the reverse proxy:

```
Local Device → http://192.168.1.17:9191/
```

External access still routes through NPM:

```
External Client → https://dispatcharr.chadbartel.duckdns.org/ → NPM → dispatcharr-web:9191
```

---

## Container Overview

| Container | Port | Purpose |
|-----------|------|---------|
| `dispatcharr-web` | `9191` | Web UI + API (uWSGI/Nginx) |
| `dispatcharr-db` | `5432` | PostgreSQL database |
| `dispatcharr-redis` | `6379` | Redis broker |
| `dispatcharr-celery` | – | Background jobs + DVR |

---

## Quick Diagnostics

```bash
# View all logs
docker logs dispatcharr-web
docker logs dispatcharr-celery
docker logs dispatcharr-db

# Check network connectivity
docker exec dispatcharr-web ping dispatcharr-redis
docker exec dispatcharr-celery ping dispatcharr-db

# Verify GPU
docker exec dispatcharr-web nvidia-smi

# Check port binding
docker port dispatcharr-web
```

---

## Next Steps

- Configure M3U sources in the web UI (`http://192.168.1.17:9191`)
- Set up EPG/guide data
- Create stream profiles (FFmpeg, Streamlink, VLC, yt-dlp)
- Configure output profiles (transcoding presets)
- Enable DVR recording (requires Celery + Comskip)
- Add users and manage permissions
- Install custom plugins (optional)

See [README.md](README.md) for detailed configuration.
