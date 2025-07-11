#!/bin/bash
# SSH Troubleshooting Script for Homelab Ansible

echo "🔍 SSH Troubleshooting for Homelab Ansible"
echo "=========================================="

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Check SSH agent
echo -e "${BLUE}1. SSH Agent Status${NC}"
if [ -n "$SSH_AUTH_SOCK" ] && [ -S "$SSH_AUTH_SOCK" ]; then
    echo -e "   Agent: ${GREEN}Running${NC} (Socket: $SSH_AUTH_SOCK)"
    if ssh-add -l >/dev/null 2>&1; then
        echo "   Loaded keys:"
        ssh-add -l | sed 's/^/     /'
    else
        echo -e "   Keys: ${RED}No keys loaded${NC}"
    fi
else
    echo -e "   Agent: ${RED}Not running${NC}"
fi

echo ""

# Check SSH key
echo -e "${BLUE}2. SSH Key Check${NC}"
SSH_KEY="$HOME/.ssh/id_rsa"
if [ -f "$SSH_KEY" ]; then
    echo -e "   Key file: ${GREEN}Found${NC} ($SSH_KEY)"
    echo "   Permissions: $(ls -l $SSH_KEY | awk '{print $1, $3, $4}')"
    
    # Check key format
    if ssh-keygen -l -f "$SSH_KEY" >/dev/null 2>&1; then
        echo -e "   Format: ${GREEN}Valid${NC}"
        ssh-keygen -l -f "$SSH_KEY" | sed 's/^/     /'
    else
        echo -e "   Format: ${RED}Invalid or corrupted${NC}"
    fi
else
    echo -e "   Key file: ${RED}Not found${NC} ($SSH_KEY)"
fi

# Check public key
PUB_KEY="$SSH_KEY.pub"
if [ -f "$PUB_KEY" ]; then
    echo -e "   Public key: ${GREEN}Found${NC}"
else
    echo -e "   Public key: ${YELLOW}Not found${NC} (may need to regenerate)"
fi

echo ""

# Check connectivity to hosts
echo -e "${BLUE}3. Host Connectivity${NC}"
if [ -f "inventory.yml" ]; then
    # Extract host info from inventory
    hosts=$(grep -A1 "hosts:" inventory.yml | grep -E "^\s+\w+:" | awk -F: '{print $1}' | tr -d ' ')
    
    for host in $hosts; do
        if [ "$host" != "hosts" ]; then
            echo -n "   Testing $host... "
            
            # Get host IP from inventory
            host_ip=$(grep -A2 "$host:" inventory.yml | grep "ansible_host:" | awk '{print $2}')
            
            if [ -n "$host_ip" ]; then
                # Test basic connectivity
                if ping -c 1 -W 2 "$host_ip" >/dev/null 2>&1; then
                    echo -n -e "${GREEN}Ping OK${NC} "
                else
                    echo -n -e "${RED}Ping Failed${NC} "
                fi
                
                # Test SSH port
                if timeout 5 bash -c "</dev/tcp/$host_ip/22" >/dev/null 2>&1; then
                    echo -n -e "${GREEN}SSH Port Open${NC} "
                else
                    echo -n -e "${RED}SSH Port Closed${NC} "
                fi
                
                # Test SSH auth (if agent is working)
                if [ -n "$SSH_AUTH_SOCK" ] && ssh-add -l >/dev/null 2>&1; then
                    ssh_user=$(grep -A3 "$host:" inventory.yml | grep "ansible_user:" | awk '{print $2}')
                    if [ -n "$ssh_user" ]; then
                        if timeout 10 ssh -o BatchMode=yes -o ConnectTimeout=5 -o StrictHostKeyChecking=no "$ssh_user@$host_ip" "exit" >/dev/null 2>&1; then
                            echo -e "${GREEN}SSH Auth OK${NC}"
                        else
                            echo -e "${RED}SSH Auth Failed${NC}"
                        fi
                    else
                        echo -e "${YELLOW}No user specified${NC}"
                    fi
                else
                    echo -e "${YELLOW}No SSH agent${NC}"
                fi
            else
                echo -e "${RED}No IP found in inventory${NC}"
            fi
        fi
    done
else
    echo -e "   ${YELLOW}inventory.yml not found${NC}"
fi

echo ""

# Recommendations
echo -e "${BLUE}4. Recommendations${NC}"
if [ ! -n "$SSH_AUTH_SOCK" ] || ! ssh-add -l >/dev/null 2>&1; then
    echo -e "   ${YELLOW}→ Run: ./setup-ssh.sh${NC}"
fi

if [ ! -f "$HOME/.ssh/id_rsa" ]; then
    echo -e "   ${YELLOW}→ Generate SSH key: ssh-keygen -t rsa -b 4096 -C 'your_email@example.com'${NC}"
fi

echo -e "   ${BLUE}→ For manual setup: eval \$(ssh-agent -s) && ssh-add ~/.ssh/id_rsa${NC}"
echo -e "   ${BLUE}→ Test individual host: ssh -v user@host${NC}"
echo -e "   ${BLUE}→ Copy keys to hosts: ssh-copy-id user@host${NC}"

echo ""
echo -e "${GREEN}Run './setup-ssh.sh' to automatically resolve most issues!${NC}"
