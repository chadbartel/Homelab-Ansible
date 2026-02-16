# Jellyfin Configuration Role

Ansible role for post-deployment configuration of Jellyfin media server in Docker Swarm environments. This role provides idempotent, modular configuration tasks that can be run independently or as a complete setup workflow.

## Features

- ✅ **Idempotent Operations**: All tasks safely re-runnable without side effects
- 🔍 **Automatic Container Discovery**: Finds Jellyfin containers in Swarm cluster
- 🎯 **Modular Task Files**: Use individual tasks or complete setup workflow
- 🔐 **Secure API Key Management**: Creates or retrieves API keys with duplicate checking
- 📚 **Library Management**: Configures media libraries via declarative variables
- 🧙 **Setup Wizard Automation**: Completes first-time Jellyfin setup automatically

## Requirements

- Ansible 2.9+
- Docker Swarm cluster with Jellyfin service deployed
- `jellyfin` role (dependency for library management)
- Admin credentials for Jellyfin instance

## Role Variables

### Service Discovery

```yaml
jellyfin_config_service_name: "jellyfin-stack_jellyfin"  # Swarm service name
jellyfin_config_swarm_manager: "pi4_01"                   # Swarm manager node
jellyfin_config_target_node: "lenovo_server"             # Node where container runs
jellyfin_config_web_port: 8096                            # Jellyfin web port
```

### Service Readiness

```yaml
jellyfin_config_readiness_retries: 24       # Number of readiness checks
jellyfin_config_readiness_delay: 10         # Delay between checks (seconds)
jellyfin_config_readiness_timeout: 180      # Total timeout for port check
jellyfin_config_startup_wait: 45            # Initial wait before checks
```

### Setup Wizard

```yaml
jellyfin_config_server_name: "jellyfin"
jellyfin_config_ui_culture: "en-US"
jellyfin_config_metadata_country: "US"
jellyfin_config_preferred_metadata_language: "en"
jellyfin_config_disable_remote_access: false
```

### Admin User

```yaml
jellyfin_config_admin_user: "{{ admin_user }}"
jellyfin_config_admin_password: "{{ jellyfin_thatsmidnight_password }}"
```

**⚠️ Security Note**: Store password in `vault.yml`:

```yaml
vault_jellyfin_admin_password: "your_secure_password"
```

### API Key

```yaml
jellyfin_config_api_key_app_name: "ansible_automation"
jellyfin_config_api_token: ""  # Auto-generated or provided
```

### Media Libraries

```yaml
jellyfin_config_libraries:
  - name: "Music"
    type: "music"
    paths:
      - "/media/music"
    refresh_on_create: true
  
  - name: "Movies"
    type: "movies"
    paths:
      - "/media/movies"
    refresh_on_create: true
  
  - name: "TV Shows"
    type: "tvshows"
    paths:
      - "/media/tvshows"
    refresh_on_create: true
```

**Supported Library Types**:

- `music` - Music library
- `movies` - Movie library
- `tvshows` - TV show library
- `books` - Book library
- `photos` - Photo library

## Task Files

### `discover_container.yml`

Discovers the Jellyfin container in Docker Swarm and sets facts:

- `jellyfin_task_id`: Swarm task ID
- `jellyfin_node_name`: Node where container is running
- `jellyfin_container_id`: Docker container ID

```yaml
- include_tasks: discover_container.yml
```

### `wait_for_service.yml`

Waits for Jellyfin service to be fully ready and checks for errors.

```yaml
- include_tasks: wait_for_service.yml
  vars:
    target_host: "{{ ansible_host }}"  # Optional override
```

### `setup_wizard.yml`

Completes the initial Jellyfin setup wizard (idempotent - skips if already done).

```yaml
- include_tasks: setup_wizard.yml
  vars:
    target_url: "http://127.0.0.1:8096"  # Optional override
```

### `api_keys.yml`

Creates or retrieves API keys for automation (idempotent - checks for existing keys).

**Sets fact**: `jellyfin_config_api_token`

```yaml
- include_tasks: api_keys.yml
```

### `libraries.yml`

Configures media libraries using the `jellyfin` role.

```yaml
- include_tasks: libraries.yml
```

## Usage Examples

### Complete Post-Deployment Setup

```yaml
- name: Configure Jellyfin after deployment
  hosts: lenovo_server
  vars:
    jellyfin_config_admin_user: "{{ admin_user }}"
    jellyfin_config_admin_password: "{{ vault_jellyfin_admin_password }}"
  tasks:
    - name: Run complete Jellyfin configuration
      import_role:
        name: jellyfin_config
      vars:
        jellyfin_config_run_complete_setup: true
```

### Individual Task Usage

```yaml
- name: Only wait for service and create API key
  hosts: lenovo_server
  tasks:
    - name: Wait for Jellyfin to be ready
      import_role:
        name: jellyfin_config
        tasks_from: wait_for_service
    
    - name: Create API key
      import_role:
        name: jellyfin_config
        tasks_from: api_keys
      vars:
        jellyfin_config_admin_user: "admin"
        jellyfin_config_admin_password: "{{ vault_password }}"
```

### Custom Library Configuration

```yaml
- name: Configure custom libraries
  import_role:
    name: jellyfin_config
    tasks_from: libraries
  vars:
    jellyfin_config_api_token: "{{ vault_jellyfin_api_token }}"
    jellyfin_config_libraries:
      - name: "Documentaries"
        type: "movies"
        paths:
          - "/media/documentaries"
        refresh_on_create: true
      
      - name: "Audiobooks"
        type: "books"
        paths:
          - "/media/audiobooks"
        refresh_on_create: false
```

## Integration with Existing Homelab-Ansible Project

Replace the current `tasks/post_setup_jellyfin.yml` with this role:

```yaml
# tasks/post_setup.yml
- name: Configure Jellyfin post-deployment
  import_role:
    name: jellyfin_config
    tasks_from: wait_for_service
  delegate_to: lenovo_server

- name: Complete Jellyfin setup wizard
  import_role:
    name: jellyfin_config
    tasks_from: setup_wizard
  delegate_to: lenovo_server

- name: Create Jellyfin API key
  import_role:
    name: jellyfin_config
    tasks_from: api_keys
  delegate_to: lenovo_server

- name: Configure Jellyfin libraries
  import_role:
    name: jellyfin_config
    tasks_from: libraries
  delegate_to: lenovo_server
```

## Idempotency Details

### Setup Wizard

- Checks `/Startup/Configuration` endpoint
- Only runs wizard steps if status is `200` (wizard not completed)
- Skips if status is `404` (wizard already done)

### API Keys

- Queries existing API keys via `/Auth/Keys`
- Searches for key with matching `AppName`
- Only creates new key if matching key not found
- Returns existing key if found

### Libraries

- Delegates to `jellyfin` role which handles library creation idempotency
- Checks for existing libraries by name before creating

## Dependencies

This role depends on the `jellyfin` role for library management operations. Ensure the role is available:

```yaml
# requirements.yml
- src: ./roles/jellyfin
  name: jellyfin
```

## Facts Set by This Role

| Fact Name | Description | Set By |
| ----------- | ------------- | -------- |
| `jellyfin_task_id` | Swarm task ID | `discover_container.yml` |
| `jellyfin_node_name` | Swarm node hostname | `discover_container.yml` |
| `jellyfin_container_id` | Container ID | `discover_container.yml` |
| `jellyfin_config_api_token` | API authentication token | `api_keys.yml` |

## Troubleshooting

### Service Not Found

```text
failed_when: jellyfin_service_check.stdout == ""
```

**Solution**: Verify Jellyfin stack is deployed in Portainer:

```bash
docker service ls | grep jellyfin
```

### Authentication Failed

```text
Authentication failed (status: 401)
```

**Solution**: Verify admin credentials are correct in `vault.yml`

### Container Not Running on Expected Node

The role automatically discovers which node the container is on. If placement constraints aren't being honored, check the compose template:

```yaml
deploy:
  placement:
    constraints:
      - node.hostname == midnight-laptop
```

### API Key Already Exists with Different App Name

The role searches by `AppName`. If you change `jellyfin_config_api_key_app_name`, it will create a new key. To use an existing key, either:

1. Set `jellyfin_config_api_key_app_name` to match existing app name
2. Manually set `jellyfin_config_api_token` to bypass creation

## License

GPL-3.0-or-later

## Author

Homelab Ansible Project

## See Also

- [QUICK_START.md](QUICK_START.md) - Quick start guide
- [Jellyfin Role](../jellyfin/README.md) - Library management operations
- [Jellyctl Role](../jellyctl/README.md) - Alternative CLI-based management
- [Examples](examples/) - Example playbooks
