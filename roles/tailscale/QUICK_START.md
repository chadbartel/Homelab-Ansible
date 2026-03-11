# Tailscale Role — Quick Start

## Prerequisites

1. Add your Tailscale auth key to `vault.yml`:
   ```bash
   ansible-vault edit vault.yml
   # Add: vault_tailscale_auth_key: "tskey-auth-<your-key>"
   ```

2. Add to `vars.yml`:
   ```yaml
   tailscale_auth_key: "{{ vault_tailscale_auth_key }}"
   ```

## Deploy (all servers)

```yaml
- name: Deploy Tailscale
  hosts: homelab_servers
  become: true
  vars_files:
    - vars.yml
    - vault.yml
  tasks:
    - ansible.builtin.include_role:
        name: tailscale
      tags: ["tailscale"]
```

```bash
ansible-playbook main.yml --tags tailscale
```

## Post-Deploy

After the first run, **approve the subnet route** in the Tailscale admin console:

1. Go to https://login.tailscale.com/admin/machines
2. Find each homelab node
3. Click **Edit route settings** → Enable `192.168.1.0/24`

## Verify

```bash
# Check container is running
docker ps | grep tailscale

# Check tailnet status
docker exec tailscale tailscale status
```

## Variables

| Variable | Default | Description |
|---|---|---|
| `tailscale_image` | `tailscale/tailscale:latest` | Docker image |
| `tailscale_container_name` | `tailscale` | Container name |
| `tailscale_hostname` | `{{ inventory_hostname \| replace('_','-') }}` | Tailnet node name |
| `tailscale_routes` | `192.168.1.0/24` | Advertised subnet |
| `tailscale_state_dir` | `/var/lib/tailscale` | State directory |
| `tailscale_volume_name` | `tailscale_data` | Named volume |
| `tailscale_auth_key` | *(required)* | Auth key from vault |
| `tailscale_restart_policy` | `unless-stopped` | Restart policy |
