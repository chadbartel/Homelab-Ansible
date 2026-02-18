# Migration Guide: nginx_proxy_manager_config → nginx_proxy_manager_api

This guide helps you migrate from the existing `nginx_proxy_manager_config` role to the new `nginx_proxy_manager_api` role.

## Key Differences

| Feature | nginx_proxy_manager_config | nginx_proxy_manager_api |
| --------- | --------------------------- | ------------------------- |
| **Scope** | Basic proxy host configuration | Full SSL + proxy management |
| **SSL Certificates** | ❌ Manual setup required | ✅ Automated Let's Encrypt (DNS-01) |
| **Backend Schemes** | HTTP only | HTTP and HTTPS |
| **Idempotency** | Partial (checks existing hosts) | Full (checks certs and hosts) |
| **Use Case** | Simple reverse proxy | Complete HTTPS automation |

## When to Use Each Role

### Use `nginx_proxy_manager_config` when

- You already have SSL certificates configured
- You only need basic reverse proxy setup
- You're managing certificates manually or externally

### Use `nginx_proxy_manager_api` when

- You want automated Let's Encrypt wildcard certificates
- You need HTTPS for services (especially OpenVPN Admin UI)
- You want complete SSL automation via DNS-01 challenge
- You need to support both HTTP and HTTPS backend schemes

## Migration Steps

### Step 1: Understand Current Configuration

Your current `post_setup_npm.yml` uses:

```yaml
- include_role:
    name: nginx_proxy_manager_config
    tasks_from: proxy_hosts
  vars:
    npm_config_proxy_hosts: "{{ npm_proxy_hosts_config }}"
```

### Step 2: Update Variables

**Old format** (nginx_proxy_manager_config):

```yaml
# In host_vars or vars.yml
proxy_hosts:
  - domain: "jellyfin.example.com"
    host: "192.168.1.12"
    port: 8096
    scheme: "http"
```

**New format** (nginx_proxy_manager_api):

```yaml
# In vars.yml
npm_domain: "chadbartel.duckdns.org"
duckdns_token: "{{ vault_duckdns_token }}"

proxy_hosts:
  - domain: "jellyfin.{{ npm_domain }}"
    forward_host: "192.168.1.12"
    forward_port: 8096
    scheme: "http"
    websockets_enabled: true
```

**Key changes**:

- `host` → `forward_host`
- `port` → `forward_port`
- Added `npm_domain` variable
- Added `duckdns_token` for DNS-01 challenge
- Added optional `websockets_enabled` (defaults to `true`)

### Step 3: Add Required Variables

Add to your `vars.yml`:

```yaml
# Domain configuration
vault_domain_name: "chadbartel.duckdns.org"

# NPM API settings
npm_api_url: "http://{{ hostvars[groups['manager_nodes'][0]].ansible_host }}:{{ proxy_host_port }}"
```

Add to your `vault.yml`:

```yaml
# DuckDNS credentials
vault_duckdns_token: "your-duckdns-token-here"

# NPM admin password (if not already present)
vault_npm_admin_password: "your-npm-password"
```

### Step 4: Update Task File

**Option A: Replace existing role** (recommended)

Replace in `tasks/post_setup_npm.yml`:

```yaml
# OLD
- include_role:
    name: nginx_proxy_manager_config
    tasks_from: proxy_hosts

# NEW
- import_role:
    name: nginx_proxy_manager_api
  vars:
    npm_user: "{{ admin_email }}"
    npm_password: "{{ vault_npm_admin_password }}"
    npm_domain: "{{ vault_domain_name }}"
    duckdns_token: "{{ vault_duckdns_token }}"
```

**Option B: Run both roles** (gradual migration)

```yaml
# Keep existing role for basic proxies
- include_role:
    name: nginx_proxy_manager_config
    tasks_from: proxy_hosts

# Add new role for SSL automation
- import_role:
    name: nginx_proxy_manager_api
  when: enable_ssl_automation | default(false)
```

### Step 5: Test Migration

```bash
# 1. Verify variables are defined
ansible-playbook main.yml --check --tags=npm

# 2. Run in isolation first
ansible-playbook roles/nginx_proxy_manager_api/examples/basic_setup.yml

# 3. Run full deployment
ansible-playbook main.yml --tags=npm
```

## Variable Mapping Reference

| Old (nginx_proxy_manager_config) | New (nginx_proxy_manager_api) |
| ---------------------------------- | ------------------------------ |
| `npm_config_service_name` | N/A (API-based, no container access) |
| `npm_config_web_port` | `proxy_host_port` (in npm_api_url) |
| `npm_config_admin_email` | `npm_user` |
| `npm_config_admin_password` | `npm_password` |
| `npm_config_proxy_hosts[].domain` | `proxy_hosts[].domain` |
| `npm_config_proxy_hosts[].forward_host` | `proxy_hosts[].forward_host` |
| `npm_config_proxy_hosts[].forward_port` | `proxy_hosts[].forward_port` |
| `npm_config_proxy_hosts[].forward_scheme` | `proxy_hosts[].scheme` |
| N/A | `npm_domain` (new) |
| N/A | `duckdns_token` (new) |
| N/A | `npm_cert_id` (auto-generated) |

## OpenVPN Admin UI Fix

The new role specifically addresses the OpenVPN Admin UI issue:

**Before** (didn't work):

```yaml
proxy_hosts:
  - domain: "vpn.example.com"
    forward_host: "192.168.1.10"
    forward_port: 943
    forward_scheme: "http"  # WRONG - causes "Failed to load resource"
```

**After** (works correctly):

```yaml
proxy_hosts:
  - domain: "vpn.{{ npm_domain }}"
    forward_host: "192.168.1.10"
    forward_port: 943
    scheme: "https"  # CORRECT - matches OpenVPN's HTTPS backend
    websockets_enabled: true
    hsts_enabled: true
```

## Rollback Plan

If you need to rollback:

```bash
# 1. Comment out nginx_proxy_manager_api role
# 2. Restore nginx_proxy_manager_config role
# 3. Manually delete SSL certificate from NPM UI
# 4. Redeploy with old configuration
ansible-playbook main.yml --tags=npm
```

## Support & Troubleshooting

See the main [README.md](README.md#troubleshooting) for detailed troubleshooting steps.

Common migration issues:

- **Missing duckdns_token**: Ensure vault.yml has `vault_duckdns_token`
- **Wrong API URL**: Check `npm_api_url` points to NPM's port 81
- **Certificate creation fails**: Verify DuckDNS domain is registered
- **502 Bad Gateway**: Check backend `scheme` is correct (http vs https)
