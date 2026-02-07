# Jellyfin Ansible Role

An Ansible role that provides a simple, intuitive abstraction layer for interacting with the Jellyfin API. This role eliminates the need to manually construct JSON bodies and handles authentication automatically.

## Features

- ✅ **Simple API Interaction**: Use the `jellyfin_api` module to interact with any Jellyfin API endpoint
- ✅ **No Manual JSON Construction**: Pass arguments as Ansible dictionaries - the module handles JSON conversion
- ✅ **Automatic Authentication**: Supports both API tokens and username/password authentication
- ✅ **Pre-built Tasks**: Common operations (users, libraries, API keys, etc.) available as importable task files
- ✅ **Based on OpenAPI Spec**: Built from the official Jellyfin OpenAPI specification (v10.11.6)
- ✅ **Idempotent**: Follows Ansible best practices for idempotency
- ✅ **Comprehensive Error Handling**: Proper error messages and status codes

## Requirements

- Ansible 2.9 or higher
- Python 3.6 or higher
- Access to a Jellyfin server (v10.11.6 or compatible)
- Valid API token or username/password credentials

## Installation

This role is designed to be used locally in your Ansible project. It's already available in the `roles/` directory.

## Role Variables

### Default Variables (defined in `defaults/main.yml`)

```yaml
# Jellyfin server configuration
jellyfin_url: "http://localhost:8096"
jellyfin_api_token: ""
jellyfin_username: ""
jellyfin_password: ""

# SSL/TLS certificate validation
jellyfin_validate_certs: true

# Request timeout (seconds)
jellyfin_request_timeout: 30

# Common operation defaults
jellyfin_user_password_required: false
jellyfin_library_refresh_on_create: true
```

## The `jellyfin_api` Module

The core of this role is the `jellyfin_api` custom module, which provides a generic interface to any Jellyfin API endpoint.

### Module Parameters

| Parameter | Required | Default | Description |
|-----------|----------|---------|-------------|
| `base_url` | Yes | - | Base URL of the Jellyfin server |
| `api_token` | No* | - | API token for authentication |
| `username` | No* | - | Username for authentication |
| `password` | No* | - | Password for authentication |
| `endpoint` | Yes | - | API endpoint path (e.g., `/Users`) |
| `method` | No | GET | HTTP method (GET, POST, PUT, DELETE, PATCH) |
| `query_params` | No | {} | Query parameters as a dictionary |
| `body` | No | {} | Request body as a dictionary |
| `headers` | No | {} | Additional headers |
| `validate_certs` | No | true | Validate SSL certificates |
| `timeout` | No | 30 | Request timeout in seconds |

\* Either `api_token` or both `username` and `password` must be provided.

### Module Examples

```yaml
# Get system information
- name: Get Jellyfin system info
  jellyfin_api:
    base_url: "http://localhost:8096"
    api_token: "your-api-token"
    endpoint: "/System/Info"
    method: GET

# Create a new user
- name: Create Jellyfin user
  jellyfin_api:
    base_url: "http://localhost:8096"
    api_token: "{{ jellyfin_api_token }}"
    endpoint: "/Users/New"
    method: POST
    body:
      Name: "newuser"
      Password: "securepassword"

# Get library items with filters
- name: Get library items
  jellyfin_api:
    base_url: "{{ jellyfin_url }}"
    api_token: "{{ jellyfin_api_token }}"
    endpoint: "/Items"
    method: GET
    query_params:
      ParentId: "{{ library_id }}"
      Recursive: true
      Fields: "Path,MediaSources"
```

## Pre-built Task Files

The role includes several task files for common operations:

### 1. User Management (`users.yml`)

```yaml
# List all users
- import_role:
    name: jellyfin
    tasks_from: users
  vars:
    jellyfin_url: "http://localhost:8096"
    jellyfin_api_token: "your-token"
    jellyfin_action: list

# Create a user
- import_role:
    name: jellyfin
    tasks_from: users
  vars:
    jellyfin_url: "http://localhost:8096"
    jellyfin_api_token: "your-token"
    jellyfin_action: create
    jellyfin_new_user_name: "john"
    jellyfin_new_user_password: "securepass123"

# Update user password
- import_role:
    name: jellyfin
    tasks_from: users
  vars:
    jellyfin_url: "http://localhost:8096"
    jellyfin_api_token: "your-token"
    jellyfin_action: update_password
    jellyfin_user_id: "user-id-here"
    jellyfin_user_new_password: "newsecurepass"

# Delete a user
- import_role:
    name: jellyfin
    tasks_from: users
  vars:
    jellyfin_action: delete
    jellyfin_user_id: "user-id-here"
```

**Available Actions:** `list`, `create`, `get`, `update`, `delete`, `update_password`, `update_policy`

### 2. Library Management (`libraries.yml`)

```yaml
# List all libraries
- import_role:
    name: jellyfin
    tasks_from: libraries
  vars:
    jellyfin_url: "http://localhost:8096"
    jellyfin_api_token: "your-token"
    jellyfin_action: list

# Create a library
- import_role:
    name: jellyfin
    tasks_from: libraries
  vars:
    jellyfin_action: create
    jellyfin_library_name: "Movies"
    jellyfin_library_type: "movies"
    jellyfin_library_paths:
      - Path: "/mnt/media/movies"

# Scan library
- import_role:
    name: jellyfin
    tasks_from: libraries
  vars:
    jellyfin_action: scan

# Add path to existing library
- import_role:
    name: jellyfin
    tasks_from: libraries
  vars:
    jellyfin_action: add_path
    jellyfin_library_name: "Movies"
    jellyfin_media_path: "/mnt/media/movies2"
```

**Available Actions:** `list`, `create`, `delete`, `scan`, `get_items`, `add_path`, `remove_path`

### 3. API Key Management (`api_keys.yml`)

```yaml
# List all API keys
- import_role:
    name: jellyfin
    tasks_from: api_keys
  vars:
    jellyfin_url: "http://localhost:8096"
    jellyfin_api_token: "your-token"
    jellyfin_action: list

# Create API key
- import_role:
    name: jellyfin
    tasks_from: api_keys
  vars:
    jellyfin_action: create
    jellyfin_api_key_app_name: "Ansible Automation"

# Revoke API key
- import_role:
    name: jellyfin
    tasks_from: api_keys
  vars:
    jellyfin_action: revoke
    jellyfin_api_key_to_revoke: "key-to-revoke"
```

**Available Actions:** `list`, `create`, `revoke`

### 4. System Operations (`system.yml`)

```yaml
# Get system information
- import_role:
    name: jellyfin
    tasks_from: system
  vars:
    jellyfin_url: "http://localhost:8096"
    jellyfin_api_token: "your-token"
    jellyfin_action: info

# Get activity log
- import_role:
    name: jellyfin
    tasks_from: system
  vars:
    jellyfin_action: activity_log
    jellyfin_log_limit: 100

# Restart Jellyfin
- import_role:
    name: jellyfin
    tasks_from: system
  vars:
    jellyfin_action: restart

# Ping server
- import_role:
    name: jellyfin
    tasks_from: system
  vars:
    jellyfin_action: ping
```

**Available Actions:** `info`, `public_info`, `get_config`, `update_config`, `restart`, `shutdown`, `activity_log`, `logs`, `ping`

### 5. Backup Operations (`backups.yml`)

```yaml
# List backups
- import_role:
    name: jellyfin
    tasks_from: backups
  vars:
    jellyfin_url: "http://localhost:8096"
    jellyfin_api_token: "your-token"
    jellyfin_action: list

# Create backup
- import_role:
    name: jellyfin
    tasks_from: backups
  vars:
    jellyfin_action: create

# Restore backup
- import_role:
    name: jellyfin
    tasks_from: backups
  vars:
    jellyfin_action: restore
    jellyfin_backup_name: "backup-name.zip"
```

**Available Actions:** `list`, `create`, `download`, `restore`

## Complete Examples

### Example 1: Initial Setup with User and Library

```yaml
---
- name: Setup Jellyfin
  hosts: localhost
  vars:
    jellyfin_url: "http://localhost:8096"
    jellyfin_api_token: "{{ vault_jellyfin_api_token }}"
  
  tasks:
    # Create admin user
    - import_role:
        name: jellyfin
        tasks_from: users
      vars:
        jellyfin_action: create
        jellyfin_new_user_name: "admin"
        jellyfin_new_user_password: "{{ vault_admin_password }}"
    
    # Create Movies library
    - import_role:
        name: jellyfin
        tasks_from: libraries
      vars:
        jellyfin_action: create
        jellyfin_library_name: "Movies"
        jellyfin_library_type: "movies"
        jellyfin_library_paths:
          - Path: "/mnt/media/movies"
    
    # Create TV Shows library
    - import_role:
        name: jellyfin
        tasks_from: libraries
      vars:
        jellyfin_action: create
        jellyfin_library_name: "TV Shows"
        jellyfin_library_type: "tvshows"
        jellyfin_library_paths:
          - Path: "/mnt/media/tv"
```

### Example 2: Direct Module Usage for Custom Operations

```yaml
---
- name: Custom Jellyfin Operations
  hosts: localhost
  vars:
    jellyfin_url: "http://localhost:8096"
    jellyfin_api_token: "your-token"
  
  tasks:
    # Get all scheduled tasks
    - name: Get scheduled tasks
      jellyfin_api:
        base_url: "{{ jellyfin_url }}"
        api_token: "{{ jellyfin_api_token }}"
        endpoint: "/ScheduledTasks"
        method: GET
      register: scheduled_tasks
    
    # Trigger a specific task
    - name: Trigger library scan task
      jellyfin_api:
        base_url: "{{ jellyfin_url }}"
        api_token: "{{ jellyfin_api_token }}"
        endpoint: "/ScheduledTasks/Running/{{ task_id }}"
        method: POST
      vars:
        task_id: "{{ (scheduled_tasks.response | selectattr('Name', 'equalto', 'Scan Media Library') | first).Id }}"
    
    # Get all plugins
    - name: List installed plugins
      jellyfin_api:
        base_url: "{{ jellyfin_url }}"
        api_token: "{{ jellyfin_api_token }}"
        endpoint: "/Plugins"
        method: GET
      register: plugins
    
    - name: Display plugins
      debug:
        var: plugins.response
```

### Example 3: Authentication with Username/Password

```yaml
---
- name: Jellyfin operations with password auth
  hosts: localhost
  vars:
    jellyfin_url: "http://localhost:8096"
  
  tasks:
    # Using username/password instead of API token
    - name: Get current user information
      jellyfin_api:
        base_url: "{{ jellyfin_url }}"
        username: "admin"
        password: "{{ vault_jellyfin_password }}"
        endpoint: "/Users/Me"
        method: GET
      register: current_user
    
    - name: Display user info
      debug:
        msg: "Logged in as: {{ current_user.response.Name }}"
```

## Advanced Usage

### Working with the OpenAPI Specification

The role is built from the official Jellyfin OpenAPI specification (`jellyfin-openapi-stable.json`). You can reference this file to discover all available endpoints:

```yaml
# Any endpoint from the OpenAPI spec can be called
- name: Get branding options
  jellyfin_api:
    base_url: "{{ jellyfin_url }}"
    api_token: "{{ jellyfin_api_token }}"
    endpoint: "/Branding/Configuration"
    method: GET

# Create a collection
- name: Create movie collection
  jellyfin_api:
    base_url: "{{ jellyfin_url }}"
    api_token: "{{ jellyfin_api_token }}"
    endpoint: "/Collections"
    method: POST
    query_params:
      name: "Marvel Movies"
      parentId: "{{ movies_library_id }}"
      ids: "{{ movie_ids | join(',') }}"
```

### Error Handling

```yaml
- name: Check if Jellyfin is accessible
  jellyfin_api:
    base_url: "{{ jellyfin_url }}"
    endpoint: "/System/Ping"
    method: GET
  register: ping_result
  ignore_errors: true

- name: Handle connection failure
  debug:
    msg: "Jellyfin server is not accessible!"
  when: ping_result.failed

- name: Proceed with operations
  block:
    - import_role:
        name: jellyfin
        tasks_from: users
      vars:
        jellyfin_action: list
  when: not ping_result.failed
```

## API Endpoint Reference

Here are some commonly used endpoints from the Jellyfin API:

### User Endpoints

- `GET /Users` - Get all users
- `POST /Users/New` - Create new user
- `GET /Users/{userId}` - Get user by ID
- `POST /Users/{userId}` - Update user
- `DELETE /Users/{userId}` - Delete user
- `POST /Users/{userId}/Password` - Update password
- `POST /Users/{userId}/Policy` - Update user policy

### Library Endpoints

- `GET /Library/VirtualFolders` - Get all libraries
- `POST /Library/VirtualFolders` - Create library
- `DELETE /Library/VirtualFolders` - Delete library
- `POST /Library/Refresh` - Scan all libraries
- `GET /Items` - Get library items

### System Endpoints

- `GET /System/Info` - Get system information
- `GET /System/Info/Public` - Get public system information
- `GET /System/Configuration` - Get server configuration
- `POST /System/Configuration` - Update configuration
- `POST /System/Restart` - Restart server
- `GET /System/ActivityLog/Entries` - Get activity log

### API Key Endpoints

- `GET /Auth/Keys` - Get all API keys
- `POST /Auth/Keys` - Create API key
- `DELETE /Auth/Keys/{key}` - Revoke API key

For a complete list of endpoints, refer to the `jellyfin-openapi-stable.json` file.

## Security Considerations

1. **Protect API Tokens**: Always use Ansible Vault for storing sensitive data:

   ```bash
   ansible-vault encrypt_string 'your-api-token' --name 'jellyfin_api_token'
   ```

2. **Use HTTPS**: In production, always use HTTPS for the Jellyfin URL:

   ```yaml
   jellyfin_url: "https://jellyfin.yourdomain.com"
   ```

3. **Certificate Validation**: Keep `jellyfin_validate_certs: true` in production

4. **Least Privilege**: Create dedicated API keys with appropriate permissions for automation

## Troubleshooting

### Module not found

If Ansible can't find the `jellyfin_api` module, ensure you're using the role correctly:

```yaml
- import_role:
    name: jellyfin
```

### Authentication failures

- Verify your API token is correct and not expired
- Check that the user has appropriate permissions
- Ensure the Jellyfin server URL is accessible

### SSL certificate errors

If using self-signed certificates:

```yaml
jellyfin_validate_certs: false
```

## Contributing

To extend this role:

1. **Add new task files**: Create new files in `roles/jellyfin/tasks/` for specific operations
2. **Consult the OpenAPI spec**: Reference `jellyfin-openapi-stable.json` for endpoint details
3. **Follow the pattern**: Use the existing task files as templates

## License

GNU General Public License v3.0+

## Author

Homelab Ansible Project

## Version

1.0.0 - Based on Jellyfin API v10.11.6
