# Homelab Ansible Collection

A comprehensive, modular collection of Ansible roles for deploying and managing homelab infrastructure.

## 🎯 Overview

This collection provides a set of independent, reusable Ansible roles for building a complete homelab infrastructure. Each role can be used standalone or combined for complex deployments.

## 📦 Included Roles

### Core Infrastructure
- **`common`** - Base system configuration, user management, SSH hardening
- **`docker`** - Docker Engine installation and configuration  
- **`docker_swarm`** - Docker Swarm cluster management

### Services
- **`portainer`** - Container management platform
- **`pihole`** - DNS ad blocker with custom entries
- **`nginx_proxy_manager`** - Reverse proxy manager *(coming soon)*
- **`heimdall`** - Application dashboard *(coming soon)*
- **`openvpn`** - VPN server *(coming soon)*

### Orchestration
- **`homelab_stack`** - Complete homelab orchestration *(coming soon)*

## 🚀 Quick Start

### 1. Prerequisites
```bash
# Install dependencies
make install

# Setup SSH
make setup-ssh

# Configure variables
cp vars.example.yml vars.yml
# Edit vars.yml with your settings

# Create vault for sensitive data
ansible-vault create vault.yml
```

### 2. Choose Your Deployment

#### Single Node Setup
```bash
make deploy-single-node
```

#### Multi-Node Swarm Cluster
```bash
make deploy-multi-node
```

#### Minimal Setup (Docker + Portainer only)
```bash
make deploy-minimal
```

#### Full Role-Based Deployment
```bash
make deploy-roles
```

## 📖 Role Documentation

### Common Role
Base system configuration for all homelab servers.

```yaml
- role: common
  vars:
    common_admin_user: "homelab"
    common_admin_email: "admin@homelab.local"
    common_timezone: "America/New_York"
```

### Docker Role
Installs and configures Docker Engine with multi-architecture support.

```yaml
- role: docker
  vars:
    docker_users:
      - "{{ ansible_user }}"
    docker_daemon_options:
      log-driver: "json-file"
      log-opts:
        max-size: "100m"
```

### Docker Swarm Role
Manages Docker Swarm cluster initialization and node management.

```yaml
- role: docker_swarm
  vars:
    docker_swarm_role: "manager"  # or "worker"
```

### Portainer Role
Deploys Portainer for container management.

```yaml
- role: portainer
  vars:
    portainer_mode: "swarm"  # or "standalone"
    portainer_admin_password: "{{ vault_portainer_password }}"
```

### Pi-hole Role
Deploys Pi-hole DNS server with ad blocking and custom DNS entries.

```yaml
- role: pihole
  vars:
    pihole_web_password: "{{ vault_pihole_password }}"
    pihole_custom_dns_entries:
      - hostname: "home.lab"
        ip: "192.168.1.100"
```

## 🔧 Advanced Usage

### Custom Playbook Example
```yaml
---
- name: Custom homelab deployment
  hosts: homelab_servers
  become: true
  roles:
    - common
    - docker
    - portainer
    - pihole
```

### Role Variables
Each role has comprehensive defaults that can be overridden:

```yaml
# Example: Custom Docker configuration
docker_daemon_options:
  storage-driver: "overlay2"
  log-driver: "json-file"
  insecure-registries:
    - "registry.homelab.local:5000"
```

## 🏗️ Architecture

### Single Node
```
┌─────────────────────────────────────┐
│            Homelab Server           │
├─────────────────────────────────────┤
│ Common → Docker → Portainer → Pi-hole │
└─────────────────────────────────────┘
```

### Multi-Node Swarm
```
┌──────────────────┐    ┌──────────────────┐
│   Manager Node   │    │   Worker Node    │
│  ┌─────────────┐ │    │ ┌─────────────┐  │
│  │ Portainer   │ │    │ │   Agent     │  │
│  │ Pi-hole     │ │────┤ │             │  │
│  │ Services    │ │    │ │ Workloads   │  │
│  └─────────────┘ │    │ └─────────────┘  │
└──────────────────┘    └──────────────────┘
```

## 🔒 Security

- SSH key-based authentication
- Disabled root login
- Docker daemon security
- Service isolation
- Encrypted vault for secrets

## 🧪 Testing

```bash
# Test connectivity
make test

# Validate configuration
make validate-idempotency

# Debug deployment
make debug
```

## 📁 Project Structure

```
├── roles/                    # Ansible roles
│   ├── common/              # Base system configuration
│   ├── docker/              # Docker installation
│   ├── docker_swarm/        # Swarm management
│   ├── portainer/           # Container management
│   └── pihole/              # DNS ad blocker
├── playbooks/               # Example playbooks
│   ├── site.yml            # Main deployment
│   └── examples/           # Usage examples
├── docs/                   # Documentation
├── galaxy.yml              # Collection metadata
└── requirements.yml        # Dependencies
```

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Add tests for new functionality
4. Submit a pull request

## 📄 License

CC0-1.0

## 👤 Author

**thatsmidnight**
- GitHub: [@thatsmidnight](https://github.com/thatsmidnight)
- Email: thatsmidnight@thatsmidnight.com
