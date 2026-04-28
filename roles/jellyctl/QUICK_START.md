# jellyctl Ansible Role - Quick Reference

## Quick Start

### Basic Usage

```yaml
- hosts: jellyfin_servers
  vars:
    jellyctl_url: "http://localhost:8096"
    jellyctl_token: "{{ vault_token }}"
    jellyctl_user_operation: "list"
  roles:
    - jellyctl
```

## Operation Variables Quick Reference

### User Operations

Set `jellyctl_user_operation` to:

- `list` - List all users
- `create` - Create user (requires `jellyctl_username`)
- `delete` - Delete user (requires `jellyctl_username`)
- `enable` - Enable user (requires `jellyctl_username`)
- `disable` - Disable user (requires `jellyctl_username`)
- `set-admin` - Grant admin (requires `jellyctl_username`)
- `unset-admin` - Revoke admin (requires `jellyctl_username`)
- `set-hidden` - Hide from login (requires `jellyctl_username`)
- `unset-hidden` - Show on login (requires `jellyctl_username`)

### Library Operations

Set `jellyctl_library_operation` to:

- `scan` - Trigger library rescan
- `unscraped` - List unscraped items
- `search` - Search library (requires `jellyctl_library_search_term`)
- `duplicates` - Find duplicate media

### System Operations

Set `jellyctl_system_operation` to:

- `info` - Get system info
- `shutdown` - Stop Jellyfin
- `restart` - Restart Jellyfin
- `backup` - Export data
- `restore` - Import data (requires `jellyctl_backup_file`)

### Key Operations

Set `jellyctl_key_operation` to:

- `list` - List API keys
- `create` - Create key (requires `jellyctl_key_name`)
- `delete` - Delete key (requires `jellyctl_key_name`)

### Task Operations

Set `jellyctl_task_operation` to:

- `list` - List scheduled tasks
- `start` - Start task (requires `jellyctl_task_name`)
- `stop` - Stop task (requires `jellyctl_task_name`)

### Activity Operations

Set `jellyctl_activity_operation` to:

- `list` - View activity logs

## Common Variables

```yaml
# Required
jellyctl_url: "http://localhost:8096"
jellyctl_token: "your-api-token"

# Common
jellyctl_output_format: "json"  # or "text"
jellyctl_username: "username"
jellyctl_library_search_term: "search term"
jellyctl_key_name: "key name"
jellyctl_task_name: "task name"
```

## One-Liner Examples

### Users

```yaml
# List users
vars: { jellyctl_user_operation: "list" }

# Create user
vars: { jellyctl_user_operation: "create", jellyctl_username: "bob" }

# Make admin
vars: { jellyctl_user_operation: "set-admin", jellyctl_username: "alice" }
```

### Library

```yaml
# Scan
vars: { jellyctl_library_operation: "scan" }

# Search
vars: { jellyctl_library_operation: "search", jellyctl_library_search_term: "Matrix" }
```

### System

```yaml
# Info
vars: { jellyctl_system_operation: "info" }

# Restart
vars: { jellyctl_system_operation: "restart" }
```

## Error Handling

The role will fail if:

- `jellyctl` binary is not found in PATH
- `jellyctl_url` is not defined or empty
- Required parameters are missing for specific operations

## Security Best Practices

1. **Always use Ansible Vault for tokens**

   ```bash
   ansible-vault create vault.yml
   ```

2. **Never commit tokens to version control**

   ```yaml
   # Good
   jellyctl_token: "{{ vault_jellyfin_token }}"
   
   # Bad - NEVER DO THIS
   jellyctl_token: "actual-token-here"
   ```

3. **Use least privilege**
   - Create separate API keys for different purposes
   - Use service accounts for automation

## Testing Your Setup

```yaml
- name: Test jellyctl connectivity
  hosts: jellyfin_servers
  vars:
    jellyctl_system_operation: "info"
    jellyctl_system_public_info: true  # No token required
  roles:
    - jellyctl
```
