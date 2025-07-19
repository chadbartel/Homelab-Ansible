# Homelab Ansible Makefile
# Convenience commands for managing the homelab deployment

.PHONY: help install install-docker-sdk deploy deploy-roles deploy-single-node deploy-minimal deploy-multi-node debug clean test lint validate setup-ssh troubleshoot-ssh destroy cleanup-volumes

# Default target
help:
	@echo "Homelab Ansible Management"
	@echo "=========================="
	@echo ""
	@echo "Available targets:"
	@echo "  help             - Show this help message"
	@echo "  install          - Install Ansible and dependencies"
	@echo "  install-docker-sdk - Install Docker SDK on remote hosts"
	@echo "  setup            - Setup configuration files from examples"
	@echo "  setup-ssh        - Setup SSH agent and load keys"
	@echo "  troubleshoot-ssh - Troubleshoot SSH connectivity issues"
	@echo "  deploy           - Deploy using new role-based structure (main deployment)"
	@echo "  deploy-single-node - Deploy single-node homelab"
	@echo "  deploy-minimal   - Deploy minimal setup (Docker + Portainer)"
	@echo "  deploy-multi-node - Deploy multi-node homelab"
	@echo "  destroy          - 🔥 DESTROY all homelab infrastructure 🔥"
	@echo "  cleanup-volumes  - Clean up unused Docker volumes"
	@echo "  debug            - Run debugging playbook"
	@echo "  test             - Test connectivity to all hosts"
	@echo "  lint             - Lint Ansible playbooks"
	@echo "  validate         - Validate the structure of the project"
	@echo "  clean            - Clean up temporary files"

# Install Ansible and dependencies
install:
	@echo "Installing Ansible and dependencies..."
	@if command -v poetry >/dev/null 2>&1; then \
		poetry install --no-root; \
	else \
		echo "Poetry not found, using pip..."; \
		pip3 install --user ansible; \
	fi
	ansible-galaxy collection install -r requirements.yml --force

# Setup SSH agent and load keys
setup-ssh:
	@echo "Setting up SSH agent and keys..."
	./bash_scripts/setup-ssh.sh auto

# Troubleshoot SSH issues
troubleshoot-ssh:
	@echo "Running SSH troubleshooting..."
	./bash_scripts/troubleshoot-ssh.sh

# Install Docker SDK on remote hosts
install-docker-sdk: setup-ssh
	@echo "Installing Docker SDK on remote hosts..."
	./bash_scripts/ansible-wrapper.sh ansible homelab_servers -m ansible.builtin.pip -a "name=docker state=present" --become

# Setup configuration files
setup:
	@echo "Setting up configuration files..."
	@if [ ! -f vars.yml ]; then cp vars.example.yml vars.yml; echo "Created vars.yml from example"; fi
	@if [ ! -f vault.yml ]; then echo "Please create vault.yml: ansible-vault create vault.yml"; fi

# Add back the original deploy target
deploy: setup-ssh
    @echo "Deploying homelab using flat structure..."
    ./bash_scripts/ansible-wrapper.sh ansible-playbook main.yml --ask-vault-pass

# Keep the role-based deployments as alternatives
deploy-roles: setup-ssh
    @echo "Deploying homelab using role-based playbooks..."
    ./bash_scripts/ansible-wrapper.sh ansible-playbook playbooks/site.yml --ask-vault-pass

# Destroy all homelab infrastructure
destroy: setup-ssh
	@echo "🔥 DESTROYING homelab infrastructure..."
	@echo "This will remove ALL containers, volumes, networks, and configuration!"
	@read -p "Are you sure? Type 'yes' to continue: " confirm && [ "$$confirm" = "yes" ] || exit 1
	./bash_scripts/ansible-wrapper.sh ansible-playbook destroy.yml --ask-vault-pass

# Run debug playbook
debug: setup-ssh
	@echo "Running debug checks..."
	./bash_scripts/ansible-wrapper.sh ansible-playbook debug.yml

# Test connectivity
test: setup-ssh
	@echo "Testing connectivity to all hosts..."
	./bash_scripts/ansible-wrapper.sh ansible all -m ping

# Lint playbooks
lint:
	@echo "Linting Ansible playbooks..."
	ansible-lint playbooks/ roles/ || true

# Validate the structure
validate:
	bash bash_scripts/validate.sh

# Clean temporary files
clean:
	@echo "Cleaning temporary files..."
	find . -name "*.retry" -delete
	find . -name "*.pyc" -delete
	find . -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true

# Clean up unused Docker volumes
cleanup-volumes: setup-ssh
	@echo "Cleaning up unused Docker volumes..."
	./bash_scripts/ansible-wrapper.sh ansible-playbook playbooks/site.yml --tags "cleanup" --ask-vault-pass

# Deploy specific configurations
deploy-single-node: setup-ssh
	@echo "Deploying single-node homelab..."
	./bash_scripts/ansible-wrapper.sh ansible-playbook playbooks/examples/single-node.yml --ask-vault-pass

deploy-minimal: setup-ssh
	@echo "Deploying minimal homelab setup..."
	./bash_scripts/ansible-wrapper.sh ansible-playbook playbooks/examples/minimal-setup.yml --ask-vault-pass

deploy-multi-node: setup-ssh
	@echo "Deploying multi-node homelab..."
	./bash_scripts/ansible-wrapper.sh ansible-playbook playbooks/examples/multi-node-homelab.yml --ask-vault-pass
