#!/bin/bash
# Validation script for flat structure homelab deployment

set -e

echo "🔍 Validating Flat Structure Homelab Ansible Project"
echo "================================================="

# Check core files
required_files=(
    "main.yml"
    "ansible.cfg"
    "vars.yml"
    "vault.yml"
    "inventory.yml"
    "requirements.yml"
    "handlers.yml"
)

for file in "${required_files[@]}"; do
    if [[ -f "$file" ]]; then
        echo "✅ $file exists"
    else
        echo "❌ $file is missing"
        exit 1
    fi
done

# Check directory structure
required_dirs=("tasks" "templates" "bash_scripts")
for dir in "${required_dirs[@]}"; do
    if [[ -d "$dir" ]]; then
        echo "✅ $dir/ directory exists"
    else
        echo "❌ $dir/ directory is missing"
        exit 1
    fi
done

# Check task files
task_files=("initial_setup.yml" "docker.yml" "portainer.yml" "deploy_stacks.yml" "post_setup.yml")
for task in "${task_files[@]}"; do
    if [[ -f "tasks/$task" ]]; then
        echo "✅ tasks/$task exists"
    else
        echo "❌ tasks/$task is missing"
        exit 1
    fi
done

# Check template files
template_files=("pihole-compose.yml.j2" "npm-compose.yml.j2" "heimdall-compose.yml.j2" "openvpn-compose.yml.j2")
for template in "${template_files[@]}"; do
    if [[ -f "templates/$template" ]]; then
        echo "✅ templates/$template exists"
    else
        echo "❌ templates/$template is missing"
        exit 1
    fi
done

echo "✅ All validations passed! Flat structure is ready."