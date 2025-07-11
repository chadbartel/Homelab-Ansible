#!/bin/bash
# SSH Key Management Script for Homelab Ansible
# Automatically manages SSH agent and key loading

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
SSH_KEY_PATH="${SSH_KEY_PATH:-$HOME/.ssh/id_rsa}"
SSH_AGENT_TIMEOUT="${SSH_AGENT_TIMEOUT:-3600}" # 1 hour default

echo -e "${BLUE}🔑 SSH Key Management for Homelab Ansible${NC}"
echo "=========================================="

# Function to check if SSH agent is running
check_ssh_agent() {
    if [ -n "$SSH_AUTH_SOCK" ] && [ -S "$SSH_AUTH_SOCK" ]; then
        if ssh-add -l >/dev/null 2>&1; then
            return 0
        fi
    fi
    return 1
}

# Function to start SSH agent
start_ssh_agent() {
    echo -e "${YELLOW}Starting SSH agent...${NC}"
    eval $(ssh-agent -s)
    
    # Save agent info for future sessions
    echo "export SSH_AUTH_SOCK=$SSH_AUTH_SOCK" > ~/.ssh-agent-info
    echo "export SSH_AGENT_PID=$SSH_AGENT_PID" >> ~/.ssh-agent-info
    
    echo -e "${GREEN}✅ SSH agent started (PID: $SSH_AGENT_PID)${NC}"
}

# Function to load existing agent
load_ssh_agent() {
    if [ -f ~/.ssh-agent-info ]; then
        source ~/.ssh-agent-info
        if check_ssh_agent; then
            echo -e "${GREEN}✅ Using existing SSH agent (PID: $SSH_AGENT_PID)${NC}"
            return 0
        else
            # Clean up stale agent info
            rm -f ~/.ssh-agent-info
        fi
    fi
    return 1
}

# Function to check if key is loaded
is_key_loaded() {
    # Check if any key is loaded (more permissive approach)
    ssh-add -l >/dev/null 2>&1
}

# Function to add SSH key
add_ssh_key() {
    if [ ! -f "$SSH_KEY_PATH" ]; then
        echo -e "${RED}❌ SSH key not found at $SSH_KEY_PATH${NC}"
        echo "Please ensure your SSH key exists or set SSH_KEY_PATH environment variable"
        exit 1
    fi
    
    if is_key_loaded; then
        echo -e "${GREEN}✅ SSH key already loaded${NC}"
        return 0
    fi
    
    echo -e "${YELLOW}Adding SSH key to agent...${NC}"
    
    # Don't clear existing keys - just add ours
    # ssh-add -D >/dev/null 2>&1 || true
    
    # Try to add key with timeout
    if ! ssh-add -t $SSH_AGENT_TIMEOUT "$SSH_KEY_PATH"; then
        echo -e "${RED}❌ Failed to add SSH key${NC}"
        exit 1
    fi
    
    # Verify the key was added
    if ! is_key_loaded; then
        echo -e "${RED}❌ SSH key was not properly loaded${NC}"
        exit 1
    fi
    
    echo -e "${GREEN}✅ SSH key added successfully${NC}"
    
    # Export agent variables for current session
    echo "export SSH_AUTH_SOCK=$SSH_AUTH_SOCK" > ~/.ssh-agent-info
    echo "export SSH_AGENT_PID=$SSH_AGENT_PID" >> ~/.ssh-agent-info
}

# Function to test SSH connectivity
test_ssh_connectivity() {
    echo -e "${BLUE}🔍 Testing SSH connectivity to hosts...${NC}"
    
    # Extract hosts from inventory
    local hosts=()
    if [ -f "inventory.yml" ]; then
        hosts=($(grep -E "ansible_host:" inventory.yml | awk '{print $1}' | grep -v "ansible_host" || true))
    fi
    
    if [ ${#hosts[@]} -eq 0 ]; then
        echo -e "${YELLOW}⚠️  No hosts found in inventory.yml, skipping connectivity test${NC}"
        return 0
    fi
    
    local failed=0
    for host in "${hosts[@]}"; do
        if [ "$host" != "ansible_host:" ]; then
            echo -n "  Testing $host... "
            if ansible "$host" -m ping -o >/dev/null 2>&1; then
                echo -e "${GREEN}✅${NC}"
            else
                echo -e "${RED}❌${NC}"
                failed=$((failed + 1))
            fi
        fi
    done
    
    if [ $failed -eq 0 ]; then
        echo -e "${GREEN}✅ All hosts are reachable${NC}"
    else
        echo -e "${YELLOW}⚠️  $failed host(s) failed connectivity test${NC}"
        echo "This might be normal if hosts are not currently online"
    fi
}

# Function to show SSH agent status
show_status() {
    echo -e "${BLUE}📊 SSH Agent Status${NC}"
    echo "=================="
    
    if check_ssh_agent; then
        echo -e "Agent Status: ${GREEN}Running${NC} (PID: $SSH_AGENT_PID)"
        echo -e "Socket: $SSH_AUTH_SOCK"
        echo ""
        echo "Loaded Keys:"
        ssh-add -l | while read key; do
            echo "  • $key"
        done
    else
        echo -e "Agent Status: ${RED}Not running${NC}"
    fi
}

# Main execution
main() {
    case "${1:-auto}" in
        "status")
            show_status
            ;;
        "test")
            if ! check_ssh_agent; then
                echo -e "${RED}❌ SSH agent not running${NC}"
                exit 1
            fi
            test_ssh_connectivity
            ;;
        "restart")
            echo -e "${YELLOW}Restarting SSH agent...${NC}"
            if [ -n "$SSH_AGENT_PID" ]; then
                kill "$SSH_AGENT_PID" 2>/dev/null || true
            fi
            rm -f ~/.ssh-agent-info
            start_ssh_agent
            add_ssh_key
            ;;
        "auto"|*)
            # Automatic mode - ensure everything is set up
            if ! load_ssh_agent; then
                start_ssh_agent
            fi
            add_ssh_key
            
            # Verify SSH agent is working properly
            echo -e "${BLUE}🔍 Verifying SSH agent configuration...${NC}"
            if ssh-add -l >/dev/null 2>&1; then
                echo -e "${GREEN}✅ SSH agent is properly configured${NC}"
                ssh-add -l | while read key; do
                    echo "  🔑 $key"
                done
            else
                echo -e "${RED}❌ SSH agent verification failed${NC}"
                exit 1
            fi
            
            # Optional connectivity test (can be disabled)
            if [ "${SSH_SKIP_TEST:-}" != "1" ]; then
                test_ssh_connectivity
            fi
            ;;
    esac
}

# Handle script arguments
if [ "$1" = "--help" ] || [ "$1" = "-h" ]; then
    echo "Usage: $0 [auto|status|test|restart]"
    echo ""
    echo "Commands:"
    echo "  auto     - Automatically set up SSH agent and keys (default)"
    echo "  status   - Show SSH agent and key status"
    echo "  test     - Test SSH connectivity to inventory hosts"
    echo "  restart  - Restart SSH agent and reload keys"
    echo ""
    echo "Environment Variables:"
    echo "  SSH_KEY_PATH     - Path to SSH private key (default: ~/.ssh/id_rsa)"
    echo "  SSH_AGENT_TIMEOUT - Key timeout in seconds (default: 3600)"
    echo "  SSH_SKIP_TEST    - Set to '1' to skip connectivity test"
    exit 0
fi

main "$@"

echo -e "${GREEN}🎉 SSH setup complete!${NC}"
