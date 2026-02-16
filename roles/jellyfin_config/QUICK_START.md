# Quick Start Guide - Jellyfin Config Role

This guide demonstrates the most common use cases for the jellyfin_config role.

## Scenario 1: Complete Initial Setup

Run all configuration tasks in sequence after Jellyfin deployment:

```bash
ansible-playbook examples/complete_setup.yml
```

Or in your main playbook:

```yaml
- name: Configure Jellyfin post-deployment
  hosts: lenovo_server
  vars_files:
    - vars.yml
    - vault.yml
  
  tasks:
    - name: Run complete Jellyfin configuration
      import_role:
        name: jellyfin_config
      vars:
        jellyfin_config_run_complete_setup: true
```

## Scenario 2: API Key Management Only

Create or retrieve API key without running full setup:

```bash
ansible-playbook examples/api_key_creation.yml
```

## Scenario 3: Library Configuration Only

Configure libraries after initial setup:

```bash
ansible-playbook examples/library_management.yml
```

## Scenario 4: Wait for Service Readiness

Check if Jellyfin is ready before proceeding with other tasks:

```bash
ansible-playbook examples/wait_for_ready.yml
```

## Scenario 5: Check Mode (Dry Run)

See what would change without applying:

```bash
ansible-playbook examples/complete_setup.yml --check
```

## Scenario 6: Verify Idempotency

Run twice to ensure no unnecessary changes:

```bash
ansible-playbook examples/complete_setup.yml
ansible-playbook examples/complete_setup.yml  # Should show changed=0 or minimal changes
```

## Integration with Main Playbook

Add to your main Homelab-Ansible playbook (`tasks/post_setup_jellyfin.yml`):

```yaml
---
# Jellyfin post-deployment configuration using jellyfin_config role

- name: Wait for Jellyfin service
  import_role:
    name: jellyfin_config
    tasks_from: wait_for_service
  delegate_to: lenovo_server

- name: Complete setup wizard
  import_role:
    name: jellyfin_config
    tasks_from: setup_wizard
  delegate_to: lenovo_server

- name: Create API key
  import_role:
    name: jellyfin_config
    tasks_from: api_keys
  delegate_to: lenovo_server

- name: Configure libraries
  import_role:
    name: jellyfin_config
    tasks_from: libraries
  delegate_to: lenovo_server

- name: Display completion message
  ansible.builtin.debug:
    msg: |
      ✅ Jellyfin configuration completed!
      Access: http://{{ ansible_host }}:{{ jellyfin_config_web_port }}
      API Token: {{ jellyfin_config_api_token }}
```

## Common Variables (vars.yml)

```yaml
# Jellyfin service configuration
jellyfin_config_service_name: "jellyfin-stack_jellyfin"
jellyfin_config_swarm_manager: "pi4_01"
jellyfin_config_target_node: "lenovo_server"
jellyfin_config_web_port: 8096

# Admin credentials (use vault for password!)
jellyfin_config_admin_user: "{{ admin_user }}"
jellyfin_config_admin_password: "{{ vault_jellyfin_admin_password }}"

# API key configuration
jellyfin_config_api_key_app_name: "ansible_automation"

# Media libraries
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

## Vault Variables (vault.yml)

```yaml
# Encrypt this file with: ansible-vault encrypt vault.yml
vault_jellyfin_admin_password: "your_secure_password_here"
vault_jellyfin_api_token: ""  # Auto-populated after first run
```

## Troubleshooting

### Service Not Found

Check if Jellyfin is running:

```bash
docker service ls | grep jellyfin
docker service ps jellyfin-stack_jellyfin
```

If service doesn't exist, check Portainer for deployment errors.

### Authentication Failed

Verify credentials in vault.yml:

```bash
ansible-vault edit vault.yml
```

Test authentication manually:

```bash
curl -X POST "http://192.168.1.12:8096/User/AuthenticateByName" \
  -H "Content-Type: application/json" \
  -d '{"Username":"admin","Pw":"your_password"}'
```

### Container Running on Wrong Node

Check placement constraints in `templates/jellyfin-compose.yml.j2`:

```yaml
deploy:
  placement:
    constraints:
      - node.hostname == midnight-laptop  # Use Swarm hostname, not Ansible inventory name
```

### Setup Wizard Already Completed

The role is idempotent and will skip wizard steps if already done. To reset:

1. Remove Jellyfin volume data
2. Restart the service
3. Run the role again

### API Key Shows "Not Found" Despite Existing

The role searches by `jellyfin_config_api_key_app_name`. If you changed this variable, it will create a new key. To use an existing key:

1. Check existing keys in Jellyfin Dashboard → API Keys
2. Set `jellyfin_config_api_key_app_name` to match the existing key's app name
3. Or manually set `jellyfin_config_api_token` in vars.yml

### Library Not Created

Check that:

1. API token is valid
2. Media paths exist in the container (`/media/music`, etc.)
3. NFS mounts are working (if using NFS storage)

Verify paths in the container:

```bash
docker exec <container_id> ls -la /media/
```

## Advanced Usage

### Custom Library Types

```yaml
jellyfin_config_libraries:
  - name: "Audiobooks"
    type: "books"
    paths:
      - "/media/audiobooks"
    refresh_on_create: false  # Don't scan immediately
  
  - name: "Concerts"
    type: "musicvideos"
    paths:
      - "/media/concerts"
    refresh_on_create: true
```

### Multiple Library Paths

```yaml
jellyfin_config_libraries:
  - name: "Movies"
    type: "movies"
    paths:
      - "/media/movies"
      - "/media/movies_4k"
      - "/media/classic_films"
    refresh_on_create: true
```

### Disable Output Messages

```yaml
- import_role:
    name: jellyfin_config
  vars:
    jellyfin_config_display_results: false  # Suppress informational messages
```

## Next Steps

1. **Store API Token**: After first run, save the API token to vault.yml:

   ```bash
   ansible-vault edit vault.yml
   # Add: vault_jellyfin_api_token: "your_token_here"
   ```

2. **Configure Hardware Acceleration**: 
   - Open Jellyfin Dashboard → Playback → Transcoding
   - Set to "Intel Quick Sync (QSV)" if using Intel GPU

3. **Monitor Library Scans**:
   - Dashboard → Scheduled Tasks → Scan Media Library
   - Check progress of initial media scanning

4. **Set Up Additional Users**: Use the `jellyfin` role for user management:

   ```yaml
   - import_role:
       name: jellyfin
       tasks_from: users
   ```

5. **Configure Backup**: Use the `jellyfin` role for automated backups:

   ```yaml
   - import_role:
       name: jellyfin
       tasks_from: backups
   ```

## See Also

- [README.md](README.md) - Complete role documentation
- [Examples](examples/) - Example playbooks
- [Jellyfin Role](../jellyfin/README.md) - Ongoing management operations
- [Jellyctl Role](../jellyctl/README.md) - CLI-based management alternative
