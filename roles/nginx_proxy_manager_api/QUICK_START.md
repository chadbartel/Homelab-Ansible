# Quick Start Guide - NGINX Proxy Manager API Role

Get HTTPS with Let's Encrypt wildcard certificates in 5 minutes!

## Prerequisites

1. ✅ NGINX Proxy Manager running and accessible
2. ✅ DuckDNS account with domain registered
3. ✅ Ansible 2.12+ installed

## Step 1: Configure Variables

Create or update your `vars.yml`:

```yaml
# NPM API connection
npm_api_url: "http://192.168.1.10:81"
admin_email: "your-email@example.com"

# Domain configuration
vault_domain_name: "yourname.duckdns.org"
```

Create or update your `vault.yml`:

```bash
ansible-vault create vault.yml
# OR edit existing:
ansible-vault edit vault.yml
```

Add to vault:

```yaml
vault_npm_admin_password: "your-npm-password"
vault_duckdns_token: "your-duckdns-token"
```

## Step 2: Define Proxy Hosts

In `vars.yml`, add your services:

```yaml
proxy_hosts:
  # Jellyfin media server
  - domain: "jellyfin.{{ vault_domain_name }}"
    forward_host: "192.168.1.12"
    forward_port: 8096
    scheme: "http"
  
  # OpenVPN Admin UI (requires https backend!)
  - domain: "vpn.{{ vault_domain_name }}"
    forward_host: "192.168.1.10"
    forward_port: 943
    scheme: "https"
```

## Step 3: Create Playbook

Create `configure_npm.yml`:

```yaml
---
- name: Configure NPM with SSL and Proxy Hosts
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

## Step 4: Run Playbook

```bash
# Test connectivity first
ansible localhost -m ping

# Run the playbook
ansible-playbook configure_npm.yml --ask-vault-pass
```

## Step 5: Update DNS

Ensure your DuckDNS domain points to your public IP:

```bash
curl "https://www.duckdns.org/update?domains=yourname&token=YOUR_TOKEN&ip=YOUR_PUBLIC_IP"
```

## Step 6: Test Services

```bash
# Test Jellyfin
curl -I https://jellyfin.yourname.duckdns.org

# Test OpenVPN Admin UI
curl -I https://vpn.yourname.duckdns.org
```

## Common Issues

### Certificate Creation Fails

**Symptom**: "DNS-01 challenge failed"

**Solution**:

1. Verify DuckDNS token: `curl "https://www.duckdns.org/update?domains=yourname&token=YOUR_TOKEN"`
2. Check DNS propagation: `dig yourname.duckdns.org`
3. Wait 2-5 minutes for DNS to propagate

### Proxy Host Returns 502

**Symptom**: Certificate works but proxy shows "502 Bad Gateway"

**Solutions**:

1. Check backend service is running: `curl http://192.168.1.12:8096`
2. For OpenVPN, ensure `scheme: "https"` (not `http`)
3. Verify firewall allows NPM → backend traffic

### OpenVPN Admin UI Shows Errors

**Symptom**: "Failed to load resource" or blank page

**Solution**: Change backend scheme to HTTPS

```yaml
- domain: "vpn.yourname.duckdns.org"
  scheme: "https"  # CRITICAL for OpenVPN Admin UI
  forward_port: 943
```

## Next Steps

- 📖 Read the [full README](README.md) for advanced configuration
- 🔧 Review [examples](examples/) for more complex setups
- 🔐 Set up port forwarding (80/443) on your router
- 🚀 Add more services to your `proxy_hosts` list

## Support

- Check [Troubleshooting](README.md#troubleshooting) section in README
- Review existing role configuration in `defaults/main.yml`
- Test NPM API manually: `curl -X POST http://192.168.1.10:81/api/tokens -d '{"identity":"admin@example.com","secret":"changeme"}'`
