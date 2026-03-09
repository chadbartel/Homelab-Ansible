# Homelab Ansible Collection

A modular Ansible collection for deploying and managing homelab infrastructure with Docker, Docker Swarm, Portainer, and various services. Built with reusable roles following Ansible Galaxy best practices.

## 🏗️ Architecture

This collection provides independent, reusable roles that can be composed to create various homelab deployments:

- **Common**: Base system configuration, user management, SSH hardening
- **Docker**: Docker Engine installation with multi-architecture support
- **Docker Swarm**: Docker Swarm cluster management
- **Portainer**: Container management platform (Swarm or standalone modes)
- **Pi-hole**: DNS ad blocker with custom homelab domain resolution
- **Pi-hole API**: Comprehensive Pi-hole API v6.0 management (80+ endpoints) 🆕

### 🆕 Pi-hole API Role

The `pihole_api` role provides complete management of Pi-hole via its REST API v6.0, including:

- **Rate Limiting Management**: Fix "Client X has been rate-limited" errors
- **Statistics & Metrics**: Query history, top clients, top domains
- **Domain Management**: Whitelist/blocklist with exact or regex matching
- **Client Management**: Per-client configuration and rate limits
- **Configuration**: Full Pi-hole configuration via API
- **Backup & Restore**: Teleporter-based configuration backup/restore

**Quick Fix for Rate Limiting**:

```bash
ansible-playbook roles/pihole_api/examples/rate_limit_fix.yml
```

See [roles/pihole_api/README.md](roles/pihole_api/README.md) for full documentation.

**Incident Report**: [docs/PIHOLE_RATE_LIMIT_INCIDENT.md](docs/PIHOLE_RATE_LIMIT_INCIDENT.md)

## 📁 Structure

```text
homelab-ansible/
├── roles/                      # Reusable Ansible roles
│   ├── common/                 # Base system configuration
│   ├── docker/                 # Docker Engine installation
│   ├── docker_swarm/           # Docker Swarm cluster management
│   ├── portainer/              # Portainer deployment
│   └── pihole/                 # Pi-hole DNS configuration
├── playbooks/                  # Deployment playbooks
│   ├── site.yml                # Main deployment playbook
│   └── examples/               # Example deployment scenarios
│       ├── single-node.yml     # Single-node homelab
│       ├── multi-node-homelab.yml # Multi-node cluster
│       └── minimal-setup.yml   # Minimal Docker + Portainer
├── docs/                       # Documentation
│   └── README.md               # Detailed documentation
├── meta/                       # Collection metadata
│   └── runtime.yml             # Ansible version requirements
├── inventory.yml               # Host inventory and variables
├── galaxy.yml                  # Collection metadata
├── ansible.cfg                 # Ansible configuration
├── debug.yml                   # Debugging playbook
├── vars.example.yml            # Example variables file
├── vault.example.yml           # Example vault file
└── README.md                   # This file
```

## 🔐 SSH Setup (Important!)

Before running any Ansible commands, you need to set up SSH authentication to avoid password prompts:

```bash
# Automatic SSH setup (recommended)
make setup-ssh

# Or it will run automatically with:
make deploy
make debug
make test
```

For troubleshooting SSH issues:

```bash
make troubleshoot-ssh
```

See [SSH-SETUP.md](SSH-SETUP.md) for detailed SSH configuration guide.

## 🚀 Quick Start

### 1. Initial Setup

```bash
# Clone the repository
git clone <repository-url>
cd homelab-ansible

# Copy example files
cp vars.example.yml vars.yml
cp vault.example.yml vault.yml

# Edit variables to match your environment
nano vars.yml

# Create encrypted vault for sensitive data
ansible-vault create vault.yml
# or edit existing vault
ansible-vault edit vault.yml
```

### 2. Update Inventory

Edit `inventory.yml` to match your hosts:

```yaml
all:
  children:
    servers:
      hosts:
        pi4_01:
          ansible_host: 192.168.1.10
          ansible_user: your_user
        server2:
          ansible_host: 192.168.1.11
          ansible_user: your_user
```

### 3. Deploy Infrastructure

```bash
# Deploy the complete homelab infrastructure
make deploy

# Or deploy specific configurations
make deploy-single-node    # Single-node setup
make deploy-minimal        # Docker + Portainer only  
make deploy-multi-node     # Multi-node cluster

# Run specific playbooks directly
ansible-playbook playbooks/site.yml --ask-vault-pass
ansible-playbook playbooks/examples/single-node.yml --ask-vault-pass
```

## 🛠️ Usage

### Deployment Options

```bash
# Main deployment (recommended)
make deploy

# Specific deployment scenarios
make deploy-single-node    # Single server with all services
make deploy-minimal        # Just Docker and Portainer
make deploy-multi-node     # Full cluster deployment

# Debug and maintenance
make debug                 # Run diagnostics
make test                  # Test connectivity
make cleanup-volumes       # Clean unused Docker volumes
```

### Role-Based Deployment

Each role can be used independently or composed with others:

```yaml
# Example: Deploy only Docker and Portainer
- hosts: homelab_servers
  become: yes
  roles:
    - common
    - docker
    - portainer
```

### Debugging

```bash
# Check system status  
make debug

# Test connectivity
make test

# Check Docker status
ansible homelab_servers -m shell -a "docker --version"
```

## 🔐 Security

### Vault Management

```bash
# Create vault
ansible-vault create vault.yml

# Edit vault
ansible-vault edit vault.yml

# Change vault password
ansible-vault rekey vault.yml

# View vault contents
ansible-vault view vault.yml
```

### SSH Configuration

The playbook automatically:

- Disables password authentication
- Disables root login
- Sets up public key authentication
- Hardens SSH configuration

## 📋 Services

### Portainer

- **URL**: `https://your-manager-ip:9443`
- **Purpose**: Docker management interface

### Pi-hole

- **URL**: `http://your-manager-ip:80/admin`
- **Purpose**: Network-wide ad blocking and DNS
- **API Management**: Use `pihole_api` role for programmatic configuration (rate limits, statistics, domain/client management, backup/restore)
- **Quick Fix**: `ansible-playbook roles/pihole_api/examples/rate_limit_fix.yml` for rate limiting issues

### Nginx Proxy Manager

- **URL**: `http://your-manager-ip:8181`
- **Purpose**: Reverse proxy with SSL

### OpenVPN Access Server

- **URL**: `https://your-manager-ip:943`
- **Purpose**: VPN server

## 🔧 Customization

### Adding New Services

1. Create a new template in `templates/`
2. Add service configuration to `vars.yml`
3. Update `portainer_stacks` list in inventory
4. Create specific task file if needed

### Modifying Existing Services

1. Edit the corresponding template in `templates/`
2. Update variables in `vars.yml`
3. Re-run the playbook

## 🐛 Troubleshooting

### Common Issues

1. **Permission Denied**: Ensure SSH keys are properly configured
2. **Docker Installation Fails**: Check internet connectivity and package repositories
3. **Swarm Join Fails**: Verify network connectivity between nodes
4. **Service Won't Start**: Check Docker logs and resource availability
5. **Pi-hole Rate Limiting Errors**: Run `ansible-playbook roles/pihole_api/examples/rate_limit_fix.yml` to increase rate limits or use `identify_rate_limit_source.yml` to find heavy clients

### Useful Commands

```bash
# Check Docker Swarm status
docker node ls

# View service logs
docker service logs <service-name>

# Check container status
docker ps -a

# View Ansible facts
ansible <host> -m setup
```

## 📝 Migration from Old Structure

This refactored structure consolidates the previous role-based layout into a flatter, more maintainable format while preserving all functionality:

- **Old**: Multiple nested roles with complex dependencies
- **New**: Simple task-based structure with clear separation of concerns
- **Benefits**: Easier navigation, reduced complexity, maintained functionality

## 🤝 Contributing

1. Follow the existing code style
2. Test changes thoroughly
3. Update documentation
4. Submit pull requests with clear descriptions

## 📄 License

This project is licensed under the CC0-1.0 License - see the [LICENSE.md](./LICENSE.md) file for details.
