# Tailscale Role: Quick Start

## 5-Minute Setup

### 1. Add to Your Vault

Edit `vault.yml` (decrypt with `ansible-vault edit vault.yml`):

```yaml
vault_tailscale_auth_key: "tskey-XXXXX..."  # From Tailscale admin console
vault_tailscale_api_key: "tsk_XXXXX..."
```

### 2. Add to Bootstrap Phase (main.yml)

```yaml
- name: Install and configure native Tailscale
  ansible.builtin.include_role:
    name: tailscale
  vars:
    tailscale_advertise_routes: "192.168.1.0/24"
    tailscale_advertise_exit_node: true
  tags: ["bootstrap", "tailscale"]
```

### 3. Run the Playbook

```bash
ansible-playbook main.yml --tags bootstrap
```

### 4. Verify on Your Home Server

```bash
ssh ubuntu@192.168.1.17
sudo tailscale status
```

You should see:
```
     100.x.x.1 monolith         [your-server] tailscale ipv6
     peer routes: 192.168.1.0/24
     exit node: yes
```

### 5. Connect Your Phone/Laptop

1. Install Tailscale on your device
2. Log in with your Tailscale account
3. You'll see `monolith` in your peer list
4. For exit node: Click the 3-dot menu → **Use as exit node**

## Common Tasks

| Task | Command |
|------|---------|
| Check status | `sudo tailscale status` |
| Disable exit node | `sudo tailscale up --advertise-exit-node=false` |
| Add more routes | `ansible-playbook main.yml --tags tailscale -e tailscale_advertise_routes="192.168.1.0/24,10.0.0.0/8"` |
| Check logs | `sudo journalctl -u tailscaled -f` |
| Restart daemon | `sudo systemctl restart tailscaled` |

## Troubleshooting

### Status says "NeedsLogin"
```bash
sudo journalctl -u tailscaled -n 50
# Check that vault.yml has vault_tailscale_auth_key defined
# Verify the key is still valid (not expired in Tailscale console)
```

### Can't ping from remote device
```bash
# On home server
sudo tailscale status
# Check advertised routes: "peer routes: 192.168.1.0/24"

# On remote device
tailscale status --json | jq '.Self.Routes'
# Should see 192.168.1.0/24 listed
```

### Exit node not working
```bash
# Check IP forwarding is enabled
sysctl net.ipv4.ip_forward  # Should return "1"
# If not, run: ansible-playbook main.yml --tags bootstrap
```

## Generated Auth Key (One-Time Ephemeral)

Create in Tailscale Admin Console (https://login.tailscale.com):

1. Go to **Settings > Keys**
2. Click **Create auth key**
3. **Recommended settings:**
   - Expiration: 1 hour (for automation purposes)
   - Reusable: No (creates new nodes on each auth)
   - Tags: Leave empty or use `tag:homelab`
4. Copy and paste into vault

This key is single-use; each run that needs authentication will auto-generate a fresh auth flow. Once your node is authenticated, re-runs are idempotent and safe.

## Variables You Can Override

```yaml
# Adjust to your local subnet
tailscale_advertise_routes: "192.168.1.0/24"

# Enable/disable exit node
tailscale_advertise_exit_node: true

# Additional flags (--ssh, --shields-up, etc.)
tailscale_additional_flags: ""

# Skip IP forwarding verification
verify_ip_forwarding: true
```

Use with `-e` on command line:
```bash
ansible-playbook main.yml --tags tailscale \
  -e tailscale_advertise_routes="10.0.0.0/8" \
  -e tailscale_advertise_exit_node=false
```

## Next Steps

- **DNS Integration**: Add entries to Pi-hole for Tailscale domain names
- **SSH Access**: Set up Tailscale SSH (`--ssh` flag) for passwordless SSH
- **Service Access**: Update Nginx Proxy Manager to accept Tailscale connections
- **ACLs**: Configure access control in Tailscale admin console

See full README.md for advanced topics.
