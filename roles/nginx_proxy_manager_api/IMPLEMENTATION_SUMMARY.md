# nginx_proxy_manager_api Role - Implementation Summary

## Overview

✅ **Role Created**: `roles/nginx_proxy_manager_api/`

A complete Ansible role for automating NGINX Proxy Manager configuration via REST API, including:

- Let's Encrypt wildcard certificate automation (DNS-01 challenge via DuckDNS)
- Idempotent reverse proxy host management
- Support for both HTTP and HTTPS backend schemes (critical for OpenVPN Admin UI)
- WebSocket support for real-time applications (Jellyfin, OpenVPN, etc.)

## What Was Created

### Directory Structure

```texts
roles/nginx_proxy_manager_api/
├── README.md                      # Comprehensive documentation
├── QUICK_START.md                 # 5-minute getting started guide
├── MIGRATION.md                   # Migration from nginx_proxy_manager_config
├── defaults/
│   └── main.yml                   # Default variables (fully documented)
├── tasks/
│   ├── main.yml                   # Main orchestrator (4 phases)
│   ├── authenticate.yml           # NPM API authentication
│   ├── manage_certificate.yml     # Let's Encrypt wildcard cert (DNS-01)
│   ├── manage_proxy_hosts.yml     # Proxy host iteration
│   └── process_proxy_host.yml     # Individual proxy host creation/update
├── meta/
│   └── main.yml                   # Role metadata for Ansible Galaxy
├── examples/
│   ├── basic_setup.yml           # Minimal configuration example
│   ├── advanced_setup.yml        # Advanced with custom settings
│   ├── complete_setup.yml        # Full production integration
│   └── integration_playbook.yml  # Integration with existing infrastructure
├── vars.example.yml              # Variable template for easy configuration
└── vault.example.yml             # Vault template for secrets
```

## Key Features

### 1. **Idempotent Operations**

- ✅ Checks for existing certificates before creating new ones
- ✅ Detects existing proxy hosts and updates only when changed
- ✅ Safe to run multiple times without duplicates

### 2. **Let's Encrypt Wildcard Certificates**

- ✅ Automated DNS-01 challenge via DuckDNS
- ✅ Covers both wildcard (`*.example.com`) and apex domain (`example.com`)
- ✅ Automatic renewal support (re-run playbook before expiry)

### 3. **Reverse Proxy Management**

- ✅ Create/update proxy hosts via NPM API
- ✅ SSL termination with forced HTTPS redirect
- ✅ HTTP/2 and HSTS support
- ✅ WebSocket proxying enabled by default

### 4. **OpenVPN Admin UI Fix**

- ✅ Supports HTTPS backend scheme (critical for OpenVPN Admin UI)
- ✅ Prevents "Failed to load resource" errors
- ✅ Configurable per-host backend scheme (http or https)

## Quick Start

### 1. Configure Variables

Add to `vars.yml`:

```yaml
npm_api_url: "http://192.168.1.10:81"
admin_email: "admin@example.com"
vault_domain_name: "chadbartel.duckdns.org"
```

Add to `vault.yml`:

```yaml
vault_npm_admin_password: "your-npm-password"
vault_duckdns_token: "your-duckdns-token"
```

### 2. Define Proxy Hosts

In `vars.yml`:

```yaml
proxy_hosts:
  - domain: "jellyfin.{{ vault_domain_name }}"
    forward_host: "192.168.1.12"
    forward_port: 8096
    scheme: "http"
  
  - domain: "vpn.{{ vault_domain_name }}"
    forward_host: "192.168.1.10"
    forward_port: 943
    scheme: "https"  # CRITICAL for OpenVPN Admin UI
```

### 3. Create Playbook

Create `configure_npm_ssl.yml`:

```yaml
---
- name: Configure NPM with SSL
  hosts: localhost
  gather_facts: false
  vars_files:
    - vars.yml
    - vault.yml
  vars:
    npm_user: "{{ admin_email }}"
    npm_password: "{{ vault_npm_admin_password }}"
    npm_domain: "{{ vault_domain_name }}"
    duckdns_token: "{{ vault_duckdns_token }}"
  roles:
    - nginx_proxy_manager_api
```

### 4. Run Playbook

```bash
# Syntax check
ansible-playbook configure_npm_ssl.yml --syntax-check

# Dry run
ansible-playbook configure_npm_ssl.yml --check

# Execute
ansible-playbook configure_npm_ssl.yml --ask-vault-pass
```

## Integration with Existing Infrastructure

### Option 1: Standalone Playbook (Recommended for Testing)

Create a separate playbook to run independently:

```bash
ansible-playbook configure_npm_ssl.yml --ask-vault-pass
```

### Option 2: Add to main.yml

Add this play to your `main.yml` after NPM stack deployment:

```yaml
# ... existing NPM deployment tasks ...

- name: Configure NPM SSL and Reverse Proxies
  hosts: localhost
  gather_facts: false
  connection: local
  vars_files:
    - vars.yml
    - vault.yml
  vars:
    npm_api_url: "http://{{ hostvars[groups['manager_nodes'][0]].ansible_host }}:{{ proxy_host_port }}"
    npm_user: "{{ admin_email }}"
    npm_password: "{{ vault_npm_admin_password }}"
    npm_domain: "{{ vault_domain_name }}"
    duckdns_token: "{{ vault_duckdns_token }}"
  pre_tasks:
    - name: Wait for NPM API
      ansible.builtin.uri:
        url: "{{ npm_api_url }}/api/schema"
        status_code: 200
        validate_certs: false
      retries: 30
      delay: 10
  roles:
    - role: nginx_proxy_manager_api
      tags: ["npm", "ssl", "https"]
```

### Option 3: Replace Existing Role

In `tasks/post_setup_npm.yml`, replace:

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
  delegate_to: localhost
```

## Required Variables Summary

| Variable | Source | Description |
| ---------- | -------- | ------------- |
| `npm_api_url` | vars.yml | NPM API endpoint (<http://IP:81>) |
| `npm_user` | vars.yml | NPM admin email |
| `npm_password` | vault.yml | NPM admin password (use vault) |
| `npm_domain` | vault.yml | Base domain (e.g., chadbartel.duckdns.org) |
| `duckdns_token` | vault.yml | DuckDNS API token |
| `proxy_hosts` | vars.yml | List of services to proxy |

## OpenVPN Admin UI Configuration

**Critical**: OpenVPN Admin UI requires `scheme: "https"` backend:

```yaml
proxy_hosts:
  - domain: "vpn.{{ npm_domain }}"
    forward_host: "192.168.1.10"
    forward_port: 943
    scheme: "https"  # MUST be https (not http)
    websockets_enabled: true
    hsts_enabled: true
    hsts_subdomains: false
```

**Why**: OpenVPN Access Server serves HTTPS on port 943. Using `scheme: "http"` causes:

- "Failed to load resource" errors
- ERR_SSL_PROTOCOL_ERROR
- Blank Admin UI pages

## Testing & Validation

### 1. Syntax Validation

```bash
# All examples are pre-validated ✅
ansible-playbook roles/nginx_proxy_manager_api/examples/basic_setup.yml --syntax-check
ansible-playbook roles/nginx_proxy_manager_api/examples/advanced_setup.yml --syntax-check
```

### 2. Role-Only Test

```bash
# Test just the role with minimal config
ansible-playbook roles/nginx_proxy_manager_api/examples/basic_setup.yml --ask-vault-pass
```

### 3. Certificate Verification

```bash
# After playbook runs successfully:
curl -I https://jellyfin.chadbartel.duckdns.org
curl -I https://vpn.chadbartel.duckdns.org

# Check certificate details:
openssl s_client -connect jellyfin.chadbartel.duckdns.org:443 -servername jellyfin.chadbartel.duckdns.org < /dev/null 2>/dev/null | openssl x509 -noout -text | grep -A2 "Subject Alternative Name"
```

### 4. Service Accessibility

```bash
# Jellyfin
curl https://jellyfin.chadbartel.duckdns.org

# OpenVPN Admin UI
curl https://vpn.chadbartel.duckdns.org

# Portainer
curl https://portainer.chadbartel.duckdns.org
```

## Troubleshooting

### Certificate Creation Fails

**Error**: "DNS-01 challenge failed" or "NXDOMAIN"

**Solutions**:

1. Verify DuckDNS token: `curl "https://www.duckdns.org/update?domains=chadbartel&token=YOUR_TOKEN"`
2. Check DNS propagation: `dig chadbartel.duckdns.org`
3. Wait 2-5 minutes for DNS to propagate
4. Increase `propagation_seconds` in certificate task (default: 120)

### Proxy Host Returns 502

**Error**: "502 Bad Gateway" after certificate is created

**Solutions**:

1. Verify backend service is running: `curl http://192.168.1.12:8096`
2. For OpenVPN, ensure `scheme: "https"` (not `http`)
3. Check NPM can reach backend: `docker exec <npm-container> curl http://192.168.1.12:8096`
4. Review NPM logs: `docker service logs npm-stack_npm`

### Authentication Fails

**Error**: "Invalid credentials" or 401 Unauthorized

**Solutions**:

1. Verify NPM credentials match admin account
2. Reset password via NPM web UI if needed
3. Ensure vault is decrypted: `ansible-vault view vault.yml`
4. Check API URL is accessible: `curl http://192.168.1.10:81/api/schema`

## Next Steps

1. **Configure DNS**:

   ```bash
   curl "https://www.duckdns.org/update?domains=chadbartel&token=YOUR_TOKEN"
   ```

2. **Port Forwarding**:
   - Forward ports 80/443 to NPM host (192.168.1.10)
   - On your router: External 80 → Internal 192.168.1.10:80
   - On your router: External 443 → Internal 192.168.1.10:443

3. **Test Services**:
   - Jellyfin: <https://jellyfin.chadbartel.duckdns.org>
   - OpenVPN Admin: <https://vpn.chadbartel.duckdns.org>
   - Portainer: <https://portainer.chadbartel.duckdns.org>

4. **Monitor Certificate Expiry**:
   - Let's Encrypt certificates expire after 90 days
   - Re-run playbook monthly to auto-renew
   - Set up a cron job or CI/CD pipeline for automation

## Documentation

- [README.md](roles/nginx_proxy_manager_api/README.md) - Full documentation
- [QUICK_START.md](roles/nginx_proxy_manager_api/QUICK_START.md) - 5-minute guide
- [MIGRATION.md](roles/nginx_proxy_manager_api/MIGRATION.md) - Migration from existing role
- [examples/](roles/nginx_proxy_manager_api/examples/) - Usage examples

## Support & Resources

- **NPM API Documentation**: <https://app.swaggerhub.com/apis-docs/portainer/portainer-ce/>
- **Let's Encrypt DNS-01**: <https://letsencrypt.org/docs/challenge-types/#dns-01-challenge>
- **DuckDNS API**: <https://www.duckdns.org/spec.jsp>
- **Ansible URI Module**: <https://docs.ansible.com/ansible/latest/collections/ansible/builtin/uri_module.html>

---

**Status**: ✅ Role complete and ready for use!

**Version**: 1.0.0  
**Created**: 2026-02-18  
**Author**: Homelab-Ansible Project
