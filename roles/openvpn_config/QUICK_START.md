# OpenVPN Access Server Configuration - Quick Start

Fast reference for using the `openvpn_config` role with any deployment type.

## Choose Your Deployment Mode

The role auto-detects deployment mode. Pick **ONE** method:

### Docker Swarm

```yaml
openvpn_config_service_name: "vpn-service"
openvpn_config_swarm_manager: "manager-node"
```

### Standalone Docker

```yaml
openvpn_config_container_name: "openvpn-as"
openvpn_config_target_host: "docker-host"
```

### Direct Container ID

```yaml
openvpn_config_container_id: "a1b2c3d4e5f6"
openvpn_config_target_host: "docker-host"
```

## 5-Minute Setup

### 1. Required Variables (in `vars.yml`)

```yaml
# Container discovery (pick one method from above)
openvpn_config_container_name: "openvpn-as"    # Example: standalone Docker
openvpn_config_target_host: "{{ inventory_hostname }}"

# Configuration
openvpn_config_admin_password: "{{ vault_openvpn_admin_password }}"
openvpn_config_server_hostname: "vpn.example.com"
openvpn_config_activation_key: "{{ vault_openvpn_activation_key }}"
openvpn_config_users:
  - username: "alice"
    password: "{{ vault_openvpn_alice_password }}"
    autologin: true
```

### 2. Minimal Playbook

```yaml
---
- name: Configure OpenVPN
  hosts: docker_hosts
  gather_facts: yes
  
  tasks:
    - include_role:
        name: openvpn_config
```

### 3. Run It

```bash
ansible-playbook openvpn_setup.yml
```

## Common Use Cases

### Swarm Deployment

```yaml
- include_role:
    name: openvpn_config
  vars:
    openvpn_config_service_name: "vpn-stack_openvpn"
    openvpn_config_swarm_manager: "swarm-manager"
    openvpn_config_admin_password: "{{ vault_password }}"
```

### Just Wait for Service

```yaml
- include_role:
    name: openvpn_config
    tasks_from: wait_for_service
```

### Just Create Users

```yaml
- include_role:
    name: openvpn_config
    tasks_from: users
  vars:
    openvpn_config_users:
      - username: "bob"
        password: "{{ vault_bob_password }}"
        autologin: false
```

### Force Reconfiguration

```yaml
- include_role:
    name: openvpn_config
  vars:
    openvpn_config_force_reconfigure: true
```

### Advanced Server Settings

```yaml
- include_role:
    name: openvpn_config
  vars:
    openvpn_config_server_settings:
      - key: "vpn.server.routing.private_network.0"
        value: "192.168.1.0/24"
      - key: "vpn.client.routing.reroute_dns"
        value: "true"
```

## Variable Quick Reference

| Variable | Required | Default | Description |
| ---------- | ---------- | --------- | ------------- |
| `openvpn_config_admin_password` | **Yes** | - | Admin password |
| `openvpn_config_server_hostname` | Recommended | - | VPN server hostname |
| `openvpn_config_activation_key` | **Yes** | - | License key |
| `openvpn_config_users` | No | `[]` | List of VPN users |
| `openvpn_config_web_port` | No | `943` | Web UI port |
| `openvpn_config_force_reconfigure` | No | `false` | Force reconfiguration |

### Discovery Variables (pick ONE method)

| Variable | Mode | Description |
| ---------- | ------ | ------------- |
| `openvpn_config_container_id` | Direct | Known container ID |
| `openvpn_config_service_name` | Swarm | Swarm service name |
| `openvpn_config_swarm_manager` | Swarm | Manager node hostname |
| `openvpn_config_container_name` | Docker | Container name (standalone) |
| `openvpn_config_target_host` | All | Hostname where container runs |

## User Configuration Format

```yaml
openvpn_config_users:
  - username: "alice"           # Required
    password: "secret123"        # Required (use vault!)
    autologin: true             # Optional (default: false)
  
  - username: "bob"
    password: "secret456"
    autologin: false
```

## Troubleshooting

### Container Not Found

**Swarm:**

```bash
docker service ps <service-name>
```

**Standalone:**

```bash
docker ps | grep <container-name>
```

### Check Logs

**Swarm:**

```bash
docker service logs <service-name> --tail 50
```

**Standalone:**

```bash
docker logs <container-name> --tail 50
```

### List Users

```bash
docker exec <container-id> sacli UserPropGet
```

### Manual Configuration

```bash
docker exec <container-id> sacli --help
```

## Access Points

After configuration (replace `your-host` with actual hostname/IP):

- **Admin UI**: `https://your-host:943/admin`
- **Client UI**: `https://your-host:943/`
- **Download Profiles**: Client UI → Login → Download VPN Profile

## Security Tips

✓ Use Ansible Vault for all passwords and keys  
✓ Use strong, unique passwords  
✓ Set `autologin: false` for admin users  
✓ Regularly update OpenVPN Access Server  
✓ Use HTTPS only (port 943)

## Next Steps

- Read [full documentation](README.md) for advanced usage
- Check [example playbooks](examples/) for more scenarios
- Review [OpenVPN AS docs](https://openvpn.net/vpn-server-resources/) for configuration options
