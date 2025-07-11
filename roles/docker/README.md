# Ansible Role: Docker

Docker Engine installation and configuration with multi-architecture support for homelab environments.

## Requirements

- Ansible >= 2.14
- Target OS: Ubuntu 20.04+, Debian 11+
- Internet connectivity for Docker repository access

## Role Variables

### Default Variables
```yaml
# Docker packages to install
docker_packages:
  - docker-ce
  - docker-ce-cli
  - containerd.io
  - docker-buildx-plugin
  - docker-compose-plugin

# Users to add to docker group
docker_users: 
  - "{{ ansible_user }}"

# Docker daemon configuration
docker_daemon_options:
  storage-driver: "overlay2"
  log-driver: "json-file"
  log-opts:
    max-size: "100m"
    max-file: "3"

# Version requirements
docker_min_version: "24.0.0"

# Health checks
docker_health_checks_enabled: true
```

## Dependencies

- `common` role (optional, when `docker_install_common: true`)

## Example Playbook

```yaml
---
- hosts: servers
  become: true
  roles:
    - role: docker
      vars:
        docker_users:
          - "homelab"
          - "admin"
        docker_daemon_options:
          log-driver: "syslog"
          storage-driver: "overlay2"
```

## Supported Architectures

- x86_64 (amd64)
- ARM64 (aarch64)

## Supported Distributions

- Ubuntu 20.04, 22.04, 24.04
- Debian 11, 12

## Tags

- `docker` - All Docker tasks
- `validate` - Configuration validation
- `install` - Docker installation
- `configure` - Docker configuration
- `health` - Health checks

## Features

- ✅ Multi-architecture support
- ✅ Version checking and idempotent installation
- ✅ Docker daemon configuration
- ✅ User management for Docker group
- ✅ Health checks and validation
- ✅ Fallback installation method

## License

CC0-1.0

## Author Information

This role was created by [thatsmidnight](https://github.com/thatsmidnight).
