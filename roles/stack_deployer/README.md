# Stack Deployer Role

**Abstraction layer for deploying Docker Compose stacks via multiple backends**

This role decouples stack deployment from specific orchestration tools, allowing you to switch between Portainer API, direct Docker CLI, or Kompose with minimal configuration changes.

## Features

- ✅ **Multiple Backends**: Portainer API, direct `docker stack deploy`, Kompose (future)
- ✅ **Backend Switching**: Change deployment method with a single variable
- ✅ **Idempotent**: Safe to re-run, updates existing stacks when needed
- ✅ **Flexible**: Works with templated or inline compose content
- ✅ **Consistent API**: Same role interface regardless of backend

## Supported Backends

### 1. **Portainer** (`stack_deployer_backend: portainer`)
Deploys stacks via Portainer API v2.33.7. Best for:
- Centralized management UI
- Multi-endpoint environments
- RBAC and access control
- Integrated monitoring

**Requirements**: Portainer CE/EE deployed and accessible

### 2. **Direct** (`stack_deployer_backend: direct`) ⭐ Default
Deploys stacks using `docker stack deploy` CLI. Best for:
- Simple deployments
- CI/CD pipelines
- Minimal dependencies
- Direct control

**Requirements**: Docker Swarm initialized, manager node accessible

### 3. **Kompose** (`stack_deployer_backend: kompose`) 🚧 Future
Converts Docker Compose to Kubernetes manifests. Best for:
- Kubernetes migration path
- Hybrid Swarm/K8s environments

**Status**: Placeholder implementation

## Quick Start

### Basic Usage (Direct Backend)

```yaml
- name: Deploy stacks using direct backend
  ansible.builtin.include_role:
    name: stack_deployer
  vars:
    stack_deployer_backend: "direct"
    stack_deployer_swarm_manager: "pi4_01"
    stack_deployer_stacks:
      - name: "pihole-stack"
        compose_template: "templates/pihole-compose.yml.j2"
      - name: "jellyfin-stack"
        compose_template: "templates/jellyfin-compose.yml.j2"
```

### Portainer Backend

```yaml
- name: Deploy stacks via Portainer API
  ansible.builtin.include_role:
    name: stack_deployer
  vars:
    stack_deployer_backend: "portainer"
    stack_deployer_swarm_manager: "pi4_01"
    stack_deployer_portainer_url: "https://192.168.1.10:9443"
    stack_deployer_portainer_admin_password: "{{ vault_portainer_password }}"
    stack_deployer_stacks:
      - name: "pihole-stack"
        compose_template: "templates/pihole-compose.yml.j2"
```

## Role Variables

### Common Variables (All Backends)

| Variable | Default | Description |
|----------|---------|-------------|
| `stack_deployer_backend` | `direct` | Backend to use: `portainer`, `direct`, `kompose` |
| `stack_deployer_swarm_manager` | `pi4_01` | Swarm manager node hostname |
| `stack_deployer_stacks` | `[]` | List of stacks to deploy (see structure below) |
| `stack_deployer_compose_dir` | `/tmp/docker-stacks` | Directory for compose files |

**Stack Structure**:
```yaml
stack_deployer_stacks:
  - name: "stack-name"           # Stack name in Swarm
    compose_template: "path.j2"  # Template path (relative to playbook)
```

### Portainer Backend Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `stack_deployer_portainer_url` | `https://{{ ansible_host }}:9443` | Portainer API URL |
| `stack_deployer_portainer_admin_user` | `admin` | Portainer username |
| `stack_deployer_portainer_admin_password` | Required | Portainer password |
| `stack_deployer_portainer_endpoint_id` | `1` | Swarm endpoint ID |
| `stack_deployer_portainer_validate_certs` | `false` | SSL verification |
| `stack_deployer_portainer_api_timeout` | `60` | API timeout (seconds) |

### Direct Backend Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `stack_deployer_direct_prune` | `false` | Prune old services |
| `stack_deployer_direct_compose_version` | `3.8` | Compose file version |

## Examples

See the `examples/` directory for complete playbooks:

- **basic_direct.yml** - Simple direct deployment
- **portainer_api.yml** - Portainer API deployment
- **backend_switching.yml** - Switch between backends
- **complete_setup.yml** - Full deployment with all options

## Architecture

### Backend Dispatch Flow

```
main.yml
   ├─ Validate backend parameter
   ├─ Create proxy network
   └─ Dispatch to backend:
      ├─ portainer.yml → Portainer API calls
      ├─ direct.yml → docker stack deploy
      └─ kompose.yml → Kubernetes conversion
```

### Portainer Backend Flow

```
portainer.yml
   ├─ Authenticate (POST /api/auth)
   ├─ Verify endpoint (GET /api/endpoints/{id})
   ├─ Get existing stacks (GET /api/stacks)
   ├─ Template compose files
   └─ For each stack:
      ├─ If new: POST /api/stacks/create/swarm/string
      └─ If exists: PUT /api/stacks/{id}
```

## Integration with Homelab-Ansible

This role is designed to replace the `tasks/deploy_stacks.yml` task file:

**Before** (tightly coupled):
```yaml
# tasks/deploy_stacks.yml
- name: Deploy stacks to Docker Swarm
  ansible.builtin.shell:
    cmd: "docker stack deploy -c /tmp/docker-stacks/{{ item.name }}.yml {{ item.name }}"
  loop: "{{ portainer_stacks }}"
```

**After** (abstracted):
```yaml
# tasks/deploy_stacks.yml
- name: Deploy stacks using stack_deployer role
  ansible.builtin.include_role:
    name: stack_deployer
  vars:
    stack_deployer_backend: "{{ deployment_backend | default('direct') }}"
    stack_deployer_stacks: "{{ portainer_stacks }}"
```

## Troubleshooting

### Portainer Backend Issues

**Authentication Failures**:
```bash
# Verify Portainer is accessible
curl -k https://192.168.1.10:9443/api/status

# Test authentication manually
curl -k -X POST https://192.168.1.10:9443/api/auth \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"yourpassword"}'
```

**Stack Already Exists**:
- The role automatically updates existing stacks
- Check Portainer UI to verify stack status
- Use `GET /api/stacks` to see all stacks

### Direct Backend Issues

**Swarm Not Initialized**:
```bash
# Check Swarm status
docker info | grep Swarm

# Initialize if needed
docker swarm init
```

**Network Already Exists**:
- Role creates `proxy-network` if missing
- Uses existing network if already present

## API Reference

### Portainer API Endpoints Used

Based on [Portainer API v2.33.7](https://app.swaggerhub.com/apis-docs/portainer/portainer-ce/2.33.7):

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/auth` | POST | Authenticate and get JWT token |
| `/api/endpoints/{id}` | GET | Verify Swarm endpoint |
| `/api/stacks` | GET | List existing stacks |
| `/api/stacks/create/swarm/string` | POST | Create new stack |
| `/api/stacks/{id}` | PUT | Update existing stack |

## Future Enhancements

- [ ] **Kompose Backend**: Full Kubernetes conversion support
- [ ] **Custom Module**: `portainer_stack` module for better idempotency
- [ ] **Stack Deletion**: Support for removing stacks
- [ ] **Environment Variables**: Direct environment variable injection
- [ ] **Stack Updater**: Automatic update checks and rollback
- [ ] **Health Checks**: Post-deployment verification

## Contributing

When extending this role:

1. Follow the modular task file pattern (one file per backend)
2. Maintain consistent variable naming (`stack_deployer_*`)
3. Ensure idempotency (check before create/update)
4. Add examples for new backends
5. Update this README

## License

MIT

## Author

Homelab-Ansible Project
