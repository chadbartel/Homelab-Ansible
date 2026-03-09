# Pi-hole API Role

Comprehensive Ansible role for managing Pi-hole via its REST API (v6.0). Provides complete coverage of all ~80+ API endpoints with idempotent operations, session management, and extensive examples.

## Features

- **Complete API Coverage**: All 14 endpoint categories (80+ endpoints)
- **Custom Ansible Module**: `pihole_api` module for transparent HTTP/JSON handling
- **Session Management**: Automatic authentication with session reuse
- **Idempotent Operations**: Check-before-create pattern prevents unnecessary changes
- **Modular Task Structure**: Import only the task files you need
- **Comprehensive Examples**: Real-world playbooks for common operations
- **Rate Limit Management**: Built-in tools to diagnose and fix rate-limiting issues

## Supported API Endpoints

### Authentication (`tasks/auth.yml`)

- POST /auth - Create session
- GET /auth - Verify session
- DELETE /auth - Destroy session
- GET /auth/sessions - List sessions
- DELETE /auth/session/{id} - Delete session

### Configuration (`tasks/config.yml`) ⭐ CRITICAL

- GET /config - Get configuration
- PATCH /config - Update configuration
- GET/PUT/DELETE /config/{element}/{value} - Element management
- **Rate Limit Configuration** (idempotent)

### Metrics & Statistics (`tasks/metrics.yml`)

- GET /stats/summary - Overall stats
- GET /stats/top_clients - Top query clients
- GET /stats/top_domains - Top queried domains
- GET /stats/query_types - Query distribution
- GET /stats/upstreams - Upstream server stats
- GET /history/* - Query history
- GET /queries - Real-time queries

### DNS Control (`tasks/dns_control.yml`)

- GET /dns/blocking - Get blocking status
- POST /dns/blocking - Enable/disable blocking

### Domain Management (`tasks/domains.yml`)

- POST /domains/{type}/{kind} - Add domain (whitelist/blocklist, exact/regex)
- GET/PUT/DELETE /domains/{type}/{kind}/{domain} - Manage domains
- POST /domains:batchDelete - Batch delete

### Client Management (`tasks/clients.yml`)

- POST /clients - Create client
- GET/PUT/DELETE /clients/{client} - Manage clients
- GET /clients/_suggestions - Discover clients
- POST /clients:batchDelete - Batch delete

### Group Management (`tasks/groups.yml`)

- POST /groups - Create group
- GET/PUT/DELETE /groups/{name} - Manage groups
- POST /groups:batchDelete - Batch delete

### List Management (`tasks/lists.yml`)

- POST /lists - Create adlist
- GET/PUT/DELETE /lists/{list} - Manage lists
- GET /search/{domain} - Search domain in lists
- POST /lists:batchDelete - Batch delete

### FTL Information (`tasks/info.yml`)

- GET /info/ftl - FTL daemon info
- GET /info/host - Host system info
- GET /info/system - Pi-hole system info
- GET /info/version - Version info
- GET /info/database - Database info
- GET /info/metrics - Prometheus metrics
- GET /info/messages - System messages
- GET /endpoints - List all endpoints

### Logs (`tasks/logs.yml`)

- GET /logs/dnsmasq - Dnsmasq log
- GET /logs/ftl - FTL log
- GET /logs/webserver - Webserver log

### Network (`tasks/network.yml`)

- GET /network/devices - Network devices
- GET /network/gateway - Gateway info
- GET /network/interfaces - Network interfaces
- GET /network/routes - Network routes
- DELETE /network/devices/{id} - Delete device

### Actions (`tasks/actions.yml`)

- POST /action/gravity - Update gravity (adlists)
- POST /action/restartdns - Restart DNS
- POST /action/flush/logs - Flush logs
- POST /action/flush/network - Flush network table

### Teleporter (`tasks/teleporter.yml`)

- GET /teleporter - Export configuration (backup)
- POST /teleporter - Import configuration (restore)

### DHCP (`tasks/dhcp.yml`)

- GET /dhcp/leases - Get DHCP leases
- DELETE /dhcp/leases/{ip} - Delete lease

## Quick Start

### 1. Basic Authentication

```yaml
- name: Authenticate with Pi-hole
  include_role:
    name: pihole_api
    tasks_from: auth.yml
  vars:
    pihole_api_operation: "auth"
    pihole_api_auth_operation: "create_session"
    pihole_api_password: "{{ vault_pihole_admin_password }}"
```

### 2. Fix Rate Limiting (Critical)

```bash
# Run the rate limit fix playbook
ansible-playbook roles/pihole_api/examples/rate_limit_fix.yml
```

This increases the rate limit from the default 1000 queries/60s to 10000 queries/60s, preventing "Client X has been rate-limited" errors.

### 3. Get Statistics

```yaml
- include_role:
    name: pihole_api
    tasks_from: metrics.yml
  vars:
    pihole_api_operation: "metrics"
    pihole_api_metrics_operation: "get_summary"
    pihole_session_id: "{{ pihole_session_id }}"
```

### 4. Manage Domains

```yaml
# Whitelist a domain
- include_role:
    name: pihole_api
    tasks_from: domains.yml
  vars:
    pihole_api_operation: "domains"
    pihole_api_domain_operation: "whitelist_exact"
    pihole_api_domain: "example.com"
    pihole_api_domain_comment: "Whitelisted via API"
    pihole_session_id: "{{ pihole_session_id }}"
```

## Variables

### Connection Settings

| Variable | Default | Description |
| ---------- | --------- | ------------- |
| `pihole_api_base_url` | `http://{{ ansible_host }}:8081/api` | Pi-hole API URL |
| `pihole_api_web_port` | `8081` | Pi-hole web interface port |
| `pihole_api_password` | `{{ vault_pihole_admin_password }}` | Web password |
| `pihole_api_target_node` | `lenovo_server` | Ansible inventory hostname |
| `pihole_api_validate_certs` | `false` | SSL verification |
| `pihole_api_timeout` | `30` | Request timeout (seconds) |

### Rate Limiting

| Variable | Default | Description |
| ---------- | --------- | ------------- |
| `pihole_api_rate_limit_count` | `10000` | Queries per interval |
| `pihole_api_rate_limit_interval` | `60` | Interval in seconds |

### Operations

Set `pihole_api_operation` to choose the category, then set the sub-operation variable:

- `pihole_api_auth_operation` - Authentication operations
- `pihole_api_metrics_operation` - Metrics/stats operations
- `pihole_api_config_operation` - Configuration operations
- `pihole_api_dns_operation` - DNS control operations
- `pihole_api_domain_operation` - Domain management
- `pihole_api_client_operation` - Client management
- And more... (see [defaults/main.yml](defaults/main.yml))

## Examples

All examples are in the [`examples/`](examples/) directory:

| Playbook | Purpose |
| ---------- | --------- |
| [`rate_limit_fix.yml`](examples/rate_limit_fix.yml) | Fix rate-limiting issues (CRITICAL) |
| [`identify_rate_limit_source.yml`](examples/identify_rate_limit_source.yml) | Investigate rate-limit culprits |
| [`authentication.yml`](examples/authentication.yml) | Session management |
| [`metrics_dashboard.yml`](examples/metrics_dashboard.yml) | Statistics gathering |
| [`domain_management.yml`](examples/domain_management.yml) | Whitelist/blocklist management |
| [`client_management.yml`](examples/client_management.yml) | Client configuration |
| [`backup_restore.yml`](examples/backup_restore.yml) | Teleporter backup/restore |

## Usage Patterns

### Pattern 1: One-off API Call

```yaml
- name: Direct module usage
  pihole_api:
    base_url: "http://192.168.1.12:8081/api"
    password: "{{ vault_pihole_admin_password }}"
    endpoint: "/stats/summary"
    method: GET
  register: stats
```

### Pattern 2: Role-based with Session Reuse

```yaml
# Step 1: Authenticate
- include_role:
    name: pihole_api
    tasks_from: auth.yml
  vars:
    pihole_api_operation: "auth"
    pihole_api_auth_operation: "create_session"

# Step 2: Use session for multiple calls
- include_role:
    name: pihole_api
    tasks_from: metrics.yml
  vars:
    pihole_api_operation: "metrics"
    pihole_api_metrics_operation: "get_summary"
    # pihole_session_id automatically set from auth

# Step 3: Cleanup
- include_role:
    name: pihole_api
    tasks_from: auth.yml
  vars:
    pihole_api_operation: "auth"
    pihole_api_auth_operation: "destroy_session"
```

### Pattern 3: Idempotent Configuration

```yaml
# Only updates if values differ
- include_role:
    name: pihole_api
    tasks_from: config.yml
  vars:
    pihole_api_operation: "config"
    pihole_api_config_operation: "configure_rate_limit"
    pihole_api_rate_limit_count: 10000
    pihole_api_rate_limit_interval: 60
```

## Rate Limiting Troubleshooting

**Problem**: "Client X has been rate-limited for at least Y seconds"

**Diagnosis**:

```bash
# Run the diagnostic playbook
ansible-playbook roles/pihole_api/examples/identify_rate_limit_source.yml
```

**Quick Fix**:

```bash
# Increase global rate limit (idempotent)
ansible-playbook roles/pihole_api/examples/rate_limit_fix.yml
```

**Manual Configuration**:

```yaml
# In vars.yml
pihole_api_rate_limit_count: 10000  # 10x default
pihole_api_rate_limit_interval: 60

# Apply via API
- include_role:
    name: pihole_api
    tasks_from: config.yml
  vars:
    pihole_api_config_operation: "configure_rate_limit"
```

## Architecture

```text
roles/pihole_api/
├── library/
│   └── pihole_api.py          # Custom Ansible module
├── tasks/
│   ├── main.yml               # Router (imports other task files)
│   ├── auth.yml               # Authentication endpoints
│   ├── config.yml             # Configuration endpoints (rate limiting)
│   ├── metrics.yml            # Statistics endpoints
│   ├── dns_control.yml        # DNS blocking control
│   ├── domains.yml            # Domain whitelist/blocklist
│   ├── clients.yml            # Client management
│   ├── groups.yml             # Group management
│   ├── lists.yml              # Adlist management
│   ├── info.yml               # FTL/system information
│   ├── logs.yml               # Log access
│   ├── network.yml            # Network information
│   ├── actions.yml            # Gravity update, DNS restart
│   ├── teleporter.yml         # Backup/restore
│   └── dhcp.yml               # DHCP lease management
├── defaults/main.yml          # Default variables
├── meta/main.yml              # Role metadata
└── examples/                  # Example playbooks
```

## Dependencies

- Ansible >= 2.14
- Python >= 3.8 (on control node)
- Pi-hole v6.0 with API enabled
- Network access to Pi-hole API (default port 8081)

## Integration

### With Existing Homelab

```yaml
# In main.yml
- name: Configure Pi-hole rate limiting
  hosts: localhost
  connection: local
  tasks:
    - include_role:
        name: pihole_api
        tasks_from: config.yml
      vars:
        pihole_api_operation: "config"
        pihole_api_config_operation: "configure_rate_limit"
        pihole_api_password: "{{ vault_pihole_admin_password }}"
```

### With Post-Deployment Hook

```yaml
# In tasks/post_setup_pihole.yml
- name: Apply rate limit fix after Pi-hole deployment
  include_role:
    name: pihole_api
    tasks_from: config.yml
  vars:
    pihole_api_operation: "config"
    pihole_api_config_operation: "configure_rate_limit"
```

## Security Considerations

- **No-log**: Password and session ID are marked `no_log: true`
- **Session Management**: Sessions auto-expire after inactivity
- **HTTPS**: Enable `pihole_api_validate_certs: true` for production
- **Vault**: Store `pihole_api_password` in Ansible Vault

## Limitations

- **API Version**: Designed for Pi-hole API v6.0
- **Authentication**: Session-based only (no API key support in v6.0)
- **Network**: Requires direct network access to Pi-hole host

## Troubleshooting

### "401 Unauthorized"

- Check `pihole_api_password` matches Pi-hole web password
- Verify session hasn't expired
- Re-authenticate with `auth_operation: create_session`

### "Connection Timeout"

- Verify Pi-hole container is running
- Check firewall rules for port 8081
- Confirm `pihole_api_base_url` is correct

### "Module not found"

- Ensure `library/pihole_api.py` exists
- Check `ANSIBLE_LIBRARY` path
- Verify role is in `roles/` directory

## License

GPL-3.0-or-later

## Author

Homelab Ansible

## See Also

- [QUICK_START.md](QUICK_START.md) - Quick reference guide
- [Pi-hole API Documentation](http://pihole.chadbartel.duckdns.org/api/docs/)
- [examples/](examples/) - Example playbooks
