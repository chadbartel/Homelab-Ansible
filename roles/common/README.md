# Ansible Role: Common

Base system configuration for homelab servers including user management, SSH hardening, and essential package installation.

## Requirements

- Ansible >= 2.14
- Target OS: Ubuntu 20.04+, Debian 11+
- Sudo access on target hosts

## Role Variables

### Required Variables
```yaml
common_admin_user: "homelab"          # Admin username
common_admin_email: "admin@home.lab"  # Admin email
```

### Optional Variables
```yaml
common_admin_password: ""             # Admin password (hashed)
common_admin_ssh_key: ""              # SSH public key
common_timezone: "UTC"                # System timezone
common_ssh_port: 22                   # SSH port
common_ssh_password_auth: false       # Allow SSH password auth
common_disable_root_login: true       # Disable root SSH access

# Packages to install
common_essential_packages:
  - curl
  - wget
  - git
  - htop
  - vim
  - unzip
  - ca-certificates
  - gnupg
  - lsb-release
  - python3-pip
  - python3-venv
```

## Dependencies

None

## Example Playbook

```yaml
---
- hosts: servers
  become: true
  roles:
    - role: common
      vars:
        common_admin_user: "homelab"
        common_admin_email: "admin@homelab.local"
        common_admin_ssh_key: "ssh-rsa AAAAB3NzaC1yc2E..."
        common_timezone: "America/New_York"
```

## Tags

- `common` - All common tasks
- `validate` - Configuration validation
- `users` - User management
- `packages` - Package installation
- `system` - System configuration

## License

CC0-1.0

## Author Information

This role was created by [thatsmidnight](https://github.com/thatsmidnight).
