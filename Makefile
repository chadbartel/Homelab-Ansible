# Homelab Ansible Makefile
# Convenience commands for managing the homelab deployment

.PHONY: help install setup setup-ssh troubleshoot-ssh deploy deploy-roles destroy debug test lint validate clean

# Default target
help:
	@echo "Homelab Ansible Management"
	@echo "=========================="
	@echo ""
	@echo "Available targets:"
	@echo "  help             - Show this help message"
	@echo "  install          - Install Ansible and dependencies"
	@echo "  setup            - Setup configuration files from examples"
	@echo "  setup-ssh        - Setup SSH agent and load keys"
	@echo "  troubleshoot-ssh - Troubleshoot SSH connectivity issues"
	@echo "  deploy           - Deploy using new role-based structure (main deployment)"
	@echo "  destroy          - 🔥 DESTROY all homelab infrastructure 🔥"
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
	ansible-lint tasks/ main.yml handler.yml || true

# Validate the structure
validate:
	bash bash_scripts/validate.sh

# Clean temporary files
clean:
	@echo "Cleaning temporary files..."
	find . -name "*.retry" -delete
	find . -name "*.pyc" -delete
	find . -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true
