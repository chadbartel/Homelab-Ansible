#!/bin/bash
# Role-based validation script for Homelab Ansible Collection

set -e

echo "🔍 Validating Role-Based Homelab Ansible Project"
echo "=============================================="

# Check core files
required_files=(
    "ansible.cfg"
    "playbooks/site.yml"
    "vars.yml"
    "vault.yml"
    "inventory.yml"
    "requirements.yml"
    "galaxy.yml"
)

for file in "${required_files[@]}"; do
    if [[ -f "$file" ]]; then
        echo "✅ $file exists"
    else
        echo "❌ $file is missing"
        exit 1
    fi
done

# Check role structure
required_roles=("common" "docker" "docker_swarm" "portainer" "pihole")
for role in "${required_roles[@]}"; do
    if [[ -d "roles/$role" ]] && [[ -f "roles/$role/tasks/main.yml" ]]; then
        echo "✅ Role $role properly structured"
    else
        echo "❌ Role $role missing or improperly structured"
        exit 1
    fi
done

# Check for legacy files that shouldn't exist
legacy_items=("tasks/" "templates/" "main.yml" ".ansible/")
for item in "${legacy_items[@]}"; do
    if [[ -e "$item" ]]; then
        echo "⚠️  Legacy item $item still exists (should be removed)"
    else
        echo "✅ Legacy item $item properly removed"
    fi
done

echo "✅ All validations passed!"