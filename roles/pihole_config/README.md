# Pi-hole Configuration Role

An Ansible role for managing Pi-hole configuration in Docker Swarm environments. This role provides idempotent, modular management of Pi-hole adlists, custom DNS entries, and dnsmasq settings.

## Features

- ✅ **Idempotent operations** - Safe to run multiple times without side effects
- 🔍 **Automatic container discovery** - Finds Pi-hole containers in Docker Swarm
- 📋 **Adlist management** - Custom Ansible module for block list configuration
- 🌐 **Custom DNS entries** - Template-based local domain resolution
- ⚙️ **Dnsmasq configuration** - Manage dnsmasq settings with proper idempotency
- 🐳 **Docker Swarm aware** - Understands and works with Swarm service placement
- 📦 **Standalone or integrated** - Use as a complete role or individual task files

## Requirements

- Ansible 2.9 or higher
- Docker Swarm cluster with Pi-hole deployed as a service
- SSH access to Swarm manager and worker nodes
- Python 3.6+ on control node and managed nodes

## Role Variables

### Service Discovery

```yaml
# Docker Swarm service name for Pi-hole
pihole_config_service_name: "pihole-stack_pihole"

# Swarm manager node (Ansible inventory hostname)
pihole_config_swarm_manager: "pi4_01"

# Node where Pi-hole container runs (Ansible inventory hostname)
pihole_config_target_node: "lenovo_server"
```

### Service Readiness

```yaml
# Pi-hole web interface port
pihole_config_web_port: 8081

# Readiness check configuration
pihole_config_readiness_retries: 20
pihole_config_readiness_delay: 10
pihole_config_readiness_timeout: 180

# FTL service initialization
pihole_config_ftl_retries: 12
pihole_config_ftl_delay: 10
```

### Adlist Configuration

```yaml
# List of block lists to configure
pihole_config_adlists:
  - url: "https://adaway.org/hosts.txt"
    comment: "AdAway"
    enabled: true
  - url: "https://v.firebog.net/hosts/Easylist.txt"
    comment: "EasyList"
    enabled: true

# Update gravity after adlist changes
pihole_config_update_gravity: true
```

### Custom DNS Entries

```yaml
# Local domain resolution
pihole_config_custom_dns_entries:
  - ip: "192.168.1.10"
    hostname: "pihole.local"
  - ip: "192.168.1.10"
    hostname: "portainer.local"
```

### Dnsmasq Settings

```yaml
# Dnsmasq configuration options
pihole_config_dnsmasq_settings:
  - "dns-forward-max=300"
  - "cache-size=10000"
```

### Display Options

```yaml
# Show detailed output
pihole_config_display_results: true
```

## Task Files

The role provides modular task files that can be used individually:

### Container Discovery

```yaml
- import_role:
    name: pihole_config
    tasks_from: discover_container
```

Sets facts: `pihole_task_id`, `pihole_node_name`, `pihole_container_id`

### Service Readiness

```yaml
- import_role:
    name: pihole_config
    tasks_from: wait_for_service
```

Waits for Pi-hole web interface and FTL service to be ready.

### Adlist Management

```yaml
- import_role:
    name: pihole_config
    tasks_from: adlists
  vars:
    pihole_config_adlists:
      - url: "https://example.com/blocklist.txt"
        comment: "Example Blocklist"
        enabled: true
```

Manages Pi-hole block lists with automatic gravity updates.

### Custom DNS Configuration

```yaml
- import_role:
    name: pihole_config
    tasks_from: custom_dns
  vars:
    pihole_config_custom_dns_entries:
      - ip: "192.168.1.10"
        hostname: "service.local"
```

Configures local domain resolution.

### Dnsmasq Settings

```yaml
- import_role:
    name: pihole_config
    tasks_from: dnsmasq
  vars:
    pihole_config_dnsmasq_settings:
      - "dns-forward-max=300"
```

Manages dnsmasq configuration options.

## Custom Modules

The role includes two custom Ansible modules for idempotent Pi-hole management.

### pihole_adlist

Manages Pi-hole adlists (block lists) with true SQLite-based idempotency.

**Parameters:**

- `container_id` (required) - Docker container ID
- `url` (required) - Adlist URL
- `comment` (optional) - Description of the adlist
- `enabled` (optional, default: true) - Whether adlist is enabled
- `state` (optional, default: present) - `present` or `absent`

**Example:**

```yaml
- name: Manage Pi-hole adlists
  pihole_adlist:
    container_id: "{{ pihole_container_id }}"
    url: "https://v.firebog.net/hosts/AdguardDNS.txt"
    comment: "AdGuard DNS"
    enabled: true
    state: present
```

### docker_exec_lineinfile

Manages lines in files inside Docker containers, similar to `ansible.builtin.lineinfile` but executes via `docker exec`.

**Parameters:**

- `container_id` (required) - Docker container ID or name
- `path` (required) - Path to file inside container
- `line` (required for state=present) - Line to insert/ensure present
- `regexp` (optional) - Regular expression to match and replace
- `state` (optional, default: present) - `present` or `absent`
- `create` (optional, default: false) - Create file if it doesn't exist
- `backup` (optional, default: false) - Create timestamped backup before changes

**Example:**

```yaml
- name: Configure dnsmasq max forwarding queries
  docker_exec_lineinfile:
    container_id: "{{ pihole_container_id }}"
    path: /etc/dnsmasq.d/misc.dnsmasq_lines
    line: "dns-forward-max=300"
    state: present
    create: true
```

## Example Playbooks

See the `examples/` directory for complete playbook examples:

- `complete_setup.yml` - Full Pi-hole configuration
- `adlist_management.yml` - Block list configuration
- `custom_dns_setup.yml` - Local domain resolution
- `dnsmasq_tuning.yml` - Dnsmasq performance settings

## Usage Examples

### Complete Configuration

```yaml
---
- name: Configure Pi-hole
  hosts: localhost
  vars:
    pihole_config_service_name: "pihole-stack_pihole"
    pihole_config_swarm_manager: "pi4_01"
    pihole_config_target_node: "lenovo_server"
    
    pihole_config_adlists:
      - url: "https://adaway.org/hosts.txt"
        comment: "AdAway"
        enabled: true
    
    pihole_config_custom_dns_entries:
      - ip: "192.168.1.10"
        hostname: "pihole.local"
    
    pihole_config_dnsmasq_settings:
      - "dns-forward-max=300"
  
  tasks:
    - name: Wait for Pi-hole to be ready
      import_role:
        name: pihole_config
        tasks_from: wait_for_service
    
    - name: Configure adlists
      import_role:
        name: pihole_config
        tasks_from: adlists
    
    - name: Configure custom DNS
      import_role:
        name: pihole_config
        tasks_from: custom_dns
    
    - name: Configure dnsmasq
      import_role:
        name: pihole_config
        tasks_from: dnsmasq
```

### Quick Adlist Update

```yaml
---
- name: Update Pi-hole adlists
  hosts: localhost
  vars:
    pihole_config_adlists:
      - url: "https://new-blocklist.example.com/list.txt"
        comment: "New Blocklist"
        enabled: true
  
  tasks:
    - import_role:
        name: pihole_config
        tasks_from: adlists
```

## Architecture

This role follows Ansible best practices for modularity and reusability:

1. **Separation of Concerns** - Each configuration aspect is in its own task file
2. **True Idempotency** - Uses custom modules and proper change detection
3. **Docker Swarm Aware** - Handles container discovery and node delegation
4. **Fact Caching** - Container facts are cached for reuse across tasks
5. **Template-Based** - Custom DNS uses Jinja2 templates for predictable output

## Comparison with Previous Implementation

| Aspect | Old Implementation | New Role |
| -------- | ------------------- | ---------- |
| Idempotency | ❌ Bash scripts regenerated every run | ✅ Custom modules with proper state checking |
| Coupling | ❌ Hardcoded node names | ✅ Configurable via variables |
| Reusability | ❌ Monolithic task file | ✅ Modular task files |
| Container Discovery | ❌ Repeated in each task | ✅ Centralized discover_container.yml |
| Custom DNS | ❌ Always restarts DNS | ✅ Only restarts on actual changes |
| Dnsmasq | ❌ Shell script with grep | ✅ docker_exec_lineinfile module |

## Integration with Homelab-Ansible

To integrate this role into the main Homelab-Ansible project:

1. Replace `tasks/post_setup_pihole.yml` with:

```yaml
---
- name: Configure Pi-hole using pihole_config role
  import_role:
    name: pihole_config
    tasks_from: "{{ item }}"
  loop:
    - wait_for_service
    - adlists
    - custom_dns
    - dnsmasq
  vars:
    pihole_config_service_name: "pihole-stack_pihole"
    pihole_config_swarm_manager: "pi4_01"
    pihole_config_target_node: "lenovo_server"
    pihole_config_adlists: "{{ pihole_adlists }}"
    pihole_config_custom_dns_entries: "{{ pihole_custom_dns }}"
```

1. Move adlist and DNS configuration to `vars.yml`:

```yaml
pihole_adlists:
  - url: "https://adaway.org/hosts.txt"
    comment: "AdAway"
    enabled: true
  # ... more adlists

pihole_custom_dns:
  - ip: "{{ manager_node_ip }}"
    hostname: "pihole.{{ local_domain }}"
  - ip: "{{ manager_node_ip }}"
    hostname: "portainer.{{ local_domain }}"
```

## Testing

Test the role with check mode:

```bash
ansible-playbook playbook.yml --check
```

Verify idempotency (second run should show no changes):

```bash
ansible-playbook playbook.yml
ansible-playbook playbook.yml  # Should show changed=0
```

## License

GPL-3.0-or-later

## Author

Homelab Ansible Project

## Contributing

Contributions welcome! Please ensure:

- All task files include proper documentation
- Changes maintain idempotency
- Examples are updated for new features
- Code follows existing role structure (see roles/jellyfin)
