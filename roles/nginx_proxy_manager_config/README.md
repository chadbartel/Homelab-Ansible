# NGINX Proxy Manager Configuration Role

Ansible role for idempotent post-deployment configuration of NGINX Proxy Manager (NPM) in Docker Swarm environments.

## Features

- **True Idempotency**: Checks existing proxy hosts before creating new ones
- **Docker Swarm Native**: Automatic container discovery across Swarm nodes
- **Modular Task Files**: Use individual task files or the complete role
- **SSL Certificate Management**: Configurable SSL/TLS settings per proxy host
- **API-Based**: Uses NPM REST API for reliable configuration

## Requirements

- Ansible 2.9 or higher
- Docker Swarm cluster with NPM service deployed
- NPM admin credentials
- Python `requests` library on control node

## Role Variables

### Service Discovery

```yaml
npm_config_service_name: "npm-stack_npm"  # Swarm service name
npm_config_swarm_manager: "pi4_01"  # Manager node hostname
npm_config_target_node: "lenovo_server"  # Node where NPM runs
npm_config_web_port: 8181  # NPM web interface port
```

### Authentication

```yaml
npm_config_admin_email: "admin@example.com"
npm_config_admin_password: ""  # Override with vault variable
```

### Proxy Host Configuration

```yaml
npm_config_proxy_hosts:
  - domain: "example.com"
    forward_scheme: "http"  # or "https"
    forward_host: "192.168.1.100"
    forward_port: 8080
    ssl_certificate_id: 0  # 0 for no SSL, >0 for cert ID
    ssl_forced: false
    websocket_upgrade: true
    block_exploits: true
    caching_enabled: false
```

### SSL/TLS Defaults

```yaml
npm_config_default_ssl_cert_id: 0
npm_config_ssl_forced: false
npm_config_hsts_enabled: false
npm_config_hsts_subdomains: false
npm_config_http2_support: false
```

See [defaults/main.yml](defaults/main.yml) for all available variables.

## Dependencies

None.

## Example Playbook

### Basic Usage

```yaml
- hosts: localhost
  vars:
    npm_config_admin_email: "admin@example.com"
    npm_config_admin_password: "{{ vault_npm_password }}"
    npm_config_proxy_hosts:
      - domain: "jellyfin.home.local"
        forward_host: "192.168.1.12"
        forward_port: 8096
      - domain: "pihole.home.local"
        forward_host: "192.168.1.12"
        forward_port: 8081
  roles:
    - nginx_proxy_manager_config
```

### With SSL Certificates

```yaml
- hosts: localhost
  vars:
    npm_config_admin_email: "admin@example.com"
    npm_config_admin_password: "{{ vault_npm_password }}"
    npm_config_default_ssl_cert_id: 2
    npm_config_ssl_forced: true
    npm_config_hsts_enabled: true
    npm_config_http2_support: true
    npm_config_proxy_hosts:
      - domain: "secure.example.com"
        forward_host: "192.168.1.100"
        forward_port: 8080
        ssl_certificate_id: 2
        ssl_forced: true
  roles:
    - nginx_proxy_manager_config
```

### Using Individual Task Files

```yaml
- hosts: localhost
  tasks:
    - name: Wait for NPM to be ready
      include_role:
        name: nginx_proxy_manager_config
        tasks_from: wait_for_service
      vars:
        npm_config_target_node: "lenovo_server"
        npm_config_web_port: 8181

    - name: Configure proxy hosts
      include_role:
        name: nginx_proxy_manager_config
        tasks_from: proxy_hosts
      vars:
        npm_config_admin_email: "admin@example.com"
        npm_config_admin_password: "{{ vault_npm_password }}"
        npm_config_proxy_hosts:
          - domain: "app.example.com"
            forward_host: "192.168.1.50"
            forward_port: 3000
```

## Task Files

### `discover_container.yml`

Discovers NPM container in Docker Swarm cluster.

**Sets Facts**:

- `npm_container_node`: Node hostname where container runs
- `npm_container_id`: Container ID

### `wait_for_service.yml`

Waits for NPM API to be accessible.

**Requirements**:

- `npm_config_target_node`: Node where NPM is running
- `npm_config_web_port`: NPM web interface port

### `proxy_hosts.yml`

Creates and updates proxy hosts with true idempotency.

**Features**:

- Checks existing proxy hosts before creating
- Updates existing hosts if configuration changed
- Skips unchanged hosts

**Requirements**:

- `npm_config_admin_email`: Admin email for authentication
- `npm_config_admin_password`: Admin password (use vault)
- `npm_config_proxy_hosts`: List of proxy host configurations

## Idempotency

This role is designed for true idempotency:

1. **Proxy Host Creation**: Queries existing hosts via GET `/api/nginx/proxy-hosts` before creating
2. **Configuration Updates**: Only updates hosts where configuration differs
3. **No Duplicates**: Checks by domain name to prevent duplicate proxy hosts

Running the role multiple times with the same configuration will result in:

- First run: Creates proxy hosts (changed=true)
- Subsequent runs: Skips existing hosts (changed=false)

## Docker Swarm Integration

The role automatically discovers containers in Swarm:

1. Queries manager node for service task placement
2. Gets container ID from Swarm task
3. Maps Swarm node hostname to Ansible inventory hostname
4. Delegates tasks to appropriate nodes

**Important**: Ensure Ansible inventory hostnames match Swarm node hostnames or create appropriate mappings.

## Security

- **Credentials**: Never hardcode passwords; use Ansible Vault
- **API Tokens**: Auth tokens are not logged (`no_log: true`)
- **HTTPS**: Configure SSL certificates for production environments
- **Access Lists**: Use `access_list_id` to restrict access

## Troubleshooting

### NPM API not responding

```yaml
# Increase timeout and retries
npm_config_readiness_timeout: 240
npm_config_readiness_retries: 30
npm_config_readiness_delay: 15
```

### Authentication failures

1. Verify admin email and password are correct
2. Check NPM logs: `docker service logs npm-stack_npm`
3. Ensure NPM has completed initial setup

### Proxy hosts not created

1. Check for existing domain conflicts
2. Verify forward_host is accessible from NPM container
3. Review NPM error logs for validation issues

## Examples

See the [examples/](examples/) directory for:

- Basic proxy host setup
- SSL/TLS configuration
- Advanced settings (WebSocket, caching, etc.)
- Integration with other roles

## License

MIT

## Author

Created for the Homelab-Ansible project by thatsmidnight.

## Related Roles

- `jellyfin_config` - Jellyfin post-deployment configuration
- `pihole_config` - Pi-hole post-deployment configuration
