# Koffan Configuration Role

Ansible role for post-deployment configuration of Koffan grocery management app in Docker Swarm environments. This role provides idempotent, modular configuration tasks that can be run independently or as a complete setup workflow.

## Features

- ✅ **Idempotent Operations**: All tasks safely re-runnable without side effects
- 🔍 **Automatic Container Discovery**: Finds Koffan containers in Docker Swarm cluster
- 🎯 **Modular Task Files**: Use individual tasks or complete setup workflow
- 🌐 **API Verification**: Validates Koffan API connectivity
- 💾 **NFS Backup Support**: Optional configuration for centralizing database backups
- 🧙 **Simple Configuration**: Minimal setup required for basic functionality

## Requirements

- Ansible 2.9+
- Docker Swarm cluster with Koffan service deployed
- SSH access to cluster nodes
- (Optional) NFS storage for database backups

## Role Variables

### Service Discovery

```yaml
koffan_config_service_name: "koffan-stack_koffan"    # Docker Swarm service name
koffan_config_swarm_manager: "pi4_01"                # Swarm manager node (inventory name)
koffan_config_target_node: "lenovo_server"           # Node where container runs (inventory name)
koffan_config_web_port: 80                           # Container internal port
koffan_config_api_port: 80                           # API port (matches web port)
```

### Service Readiness

```yaml
koffan_config_readiness_retries: 20           # Number of readiness checks
koffan_config_readiness_delay: 10             # Delay between checks (seconds)
koffan_config_readiness_timeout: 180          # Total timeout for port check (seconds)
koffan_config_startup_wait: 45                # Initial wait before checks (seconds)
```

### API Configuration

```yaml
koffan_config_api_endpoint: "http://localhost/api"    # API base URL
koffan_config_admin_user: "admin"                     # Admin username
koffan_config_admin_password: ""                      # Should use vault variable
koffan_config_validate_certs: false                   # SSL certificate validation
```

### NFS Backup Configuration

```yaml
koffan_config_setup_nfs_backup: false                 # Enable NFS backup setup
nfs_export_path: "/mnt/ssd_media"                     # NFS storage mount point
```

## Task Files

### `discover_container.yml`

Discovers the Koffan container running in Docker Swarm and sets facts for use in subsequent tasks.

**Sets Facts:**
- `koffan_task_id`: Swarm task ID
- `koffan_node_name`: Swarm node hostname
- `koffan_container_id`: Docker container ID (12-char)

**Usage:**
```yaml
- include_tasks: discover_container.yml
```

### `wait_for_service.yml`

Waits for Koffan web interface to be fully initialized and responsive.

**Usage:**
```yaml
- include_tasks: wait_for_service.yml
  vars:
    target_host: "192.168.1.12"  # Optional override
```

### `initialize_api.yml`

Verifies Koffan REST API is responding and ready for use.

**Usage:**
```yaml
- include_tasks: initialize_api.yml
  vars:
    target_url: "http://192.168.1.12:80"  # Optional override
```

### `setup_nfs_backup.yml`

Configures NFS backup directory and creates initial database backup. This is optional and only runs if `koffan_config_setup_nfs_backup` is true.

**Usage:**
```yaml
- include_tasks: setup_nfs_backup.yml
  vars:
    nfs_export_path: "/mnt/ssd_media"
```

## Complete Setup Workflow

Run all configuration tasks in sequence (recommended):

```yaml
- name: Configure Koffan completely
  block:
    - include_tasks: tasks/post_setup_koffan.yml
  delegate_to: lenovo_server
  vars:
    koffan_config_service_name: "koffan-stack_koffan"
    koffan_config_swarm_manager: "pi4_01"
    koffan_config_target_node: "lenovo_server"
    koffan_config_admin_password: "{{ vault_koffan_admin_password }}"
```

## Individual Task Usage

Use specific tasks independently:

```yaml
# Just wait for service
- import_role:
    name: koffan_config
    tasks_from: wait_for_service
  vars:
    koffan_config_service_name: "koffan-stack_koffan"

# Just initialize API
- import_role:
    name: koffan_config
    tasks_from: initialize_api
  vars:
    koffan_config_service_name: "koffan-stack_koffan"

# Just setup NFS backup
- import_role:
    name: koffan_config
    tasks_from: setup_nfs_backup
  vars:
    koffan_config_service_name: "koffan-stack_koffan"
    koffan_config_setup_nfs_backup: true
```

## Integration with Homelab-Ansible

Koffan is fully integrated into the main deployment workflow:

1. **Docker Compose Template**: [templates/koffan-compose.yml.j2](../../templates/koffan-compose.yml.j2)
   - Defines Koffan service with persistent SQLite volume
   - Connects to `proxy-network` for NGINX reverse proxy access
   - Configured on port 80 internally

2. **Stack Deployment**: Added to `portainer_stacks` in [vars.yml](../../vars.yml)
   - Auto-deployed during `make deploy`
   - Manages database volume persistence

3. **Post-Setup Configuration**: [tasks/post_setup_koffan.yml](../../tasks/post_setup_koffan.yml)
   - Waits for service readiness
   - Initializes API connectivity
   - (Optional) Sets up NFS backups
   - Integrated into main post-setup workflow

4. **DNS Configuration**: Added to `pihole_config_custom_dns_entries`
   - Automatic DNS entry: `koffan.home.local` → manager node IP
   - Configured via Pi-hole custom DNS

5. **Reverse Proxy**: Added to `proxy_hosts` in [host_vars/lenovo_server.yml](../../host_vars/lenovo_server.yml)
   - NGINX Proxy Manager configuration
   - HTTPS access via `koffan.home.local` with SSL certificate

## Variables

### Required (global or role defaults)

```yaml
koffan_container_name: "koffan"
koffan_image: "ghcr.io/pansalut/koffan:v2.1.1"
local_domain: "home.local"
```

### Optional (from vault.yml)

```yaml
vault_koffan_admin_password: "your_secure_password"
```

## Access URLs

After deployment:

- **Direct Access**: `http://192.168.1.12:3000`
- **DNS Access**: `http://koffan.home.local:3000`
- **Via HTTPS Proxy**: `https://koffan.home.local` (if SSL certificate configured)
- **REST API**: `http://192.168.1.12:80/api`

## Troubleshooting

### Container not found

Ensure service is deployed and running:
```bash
docker service ls | grep koffan
docker service ps koffan-stack_koffan
```

### Port not accessible

Check network connectivity:
```bash
curl -I http://192.168.1.12:3000
```

### API not responding

Check container logs:
```bash
docker logs <container_id>
```

### Database file missing

The SQLite database is stored in the named volume. Verify volume exists:
```bash
docker volume ls | grep koffan_data
```

## Database Management

Koffan uses SQLite with the following characteristics:

- **Location**: `/data/shopping.db` inside container
- **Persistence**: Docker named volume `koffan_data`
- **Survives**: Container restarts, node failures (with NFS backup)
- **Access**: Via REST API or direct database tools if exposed

### Enable NFS Backup

To enable automatic NFS backup:

```yaml
koffan_config_setup_nfs_backup: true
```

This creates a backup directory at `{{ nfs_export_path }}/koffan/` and performs initial backup.

## Examples

See [roles/koffan_config/examples/](examples/) for complete configuration examples.

## License

GPL-3.0-or-later

## Author

Homelab Ansible Contributors
