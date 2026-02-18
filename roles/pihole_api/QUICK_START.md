# Pi-hole API Role - Quick Start Guide

## Installation

The role is already included in your Homelab-Ansible project at `roles/pihole_api/`.

## Common Tasks

### 1. Fix Rate Limiting (Most Common Use Case)

**Problem**: "Client 10.0.0.2 has been rate-limited for at least 2 seconds (current limit: 1000 queries per 60 seconds)"

**Solution**:

```bash
ansible-playbook roles/pihole_api/examples/rate_limit_fix.yml
```

This playbook:

- Authenticates with Pi-hole API
- Checks current rate limit configuration
- Updates to 10000 queries/60s (only if different)
- Verifies the change

**Result**: Rate limit increased 10x, preventing future rate-limit errors.

---

### 2. Identify Heavy Clients

Find out which client is making excessive DNS queries:

```bash
ansible-playbook roles/pihole_api/examples/identify_rate_limit_source.yml
```

Output shows:

- Top query clients
- Device information for 10.0.0.2
- Recent query patterns
- Recommendations

---

### 3. View Statistics Dashboard

```bash
ansible-playbook roles/pihole_api/examples/metrics_dashboard.yml
```

Shows:

- Total queries today
- Blocked queries percentage
- Top 10 clients
- Top 10 domains
- Query type distribution
- Upstream server stats
- Recently blocked domains

---

### 4. Whitelist a Domain

```yaml
---
- name: Whitelist domain
  hosts: localhost
  connection: local
  tasks:
    - include_role:
        name: pihole_api
        tasks_from: auth.yml
      vars:
        pihole_api_auth_operation: "create_session"
    
    - include_role:
        name: pihole_api
        tasks_from: domains.yml
      vars:
        pihole_api_domain_operation: "whitelist_exact"
        pihole_api_domain: "example.com"
        pihole_api_domain_comment: "Needed for work"
```

---

### 5. Backup Pi-hole Configuration

```bash
ansible-playbook roles/pihole_api/examples/backup_restore.yml
```

Creates backup in `/tmp/pihole-backup-YYYYMMDD.json` containing:

- All domain lists
- Adlists
- Client configurations
- Group assignments
- DNS settings

---

## Variable Reference

### Essential Variables

```yaml
# Connection
pihole_api_target_node: "lenovo_server"  # Where Pi-hole runs
pihole_api_web_port: 8081                 # Pi-hole web port
pihole_api_password: "{{ vault_pihole_admin_password }}"

# Rate Limiting
pihole_api_rate_limit_count: 10000        # Queries per interval
pihole_api_rate_limit_interval: 60        # Seconds
```

### Operation Variables

**Authentication**:

```yaml
pihole_api_operation: "auth"
pihole_api_auth_operation: "create_session"  # or verify_session, destroy_session
```

**Get Statistics**:

```yaml
pihole_api_operation: "metrics"
pihole_api_metrics_operation: "get_summary"  # or get_top_clients, get_top_domains, etc.
```

**Configure Rate Limit**:

```yaml
pihole_api_operation: "config"
pihole_api_config_operation: "configure_rate_limit"
pihole_api_rate_limit_count: 10000
```

**Whitelist Domain**:

```yaml
pihole_api_operation: "domains"
pihole_api_domain_operation: "whitelist_exact"  # or whitelist_regex, blocklist_exact, etc.
pihole_api_domain: "example.com"
pihole_api_domain_comment: "Optional comment"
```

**Enable/Disable Blocking**:

```yaml
pihole_api_operation: "dns_control"
pihole_api_dns_operation: "disable"  # or enable, disable_timer
pihole_api_dns_timer: 300  # For temporary disable (seconds)
```

---

## Quick Playbook Template

```yaml
---
- name: Pi-hole API Task
  hosts: localhost
  connection: local
  gather_facts: false
  
  vars:
    pihole_api_target_node: "lenovo_server"
    pihole_api_password: "{{ vault_pihole_admin_password }}"
  
  tasks:
    # Step 1: Authenticate
    - include_role:
        name: pihole_api
        tasks_from: auth.yml
      vars:
        pihole_api_operation: "auth"
        pihole_api_auth_operation: "create_session"
    
    # Step 2: Do something
    - include_role:
        name: pihole_api
        tasks_from: <TASK_FILE>.yml
      vars:
        pihole_api_operation: "<OPERATION>"
        pihole_api_<OPERATION>_operation: "<SUB_OPERATION>"
        # Additional vars...
    
    # Step 3: Cleanup
    - include_role:
        name: pihole_api
        tasks_from: auth.yml
      vars:
        pihole_api_operation: "auth"
        pihole_api_auth_operation: "destroy_session"
```

Replace:

- `<TASK_FILE>` with: config, metrics, domains, clients, etc.
- `<OPERATION>` with: config, metrics, domains, etc.
- `<SUB_OPERATION>` with specific operation (see examples)

---

## Common Operations Cheat Sheet

| Task | Task File | Operation | Sub-Operation |
| ------ | ----------- | ----------- | --------------- |
| Create session | `auth.yml` | `auth` | `create_session` |
| Get stats | `metrics.yml` | `metrics` | `get_summary` |
| Top clients | `metrics.yml` | `metrics` | `get_top_clients` |
| Fix rate limit | `config.yml` | `config` | `configure_rate_limit` |
| Enable blocking | `dns_control.yml` | `dns_control` | `enable` |
| Disable blocking | `dns_control.yml` | `dns_control` | `disable` |
| Whitelist (exact) | `domains.yml` | `domains` | `whitelist_exact` |
| Whitelist (regex) | `domains.yml` | `domains` | `whitelist_regex` |
| Blocklist (exact) | `domains.yml` | `domains` | `blocklist_exact` |
| Create client | `clients.yml` | `clients` | `create` |
| Update client | `clients.yml` | `clients` | `update` |
| Update gravity | `actions.yml` | `actions` | `update_gravity` |
| Restart DNS | `actions.yml` | `actions` | `restart_dns` |
| Backup config | `teleporter.yml` | `teleporter` | `export` |
| Restore config | `teleporter.yml` | `teleporter` | `import` |

---

## Integration with Main Playbook

Add to `tasks/post_setup_pihole.yml`:

```yaml
- name: Configure Pi-hole rate limiting after deployment
  include_role:
    name: pihole_api
    tasks_from: config.yml
  vars:
    pihole_api_operation: "config"
    pihole_api_config_operation: "configure_rate_limit"
    pihole_api_password: "{{ vault_pihole_admin_password }}"
    pihole_api_rate_limit_count: 10000
    pihole_api_rate_limit_interval: 60
  when: pihole_rate_limit_fix_enabled | default(true)
```

---

## Troubleshooting Quick Fixes

### Authentication Failed

```bash
# Check Pi-hole is running
ansible lenovo_server -a "docker ps --filter name=pihole"

# Verify password in vault
ansible-vault view vault.yml | grep pihole_admin_password

# Test API connectivity
curl -I http://192.168.1.12:8081/api/docs
```

### Module Not Found

```bash
# Verify module exists
ls -la roles/pihole_api/library/pihole_api.py

# Check it's executable
chmod +x roles/pihole_api/library/pihole_api.py
```

### Session Expired

Re-run authentication step:

```yaml
- include_role:
    name: pihole_api
    tasks_from: auth.yml
  vars:
    pihole_api_auth_operation: "create_session"
```

---

## Direct Module Usage (Advanced)

```yaml
- name: Get Pi-hole stats (direct module call)
  pihole_api:
    base_url: "http://192.168.1.12:8081/api"
    password: "{{ vault_pihole_admin_password }}"
    endpoint: "/stats/summary"
    method: GET
  register: stats

- name: Update config (direct module call)
  pihole_api:
    base_url: "http://192.168.1.12:8081/api"
    session_id: "{{ pihole_session_id }}"
    endpoint: "/config"
    method: PATCH
    body:
      dns:
        rateLimit:
          count: 10000
          interval: 60
```

---

## Example Workflows

### Workflow 1: Weekly Backup

```bash
# Create cron job
0 2 * * 0 ansible-playbook /path/to/roles/pihole_api/examples/backup_restore.yml
```

### Workflow 2: Monitor Heavy Clients

```bash
# Run daily
0 8 * * * ansible-playbook /path/to/roles/pihole_api/examples/metrics_dashboard.yml | mail -s "Pi-hole Stats" admin@example.com
```

### Workflow 3: Auto-Fix Rate Limits

```yaml
# In main.yml - run after every deployment
- include_role:
    name: pihole_api
    tasks_from: config.yml
  vars:
    pihole_api_config_operation: "configure_rate_limit"
  tags: [pihole, config]
```

---

## Next Steps

1. **Run the Rate Limit Fix**: `ansible-playbook roles/pihole_api/examples/rate_limit_fix.yml`
2. **Investigate 10.0.0.2**: `ansible-playbook roles/pihole_api/examples/identify_rate_limit_source.yml`
3. **Review Examples**: Browse `roles/pihole_api/examples/` for more use cases
4. **Read Full Docs**: See [README.md](README.md) for complete API coverage

---

## Quick Reference Card

```text
┌─────────────────────────────────────────────────────────┐
│ Pi-hole API - Most Common Commands                      │
├─────────────────────────────────────────────────────────┤
│ Fix Rate Limiting:                                      │
│   ansible-playbook roles/pihole_api/examples/           │
│                    rate_limit_fix.yml                   │
│                                                         │
│ Identify Heavy Client:                                  │
│   ansible-playbook roles/pihole_api/examples/           │
│                    identify_rate_limit_source.yml       │
│                                                         │
│ View Dashboard:                                         │
│   ansible-playbook roles/pihole_api/examples/           │
│                    metrics_dashboard.yml                │
│                                                         │
│ Backup Config:                                          │
│   ansible-playbook roles/pihole_api/examples/           │
│                    backup_restore.yml                   │
└─────────────────────────────────────────────────────────┘
```
