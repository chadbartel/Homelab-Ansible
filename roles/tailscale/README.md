# Tailscale Role

Deploys [Tailscale](https://tailscale.com/) as a **standalone Docker container** on each target host, advertising the local subnet as a Tailscale subnet router.

> **Note**: This role uses `community.docker.docker_container` directly (not Docker Swarm / `stack_deployer`) because `network_mode: host` is incompatible with Docker Swarm services. This makes it the first standalone-container role in this project.

---

## Role Variables

All variables are prefixed with `tailscale_`. Defaults are in [`defaults/main.yml`](defaults/main.yml).

### Container

| Variable | Default | Description |
|---|---|---|
| `tailscale_image` | `tailscale/tailscale:latest` | Docker image to pull |
| `tailscale_container_name` | `tailscale` | Docker container name |
| `tailscale_hostname` | `{{ inventory_hostname \| replace('_','-') }}` | Hostname shown in the Tailscale admin console. Unique per node by default. |
| `tailscale_container_state` | `started` | Desired container state (`started`, `stopped`, `absent`, `present`) |
| `tailscale_restart_policy` | `unless-stopped` | Docker restart policy |

### Tailscale Configuration

| Variable | Default | Description |
|---|---|---|
| `tailscale_routes` | `192.168.1.0/24` | Subnet routes to advertise as a subnet router (comma-separated CIDRs) |
| `tailscale_state_dir` | `/var/lib/tailscale` | State directory inside the container (`TS_STATE_DIR`) |
| `tailscale_auth_key` | *(required)* | Tailscale auth key for automatic tailnet join. **Must be defined** — set via vault (`vault_tailscale_auth_key`). |

### Volume & Devices

| Variable | Default | Description |
|---|---|---|
| `tailscale_volume_name` | `tailscale_data` | Named Docker volume for persistent state |
| `tailscale_tun_device` | `/dev/net/tun` | TUN device path (required for kernel networking) |

---

## Requirements

- Ansible `community.docker` collection
- Docker installed on all target hosts (handled by the `docker` task in `main.yml`)
- A valid [Tailscale auth key](https://login.tailscale.com/admin/settings/keys) stored in `vault.yml`

---

## Setup

### 1. Add the auth key to vault

```bash
ansible-vault edit vault.yml
```

Add:
```yaml
vault_tailscale_auth_key: "tskey-auth-<your-key-here>"
```

### 2. Configure `vars.yml`

```yaml
# Tailscale Configuration
tailscale_image: "tailscale/tailscale:latest"
tailscale_container_name: "tailscale"
tailscale_routes: "192.168.1.0/24"
tailscale_volume_name: "tailscale_data"
tailscale_auth_key: "{{ vault_tailscale_auth_key }}"
```

### 3. (Optional) Per-node hostname override

In `host_vars/lenovo_server.yml`:
```yaml
tailscale_hostname: "lenovo-homelab"
```

---

## Usage

### Via `main.yml` (recommended)

A dedicated play is already included in `main.yml`:

```bash
ansible-playbook main.yml --tags tailscale
```

### Standalone playbook

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

### Modular usage (individual task files)

```yaml
# Volume only
- ansible.builtin.include_role:
    name: tailscale
    tasks_from: volume

# Container only (volume must already exist)
- ansible.builtin.include_role:
    name: tailscale
    tasks_from: container
```

---

## Architecture Notes

### Why not Docker Swarm?

`network_mode: host` binds the container directly to the host's network stack — a requirement for Tailscale to intercept and route traffic at the kernel level. Docker Swarm services do not support `network_mode: host`, so this role deploys a plain Docker container on each host independently.

### Subnet Router

Setting `tailscale_routes: "192.168.1.0/24"` configures the container as a [subnet router](https://tailscale.com/kb/1019/subnets). After deployment, the route must be **manually approved** in the Tailscale admin console before remote clients can reach `192.168.1.0/24` through the VPN.

### Capabilities

- `net_admin` — Required for Tailscale to manage routing tables and firewall rules
- `sys_module` — Required for WireGuard kernel module loading

### ARM Hosts (pi4_01, pi3_01)

Raspberry Pi OS ships the WireGuard kernel module in recent kernels (5.6+). Verify with:
```bash
modinfo wireguard
```
If absent, install it:
```bash
sudo apt-get install wireguard-tools
```

---

## Post-Deployment Steps

1. **Approve subnet routes** in the [Tailscale admin console](https://login.tailscale.com/admin/machines):
   - Find each homelab node
   - Click **Edit route settings** → Enable `192.168.1.0/24`

2. **Verify** from a remote Tailscale client:
   ```bash
   ping 192.168.1.10   # pi4_01
   ping 192.168.1.12   # lenovo_server
   ```

---

## Idempotency

- Volume creation: `community.docker.docker_volume` with `state: present` — no-op if already exists
- Container deployment: `community.docker.docker_container` — only restarts if image or config changed
- Re-running the play with the same auth key is safe (Tailscale ignores reuse of a key it has already processed when state is persisted)

---

## Tags

| Tag | Effect |
|---|---|
| `tailscale` | Run all Tailscale tasks |
| `deploy` | Alias for the deployment task |
