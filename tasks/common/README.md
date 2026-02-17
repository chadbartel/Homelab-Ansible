# Common Tasks Directory

This directory contains reusable task files that are shared across multiple playbooks and roles.

## Dynamic Fact Gathering

### `set_swarm_manager.yml`

**Purpose**: Dynamically determines the Swarm manager node from inventory to decouple playbooks from hardcoded node references.

**Usage**:

```yaml
- name: Initialize dynamic infrastructure facts
  hosts: localhost
  connection: local
  gather_facts: false
  tasks:
    - name: Load dynamic Swarm manager fact
      ansible.builtin.include_tasks: tasks/common/set_swarm_manager.yml
```

**Fact Set**: `swarm_manager_node` - Contains the hostname of the first Swarm manager from the `swarm_managers` inventory group.

**Benefits**:

- No hardcoded `pi4_01` references throughout the project
- Easy infrastructure changes (update inventory only)
- Improved portability across different Swarm clusters
- Centralized manager node definition

**Integration**: Automatically included at the start of `main.yml` playbook with the `always` tag.

## Best Practices

1. **New Common Tasks**: Place reusable, infrastructure-agnostic tasks in this directory
2. **Naming**: Use descriptive names like `set_*.yml` for fact-setting tasks, `wait_for_*.yml` for readiness checks
3. **Documentation**: Document each task file's purpose, variables, and usage in this README
4. **Idempotency**: Ensure all tasks follow Ansible idempotency best practices
5. **Tags**: Use appropriate tags (e.g., `always` for critical fact-setting tasks)

## Planned Future Additions

- `wait_for_swarm_service.yml` - Consolidated service waiting logic (Task 4.1 from REFACTORING_PLAN.md)
- `validate_swarm_status.yml` - Swarm cluster health checks
- `set_dynamic_inventory_facts.yml` - Other dynamic infrastructure facts
