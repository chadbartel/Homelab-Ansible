# Ansible Custom Modules Library

This directory contains custom Ansible modules for the Homelab-Ansible project.

## Available Modules

### docker_swarm_container_exec

Execute commands in Docker containers with built-in idempotency support.

**Purpose**: Provides a declarative, idempotent way to execute commands in Docker containers (standalone or Swarm-managed). This module replaces shell commands with `docker exec` and provides better idempotency control through `creates` and `removes` parameters.

**Key Features**:

- ✅ **Idempotency**: Supports `creates` and `removes` parameters to avoid re-running commands
- ✅ **Check Mode**: Full support for Ansible's dry-run mode
- ✅ **Working Directory**: Change to specific directory before command execution
- ✅ **User Specification**: Run commands as specific user inside container
- ✅ **Environment Variables**: Set custom environment for command execution
- ✅ **Return Values**: Provides stdout, stderr, and return code

**Parameters**:

| Parameter | Type | Required | Description |
| ----------- | ------ | ---------- | ------------- |
| `container_id` | str | Yes | Docker container ID or name |
| `command` | raw | Yes | Command to execute (string or list) |
| `chdir` | str | No | Working directory for command execution |
| `creates` | str | No | Skip if this file exists (idempotency) |
| `removes` | str | No | Skip if this file doesn't exist (idempotency) |
| `user` | str | No | Run command as this user |
| `environment` | dict | No | Environment variables for command |
| `stdin` | str | No | String to pass to stdin |

**Return Values**:

- `stdout`: Command standard output
- `stderr`: Command standard error
- `rc`: Return code from command
- `changed`: Whether command was executed
- `skipped`: Whether command was skipped (creates/removes check)
- `msg`: Human-readable status message

**Basic Usage**:

```yaml
# Simple command execution
- name: Check Pi-hole status
  docker_swarm_container_exec:
    container_id: "{{ pihole_container_id }}"
    command: "pihole status"
  register: pihole_status
```

**Idempotency Examples**:

```yaml
# Using creates - skip if file exists
- name: Initialize configuration (only once)
  docker_swarm_container_exec:
    container_id: "{{ openvpn_container_id }}"
    command: "sacli --key 'host.name' --value 'vpn.example.com' ConfigPut"
    creates: "/usr/local/openvpn_as/.configured"

# Using removes - skip if file doesn't exist
- name: Setup service (only if setup marker missing)
  docker_swarm_container_exec:
    container_id: "{{ service_container_id }}"
    command: "initialize-service.sh"
    removes: "/var/lib/service/.needs_setup"
```

**Advanced Features**:

```yaml
# With working directory
- name: Run migration script
  docker_swarm_container_exec:
    container_id: "{{ app_container_id }}"
    command: "./migrate.sh"
    chdir: "/app/scripts"

# With specific user
- name: Run as nginx user
  docker_swarm_container_exec:
    container_id: "{{ app_container_id }}"
    command: "whoami"
    user: "nginx"

# With environment variables
- name: Run with custom environment
  docker_swarm_container_exec:
    container_id: "{{ app_container_id }}"
    command: "printenv"
    environment:
      DEBUG: "true"
      LOG_LEVEL: "info"

# In a loop
- name: Execute multiple configuration commands
  docker_swarm_container_exec:
    container_id: "{{ openvpn_container_id }}"
    command: "sacli --key '{{ item.key }}' --value '{{ item.value }}' ConfigPut"
  loop:
    - key: "vpn.daemon.0.listen.port"
      value: "1194"
    - key: "vpn.daemon.0.listen.protocol"
      value: "udp"
  loop_control:
    label: "{{ item.key }}"
```

**Migration from shell + docker exec**:

```yaml
# ❌ OLD WAY (shell with docker exec)
- name: Configure OpenVPN
  ansible.builtin.shell: |
    docker exec {{ container_id }} \
      sacli --key "host.name" --value "vpn.example.com" ConfigPut
  changed_when: true  # Always reports changed

# ✅ NEW WAY (docker_swarm_container_exec)
- name: Configure OpenVPN
  docker_swarm_container_exec:
    container_id: "{{ container_id }}"
    command: "sacli --key 'host.name' --value 'vpn.example.com' ConfigPut"
    creates: "/usr/local/openvpn_as/.configured"
  # Only runs if marker file doesn't exist - true idempotency
```

**Benefits Over Shell Commands**:

1. **True Idempotency**: `creates`/`removes` parameters prevent unnecessary re-runs
2. **Cleaner Syntax**: No need for multi-line shell scripts with backslashes
3. **Better Error Handling**: Proper return code checking and failure reporting
4. **Check Mode Support**: Works with `ansible-playbook --check`
5. **Consistent Interface**: Same module works across all container exec scenarios

**When to Use This Module**:

- ✅ Configuring services inside containers (Pi-hole, OpenVPN, etc.)
- ✅ Running initialization scripts with idempotency
- ✅ Checking container status or gathering facts
- ✅ Executing maintenance commands (gravity update, DNS restart, etc.)

**When NOT to Use**:

- ❌ For file management (use `docker_exec_lineinfile` or template + copy instead)
- ❌ For complex multi-step operations (create a custom module or role)
- ❌ When the container might not exist (check existence first)

## Best Practices

### 1. Always Use Idempotency Parameters

```yaml
# Good - uses creates for idempotency
- name: Mark service as initialized
  docker_swarm_container_exec:
    container_id: "{{ service_id }}"
    command: "touch /var/lib/service/.initialized"
    creates: "/var/lib/service/.initialized"

# Bad - always runs, always reports changed
- name: Mark service as initialized
  docker_swarm_container_exec:
    container_id: "{{ service_id }}"
    command: "touch /var/lib/service/.initialized"
```

### 2. Use Retries for Potentially Flaky Commands

```yaml
- name: Wait for service to initialize
  docker_swarm_container_exec:
    container_id: "{{ service_id }}"
    command: "service-check.sh"
  register: check_result
  retries: 5
  delay: 10
  until: check_result.rc == 0
```

### 3. Combine with changed_when for Better Control

```yaml
- name: Update gravity database
  docker_swarm_container_exec:
    container_id: "{{ pihole_container_id }}"
    command: "pihole -g"
  register: gravity_update
  changed_when: "'Update complete' in gravity_update.stdout"
```

### 4. Use no_log for Sensitive Commands

```yaml
- name: Set admin password
  docker_swarm_container_exec:
    container_id: "{{ service_id }}"
    command: "set-password '{{ admin_password }}'"
  no_log: true  # Don't log password in output
```

## Testing

### Syntax Validation

```bash
# Check syntax of custom modules
python3 -m py_compile library/docker_swarm_container_exec.py
```

### Integration Testing

```bash
# Run playbook in check mode (dry-run)
ansible-playbook main.yml --check

# Run playbook with verbose output
ansible-playbook main.yml -vvv

# Test idempotency (second run should show minimal changes)
ansible-playbook main.yml
ansible-playbook main.yml
```

## Development

### Creating a New Custom Module

Follow this structure:

```python
#!/usr/bin/python
# -*- coding: utf-8 -*-

from __future__ import absolute_import, division, print_function
__metaclass__ = type

from ansible.module_utils.basic import AnsibleModule

DOCUMENTATION = r'''
# Module documentation in YAML
'''

EXAMPLES = r'''
# Example usage
'''

RETURN = r'''
# Return value documentation
'''

def main():
    module = AnsibleModule(
        argument_spec=dict(
            # Define parameters
        ),
        supports_check_mode=True
    )
    
    # Module logic here
    
    module.exit_json(changed=False, msg="Success")

if __name__ == '__main__':
    main()
```

### Module Guidelines

1. **Always support check mode** (`supports_check_mode=True`)
2. **Provide comprehensive documentation** (DOCUMENTATION, EXAMPLES, RETURN)
3. **Handle errors gracefully** (use `module.fail_json()`)
4. **Return meaningful data** (stdout, stderr, rc, changed, etc.)
5. **Follow Ansible conventions** (snake_case for parameters, proper return values)

## See Also

- [Ansible Module Development](https://docs.ansible.com/ansible/latest/dev_guide/developing_modules_general.html)
- [docker_exec_lineinfile module](../roles/pihole_config/library/docker_exec_lineinfile.py) - For file line management
- [pihole_adlist module](../roles/pihole_config/library/pihole_adlist.py) - For Pi-hole adlist management
- [jellyfin_api module](../roles/jellyfin/library/jellyfin_api.py) - For Jellyfin API interaction
