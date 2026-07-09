# Dispatcharr Role

**Deploy Dispatcharr (IPTV/VOD management platform) in modular Docker Compose with GPU acceleration on the monolith.**

## Architecture

### Modular Mode (`DISPATCHARR_ENV=modular`)

```
┌──────────────────────────────────────────────────────────────────┐
│ Monolith Host (192.168.1.17)                                     │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌─────────────────┐  ┌──────────────┐  ┌──────────────┐        │
│  │ dispatcharr-web │  │ dispatcharr- │  │ dispatcharr- │        │
│  │ (uWSGI/Nginx)   │  │ db (PG 17)   │  │ redis        │        │
│  │ Port: 9191      │◄─┤ Port: 5432   │  │ Port: 6379   │        │
│  │ GPU: RTX 2070   │  │              │  │              │        │
│  │ (container)     │  │              │  │              │        │
│  └─────────────────┘  └──────────────┘  └──────────────┘        │
│         ▲                    ▲                    ▲               │
│         │ (flat LAN)         │                    │               │
│      9191:9191              Internal bridge network               │
│  (direct host bind)         (npm_proxy_network)                   │
│         │                                                          │
│  Local IoT (WiFi)                                                 │
│  192.168.1.x:9191                                                │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │ dispatcharr-celery (Background Jobs, DVR, Transcoding)  │   │
│  │ GPU: RTX 2070 (shared)                                   │   │
│  │ Queues: dvr (20 threads), celery (autoscale 6-1)        │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
         ▲
         │ NPM Reverse Proxy
         │ (*.chadbartel.duckdns.org via Let's Encrypt)
         │
    External Internet
```

### Key Features

- **Modular Deployment**: Separate containers for web, PostgreSQL, Redis, and Celery
- **Flat LAN Access**: Web service binds directly to `192.168.1.17:9191` for local IoT access without proxy
- **GPU Acceleration**: RTX 2070 SUPER passthrough to both `web` and `celery` containers via NVIDIA device reservation
- **Service Communication**: All containers join `npm_proxy_network` for bridged networking
- **Explicit Container Names**: Clear naming for operational debugging:
  - `dispatcharr-web` (Django/uWSGI)
  - `dispatcharr-db` (PostgreSQL 17)
  - `dispatcharr-redis` (Redis broker)
  - `dispatcharr-celery` (Background worker)
- **Idempotent Deployment**: Ansible handles state checks and safe restarts
- **Health Checks**: Container-level health probes for startup validation
- **Persistent Storage**: Data at `/mnt/data/dispatcharr/`

---

## Quick Start

### 1. Add Dispatcharr to your playbook

In your main Ansible playbook (e.g., `main.yml`):

```yaml
---
- hosts: monolith
  roles:
    - dispatcharr
```

Or in your host vars (`group_vars/monolith.yml`):

```yaml
---
# Dispatcharr Configuration
dispatcharr_enabled: true
dispatcharr_port: 9191
dispatcharr_postgres_password: "your-secure-password"  # Override default
dispatcharr_django_secret_key: "your-django-secret-key"  # Override default
```

### 2. Deploy

```bash
ansible-playbook main.yml --tags dispatcharr
```

### 3. Verify Deployment

```bash
# Check containers are running
docker ps | grep dispatcharr

# View logs
docker logs dispatcharr-web
docker logs dispatcharr-celery

# Test local access
curl http://192.168.1.17:9191/api/

# Verify GPU passthrough
docker exec dispatcharr-web nvidia-smi
```

---

## Configuration

### Variables (in `defaults/main.yml`)

| Variable | Default | Purpose |
|----------|---------|---------|
| `dispatcharr_host` | `192.168.1.17` | Monolith IP (binds port 9191 here) |
| `dispatcharr_port` | `9191` | External host port (flat LAN access) |
| `dispatcharr_port_internal` | `9191` | Internal container port |
| `dispatcharr_data_dir` | `/mnt/data/dispatcharr` | Persistent storage directory |
| `dispatcharr_postgres_user` | `dispatch` | PostgreSQL user |
| `dispatcharr_postgres_password` | (generated) | PostgreSQL password |
| `dispatcharr_postgres_db` | `dispatcharr` | PostgreSQL database name |
| `dispatcharr_redis_port` | `6379` | Redis port (internal bridge only) |
| `dispatcharr_env` | `modular` | Deployment mode (modular/aio) |
| `dispatcharr_enable_gpu` | `true` | Enable GPU passthrough |
| `dispatcharr_gpu_count` | `1` | Number of GPUs to reserve |
| `dispatcharr_npm_network` | `npm_proxy_network` | NPM bridge network name |
| `dispatcharr_log_level` | `INFO` | Django/application log level |
| `dispatcharr_restart_policy` | `unless-stopped` | Container restart policy |

### Override in `group_vars/monolith.yml`

```yaml
---
dispatcharr_postgres_password: "your-strong-password"
dispatcharr_django_secret_key: "your-50-char-secret"
dispatcharr_celery_concurrency: 6
dispatcharr_enable_gpu: true
```

---

## NPM Reverse Proxy Configuration

Once deployed, configure a reverse proxy host in **Nginx Proxy Manager**:

**Domain**: `dispatcharr.chadbartel.duckdns.org`  
**Scheme**: `http`  
**Forward Hostname**: `dispatcharr-web` (container name on bridge network)  
**Forward Port**: `9191`  
**SSL Certificate**: Let's Encrypt wildcard  

The NPM rule ensures:
- External access: `https://dispatcharr.chadbartel.duckdns.org/` → `dispatcharr-web:9191`
- Local LAN access: `http://192.168.1.17:9191/` (direct, no proxy needed for IoT)

---

## Service Details

### dispatcharr-web (Django + uWSGI + Nginx)

- **Image**: `ghcr.io/dispatcharr/dispatcharr:latest`
- **Container Port**: `9191`
- **Host Port**: `9191` (flat LAN binding)
- **GPU**: RTX 2070 SUPER (1x)
- **Health Check**: HTTP GET `/api/` every 30s
- **Restart**: `unless-stopped`

### dispatcharr-db (PostgreSQL 17)

- **Image**: `postgres:17`
- **Container Port**: `5432`
- **Host Port**: `127.0.0.1:5432` (loopback only, not exposed to LAN)
- **Volume**: `/mnt/data/dispatcharr/db` ← PostgreSQL data
- **Health Check**: `pg_isready` every 30s
- **Restart**: `unless-stopped`

### dispatcharr-redis (Redis)

- **Image**: `redis:latest`
- **Container Port**: `6379`
- **Host Port**: `127.0.0.1:6379` (loopback only)
- **Volume**: `/mnt/data/dispatcharr/redis` ← Redis data
- **Health Check**: `redis-cli ping` every 30s
- **Restart**: `unless-stopped`

### dispatcharr-celery (Celery Worker)

- **Image**: `ghcr.io/dispatcharr/dispatcharr:latest`
- **Entrypoint**: `/app/docker/entrypoint.celery.sh`
- **GPU**: RTX 2070 SUPER (1x, shared with web)
- **Queues**:
  - `dvr`: 20 thread pool (long-running recordings, transcoding)
  - `celery`: autoscale 6-1 (default async tasks)
- **Restart**: `unless-stopped`

---

## Idempotency & State Management

The Ansible role ensures idempotent deployments:

1. **Directory Creation**: Ensures `/mnt/data/dispatcharr/*` exists with `0750` permissions
2. **Compose File Generation**: Renders template with current vars
3. **Container Deployment**: Uses `community.docker.docker_compose_v2` module (idempotent)
4. **Health Verification**: Confirms all containers are running and healthy
5. **Port Verification**: Tests that port `9191` is reachable on the host
6. **State Marker**: Creates `{{ dispatcharr_data_dir }}/.dispatcharr_initialized` on first deployment

To re-deploy with updated configuration:

```bash
ansible-playbook main.yml --tags dispatcharr
```

Ansible will detect changes and only restart affected containers.

---

## Troubleshooting

### Port 9191 not accessible from LAN

- **Check host binding**: `docker port dispatcharr-web` should show `0.0.0.0:9191 -> 9191/tcp`
- **Check firewall**: Verify UFW/host firewall allows port 9191 inbound
- **Check container**: `docker logs dispatcharr-web` for startup errors

### GPU not detected in containers

- **Check nvidia-container-toolkit**: `docker run --rm --gpus all nvidia/cuda:latest nvidia-smi`
- **Check compose syntax**: Verify `deploy.resources.reservations.devices[*].capabilities` includes `gpu`
- **Check Dispatcharr logs**: `docker logs dispatcharr-web | grep -i gpu`

### PostgreSQL connection errors

- **Check service**: `docker exec dispatcharr-db pg_isready`
- **Check credentials**: Verify `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB` in compose file
- **Check bridge**: `docker network inspect npm_proxy_network` to see connected containers

### Celery not processing tasks

- **Check Redis**: `docker exec dispatcharr-redis redis-cli ping` should return `PONG`
- **Check logs**: `docker logs dispatcharr-celery | grep -E "(celery|task|queue|dvr)`
- **Verify network**: Both `dispatcharr-web` and `dispatcharr-celery` should be on `npm_proxy_network`

---

## Advanced Configuration

### External PostgreSQL/Redis (Optional)

To use external managed services instead of internal containers, override in `group_vars/monolith.yml`:

```yaml
---
# Override to use external PostgreSQL
dispatcharr_external_postgres_host: "postgres.example.com"
dispatcharr_external_postgres_port: 5432

# Override to use external Redis
dispatcharr_external_redis_host: "redis.example.com"
dispatcharr_external_redis_port: 6379
```

Then modify the compose template to conditionally use external services.

### Scaling Celery Workers

Increase `dispatcharr_celery_concurrency`:

```yaml
---
dispatcharr_celery_concurrency: 8  # More concurrent background tasks
```

Or run multiple Celery containers with different queue assignments (advanced).

### Custom GPU Count

If you have multiple GPUs:

```yaml
---
dispatcharr_gpu_count: 2  # Use 2 GPUs
```

---

## File Structure

```
roles/dispatcharr/
├── defaults/main.yml           # Role variables
├── tasks/main.yml              # Deployment tasks
├── handlers/main.yml           # Service restart handlers
└── meta/main.yml               # Role metadata

templates/
└── dispatcharr-compose.yml.j2  # Docker Compose template
```

---

## License

This role is part of the Homelab-Ansible project. See LICENSE file in the repository root.
