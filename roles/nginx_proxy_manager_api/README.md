# NGINX Proxy Manager API Automation Role

Ansible role for managing NGINX Proxy Manager (NPM) configuration via REST API. Automates Let's Encrypt wildcard certificate creation using DNS-01 challenge and configures reverse proxy hosts with SSL termination.

## Features

- ✅ **Idempotent Operations** - Safe to run multiple times without duplicates
- 🔒 **Let's Encrypt Wildcard Certificates** - Automated DNS-01 challenge via DuckDNS
- 🌐 **Reverse Proxy Management** - Create/update proxy hosts with SSL
- 🔧 **HTTP & HTTPS Backend Support** - Critical for services like OpenVPN Admin UI
- 🚀 **WebSocket Support** - Required for Jellyfin, OpenVPN, and other real-time services
- 📊 **Comprehensive Logging** - Detailed output for debugging

## Requirements

- NGINX Proxy Manager running and accessible via API
- DuckDNS account with valid token (for DNS-01 challenge)
- Ansible 2.12+
- `community.general` collection (for `uri` module)

## Role Variables

### Required Variables

```yaml
# NPM API connection
npm_api_url: "http://192.168.1.10:81"
npm_user: "admin@example.com"
npm_password: "changeme"  # Use vault!

# Domain & DNS configuration
npm_domain: "chadbartel.duckdns.org"
duckdns_token: "your-duckdns-token"  # Use vault!

# Proxy host definitions
proxy_hosts:
  - domain: "jellyfin.chadbartel.duckdns.org"
    forward_host: "192.168.1.12"
    forward_port: 8096
    scheme: "http"
    
  - domain: "vpn.chadbartel.duckdns.org"
    forward_host: "192.168.1.10"
    forward_port: 943
    scheme: "https"  # CRITICAL for OpenVPN Admin UI
```

### Optional Variables

See [defaults/main.yml](defaults/main.yml) for complete list of configurable options.

## Usage

### Basic Usage

```yaml
- name: Configure NPM with SSL certificates and proxy hosts
  hosts: localhost
  roles:
    - role: nginx_proxy_manager_api
      vars:
        npm_api_url: "http://192.168.1.10:81"
        npm_user: "{{ vault_npm_admin_email }}"
        npm_password: "{{ vault_npm_admin_password }}"
        npm_domain: "chadbartel.duckdns.org"
        duckdns_token: "{{ vault_duckdns_token }}"
        proxy_hosts:
          - domain: "jellyfin.{{ npm_domain }}"
            forward_host: "192.168.1.12"
            forward_port: 8096
            scheme: "http"
```

### Advanced Usage with Custom SSL Settings

```yaml
- name: Configure NPM with custom SSL and proxy settings
  hosts: localhost
  roles:
    - role: nginx_proxy_manager_api
      vars:
        npm_api_url: "http://192.168.1.10:81"
        npm_user: "{{ vault_npm_admin_email }}"
        npm_password: "{{ vault_npm_admin_password }}"
        npm_domain: "chadbartel.duckdns.org"
        duckdns_token: "{{ vault_duckdns_token }}"
        
        # Custom SSL settings
        npm_ssl_forced: true
        npm_http2_support: true
        npm_hsts_enabled: true
        
        # Proxy hosts with per-host customization
        proxy_hosts:
          - domain: "jellyfin.{{ npm_domain }}"
            forward_host: "192.168.1.12"
            forward_port: 8096
            scheme: "http"
            websockets_enabled: true
            caching_enabled: false
            
          - domain: "vpn.{{ npm_domain }}"
            forward_host: "192.168.1.10"
            forward_port: 943
            scheme: "https"  # OpenVPN requires HTTPS backend
            websockets_enabled: true
            hsts_enabled: true
            hsts_subdomains: false
```

### Integration with Existing Playbook

```yaml
# main.yml
- name: Deploy and configure NGINX Proxy Manager
  hosts: manager_nodes
  become: yes
  tasks:
    # ... deploy NPM stack ...
    
    - name: Wait for NPM to be ready
      ansible.builtin.wait_for:
        host: "{{ ansible_host }}"
        port: 81
        delay: 10
        timeout: 300
        
    - name: Configure NPM via API
      ansible.builtin.import_role:
        name: nginx_proxy_manager_api
      vars:
        npm_api_url: "http://{{ ansible_host }}:81"
        npm_domain: "{{ vault_domain }}"
        duckdns_token: "{{ vault_duckdns_token }}"
```

## Proxy Host Configuration

Each proxy host requires the following parameters:

| Parameter | Required | Description | Example |
| ----------- | ---------- | ------------- | --------- |
| `domain` | ✅ Yes | Fully qualified domain name | `jellyfin.example.com` |
| `forward_host` | ✅ Yes | Backend service IP/hostname | `192.168.1.12` |
| `forward_port` | ✅ Yes | Backend service port | `8096` |
| `scheme` | ✅ Yes | Backend protocol (`http` or `https`) | `http` |
| `websockets_enabled` | ❌ No | Enable WebSocket support | `true` (default) |
| `ssl_forced` | ❌ No | Force HTTPS redirect | `true` (default) |
| `http2_support` | ❌ No | Enable HTTP/2 | `true` (default) |
| `hsts_enabled` | ❌ No | Enable HSTS header | `true` (default) |
| `block_exploits` | ❌ No | Block common exploits | `true` (default) |
| `caching_enabled` | ❌ No | Enable caching | `false` (default) |

### Backend Scheme Selection

**Critical Decision**: The `scheme` parameter determines how NPM communicates with your backend service.

- **`scheme: "http"`** - Use for most services (Jellyfin, Portainer, Pi-hole)

  ```yaml
  - domain: "jellyfin.example.com"
    forward_host: "192.168.1.12"
    forward_port: 8096
    scheme: "http"  # Jellyfin speaks HTTP internally
  ```

- **`scheme: "https"`** - Use when backend requires HTTPS (OpenVPN Admin UI)

  ```yaml
  - domain: "vpn.example.com"
    forward_host: "192.168.1.10"
    forward_port: 943
    scheme: "https"  # OpenVPN Admin UI requires HTTPS
  ```

**Why this matters for OpenVPN**:

- OpenVPN Access Server Admin UI serves HTTPS on port 943
- Using `scheme: "http"` causes "Failed to load resource" errors
- NPM must connect to backend via HTTPS to match OpenVPN's expectations

## Certificate Management

The role automatically:

1. ✅ Checks for existing wildcard certificate
2. ✅ Skips creation if certificate already exists (idempotent)
3. ✅ Creates new certificate via DNS-01 challenge if missing
4. ✅ Uses DuckDNS as DNS provider for challenge verification
5. ✅ Applies certificate to all proxy hosts

**Certificate includes**:

- Wildcard: `*.chadbartel.duckdns.org`
- Apex domain: `chadbartel.duckdns.org`

## DNS Configuration

Before running this role, ensure DNS records are configured:

```bash
# DuckDNS API call to set IP
curl "https://www.duckdns.org/update?domains=chadbartel&token=YOUR_TOKEN&ip=YOUR_PUBLIC_IP"
```

Or use automatic IP detection:

```bash
curl "https://www.duckdns.org/update?domains=chadbartel&token=YOUR_TOKEN"
```

**Required DNS records** (handled by DuckDNS wildcard):

- `jellyfin.chadbartel.duckdns.org` → `YOUR_PUBLIC_IP`
- `vpn.chadbartel.duckdns.org` → `YOUR_PUBLIC_IP`

## Troubleshooting

### Certificate Creation Fails

**Error**: DNS-01 challenge fails with "NXDOMAIN"

**Solution**:

1. Verify DuckDNS token is correct
2. Ensure domain is registered with DuckDNS
3. Check DNS propagation: `dig _acme-challenge.chadbartel.duckdns.org TXT`
4. Increase `propagation_seconds` in [manage_certificate.yml](tasks/manage_certificate.yml)

### Proxy Host Returns 502 Bad Gateway

**Possible Causes**:

1. **Backend service not running**

   ```bash
   # Check service status
   curl http://192.168.1.12:8096
   ```

2. **Wrong backend scheme** (most common with OpenVPN)

   ```yaml
   # ❌ WRONG - causes 502 or SSL errors
   scheme: "http"  # for OpenVPN
   
   # ✅ CORRECT
   scheme: "https"  # for OpenVPN
   ```

3. **Firewall blocking NPM → backend**

   ```bash
   # Test from NPM host
   docker exec <npm-container> curl http://192.168.1.12:8096
   ```

### OpenVPN Admin UI "Failed to Load Resource"

**Symptom**: OpenVPN client works, but Admin UI shows errors behind NPM proxy

**Root Cause**: Backend scheme mismatch

**Solution**:

```yaml
proxy_hosts:
  - domain: "vpn.chadbartel.duckdns.org"
    forward_host: "192.168.1.10"
    forward_port: 943
    scheme: "https"  # MUST be https for OpenVPN Admin UI
```

### Authentication Fails

**Error**: "Invalid credentials" or 401 Unauthorized

**Solutions**:

1. Verify credentials match NPM admin account
2. Check if using default credentials (`admin@example.com` / `changeme`)
3. Reset password via NPM web UI if needed
4. Use vault for credentials:

   ```yaml
   npm_user: "{{ vault_npm_admin_email }}"
   npm_password: "{{ vault_npm_admin_password }}"
   ```

## Examples

See the [examples/](examples/) directory for complete usage examples:

- [Basic Setup](examples/basic_setup.yml) - Minimal configuration
- [Advanced Setup](examples/advanced_setup.yml) - Custom SSL and proxy settings
- [SSL Setup](examples/ssl_setup.yml) - Certificate-focused configuration
- [Complete Setup](examples/complete_setup.yml) - Full production configuration

## Security Considerations

1. **Never commit secrets in plaintext**

   ```yaml
   # ❌ BAD
   npm_password: "mysecretpassword"
   
   # ✅ GOOD
   npm_password: "{{ vault_npm_admin_password }}"
   ```

2. **Use Ansible Vault for sensitive data**

   ```bash
   ansible-vault create vault.yml
   # Add: vault_npm_admin_password, vault_duckdns_token
   ```

3. **Restrict NPM API access**
   - Use firewall rules to limit access to NPM's port 81
   - Consider using a VPN for NPM admin access

4. **Rotate credentials regularly**
   - Change NPM admin password periodically
   - Rotate DuckDNS token if compromised

## Dependencies

None. This role is self-contained.

## License

MIT

## Author Information

Created for Homelab-Ansible infrastructure automation project.

## See Also

- [NGINX Proxy Manager Documentation](https://nginxproxymanager.com/)
- [Let's Encrypt DNS-01 Challenge](https://letsencrypt.org/docs/challenge-types/#dns-01-challenge)
- [DuckDNS Documentation](https://www.duckdns.org/spec.jsp)
- [Homelab-Ansible Project](../../README.md)
