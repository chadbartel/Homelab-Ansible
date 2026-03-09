# Ansible Role: jellyctl

An Ansible role for managing Jellyfin media server using the `jellyctl` CLI tool. This role provides a simple, intuitive abstraction layer for common Jellyfin management tasks including user management, library operations, system control, and more.

## Requirements

- **jellyctl** must be manually installed on the target host(s)
- Ansible 2.9 or higher
- A running Jellyfin server
- Valid API token for authentication (recommended to use Ansible Vault)

## Installation

### Installing jellyctl

This role assumes `jellyctl` is already installed on the target system. Visit the [jellyctl repository](https://github.com/user/jellyctl) for installation instructions.

### Installing the Role

You can install this role using `ansible-galaxy`:

```bash
ansible-galaxy install /path/to/role
```

Or add it to your `requirements.yml`:

```yaml
---
roles:
  - src: /path/to/jellyctl
    name: jellyctl
```

## Role Variables

### Core Configuration

```yaml
# Jellyfin server URL
jellyctl_url: "http://127.0.0.1:8096"

# API token for authentication (use Ansible Vault!)
jellyctl_token: ""

# Path to jellyctl binary
jellyctl_binary: "jellyctl"

# Output format (json or text)
jellyctl_output_format: "text"
```

### User Management Variables

```yaml
# User operation to perform
# Options: list, create, delete, enable, disable, set-admin, unset-admin, set-hidden, unset-hidden
jellyctl_user_operation: ""

# Username for user operations
jellyctl_username: ""
```

### Library Management Variables

```yaml
# Library operation to perform
# Options: scan, unscraped, search, duplicates
jellyctl_library_operation: ""

# Media types for library operations
jellyctl_library_types:
  - Movie
  - Series

# Search term for library search
jellyctl_library_search_term: ""
```

### System Management Variables

```yaml
# System operation to perform
# Options: info, shutdown, restart, backup, restore
jellyctl_system_operation: ""

# Show public info (no token required)
jellyctl_system_public_info: false

# Backup file path for restore operations
jellyctl_backup_file: ""

# Restore options
jellyctl_backup_unfavorite: false
jellyctl_backup_unplay: false
```

### API Key Management Variables

```yaml
# Key operation to perform
# Options: list, create, delete
jellyctl_key_operation: ""

# Key name for create/delete operations
jellyctl_key_name: ""
```

### Scheduled Task Variables

```yaml
# Task operation to perform
# Options: list, start, stop
jellyctl_task_operation: ""

# Task name for start/stop operations
jellyctl_task_name: ""
```

### Activity Log Variables

```yaml
# Activity operation to perform
# Options: list
jellyctl_activity_operation: ""

# Activity log settings
jellyctl_activity_limit: 15
jellyctl_activity_start: 0
jellyctl_activity_after: ""  # Filter logs after this time
```

## Example Playbooks

### Basic Setup

```yaml
---
- name: Manage Jellyfin with jellyctl
  hosts: jellyfin_servers
  vars:
    jellyctl_url: "http://localhost:8096"
    jellyctl_token: "{{ vault_jellyfin_api_token }}"
  roles:
    - jellyctl
```

### List Users

```yaml
---
- name: List Jellyfin users
  hosts: jellyfin_servers
  vars:
    jellyctl_url: "http://localhost:8096"
    jellyctl_token: "{{ vault_jellyfin_api_token }}"
    jellyctl_user_operation: "list"
    jellyctl_output_format: "json"
  roles:
    - jellyctl
```

### Create a User

```yaml
---
- name: Create new Jellyfin user
  hosts: jellyfin_servers
  vars:
    jellyctl_url: "http://localhost:8096"
    jellyctl_token: "{{ vault_jellyfin_api_token }}"
    jellyctl_user_operation: "create"
    jellyctl_username: "newuser"
  roles:
    - jellyctl
```

### Manage User Permissions

```yaml
---
- name: Promote user to admin
  hosts: jellyfin_servers
  vars:
    jellyctl_url: "http://localhost:8096"
    jellyctl_token: "{{ vault_jellyfin_api_token }}"
    jellyctl_user_operation: "set-admin"
    jellyctl_username: "john"
  roles:
    - jellyctl

- name: Hide user from login page
  hosts: jellyfin_servers
  vars:
    jellyctl_url: "http://localhost:8096"
    jellyctl_token: "{{ vault_jellyfin_api_token }}"
    jellyctl_user_operation: "set-hidden"
    jellyctl_username: "service_account"
  roles:
    - jellyctl
```

### Library Operations

```yaml
---
- name: Scan Jellyfin libraries
  hosts: jellyfin_servers
  vars:
    jellyctl_url: "http://localhost:8096"
    jellyctl_token: "{{ vault_jellyfin_api_token }}"
    jellyctl_library_operation: "scan"
  roles:
    - jellyctl

- name: Find unscraped media
  hosts: jellyfin_servers
  vars:
    jellyctl_url: "http://localhost:8096"
    jellyctl_token: "{{ vault_jellyfin_api_token }}"
    jellyctl_library_operation: "unscraped"
    jellyctl_library_types:
      - Movie
      - Series
  roles:
    - jellyctl

- name: Search library
  hosts: jellyfin_servers
  vars:
    jellyctl_url: "http://localhost:8096"
    jellyctl_token: "{{ vault_jellyfin_api_token }}"
    jellyctl_library_operation: "search"
    jellyctl_library_search_term: "Inception"
  roles:
    - jellyctl

- name: Find duplicates
  hosts: jellyfin_servers
  vars:
    jellyctl_url: "http://localhost:8096"
    jellyctl_token: "{{ vault_jellyfin_api_token }}"
    jellyctl_library_operation: "duplicates"
  roles:
    - jellyctl
```

### System Management

```yaml
---
- name: Get system information
  hosts: jellyfin_servers
  vars:
    jellyctl_url: "http://localhost:8096"
    jellyctl_token: "{{ vault_jellyfin_api_token }}"
    jellyctl_system_operation: "info"
  roles:
    - jellyctl

- name: Restart Jellyfin
  hosts: jellyfin_servers
  vars:
    jellyctl_url: "http://localhost:8096"
    jellyctl_token: "{{ vault_jellyfin_api_token }}"
    jellyctl_system_operation: "restart"
  roles:
    - jellyctl

- name: Backup Jellyfin data
  hosts: jellyfin_servers
  vars:
    jellyctl_url: "http://localhost:8096"
    jellyctl_token: "{{ vault_jellyfin_api_token }}"
    jellyctl_system_operation: "backup"
  roles:
    - jellyctl

- name: Restore Jellyfin data
  hosts: jellyfin_servers
  vars:
    jellyctl_url: "http://localhost:8096"
    jellyctl_token: "{{ vault_jellyfin_api_token }}"
    jellyctl_system_operation: "restore"
    jellyctl_backup_file: "/path/to/backup.json"
  roles:
    - jellyctl
```

### API Key Management

```yaml
---
- name: List API keys
  hosts: jellyfin_servers
  vars:
    jellyctl_url: "http://localhost:8096"
    jellyctl_token: "{{ vault_jellyfin_api_token }}"
    jellyctl_key_operation: "list"
  roles:
    - jellyctl

- name: Create new API key
  hosts: jellyfin_servers
  vars:
    jellyctl_url: "http://localhost:8096"
    jellyctl_token: "{{ vault_jellyfin_api_token }}"
    jellyctl_key_operation: "create"
    jellyctl_key_name: "ansible_automation"
  roles:
    - jellyctl

- name: Delete API key
  hosts: jellyfin_servers
  vars:
    jellyctl_url: "http://localhost:8096"
    jellyctl_token: "{{ vault_jellyfin_api_token }}"
    jellyctl_key_operation: "delete"
    jellyctl_key_name: "old_key"
  roles:
    - jellyctl
```

### Scheduled Tasks

```yaml
---
- name: List scheduled tasks
  hosts: jellyfin_servers
  vars:
    jellyctl_url: "http://localhost:8096"
    jellyctl_token: "{{ vault_jellyfin_api_token }}"
    jellyctl_task_operation: "list"
  roles:
    - jellyctl

- name: Start a scheduled task
  hosts: jellyfin_servers
  vars:
    jellyctl_url: "http://localhost:8096"
    jellyctl_token: "{{ vault_jellyfin_api_token }}"
    jellyctl_task_operation: "start"
    jellyctl_task_name: "LibraryScan"
  roles:
    - jellyctl
```

### Activity Logs

```yaml
---
- name: View recent activity
  hosts: jellyfin_servers
  vars:
    jellyctl_url: "http://localhost:8096"
    jellyctl_token: "{{ vault_jellyfin_api_token }}"
    jellyctl_activity_operation: "list"
    jellyctl_activity_limit: 50
  roles:
    - jellyctl

- name: View activity with filters
  hosts: jellyfin_servers
  vars:
    jellyctl_url: "http://localhost:8096"
    jellyctl_token: "{{ vault_jellyfin_api_token }}"
    jellyctl_activity_operation: "list"
    jellyctl_activity_limit: 100
    jellyctl_activity_after: "2026-02-01 00:00:00"
  roles:
    - jellyctl
```

## Using Ansible Vault for Sensitive Data

It's strongly recommended to store your Jellyfin API token in Ansible Vault:

1. Create a vault file:

```bash
ansible-vault create vars/jellyfin_secrets.yml
```

1. Add your token:

```yaml
---
vault_jellyfin_api_token: "your-secret-token-here"
```

1. Use in your playbook:

```yaml
---
- name: Manage Jellyfin
  hosts: jellyfin_servers
  vars_files:
    - vars/jellyfin_secrets.yml
  vars:
    jellyctl_token: "{{ vault_jellyfin_api_token }}"
    jellyctl_user_operation: "list"
  roles:
    - jellyctl
```

1. Run with vault password:

```bash
ansible-playbook playbook.yml --ask-vault-pass
```

## Dependencies

None.

## License

MIT

## Author Information

This role was created by thatsmidnight.

## Notes

- This role performs a prerequisite check to ensure `jellyctl` is installed before executing any operations
- All operations that modify state (create, delete, enable, disable, etc.) are properly marked with `changed_when`
- Read-only operations (list, info, search, etc.) use `changed_when: false` to accurately reflect idempotency
- The role uses conditional task inclusion based on operation type, ensuring only relevant tasks are executed
- Error handling is built-in; if `jellyctl` is not found, the role will fail with a clear error message

## Troubleshooting

### jellyctl not found

If you receive an error that `jellyctl` is not found:

1. Verify `jellyctl` is installed on the target host
2. Check that `jellyctl` is in the system PATH
3. If installed in a custom location, set `jellyctl_binary` to the full path

### Authentication errors

If you encounter authentication issues:

1. Verify your API token is valid
2. Ensure the token has appropriate permissions
3. Check that `jellyctl_url` points to the correct Jellyfin server

### Connection errors

If unable to connect to Jellyfin:

1. Verify the Jellyfin server is running
2. Check network connectivity from the Ansible control node to the target
3. Ensure `jellyctl_url` is correct and accessible
