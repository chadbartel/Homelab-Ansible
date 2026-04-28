# OpenVPN Access Server Configuration Role

Ansible role for idempotent post-deployment configuration of OpenVPN Access Server running in Docker containers.

## Overview

This role provides automated, repeatable configuration for OpenVPN Access Server containers. It handles:

- **Container Discovery**: Automatically locates OpenVPN containers (Swarm, standalone Docker, or direct)
- **Service Readiness**: Waits for OpenVPN Access Server to be fully operational
- **Initial Setup**: Configures admin user, server hostname, and activation
- **User Management**: Creates and manages VPN users with passwords and auto-login settings
- **Idempotency**: Safe to run multiple times without side effects

## Key Features

✓ **True Idempotency** - Checks configuration state before making changes  
✓ **Modular Design** - Use individual task files or the complete role  
✓ **Deployment Agnostic** - Works with Docker Swarm, standalone Docker, or direct container access  
✓ **Auto-Detection** - Automatically determines deployment mode based on variables provided  
✓ **Secure** - No-log support for sensitive data (passwords, activation keys)  
✓ **Flexible** - Supports advanced server configuration options  
✓ **User-Friendly** - Clear output and status messages

## Requirements

- Ansible 2.9 or higher
- Docker with OpenVPN Access Server deployed
- Access to host where container runs
- OpenVPN Access Server container running and accessible

## Deployment Modes

The role automatically detects the deployment mode based on which variables you provide:

| Mode | Configuration | Use Case |
| ------ | -------------- | ---------- |
| **Direct** | `openvpn_config_container_id` | You already know the container ID |
| **Swarm** | `openvpn_config_service_name` + `openvpn_config_swarm_manager` | Docker Swarm deployment |
| **Docker** | `openvpn_config_container_name` + `openvpn_config_target_host` | Standalone Docker container |

## Role Variables

### Container Discovery

Choose **ONE** of the following methods:

#### Direct Container ID (Highest Priority)

```yaml
# Use this if you already know the container ID
openvpn_config_container_id: "a1b2c3d4e5f6"
openvpn_config_target_host: "docker-host"  # Hostname where container runs
```

#### Docker Swarm Discovery

```yaml
# For Docker Swarm deployments
openvpn_config_service_name: "vpn-stack_openvpn-as"  # Swarm service name
openvpn_config_swarm_manager: "swarm-manager-01"     # Manager node hostname
```

#### Standalone Docker Discovery

```yaml
# For standalone Docker containers
openvpn_config_container_name: "openvpn-as"  # Container name
openvpn_config_target_host: "docker-host"    # Hostname where container runs
```

### Service Readiness

```yaml
# Port on which OpenVPN Access Server web UI is accessible
openvpn_config_web_port: 943

# Maximum number of retries when waiting for service to be ready
openvpn_config_readiness_retries: 20

# Delay (in seconds) between readiness check retries
openvpn_config_readiness_delay: 15

# Initial wait time (in seconds) before starting readiness checks
openvpn_config_startup_wait: 30

# Timeout (in seconds) for service to become ready
openvpn_config_readiness_timeout: 300
```

### Initial Setup (Required)

```yaml
# Admin user name (typically 'openvpn' for OpenVPN AS)
openvpn_config_admin_user: "openvpn"

# Admin password (should be defined in vault)
openvpn_config_admin_password: "{{ vault_openvpn_admin_password }}"

# Server hostname/domain for VPN server
openvpn_config_server_hostname: "vpn.example.com"

# Activation/license key for OpenVPN Access Server
openvpn_config_activation_key: "{{ vault_openvpn_activation_key }}"
```

### VPN Users

```yaml
# List of VPN users to create
openvpn_config_users:
  - username: "user1"
    password: "{{ vault_openvpn_user1_password }}"
    autologin: true
  - username: "user2"
    password: "{{ vault_openvpn_user2_password }}"
    autologin: false
```

### Advanced Server Configuration

```yaml
# Additional server configuration settings (key-value pairs)
# These will be applied using 'sacli ConfigPut' command
openvpn_config_server_settings:
  - key: "vpn.server.routing.private_network.0"
    value: "192.168.1.0/24"
  - key: "vpn.client.routing.reroute_dns"
    value: "true"
  - key: "vpn.server.daemon.tcp.port"
    value: "443"
```

### Idempotency Control

```yaml
# Marker file path inside container to track configuration status
openvpn_config_marker_file: "/config/.ansible_configured"

# Force reconfiguration even if marker file exists
openvpn_config_force_reconfigure: false
```

## Dependencies

None.

## Example Playbook

### Docker Swarm Deployment

```yaml
---
- name: Configure OpenVPN on Docker Swarm
  hosts: localhost
  gather_facts: no
  
  tasks:
    - name: Configure OpenVPN Access Server
      ansible.builtin.include_role:
        name: openvpn_config
      vars:
        # Swarm discovery
        openvpn_config_service_name: "vpn-stack_openvpn-as"
        openvpn_config_swarm_manager: "swarm-manager-01"
        
        # Configuration
        openvpn_config_admin_password: "{{ vault_openvpn_admin_password }}"
        openvpn_config_server_hostname: "vpn.example.com"
        openvpn_config_activation_key: "{{ vault_openvpn_activation_key }}"
        openvpn_config_users:
          - username: "alice"
            password: "{{ vault_openvpn_alice_password }}"
            autologin: true
```

### Standalone Docker Deployment

```yaml
---
- name: Configure OpenVPN on standalone Docker
  hosts: docker_host
  gather_facts: yes
  
  tasks:
    - name: Configure OpenVPN Access Server
      ansible.builtin.include_role:
        name: openvpn_config
      vars:
        # Standalone Docker discovery
        openvpn_config_container_name: "openvpn-as"
        openvpn_config_target_host: "{{ inventory_hostname }}"
        
        # Configuration
        openvpn_config_admin_password: "{{ vault_openvpn_admin_password }}"
        openvpn_config_server_hostname: "vpn.example.com"
        openvpn_config_activation_key: "{{ vault_openvpn_activation_key }}"
        openvpn_config_users:
          - username: "bob"
            password: "{{ vault_openvpn_bob_password }}"
            autologin: false
```

### Direct Container ID

```yaml
---
- name: Configure OpenVPN with known container ID
  hosts: localhost
  gather_facts: no
  
  tasks:
    - name: Configure OpenVPN Access Server
      ansible.builtin.include_role:
        name: openvpn_config
      vars:
        # Direct container access
        openvpn_config_container_id: "a1b2c3d4e5f6"
        openvpn_config_target_host: "docker-host-01"
        
        # Configuration
        openvpn_config_admin_password: "{{ vault_openvpn_admin_password }}"
        openvpn_config_server_hostname: "vpn.example.com"
        openvpn_config_users:
          - username: "charlie"
            password: "{{ vault_openvpn_charlie_password }}"
```

### Modular Usage (Individual Task Files)

```yaml
---
- name: Configure OpenVPN Access Server (Modular)
  hosts: localhost
  gather_facts: no
  
  vars:
    # Choose your deployment mode
    openvpn_config_container_name: "openvpn-as"  # For standalone Docker
    openvpn_config_target_host: "docker-host"
    
  tasks:
    # Step 1: Discover container
    - name: Discover OpenVPN container
      ansible.builtin.include_role:
        name: openvpn_config
        tasks_from: discover_container
    
    # Step 2: Wait for service to be ready
    - name: Wait for OpenVPN to be ready
      ansible.builtin.include_role:
        name: openvpn_config
        tasks_from: wait_for_service
    
    # Step 3: Perform initial setup
    - name: Configure OpenVPN server
      ansible.builtin.include_role:
        name: openvpn_config
        tasks_from: initial_setup
      vars:
        openvpn_config_admin_password: "{{ vault_openvpn_admin_password }}"
        openvpn_config_server_hostname: "vpn.example.com"
        openvpn_config_activation_key: "{{ vault_openvpn_activation_key }}"
    
    # Step 4: Create users
    - name: Create VPN users
      ansible.builtin.include_role:
        name: openvpn_config
        tasks_from: users
      vars:
        openvpn_config_users:
          - username: "alice"
            password: "{{ vault_openvpn_alice_password }}"
            autologin: true
```

### Advanced Configuration

```yaml
---
- name: Advanced OpenVPN Configuration
  hosts: localhost
  gather_facts: no
  
  tasks:
    - name: Configure OpenVPN with advanced settings
      ansible.builtin.include_role:
        name: openvpn_config
      vars:
        # Discovery (choose one method)
        openvpn_config_service_name: "my-vpn-service"  # Swarm
        openvpn_config_swarm_manager: "manager-node"   # Swarm
        
        # Basic configuration
        openvpn_config_admin_password: "{{ vault_openvpn_admin_password }}"
        openvpn_config_server_hostname: "vpn.example.com"
        openvpn_config_activation_key: "{{ vault_openvpn_activation_key }}"
        openvpn_config_users:
          - username: "admin"
            password: "{{ vault_openvpn_admin_password }}"
            autologin: false
        
        # Advanced server settings
        openvpn_config_server_settings:
          # Route company network through VPN
          - key: "vpn.server.routing.private_network.0"
            value: "192.168.1.0/24"
          # Enable DNS rerouting
          - key: "vpn.client.routing.reroute_dns"
            value: "true"
          # Use TCP port 443 for better firewall compatibility
          - key: "vpn.server.daemon.tcp.port"
            value: "443"
          # Enable compression
          - key: "vpn.server.compressor"
            value: "lz4"
```

## Modular Task Files

Each task file can be used independently:

| Task File | Description |
| --------- | ----------- |
| `discover_container.yml` | Find OpenVPN container (auto-detects deployment mode) |
| `wait_for_service.yml` | Wait for OpenVPN to be ready |
| `initial_setup.yml` | Configure server (admin, hostname, activation) |
| `users.yml` | Create and manage VPN users |

## Idempotency

This role is designed to be **fully idempotent**:

- **Initial Setup**: Checks for configuration marker file before running
- **User Management**: Queries existing users before creating
- **Password Updates**: Always updates passwords (cannot check current value)
- **Force Reconfigure**: Set `openvpn_config_force_reconfigure: true` to override

### Safe to Re-run

Running this role multiple times will:

- ✓ Skip initial setup if already configured
- ✓ Create only new users
- ✓ Update passwords for existing users
- ✓ Apply only new server settings

## Security Considerations

1. **Use Ansible Vault** for sensitive variables:

   ```bash
   ansible-vault encrypt_string 'your-password' --name 'vault_openvpn_admin_password'
   ```

2. **No-log Protection**: Password and activation key tasks use `no_log: true`

3. **SSL/TLS**: OpenVPN Access Server uses HTTPS by default (port 943)

4. **User Passwords**: Always updated, even for existing users

## OpenVPN Access Server CLI (`sacli`)

This role uses the `sacli` command-line interface for configuration. Common commands:

```bash
# Set admin password
sacli --user openvpn --new_pass "password" SetLocalPassword

# Configure server property
sacli --key "host.name" --value "vpn.example.com" ConfigPut

# Create user
sacli --user alice --key "type" --value "user_connect" UserPropPut

# Enable auto-login
sacli --user alice --key "prop_autologin" --value "true" UserPropPut

# Restart service
sacli start
```

## Troubleshooting

### Container Not Found

**For Swarm deployments:**

```bash
docker service ls | grep openvpn
docker service ps <service-name>
```

**For standalone Docker:**

```bash
docker ps | grep openvpn
docker inspect <container-name>
```

**Check discovery mode:**
The role will display which discovery mode it's using. Ensure you've provided the correct variables for your deployment.

### Service Not Ready

- Increase `openvpn_config_readiness_timeout`
- Increase `openvpn_config_startup_wait`
- **For Swarm**: `docker service logs <service-name>`
- **For standalone**: `docker logs <container-name>`

### Users Not Created

- Check existing users: `docker exec <container-id> sacli UserPropGet`
- Verify passwords are defined in vault
- Check Ansible output for error messages
- Verify container has `sacli` command available

### Force Reconfiguration

```yaml
openvpn_config_force_reconfigure: true
```

This will re-run initial setup even if marker file exists.

### Variable Configuration Errors

If you see "Cannot discover OpenVPN container" error, ensure you've provided **one** of:

- `openvpn_config_container_id` + `openvpn_config_target_host`
- `openvpn_config_service_name` + `openvpn_config_swarm_manager`
- `openvpn_config_container_name` + `openvpn_config_target_host`

## License

MIT

## Author Information

Generic Ansible role for OpenVPN Access Server configuration, supporting multiple deployment modes.

## See Also

- [OpenVPN Access Server Documentation](https://openvpn.net/vpn-server-resources/access-server-command-line-tools/)
- [Docker Documentation](https://docs.docker.com/)
- [Docker Swarm Documentation](https://docs.docker.com/engine/swarm/) (for Swarm deployments)
- [Ansible Best Practices](https://docs.ansible.com/ansible/latest/user_guide/playbooks_best_practices.html)
