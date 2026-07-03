# Tailscale Native Host Role

## Overview

This Ansible role installs, configures, and authenticates Tailscale natively on a Ubuntu host (no Docker containers). It replaces the deprecated Docker-based Tailscale implementation and provides stable support for exit node and subnet router modes.

## What This Role Does

1. **Cleanup**: Removes any legacy Docker-based Tailscale containers and volumes
2. **Prerequisites**: Installs required packages (`curl`, `apt-transport-https`, `ca-certificates`, `gnupg`)
3. **Repository Setup**: Adds the official Tailscale GPG key and APT repository for your Ubuntu version
4. **Installation**: Installs the `tailscale` package from the official repository
5. **Service Management**: Enables and starts the `tailscaled` daemon
6. **Idempotent Authentication**: Uses vault-provided auth key to authenticate the node (only runs if not already authenticated)
7. **Verification**: Confirms IP forwarding is enabled for exit node/subnet router functionality

## Architecture & Use Cases

### Exit Node Mode (Coffee Shop Scenario)
Route all your phone/laptop traffic through your home internet to encrypt traffic on public WiFi:
- Flag: `--advertise-exit-node`
- Other Tailscale nodes can select your monolith as their exit node
- All traffic routes through your home connection

### Subnet Router Mode (Remote Homelab Scenario)
Access internal services (like Jellyfin, Pi-hole) from anywhere without being on your home WiFi:
- Flag: `--advertise-routes=192.168.1.0/24`
- Docker services become accessible via the Tailscale network
- Requires IP forwarding enabled

### Both Modes Enabled (Recommended)
This role enables both by default:
```
--advertise-exit-node --advertise-routes=192.168.1.0/24
```

## Prerequisites

- Ubuntu Server 20.04+
- Ansible 2.9+
- `vault_tailscale_auth_key` defined in `vault.yml`
- IP forwarding enabled (handled by `tasks/initial_setup.yml` or this role verifies it)

## Required Variables (from vault.yml)

```yaml
vault_tailscale_auth_key: "tskey-XXXXX..."  # Auth key from Tailscale admin console
vault_tailscale_api_key: "tsk_XXXXX..."      # Optional: API key for advanced operations
```

## Role Variables

Edit in `group_vars/monolith.yml` or via `-e` flags:

```yaml
# Advertise the local LAN subnet to enable subnet router mode
tailscale_advertise_routes: "192.168.1.0/24"

# Enable exit node mode for VPN passthrough
tailscale_advertise_exit_node: true

# Additional Tailscale flags (e.g., --ssh, --shields-up)
tailscale_additional_flags: ""

# Verify IP forwarding is enabled
verify_ip_forwarding: true

# Service configuration
tailscale_service_name: "tailscaled"
tailscale_service_enabled: true
tailscale_service_state: "started"
```

## Integration into Main Playbook

Add this to the bootstrap phase in `main.yml`:

```yaml
- name: Install and configure native Tailscale
  ansible.builtin.include_role:
    name: tailscale
  vars:
    tailscale_advertise_routes: "192.168.1.0/24"
    tailscale_advertise_exit_node: true
  tags: ["bootstrap", "tailscale"]
```

## Idempotency Details

**Authentication (Critical)**

The `authenticate.yml` task is fully idempotent:

1. Checks `tailscale status --json` to get current `BackendState`
2. If `BackendState != Running`, executes:
   ```bash
   tailscale up --reset --auth-key=<key> --advertise-routes=... --advertise-exit-node
   ```
3. If already running, **skips authentication** (no re-authentication noise, no connection restart)
4. Verifies final status and displays configuration

**Why `--reset` is used:**

- Ensures clean state on first run
- Does not harm subsequent runs (node remains authenticated if it was before)
- Essential for reliable subnet router and exit node setup

## Common Operations

### Check Tailscale Status on Host

```bash
sudo tailscale status
```

Output shows:
- Peer connections (your phone, laptop, etc.)
- Your Tailscale IP address
- Exit node status
- Advertised routes

### Enable Exit Node (after Tailscale is running)

```bash
sudo tailscale up --advertise-exit-node
```

### View Available Exit Nodes (from another device)

```bash
tailscale status --json | jq '.Peer[] | select(.HasCaps)'
```

### Re-run Role to Reconfigure Routes

```bash
ansible-playbook main.yml --tags tailscale \
  -e tailscale_advertise_routes="192.168.1.0/24,10.0.0.0/8"
```

### Troubleshooting Authentication Failures

If authentication hangs or fails:

1. Check auth key validity in Tailscale admin console (https://login.tailscale.com)
2. Verify vault decryption: `ansible-vault view vault.yml | grep vault_tailscale_auth_key`
3. Check connectivity: `sudo systemctl status tailscaled`
4. View logs: `sudo journalctl -u tailscaled -f`

## Vault Setup

Ensure `vault.yml` (vault-encrypted) contains:

```yaml
vault_tailscale_auth_key: "tskey-XXXXX..."
vault_tailscale_api_key: "tsk_XXXXX..."
```

Generate an ephemeral auth key in Tailscale admin console:
1. Log in to https://login.tailscale.com
2. Go to **Settings > Keys**
3. Click **Create auth key**
4. Set expiration (1 hour is fine for Ansible)
5. Copy the key and add to vault

## Post-Installation Verification

After running this role:

```bash
# On your phone/laptop connected to Tailscale
ping <monolith-tailscale-ip>                    # Basic connectivity
ssh ubuntu@<monolith-tailscale-ip>              # SSH access (if key-based auth is set up)
curl http://<jellyfin-container-ip>:8096        # Access Docker services
tailscale status --json | jq .MagicDNS          # Check DNS resolution
```

## Design Principles

- **Idempotent**: Safe to run multiple times; only makes necessary changes
- **Portable**: Works across Ubuntu 20.04 through 26.04
- **Clean**: Removes legacy Docker implementation automatically
- **Transparent**: Clear logging and status messages at each step
- **Vault-native**: All secrets encrypted and referenced from vault

## Files & Structure

```
roles/tailscale/
├── meta/main.yml                    # Galaxy metadata
├── defaults/main.yml                # Default variables
├── tasks/
│   ├── main.yml                     # Orchestration
│   ├── cleanup_docker_tailscale.yml # Remove old containers
│   ├── install_prerequisites.yml    # Install curl, etc.
│   ├── add_tailscale_repo.yml       # Add official repo
│   ├── install_tailscale.yml        # Install package
│   ├── start_service.yml            # Start tailscaled
│   ├── authenticate.yml             # Idempotent auth
│   └── verify_ip_forwarding.yml     # Check forwarding enabled
├── README.md                        # Full documentation (this file)
└── QUICK_START.md                   # Quick reference
```

## References

- [Tailscale Official Docs](https://tailscale.com/kb/)
- [Exit Nodes & Relay Servers](https://tailscale.com/kb/1103/exit-nodes/)
- [Subnet Router Setup](https://tailscale.com/kb/1019/subnets/)
- [Tailscale on Linux](https://tailscale.com/kb/1031/install-linux/)
