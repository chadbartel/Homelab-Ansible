# Koffan Configuration Role - Quick Start

Get Koffan configured and operational in 5 minutes.

## Prerequisites

- ✅ Koffan service deployed in Docker Swarm
- ✅ Ansible 2.9+ with Docker Swarm access
- ✅ Admin credentials configured in `vault.yml`

## Step 1: Configure Variables

### In `vars.yml`

```yaml
# Already added by integration:
koffan_config_service_name: "koffan-stack_koffan"
koffan_config_swarm_manager: "pi4_01"
koffan_config_target_node: "lenovo_server"
koffan_config_web_port: 80
koffan_config_api_port: 80
```

### In `vault.yml`

```bash
ansible-vault edit vault.yml
# Add this line:
vault_koffan_admin_password: "your_secure_password_here"
```

## Step 2: Deploy Koffan Service

```bash
# Deploy all stacks (including Koffan)
make deploy

# Or deploy just Koffan stack
ansible-playbook main.yml -t "deploy" --tags "koffan"
```

## Step 3: Verify Deployment

```bash
# Check Koffan service is running
docker service ls | grep koffan

# Check container is healthy
docker service ps koffan-stack_koffan

# Verify port is accessible
curl -I http://192.168.1.12:3000
```

## Step 4: Access Koffan

### Direct Access

```text
http://192.168.1.12:3000
```

### Via DNS (if configured)

```text
http://koffan.home.local:3000
```

### Via HTTPS Reverse Proxy

```text
https://koffan.home.local  (if SSL certificate is set up)
```

## Configuration Complete ✅

Koffan is now ready to use!

### What was configured

1. ✅ **Container Discovery** - Automatically finds Koffan in Swarm
2. ✅ **Service Readiness** - Waits for port to be accessible
3. ✅ **API Initialization** - Verifies API connectivity
4. ✅ **DNS Entry** - Added `koffan.home.local` to Pi-hole
5. ✅ **Reverse Proxy** - Configured in NGINX Proxy Manager
6. ✅ **Database Persistence** - SQLite volume persists data

### Optional Enhancements

#### Enable NFS Backup

```yaml
# In vars.yml
koffan_config_setup_nfs_backup: true

# Run post-setup
ansible-playbook main.yml -t "post_setup" --tags "koffan"
```

#### Verify Full Configuration

```bash
# Run idempotency test
make deploy  # First run
make deploy  # Second run - should show minimal changes
```

## API Usage

### Check API Connectivity

```bash
curl http://192.168.1.12:80/api/version
```

### Example: Create Grocery Appointment (if API supports)

```bash
curl -X POST http://192.168.1.12:80/api/appointments \
  -H "Content-Type: application/json" \
  -d '{"name": "Weekly Shopping"}'
```

See [Koffan REST API Documentation](https://github.com/PanSalut/Koffan/wiki/REST-API) for full API reference.

## Troubleshooting

### Service not starting

```bash
docker service logs koffan-stack_koffan --tail 100
```

### Port not responding

```bash
# Check if port 3000 is bound correctly
docker service inspect koffan-stack_koffan | grep -A 5 "Ports"
```

### Database missing

```bash
# Verify named volume exists
docker volume ls | grep koffan_data
docker volume inspect koffan_data
```

### DNS not resolving

```bash
# Check Pi-hole configuration
nslookup koffan.home.local 192.168.1.10
```

## Next Steps

1. **Access the Web UI** - Create your first shopping list
2. **(Optional) Configure Backup** - Set up NFS backup for redundancy
3. **(Optional) Advanced Tuning** - Adjust memory limits if needed
4. **Share Access** - Give family/friends the URL to add items

## Files Modified

- ✅ `templates/koffan-compose.yml.j2` - Docker Compose template
- ✅ `roles/koffan_config/` - Complete configuration role
- ✅ `vars.yml` - Global variables
- ✅ `host_vars/lenovo_server.yml` - Proxy configuration
- ✅ `tasks/post_setup_koffan.yml` - Post-deployment automation
- ✅ `tasks/post_setup.yml` - Integrated into main workflow

## Support

For Koffan app issues: <https://github.com/PanSalut/Koffan>

For Homelab-Ansible integration issues: See project documentation
