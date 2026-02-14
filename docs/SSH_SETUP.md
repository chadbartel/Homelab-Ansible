# SSH Setup Guide for Homelab Ansible

## 🔑 SSH Authentication Issues Resolved

This setup automatically handles SSH key management to avoid repeated password prompts during Ansible execution.

## 🚀 Quick Start

### Option 1: Automatic Setup (Recommended)

```bash
# This will automatically handle everything:
make deploy
make debug
make test
```

### Option 2: Manual Setup

```bash
# Setup SSH agent and keys manually:
make setup-ssh

# Then run your commands:
ansible-playbook main.yml --ask-vault-pass
```

## 🛠️ How It Works

1. **SSH Agent Management**: Automatically starts and manages SSH agent
2. **Key Loading**: Loads your SSH private key into the agent
3. **Session Persistence**: Saves agent info for reuse across sessions
4. **Connectivity Testing**: Verifies hosts are reachable

## 📁 Files Created

- `setup-ssh.sh` - Main SSH setup script
- `troubleshoot-ssh.sh` - SSH troubleshooting utility
- Updated `ansible.cfg` - Optimized SSH settings
- Updated `Makefile` - Automatic SSH setup integration

## 🔧 Configuration

### Environment Variables

```bash
export SSH_KEY_PATH="$HOME/.ssh/id_rsa"      # Path to your SSH key
export SSH_AGENT_TIMEOUT="3600"             # Key timeout (1 hour)
export SSH_SKIP_TEST="1"                     # Skip connectivity test
```

### Manual SSH Agent Commands

```bash
# Start agent
eval $(ssh-agent -s)

# Add key
ssh-add ~/.ssh/id_rsa

# List loaded keys
ssh-add -l

# Check agent status
./setup-ssh.sh status
```

## 🐛 Troubleshooting

### If You Get Permission Denied Errors

```bash
# Run the troubleshooting script:
make troubleshoot-ssh

# Or manually:
./troubleshoot-ssh.sh
```

### Common Issues

1. **SSH key not found**: Ensure `~/.ssh/id_rsa` exists
2. **Agent not running**: Run `make setup-ssh`
3. **Key not loaded**: Check with `ssh-add -l`
4. **Connectivity issues**: Verify hosts are online and SSH port 22 is open

### Manual Key Generation (if needed)

```bash
ssh-keygen -t rsa -b 4096 -C "your_email@example.com"
```

### Copy Keys to Remote Hosts

```bash
ssh-copy-id username@192.168.1.10
ssh-copy-id username@192.168.1.11
ssh-copy-id username@192.168.1.12
```

## ✅ Verification

Test that everything works:

```bash
# Test SSH setup
make setup-ssh

# Test connectivity
make test

# Troubleshoot issues
make troubleshoot-ssh
```

## 🎯 Benefits

- ✅ **No more password prompts** during Ansible execution
- ✅ **Automatic SSH agent management**
- ✅ **Session persistence** across terminal sessions
- ✅ **Built-in troubleshooting** tools
- ✅ **Optimized SSH settings** for faster connections
- ✅ **Integrated with all Makefile targets**

The setup will now automatically handle SSH authentication before running any Ansible commands, eliminating the need to manually enter your SSH key password multiple times! 🎉
