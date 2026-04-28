# Quick Start Guide - Pi-hole Config Role

This guide demonstrates the most common use cases for the pihole_config role.

## Scenario 1: Complete Initial Setup

Run all configuration tasks in sequence:

```bash
ansible-playbook complete_setup.yml
```

## Scenario 2: Update Adlists Only

Add or update block lists without touching DNS or dnsmasq:

```bash
ansible-playbook adlist_management.yml
```

## Scenario 3: Configure Local DNS

Set up custom DNS entries for local services:

```bash
ansible-playbook custom_dns_setup.yml
```

## Scenario 4: Performance Tuning

Apply dnsmasq settings for specific scenarios:

```bash
# High-traffic network
ansible-playbook dnsmasq_tuning.yml --tags high-traffic

# Low-memory device (Raspberry Pi)
ansible-playbook dnsmasq_tuning.yml --tags low-memory

# Privacy-focused
ansible-playbook dnsmasq_tuning.yml --tags privacy

# Performance optimized
ansible-playbook dnsmasq_tuning.yml --tags performance
```

## Scenario 5: Check Mode (Dry Run)

See what would change without applying:

```bash
ansible-playbook complete_setup.yml --check
```

## Scenario 6: Verify Idempotency

Run twice to ensure no unnecessary changes:

```bash
ansible-playbook complete_setup.yml
ansible-playbook complete_setup.yml  # Should show changed=0
```

## Integration with Main Playbook

Add to your main playbook:

```yaml
- name: Deploy and configure Pi-hole
  hosts: localhost
  vars_files:
  - vars.yml
  - vault.yml
  
  tasks:

  # ... deploy Pi-hole stack

  - name: Configure Pi-hole
      import_role:
        name: pihole_config
        tasks_from: "{{ item }}"
      loop:
    - wait_for_service
    - adlists
    - custom_dns
    - dnsmasq
```

## Common Variables (vars.yml)

```yaml
# Pi-hole service configuration
pihole_config_service_name: "pihole-stack_pihole"
pihole_config_swarm_manager: "pi4_01"
pihole_config_target_node: "lenovo_server"

# Adlists
pihole_adlists:
  - url: "https://adaway.org/hosts.txt"
    comment: "AdAway"
    enabled: true

# Custom DNS
pihole_custom_dns:
  - ip: "192.168.1.10"
    hostname: "pihole.local"

# Dnsmasq
pihole_dnsmasq_settings:
  - "dns-forward-max=300"
```

## Troubleshooting

### Container not found

Check if Pi-hole is running:

```bash
docker service ps pihole-stack_pihole
```

### Adlists not updating

Manually run gravity:

```bash
docker exec <container-id> pihole -g
```

### Custom DNS not resolving

Verify DNS was restarted:

```bash
docker exec <container-id> pihole restartdns
```

### Check dnsmasq syntax

View dnsmasq config:

```bash
docker exec <container-id> cat /etc/dnsmasq.d/misc.dnsmasq_lines
```
