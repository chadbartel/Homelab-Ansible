# Common Tasks Directory

This directory contains reusable task files that are shared across multiple playbooks and roles.

## Dynamic Fact Gathering

### `set_swarm_manager.yml`

**Purpose**: Dynamically determines the Swarm manager node from inventory to decouple playbooks from hardcoded node references.

**Usage**:

```yaml
- name: Initialize dynamic infrastructure facts
  hosts: localhost
  connection: local
  gather_facts: false
  tasks:
    - name: Load dynamic Swarm manager fact
      ansible.builtin.include_tasks: tasks/common/set_swarm_manager.yml
```

**Fact Set**: `swarm_manager_node` - Contains the hostname of the first Swarm manager from the `swarm_managers` inventory group.

**Benefits**:

- No hardcoded `pi4_01` references throughout the project
- Easy infrastructure changes (update inventory only)
- Improved portability across different Swarm clusters
- Centralized manager node definition

**Integration**: Automatically included at the start of `main.yml` playbook with the `always` tag.

## Best Practices

1. **New Common Tasks**: Place reusable, infrastructure-agnostic tasks in this directory
2. **Naming**: Use descriptive names like `set_*.yml` for fact-setting tasks, `wait_for_*.yml` for readiness checks
3. **Documentation**: Document each task file's purpose, variables, and usage in this README
4. **Idempotency**: Ensure all tasks follow Ansible idempotency best practices
5. **Tags**: Use appropriate tags (e.g., `always` for critical fact-setting tasks)

## Service Readiness Checks

### `wait_for_swarm_service.yml`

**Purpose**: Consolidated, reusable service waiting logic for Docker Swarm services. Eliminates duplication across post-setup tasks and roles.

**Features**:

- Port accessibility verification
- Optional HTTP endpoint health checks
- Optional custom validation commands (via docker exec)
- Optional Swarm service status verification
- Configurable timeouts, retries, and delays
- Support for multi-phase validation

**Usage**:

```yaml
# Basic port check
- include_tasks: tasks/common/wait_for_swarm_service.yml
  vars:
    service_name: "pihole-stack_pihole"
    wait_host: "{{ ansible_host }}"
    wait_port: 8081

# Advanced with HTTP check and custom validation
- include_tasks: tasks/common/wait_for_swarm_service.yml
  vars:
    service_name: "jellyfin-stack_jellyfin"
    wait_host: "{{ ansible_host }}"
    wait_port: 8096
    wait_path: "/health"
    wait_http_status_codes: [200, 204]
    wait_swarm_manager: "{{ swarm_manager_node }}"
    wait_initial_pause: 20
    wait_custom_command: "test -f /config/system.xml"
    wait_container_id: "{{ jellyfin_container_id }}"
    wait_delegate_to: "lenovo_server"
    wait_custom_until_condition: "wait_custom_result.rc == 0"
```

**Required Variables**:

- `service_name`: Docker Swarm service name
- `wait_host`: Hostname or IP to check
- `wait_port`: Port number to wait for

**Optional Variables**:

- `wait_path`: HTTP path for endpoint check
- `wait_timeout`: Maximum wait time (default: 300s)
- `wait_delay`: Initial delay (default: 10s)
- `wait_retries`: Retry count for HTTP checks (default: 5)
- `wait_http_status_codes`: Acceptable HTTP codes (default: [200])
- `wait_initial_pause`: Pause before checks (default: 0)
- `wait_custom_command`: Docker exec command for validation
- `wait_custom_retries`: Custom command retries (default: 5)
- `wait_custom_delay`: Custom command delay (default: 10s)
- `wait_custom_until_condition`: Success condition for custom command
- `wait_swarm_manager`: Manager node for service verification
- `wait_delegate_to`: Node for custom command execution
- `wait_container_id`: Container ID for custom commands
- `wait_display_results`: Show debug output (default: true)

**Benefits**:

- Eliminates duplicate wait logic across roles
- Consistent waiting behavior across all services
- Easy customization per service without code duplication
- Supports complex multi-phase validation workflows

## Planned Future Additions

- `validate_swarm_status.yml` - Swarm cluster health checks
- `set_dynamic_inventory_facts.yml` - Other dynamic infrastructure facts
