#!/bin/bash
# Ansible wrapper script that ensures SSH agent environment is properly set

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}🔧 Ansible SSH Wrapper${NC}"

# Source SSH agent info if available
if [ -f ~/.ssh-agent-info ]; then
    source ~/.ssh-agent-info
    echo -e "${GREEN}Loaded SSH agent info: PID=$SSH_AGENT_PID${NC}"
else
    echo -e "${YELLOW}No SSH agent info found, setting up...${NC}"
    ./bash_scripts/setup-ssh.sh auto
    if [ -f ~/.ssh-agent-info ]; then
        source ~/.ssh-agent-info
        echo -e "${GREEN}Reloaded SSH agent info: PID=$SSH_AGENT_PID${NC}"
    fi
fi

# Verify SSH agent is working
if ! ssh-add -l >/dev/null 2>&1; then
    echo -e "${RED}❌ SSH agent not properly configured. Running setup...${NC}"
    ./bash_scripts/setup-ssh.sh auto
    if [ -f ~/.ssh-agent-info ]; then
        source ~/.ssh-agent-info
        echo -e "${GREEN}🔧 Reloaded SSH agent info: PID=$SSH_AGENT_PID${NC}"
    fi
fi

# Final verification
if ssh-add -l >/dev/null 2>&1; then
    echo -e "${GREEN}✅ SSH agent verified, loaded keys:${NC}"
    ssh-add -l | sed 's/^/  🔑 /'
else
    echo -e "${RED}❌ SSH agent verification failed!${NC}"
    exit 1
fi

# Export SSH agent variables explicitly
export SSH_AUTH_SOCK
export SSH_AGENT_PID

echo -e "${BLUE}🚀 Running: $*${NC}"

# Run the ansible command with all passed arguments
exec "$@"
