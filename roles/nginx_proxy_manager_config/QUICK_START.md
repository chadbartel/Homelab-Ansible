# NGINX Proxy Manager Config - Quick Start

## Minimal Setup

```yaml
- hosts: localhost
  vars:
    npm_config_admin_password: "{{ vault_npm_password }}"
    npm_config_proxy_hosts:
      - domain: "app.example.com"
        forward_host: "192.168.1.100"
        forward_port: 8080
  roles:
    - nginx_proxy_manager_config
```

## Common Variables

```yaml
# Required
npm_config_admin_email: "admin@example.com"
npm_config_admin_password: "{{ vault_npm_password }}"

# Service Discovery
npm_config_service_name: "npm-stack_npm"
npm_config_target_node: "lenovo_server"
npm_config_web_port: 8181

# Proxy Hosts
npm_config_proxy_hosts:
  - domain: "service.local"
    forward_host: "192.168.1.10"
    forward_port: 3000
```

## Proxy Host Options

```yaml
npm_config_proxy_hosts:
  - domain: "example.com"
    forward_scheme: "http"  # or "https"
    forward_host: "192.168.1.100"
    forward_port: 8080
    ssl_certificate_id: 0  # 0 = no SSL
    ssl_forced: false
    websocket_upgrade: true
    block_exploits: true
    caching_enabled: false
```

## Usage Patterns

### All Tasks

```yaml
roles:
  - nginx_proxy_manager_config
```

### Individual Tasks

```yaml
tasks:
  - include_role:
      name: nginx_proxy_manager_config
      tasks_from: wait_for_service
  
  - include_role:
      name: nginx_proxy_manager_config
      tasks_from: proxy_hosts
```

## Integration Example

```yaml
# In your playbook
- name: Configure NPM
  include_role:
    name: nginx_proxy_manager_config
  vars:
    npm_config_admin_password: "{{ vault_npm_admin_password }}"
    npm_config_proxy_hosts: "{{ proxy_hosts }}"  # From host_vars

# In host_vars/manager_node.yml
proxy_hosts:
  - domain: "jellyfin.home.local"
    forward_host: "192.168.1.12"
    forward_port: 8096
  - domain: "portainer.home.local"
    forward_host: "192.168.1.10"
    forward_port: 9000
```

## Vault Variables

```yaml
# vault.yml (encrypted)
vault_npm_admin_password: "your-secure-password"

# vars.yml (reference)
npm_admin_password: "{{ vault_npm_admin_password }}"
```

## Idempotency Test

```bash
# First run - creates proxy hosts
ansible-playbook playbook.yml

# Second run - should show no changes
ansible-playbook playbook.yml
# Output: changed=0
```
