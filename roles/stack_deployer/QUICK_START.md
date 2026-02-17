# Stack Deployer Role - Quick Start Guide

Get started with the stack_deployer role in 5 minutes!

## 1. Choose Your Backend

```yaml
# Option A: Direct deployment (simple, no dependencies)
stack_deployer_backend: "direct"

# Option B: Portainer API (centralized management)
stack_deployer_backend: "portainer"
```

## 2. Minimal Configuration

### Direct Backend (Recommended for Getting Started)

```yaml
---
- hosts: servers
  tasks:
    - name: Deploy stacks
      ansible.builtin.include_role:
        name: stack_deployer
      vars:
        stack_deployer_backend: "direct"
        stack_deployer_swarm_manager: "{{ groups['swarm_managers'][0] }}"
        stack_deployer_stacks:
          - name: "my-app"
            compose_template: "templates/my-app.yml.j2"
```

### Portainer Backend

```yaml
---
- hosts: servers
  tasks:
    - name: Deploy stacks via Portainer
      ansible.builtin.include_role:
        name: stack_deployer
      vars:
        stack_deployer_backend: "portainer"
        stack_deployer_portainer_admin_password: "{{ vault_portainer_password }}"
        stack_deployer_stacks:
          - name: "my-app"
            compose_template: "templates/my-app.yml.j2"
```

## 3. Run the Playbook

```bash
# Run deployment
ansible-playbook deploy.yml

# With different backend
ansible-playbook deploy.yml -e "stack_deployer_backend=portainer"
```

## 4. Verify Deployment

```bash
# Check deployed stacks
docker stack ls

# Check services in a stack
docker stack services my-app

# Check service logs
docker service logs my-app_webapp
```

## Common Patterns

### Multiple Stacks

```yaml
stack_deployer_stacks:
  - name: "database-stack"
    compose_template: "templates/postgres.yml.j2"
  - name: "app-stack"
    compose_template: "templates/webapp.yml.j2"
  - name: "monitoring-stack"
    compose_template: "templates/prometheus.yml.j2"
```

### From vars.yml

```yaml
# In your playbook
- include_role:
    name: stack_deployer
  vars:
    stack_deployer_stacks: "{{ portainer_stacks }}"  # Reuse existing var
```

### Switch Backend Based on Environment

```yaml
# In group_vars/production.yml
deployment_backend: "portainer"

# In group_vars/development.yml
deployment_backend: "direct"

# In playbook
- include_role:
    name: stack_deployer
  vars:
    stack_deployer_backend: "{{ deployment_backend }}"
```

## Troubleshooting Quick Checks

### Issue: "Swarm not initialized"
```bash
docker swarm init
```

### Issue: "Portainer authentication failed"
```bash
# Test connection
curl -k https://your-portainer:9443/api/status

# Verify credentials
ansible-vault view vault.yml | grep portainer
```

### Issue: "Template not found"
```bash
# List templates
ls -la templates/

# Check template path in vars
grep compose_template vars.yml
```

## Next Steps

- Read the full [README.md](README.md) for all configuration options
- Check [examples/](examples/) for complete playbooks
- Explore backend-specific features in the README

## Need Help?

1. Check role defaults: `cat roles/stack_deployer/defaults/main.yml`
2. Enable verbose mode: `ansible-playbook -vvv deploy.yml`
3. Review backend task files: `roles/stack_deployer/tasks/*.yml`
