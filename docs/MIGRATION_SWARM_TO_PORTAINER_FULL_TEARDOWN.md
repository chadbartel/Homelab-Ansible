# Migration: Docker Swarm to Portainer-Only (Full Teardown)

You are an expert in Docker Swarm, Ansible, and Portainer.

## Objective

Migrate the Homelab-Ansible project from Docker Swarm orchestration to Portainer-managed standalone Docker environments by **tearing down all existing services and rebuilding them cleanly**. This is the faster, simpler approach — all services will experience downtime during the migration window. Portainer agents remain in use for multi-node management.

**Expected downtime**: 15–30 minutes for all services.

## Current Architecture

- **3-node cluster**:
  - `pi4_01` (192.168.1.10) — Swarm manager, runs Portainer CE + OpenVPN
  - `lenovo_server` (192.168.1.12, Swarm hostname: `midnight-laptop`) — Swarm worker, runs Pi-hole, NPM, Jellyfin
  - `pi3_01` (192.168.1.11, Swarm hostname: `midnightpi3-02`) — Swarm worker
- **Orchestration**: Docker Swarm with overlay network `proxy-network`
- **Stack deployment**: `docker stack deploy` via Ansible
- **Service discovery**: Swarm service inspect (`docker service ps`) to find containers
- **Networking**: Swarm overlay network (`proxy-network`, subnet `172.20.0.0/16`)
- **Portainer**: Running as a Swarm service (`portainer_portainer`) with Swarm agents (`portainer_agent`) deployed globally
- **Stacks**: `npm-stack`, `pihole-stack`, `vpn-stack`, `jellyfin-stack` (deployed via `docker stack deploy`)

## Target Architecture

- **3-node cluster**: Same physical nodes, same IPs
- **Orchestration**: Portainer CE managing standalone Docker endpoints via Portainer agents
- **Stack deployment**: Portainer API using Docker Compose (standalone, not Swarm stacks)
- **Service discovery**: `docker ps` directly on target node (no Swarm service inspect needed)
- **Networking**: Standard Docker bridge network (`proxy-network`) per node, no overlay
- **Portainer**: Running as a standalone container on `pi4_01` with standalone agents on all nodes

## Pre-Migration: Backup Everything

**This step is mandatory.** Even though volumes are preserved during migration, create backups in case of unexpected issues.

```bash
# From the Ansible control node (lenovo_server)

# 1. Verify all services are running
ssh thatsmidnight@192.168.1.10 "docker service ls"

# 2. Backup Portainer data
ssh thatsmidnight@192.168.1.10 "sudo tar czf /tmp/portainer_data_backup.tar.gz -C /var/lib/docker/volumes portainer_data"

# 3. Backup all service config volumes on lenovo_server
ssh thatsmidnight@192.168.1.12 "sudo tar czf /tmp/pihole_backup.tar.gz -C /var/lib/docker/volumes pihole-stack_pihole_etc pihole-stack_pihole_dnsmasq"
ssh thatsmidnight@192.168.1.12 "sudo tar czf /tmp/npm_backup.tar.gz -C /var/lib/docker/volumes npm-stack_npm_data npm-stack_npm_letsencrypt"
ssh thatsmidnight@192.168.1.12 "sudo tar czf /tmp/jellyfin_backup.tar.gz -C /var/lib/docker/volumes jellyfin-stack_jellyfin_config jellyfin-stack_jellyfin_cache jellyfin-stack_jellyfin_epg"

# 4. Backup OpenVPN config on pi4_01
ssh thatsmidnight@192.168.1.10 "sudo tar czf /tmp/openvpn_backup.tar.gz -C /var/lib/docker/volumes vpn-stack_openvpn_config"

# 5. Record current volume names for mapping later
echo "=== pi4_01 volumes ===" && ssh thatsmidnight@192.168.1.10 "docker volume ls --format '{{.Name}}'"
echo "=== lenovo_server volumes ===" && ssh thatsmidnight@192.168.1.12 "docker volume ls --format '{{.Name}}'"
echo "=== pi3_01 volumes ===" && ssh thatsmidnight@192.168.1.11 "docker volume ls --format '{{.Name}}'"

# 6. Copy backups to Ansible control node for safety
scp thatsmidnight@192.168.1.10:/tmp/portainer_data_backup.tar.gz /tmp/
scp thatsmidnight@192.168.1.10:/tmp/openvpn_backup.tar.gz /tmp/
scp thatsmidnight@192.168.1.12:/tmp/pihole_backup.tar.gz /tmp/
scp thatsmidnight@192.168.1.12:/tmp/npm_backup.tar.gz /tmp/
scp thatsmidnight@192.168.1.12:/tmp/jellyfin_backup.tar.gz /tmp/
```

---

## Phase 1: Tear Down Everything

### Step 1.1: Remove All Swarm Stacks

**On pi4_01 (Swarm manager):**

```bash
ssh thatsmidnight@192.168.1.10 << 'EOF'
  # Remove all stacks
  docker stack rm npm-stack pihole-stack vpn-stack jellyfin-stack

  # Wait for Swarm to fully drain
  echo "Waiting for stack removal..."
  sleep 30

  # Remove Portainer services
  docker service rm portainer_portainer portainer_agent 2>/dev/null || true
  sleep 10

  # Verify all services are gone
  echo "Remaining services:"
  docker service ls
  echo "Remaining stacks:"
  docker stack ls
EOF
```

### Step 1.2: Dismantle Docker Swarm

```bash
# Workers leave first
ssh thatsmidnight@192.168.1.12 "sudo docker swarm leave --force"
ssh thatsmidnight@192.168.1.11 "sudo docker swarm leave --force"

# Manager leaves last
ssh thatsmidnight@192.168.1.10 "sudo docker swarm leave --force"
```

### Step 1.3: Clean Up Swarm Network Artifacts

```bash
for host in 192.168.1.10 192.168.1.12 192.168.1.11; do
  echo "=== Cleaning $host ==="
  ssh thatsmidnight@$host << 'EOF'
    # Remove all stopped containers
    docker container prune -f

    # Remove Swarm overlay networks
    docker network rm ingress docker_gwbridge proxy-network 2>/dev/null || true
    docker network prune -f

    # Verify Swarm is inactive
    echo "Swarm state: $(docker info --format '{{.Swarm.LocalNodeState}}')"
    echo "Networks:"
    docker network ls
    echo "Volumes:"
    docker volume ls
EOF
done
```

**CRITICAL**: Do NOT run `docker volume prune` — this would delete all your service data.

### Step 1.4: Verify Volumes Are Intact

```bash
# On lenovo_server - verify Pi-hole, NPM, Jellyfin volumes exist
ssh thatsmidnight@192.168.1.12 << 'EOF'
  echo "=== Expected volumes on lenovo_server ==="
  docker volume inspect pihole-stack_pihole_etc >/dev/null 2>&1 && echo "✓ pihole_etc" || echo "✗ pihole_etc MISSING"
  docker volume inspect pihole-stack_pihole_dnsmasq >/dev/null 2>&1 && echo "✓ pihole_dnsmasq" || echo "✗ pihole_dnsmasq MISSING"
  docker volume inspect npm-stack_npm_data >/dev/null 2>&1 && echo "✓ npm_data" || echo "✗ npm_data MISSING"
  docker volume inspect npm-stack_npm_letsencrypt >/dev/null 2>&1 && echo "✓ npm_letsencrypt" || echo "✗ npm_letsencrypt MISSING"
  docker volume inspect jellyfin-stack_jellyfin_config >/dev/null 2>&1 && echo "✓ jellyfin_config" || echo "✗ jellyfin_config MISSING"
  docker volume inspect jellyfin-stack_jellyfin_cache >/dev/null 2>&1 && echo "✓ jellyfin_cache" || echo "✗ jellyfin_cache MISSING"
  docker volume inspect jellyfin-stack_jellyfin_epg >/dev/null 2>&1 && echo "✓ jellyfin_epg" || echo "✗ jellyfin_epg MISSING"
EOF

# On pi4_01 - verify OpenVPN and Portainer volumes exist
ssh thatsmidnight@192.168.1.10 << 'EOF'
  echo "=== Expected volumes on pi4_01 ==="
  docker volume inspect vpn-stack_openvpn_config >/dev/null 2>&1 && echo "✓ openvpn_config" || echo "✗ openvpn_config MISSING"
  docker volume inspect portainer_data >/dev/null 2>&1 && echo "✓ portainer_data" || echo "✗ portainer_data MISSING"
EOF
```

If any volume is missing, restore from backup:

```bash
# Example: restore pihole volumes
ssh thatsmidnight@192.168.1.12 "sudo tar xzf /tmp/pihole_backup.tar.gz -C /var/lib/docker/volumes"
```

---

## Phase 2: Update All Ansible Code

### Step 2.1: Update Ansible Inventory

**File: `inventory.yml`**

Replace the entire file:

```yaml
all:
  children:
    servers:
      hosts:
        pi4_01:
          ansible_host: 192.168.1.10
          ansible_user: thatsmidnight
          ansible_python_interpreter: "/usr/bin/python3"
        lenovo_server:
          ansible_host: 192.168.1.12
          ansible_user: thatsmidnight
          ansible_python_interpreter: "/usr/bin/python3"
        pi3_01:
          ansible_host: 192.168.1.11
          ansible_user: thatsmidnight
          ansible_python_interpreter: "/usr/bin/python3"
      vars:
        admin_user: thatsmidnight
        python_version: "3.11"
        python_venv_name: "homelab-ansible"
        python_venv_path: "/opt/homelab-ansible"
        admin_ssh_key_public: "ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABgQCuPsLKnMJQrnRs/QxWjDwJofNGzHhK4FLJOHozWMrGolN7pkSTbNO5iDcOrYrPbmkGGOByf+8+Zr4/uDKHMfQVx5hJjbiYidBF/LMDvDIk8OiCG/F4Ugxw0uTqyoSoOkg5izKBNx78fr6CLKVKjEr2ttmF6jNgf3yycwA/nM5zW2MJ4JJaxE61/sIcXdJ5dbF7imblk0hsr+Xp84OCp3CI2JlIf7L00eS+33Jcd6duVsPT6knAyzWx+ZsroV8gXnX2vK7BIVEWGMPZ3/7v5I4Hy6GcfDDgL+f9PL2xF8JLQMAt3pY+vYGctbFpyVGAZB/YeAzZfVN3ILO39TxVVX4aGxhzrKbZWeqoEBr20X1sx1KCxdyN3zAJQtmSBgO0KCZp/lu7UPOXbXWhKTn+lW8Q7W/kmOUilRtDQsxf00ubfWdwmbf0pum8LB1ZWtbs0t5ijJebIkFH4jFXImhcyqtOZJQssUhV9oFIyVk2B7XZUynaa59eOdFJNn4wyf3V4U8= me@chadbartel.com"

        # Docker Stacks Configuration
        portainer_stacks:
          - name: npm-stack
            compose_template: npm-compose.yml.j2
            target_node: lenovo_server
          - name: pihole-stack
            compose_template: pihole-compose.yml.j2
            target_node: lenovo_server
          - name: vpn-stack
            compose_template: openvpn-compose.yml.j2
            target_node: pi4_01
          - name: jellyfin-stack
            compose_template: jellyfin-compose.yml.j2
            target_node: lenovo_server

    nfs_client_nodes:
      hosts:
        pi4_01:
        pi3_01:

    arm_hosts:
      hosts:
        pi4_01:
        pi3_01:

    x86_hosts:
      hosts:
        lenovo_server:

    # Portainer server node (manages all endpoints)
    portainer_server:
      hosts:
        pi4_01:

    # All nodes that run Portainer agents
    portainer_agents:
      children:
        homelab_servers:

    homelab_servers:
      children:
        arm_hosts:
        x86_hosts:
      vars:
        admin_user: thatsmidnight
```

**Key changes**:

- Removed `manager_nodes` and `worker_nodes` groups entirely
- Added `portainer_server` group (pi4_01 only)
- Added `portainer_agents` group (all nodes)
- Added `target_node` to each stack definition for explicit placement

### Step 2.2: Replace Compose Templates

Delete the existing Swarm-format compose templates and replace them with standalone Docker Compose versions. The key differences:

- Remove `deploy:` section (Swarm-only)
- Remove `version: "3.8"` (deprecated)
- Add `container_name:` for predictable naming
- Add `restart: unless-stopped` (replaces Swarm restart policy)
- Replace overlay networks with bridge networks
- Use `external: true` volumes referencing existing Swarm volume names

**Delete and replace: `templates/pihole-compose.yml.j2`**

```yaml
---
services:
  pihole:
    container_name: pihole
    hostname: {{ pihole_container_name }}
    image: pihole/pihole:2025.11.1
    restart: unless-stopped
    ports:
      - "445:443/tcp"
      - "53:53/tcp"
      - "53:53/udp"
      - "{{ pihole_web_port }}:{{ pihole_dns_port | default(80) }}/tcp"
    environment:
      TZ: '{{ timezone }}'
      FTLCONF_webserver_api_password: '{{ pihole_web_password }}'
      FTLCONF_dns_listeningMode: 'all'
      FTLCONF_dns_revServers: 'true,192.168.1.0/24,192.168.1.1'
      FTLCONF_dns_dnssec: 'false'
      FTLCONF_dns_hosts: |
        {{ manager_node_ip }} {{ pihole_container_name }}.{{ local_domain }}
        {{ manager_node_ip }} {{ portainer_container_name }}.{{ local_domain }}
        {{ manager_node_ip }} {{ nginx_proxy_container_name }}.{{ local_domain }}
        {{ manager_node_ip }} {{ openvpn_container_name }}.{{ local_domain }}
        {{ manager_node_ip }} {{ jellyfin_container_name }}.{{ local_domain }}
      FTLCONF_dhcp_router: '{{ gateway_ip }}'
      FTLCONF_dns_domainNeeded: 'true'
    volumes:
      - pihole_etc:/etc/pihole
      - pihole_dnsmasq:/etc/dnsmasq.d
    cap_add:
      - NET_ADMIN
    networks:
      - proxy-network

volumes:
  pihole_etc:
    external: true
    name: pihole-stack_pihole_etc
  pihole_dnsmasq:
    external: true
    name: pihole-stack_pihole_dnsmasq

networks:
  proxy-network:
    name: proxy-network
    driver: bridge
    ipam:
      config:
        - subnet: "172.20.0.0/16"
          gateway: "172.20.0.1"
```

**Delete and replace: `templates/jellyfin-compose.yml.j2`**

```yaml
---
services:
  jellyfin:
    container_name: jellyfin
    image: {{ jellyfin_image | default('jellyfin/jellyfin:10') }}
    restart: unless-stopped
    user: "1000:1000"
    ports:
      - "{{ jellyfin_host_port }}:8096"
    dns:
      - 192.168.1.10
      - 1.1.1.1
      - 8.8.8.8
    dns_search:
      - local
    volumes:
      - jellyfin_config:/config
      - jellyfin_cache:/cache
      - jellyfin_epg:/epg
      - type: bind
        source: /mnt/ssd_media
        target: /media
        read_only: false
    cap_add:
      - SYS_NICE
    environment:
      JELLYFIN_FFmpeg__probesize: '1G'
      JELLYFIN_FFmpeg__analyzeduration: '3000000'
    networks:
      - proxy-network
    mem_limit: 4g
    mem_reservation: 1g

  epg-updater:
    container_name: epg-updater
    image: {{ jellyfin_epg_image | default('alpine:3.23') }}
    restart: unless-stopped
    volumes:
      - jellyfin_epg:/epg
    environment:
      - TZ={{ timezone | default('America/Los_Angeles') }}
      - EPG_URL={{ jellyfin_epg_url | default('https://epgshare01.online/epgshare01/epg_ripper_US2.xml.gz') }}
    command: >
      sh -c "
      apk add --no-cache curl tzdata &&
      echo '{{ jellyfin_epg_schedule | default("0 1 * * *") }} /epg && curl -fsSL $$EPG_URL -o epg_ripper_US2.xml.gz && gunzip -f epg_ripper_US2.xml.gz && echo \"EPG updated at $$(date)\" >> /epg/update.log' > /etc/crontabs/root &&
      echo \"EPG Updater started - scheduled for 1:00 AM PST daily\" &&
      echo \"Initial download starting...\" &&
      cd /epg && curl -fsSL $$EPG_URL -o epg_ripper_US2.xml.gz && gunzip -f epg_ripper_US2.xml.gz && echo \"Initial EPG downloaded at $$(date)\" > /epg/update.log &&
      crond -f -l 2
      "
    networks:
      - proxy-network
    mem_limit: 64m
    mem_reservation: 16m

volumes:
  jellyfin_config:
    external: true
    name: jellyfin-stack_jellyfin_config
  jellyfin_cache:
    external: true
    name: jellyfin-stack_jellyfin_cache
  jellyfin_epg:
    external: true
    name: jellyfin-stack_jellyfin_epg

networks:
  proxy-network:
    name: proxy-network
    driver: bridge
    ipam:
      config:
        - subnet: "172.20.0.0/16"
          gateway: "172.20.0.1"
```

**Delete and replace: `templates/npm-compose.yml.j2`**

```yaml
---
services:
  npm:
    container_name: npm
    image: jc21/nginx-proxy-manager:2
    restart: unless-stopped
    hostname: {{ nginx_proxy_container_name }}
    ports:
      - "{{ pihole_host_port }}:80"
      - "443:443"
      - "{{ proxy_host_port }}:81"
    environment:
      DB_SQLITE_FILE: "/data/database.sqlite"
      INITIAL_ADMIN_EMAIL: "{{ admin_email }}"
      INITIAL_ADMIN_PASSWORD: "{{ npm_admin_password }}"
      DISABLE_IPV6: 'true'
    volumes:
      - npm_data:/data
      - npm_letsencrypt:/etc/letsencrypt
    networks:
      - proxy-network

volumes:
  npm_data:
    external: true
    name: npm-stack_npm_data
  npm_letsencrypt:
    external: true
    name: npm-stack_npm_letsencrypt

networks:
  proxy-network:
    name: proxy-network
    driver: bridge
    ipam:
      config:
        - subnet: "172.20.0.0/16"
          gateway: "172.20.0.1"
```

**Delete and replace: `templates/openvpn-compose.yml.j2`**

```yaml
---
services:
  openvpn-as:
    container_name: openvpn-as
    image: openvpn/openvpn-as:2.14.3-5936bcd7-Ubuntu24
    restart: unless-stopped
    hostname: {{ openvpn_container_name }}
    cap_add:
      - NET_ADMIN
    devices:
      - /dev/net/tun:/dev/net/tun
    ports:
      - "{{ vpn_host_port }}:943"
      - "1194:1194/udp"
      - "444:443"
    volumes:
      - openvpn_config:/config
    environment:
      TZ: '{{ timezone }}'
      OPENVPN_AS_HOST: '{{ openvpn_hostname }}'
    networks:
      - proxy-network
    sysctls:
      - net.ipv4.ip_forward=1

volumes:
  openvpn_config:
    external: true
    name: vpn-stack_openvpn_config

networks:
  proxy-network:
    name: proxy-network
    driver: bridge
    ipam:
      config:
        - subnet: "172.20.0.0/16"
          gateway: "172.20.0.1"
```

### Step 2.3: Replace `tasks/portainer.yml`

Delete `tasks/portainer.yml` and replace with a standalone version:

**New file: `tasks/portainer.yml`**

```yaml
---
# Portainer standalone deployment with agents on all nodes

# ========================================
# Deploy Portainer Agents on ALL nodes
# ========================================
- name: Deploy Portainer Agent on all nodes
  community.docker.docker_container:
    name: portainer_agent
    image: portainer/agent:lts
    state: started
    restart_policy: always
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock
      - /var/lib/docker/volumes:/var/lib/docker/volumes
    ports:
      - "9001:9001"
    env:
      AGENT_SECRET: "{{ portainer_agent_secret | default('') }}"
  delegate_to: "{{ item }}"
  loop: "{{ groups['portainer_agents'] }}"

# ========================================
# Deploy Portainer CE on the server node
# ========================================
- name: Create Portainer data volume (if not exists)
  community.docker.docker_volume:
    name: portainer_data
    state: present

- name: Deploy Portainer CE as standalone container
  community.docker.docker_container:
    name: portainer
    image: portainer/portainer-ce:lts
    state: started
    restart_policy: always
    ports:
      - "8000:8000"
      - "{{ portainer_host_port }}:{{ portainer_host_port }}"
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock
      - portainer_data:/data
  register: portainer_deployment
  retries: 3
  delay: 30
  until: portainer_deployment is not failed

- name: Wait for Portainer to be ready
  ansible.builtin.wait_for:
    port: "{{ portainer_host_port }}"
    host: "{{ ansible_host }}"
    delay: 10
    timeout: 120

- name: Initialize Portainer admin user
  ansible.builtin.uri:
    url: "https://{{ ansible_host }}:{{ portainer_host_port }}/api/users/admin/init"
    method: POST
    body_format: json
    body:
      username: "admin"
      password: "{{ portainer_admin_password }}"
    validate_certs: false
    status_code: [200, 409]
  register: portainer_init
  retries: 5
  delay: 10

# ========================================
# Register Agent Endpoints in Portainer
# ========================================
- name: Authenticate with Portainer
  ansible.builtin.uri:
    url: "https://{{ ansible_host }}:{{ portainer_host_port }}/api/auth"
    method: POST
    body_format: json
    body:
      username: "admin"
      password: "{{ portainer_admin_password }}"
    validate_certs: false
    status_code: 200
  register: portainer_auth

- name: Get existing endpoints
  ansible.builtin.uri:
    url: "https://{{ ansible_host }}:{{ portainer_host_port }}/api/endpoints"
    method: GET
    headers:
      Authorization: "Bearer {{ portainer_auth.json.jwt }}"
    validate_certs: false
    status_code: 200
  register: existing_endpoints

- name: Build list of existing endpoint names
  ansible.builtin.set_fact:
    existing_endpoint_names: "{{ existing_endpoints.json | map(attribute='Name') | list }}"

- name: Register agent endpoints for each node
  ansible.builtin.uri:
    url: "https://{{ ansible_host }}:{{ portainer_host_port }}/api/endpoints"
    method: POST
    headers:
      Authorization: "Bearer {{ portainer_auth.json.jwt }}"
    body_format: form-urlencoded
    body:
      Name: "{{ item }}"
      EndpointCreationType: "2"
      URL: "tcp://{{ hostvars[item]['ansible_host'] }}:9001"
      GroupID: "1"
      TLS: "true"
      TLSSkipVerify: "true"
      TLSSkipClientVerify: "true"
    validate_certs: false
    status_code: [200, 201, 409]
  loop: "{{ groups['portainer_agents'] }}"
  when: item not in existing_endpoint_names
```

### Step 2.4: Replace `tasks/deploy_stacks.yml`

Delete `tasks/deploy_stacks.yml` and replace:

**New file: `tasks/deploy_stacks.yml`**

```yaml
---
# Deploy Docker Compose stacks via Portainer API (standalone mode)

# ========================================
# Create bridge networks on target nodes
# ========================================
- name: Create proxy-network on nodes that host services
  community.docker.docker_network:
    name: proxy-network
    state: present
    driver: bridge
    ipam_config:
      - subnet: "172.20.0.0/16"
        gateway: "172.20.0.1"
  delegate_to: "{{ item }}"
  loop:
    - lenovo_server
    - pi4_01

# ========================================
# Template compose files
# ========================================
- name: Create temporary directory for stack compose files
  ansible.builtin.file:
    path: /tmp/docker-stacks
    state: directory
    mode: '0755'

- name: Template stack compose files
  ansible.builtin.template:
    src: "{{ item.compose_template }}"
    dest: "/tmp/docker-stacks/{{ item.name }}.yml"
    mode: '0644'
  loop: "{{ portainer_stacks }}"

# ========================================
# Authenticate with Portainer
# ========================================
- name: Authenticate with Portainer
  ansible.builtin.uri:
    url: "https://{{ ansible_host }}:{{ portainer_host_port }}/api/auth"
    method: POST
    body_format: json
    body:
      username: "admin"
      password: "{{ portainer_admin_password }}"
    validate_certs: false
    status_code: 200
  register: portainer_auth

# ========================================
# Get endpoints to resolve target node IDs
# ========================================
- name: Get Portainer endpoints
  ansible.builtin.uri:
    url: "https://{{ ansible_host }}:{{ portainer_host_port }}/api/endpoints"
    method: GET
    headers:
      Authorization: "Bearer {{ portainer_auth.json.jwt }}"
    validate_certs: false
    status_code: 200
  register: portainer_endpoints

- name: Build endpoint ID map
  ansible.builtin.set_fact:
    endpoint_id_map: "{{ endpoint_id_map | default({}) | combine({item.Name: item.Id}) }}"
  loop: "{{ portainer_endpoints.json }}"

# ========================================
# Check existing stacks
# ========================================
- name: Get existing stacks from Portainer
  ansible.builtin.uri:
    url: "https://{{ ansible_host }}:{{ portainer_host_port }}/api/stacks"
    method: GET
    headers:
      Authorization: "Bearer {{ portainer_auth.json.jwt }}"
    validate_certs: false
    status_code: 200
  register: existing_stacks

- name: Build list of existing stack names
  ansible.builtin.set_fact:
    existing_stack_names: "{{ existing_stacks.json | map(attribute='Name') | list }}"

# ========================================
# Read and deploy compose files via Portainer API
# ========================================
- name: Read compose file contents
  ansible.builtin.slurp:
    src: "/tmp/docker-stacks/{{ item.name }}.yml"
  register: compose_contents
  loop: "{{ portainer_stacks }}"

- name: Ensure Jellyfin volumes exist on lenovo_server
  ansible.builtin.shell: |
    docker volume inspect jellyfin-stack_jellyfin_config >/dev/null 2>&1 || docker volume create jellyfin-stack_jellyfin_config
    docker volume inspect jellyfin-stack_jellyfin_cache >/dev/null 2>&1 || docker volume create jellyfin-stack_jellyfin_cache
    docker volume inspect jellyfin-stack_jellyfin_epg >/dev/null 2>&1 || docker volume create jellyfin-stack_jellyfin_epg
  delegate_to: lenovo_server
  register: jellyfin_volume_check
  changed_when: "'jellyfin' in jellyfin_volume_check.stdout"

- name: Deploy stacks via Portainer API
  ansible.builtin.uri:
    url: "https://{{ ansible_host }}:{{ portainer_host_port }}/api/stacks/create/standalone/string?endpointId={{ endpoint_id_map[item.item.target_node | default('lenovo_server')] }}"
    method: POST
    headers:
      Authorization: "Bearer {{ portainer_auth.json.jwt }}"
    body_format: json
    body:
      name: "{{ item.item.name }}"
      stackFileContent: "{{ item.content | b64decode }}"
      env: []
    validate_certs: false
    status_code: [200, 201]
  loop: "{{ compose_contents.results }}"
  when: item.item.name not in existing_stack_names
  register: stack_deployment_result

- name: Display stack deployment results
  ansible.builtin.debug:
    msg: |
      Stack: {{ item.item.item.name }}
      Target Node: {{ item.item.item.target_node | default('lenovo_server') }}
      Status: {{ 'Deployed' if not item.skipped | default(false) else 'Already exists' }}
  loop: "{{ stack_deployment_result.results | default([]) }}"
```

### Step 2.5: Update `main.yml`

Replace the entire file:

**File: `main.yml`**

```yaml
---
# Main playbook for homelab deployment (Standalone Docker + Portainer)

- name: Apply common configuration and install Docker on all servers
  hosts: homelab_servers
  become: true
  vars_files:
    - vars.yml
    - vault.yml
  tasks:
    - name: Run initial setup tasks
      ansible.builtin.include_tasks: tasks/initial_setup.yml
      tags: ["initial", "setup"]

    - name: Install and configure Docker
      ansible.builtin.include_tasks: tasks/docker.yml
      tags: ["docker", "setup"]

    - name: Verify Docker service is running
      ansible.builtin.systemd:
        name: docker
        state: started
        enabled: true
      register: docker_service_status

    - name: Wait for Docker socket to be available
      ansible.builtin.wait_for:
        path: /var/run/docker.sock
        timeout: 30

    - name: Test Docker daemon connectivity
      ansible.builtin.command:
        cmd: docker info
      register: docker_info_test
      changed_when: false
      retries: 3
      delay: 5

    - name: Display Docker status
      ansible.builtin.debug:
        msg: |
          Docker status on {{ inventory_hostname }}:
          Service: {{ 'Running' if docker_service_status.status.ActiveState == 'active' else 'Failed' }}
          Socket: Available
          Daemon: Connected

- name: Prepare SSD media drive on Storage Host (lenovo_server)
  hosts: lenovo_server
  become: true
  tasks:
    - name: Include SSD media drive setup tasks
      ansible.builtin.include_tasks: tasks/ssd_media_drive.yml
      tags: ["ssd-media", "storage"]

- name: Setup NFS server on Storage Host (lenovo_server)
  hosts: lenovo_server
  become: true
  vars_files:
    - vars.yml
    - vault.yml
  tasks:
    - name: Include NFS server tasks
      ansible.builtin.include_tasks: tasks/nfs_server.yml
      tags: ["nfs", "storage"]

- name: Setup NFS clients on other nodes (mount SSD via NFS)
  hosts: nfs_client_nodes
  become: true
  vars_files:
    - vars.yml
    - vault.yml
  tasks:
    - name: Include NFS client tasks
      ansible.builtin.include_tasks: tasks/nfs_client.yml
      tags: ["nfs", "storage"]

- name: Verify NFS mount on worker nodes
  hosts: nfs_client_nodes
  become: true
  vars_files:
    - vars.yml
    - vault.yml
  tasks:
    - name: Check if NFS mount is accessible
      ansible.builtin.command:
        cmd: ls -la {{ nfs_client_mount_path }}
      register: nfs_mount_check
      changed_when: false
      failed_when: nfs_mount_check.rc != 0

    - name: Display NFS mount contents
      ansible.builtin.debug:
        msg: |
          NFS mount verified on {{ inventory_hostname }}!
          Mount point: {{ nfs_client_mount_path }}
          Contents:
          {{ nfs_mount_check.stdout }}

- name: Prepare Jellyfin volume directories on storage host
  hosts: lenovo_server
  become: true
  vars_files:
    - vars.yml
    - vault.yml
  tasks:
    - name: Ensure Jellyfin volume directories exist with correct ownership
      ansible.builtin.file:
        path: "{{ item }}"
        state: directory
        owner: "1000"
        group: "1000"
        mode: "0755"
        recurse: true
      loop:
        - "/var/lib/docker/volumes/jellyfin-stack_jellyfin_config/_data"
        - "/var/lib/docker/volumes/jellyfin-stack_jellyfin_cache/_data"
      tags: ["jellyfin", "volumes", "prepare"]

- name: Deploy Portainer and service stacks
  hosts: portainer_server
  become: true
  vars_files:
    - vars.yml
    - vault.yml
  tasks:
    - name: Deploy Portainer
      ansible.builtin.include_tasks: tasks/portainer.yml
      tags: ["portainer", "deploy"]

    - name: Deploy Docker Compose stacks
      ansible.builtin.include_tasks: tasks/deploy_stacks.yml
      tags: ["stacks", "deploy"]

    - name: Run post-setup configuration
      ansible.builtin.include_tasks: tasks/post_setup.yml
      tags: ["post-setup", "configure"]
```

### Step 2.6: Update vars.yml

**File: `vars.yml`**

Apply these changes:

```yaml
# REMOVE these Swarm-specific variables:
# jellyfin_target_host: "midnight-laptop"           # DELETE
# pihole_target_host: "midnight-laptop"              # DELETE
# jellyfin_config_swarm_manager: "pi4_01"            # DELETE
# pihole_config_swarm_manager: "pi4_01"              # DELETE
# npm_swarm_manager: "pi4_01"                         # DELETE

# UPDATE these service names (Swarm prefixed → container names):
# OLD: jellyfin_config_service_name: "jellyfin-stack_jellyfin"
# NEW:
jellyfin_config_service_name: "jellyfin"

# OLD: pihole_config_service_name: "pihole-stack_pihole"
# NEW:
pihole_config_service_name: "pihole"

# OLD: npm_service_name: "npm-stack_npm"
# NEW:
npm_service_name: "npm"

# KEEP these unchanged:
# jellyfin_config_target_node: "lenovo_server"
# pihole_config_target_node: "lenovo_server"
# npm_target_node: "lenovo_server"

# ADD this comment for clarity:
# Jellyfin hardware acceleration comment update:
jellyfin_enable_hw_accel: false  # Hardware acceleration: set to true if /dev/dri exists on lenovo_server
```

### Step 2.7: Update Configuration Role Defaults

**File: `roles/pihole_config/defaults/main.yml`**

Remove `pihole_config_swarm_manager`. The role no longer needs a Swarm manager — all commands run on `pihole_config_target_node` directly.

```yaml
---
# Default variables for Pi-hole configuration role

# Container discovery configuration (standalone Docker)
pihole_config_service_name: "pihole"
pihole_config_target_node: "lenovo_server"

# Service readiness configuration
pihole_config_web_port: 8081
pihole_config_readiness_retries: 20
pihole_config_readiness_delay: 10
pihole_config_readiness_timeout: 180
pihole_config_ftl_retries: 12
pihole_config_ftl_delay: 10

# ... (keep all other defaults unchanged)
```

**File: `roles/jellyfin_config/defaults/main.yml`**

Remove `jellyfin_config_swarm_manager`:

```yaml
---
# Default variables for Jellyfin configuration role

# Container discovery configuration (standalone Docker)
jellyfin_config_service_name: "jellyfin"
jellyfin_config_target_node: "lenovo_server"

# ... (keep all other defaults unchanged)
```

**File: `roles/nginx_proxy_manager_config/defaults/main.yml`**

Remove `npm_config_swarm_manager`:

```yaml
---
# defaults file for nginx_proxy_manager_config

# NPM container discovery (standalone Docker)
npm_config_service_name: "npm"
npm_config_target_node: "lenovo_server"

# ... (keep all other defaults unchanged)
```

### Step 2.8: Update Container Discovery in All Roles

All three roles need their `discover_container.yml` updated from Swarm service inspection to direct `docker ps`.

**Replace: `roles/pihole_config/tasks/discover_container.yml`**

```yaml
---
# Pi-hole container discovery (standalone Docker)
#
# Discovers the Pi-hole container on the target node using docker ps.
#
# Sets the following facts:
#   - pihole_container_id: Docker container ID (short 12-char format)
#   - pihole_container_name_actual: Actual container name

- name: Get Pi-hole container ID
  ansible.builtin.shell: |
    docker ps --filter "name=pihole" --filter "status=running" --format '{%raw%}{{.ID}}{%endraw%}' | head -n 1
  register: pihole_container_id_result
  changed_when: false
  failed_when: pihole_container_id_result.stdout == ""
  delegate_to: "{{ pihole_config_target_node }}"

- name: Get Pi-hole container name
  ansible.builtin.shell: |
    docker ps --filter "name=pihole" --filter "status=running" --format '{%raw%}{{.Names}}{%endraw%}' | head -n 1
  register: pihole_container_name_result
  changed_when: false
  delegate_to: "{{ pihole_config_target_node }}"

- name: Set Pi-hole container facts
  ansible.builtin.set_fact:
    pihole_container_id: "{{ pihole_container_id_result.stdout }}"
    pihole_container_name_actual: "{{ pihole_container_name_result.stdout }}"
    cacheable: true

- name: Display Pi-hole container information
  ansible.builtin.debug:
    msg: |
      Pi-hole Container Discovery:
      ├─ Container ID: {{ pihole_container_id }}
      └─ Container Name: {{ pihole_container_name_actual }}
  when: pihole_config_display_results | default(true)
```

**Replace: `roles/jellyfin_config/tasks/discover_container.yml`**

```yaml
---
# Jellyfin container discovery (standalone Docker)
#
# Discovers the Jellyfin container on the target node using docker ps.
#
# Sets the following facts:
#   - jellyfin_container_id: Docker container ID (short 12-char format)
#   - jellyfin_container_name_actual: Actual container name

- name: Get Jellyfin container ID
  ansible.builtin.shell: |
    docker ps --filter "name=jellyfin" --filter "status=running" --format '{%raw%}{{.ID}}{%endraw%}' | head -n 1
  register: jellyfin_container_id_result
  changed_when: false
  failed_when: jellyfin_container_id_result.stdout == ""
  delegate_to: "{{ jellyfin_config_target_node }}"

- name: Get Jellyfin container name
  ansible.builtin.shell: |
    docker ps --filter "name=jellyfin" --filter "status=running" --format '{%raw%}{{.Names}}{%endraw%}' | head -n 1
  register: jellyfin_container_name_result
  changed_when: false
  delegate_to: "{{ jellyfin_config_target_node }}"

- name: Set Jellyfin container facts
  ansible.builtin.set_fact:
    jellyfin_container_id: "{{ jellyfin_container_id_result.stdout }}"
    jellyfin_container_name_actual: "{{ jellyfin_container_name_result.stdout }}"
    cacheable: true

- name: Display Jellyfin container information
  ansible.builtin.debug:
    msg: |
      Jellyfin Container Discovery:
      ├─ Container ID: {{ jellyfin_container_id }}
      └─ Container Name: {{ jellyfin_container_name_actual }}
  when: jellyfin_config_display_results | default(true)
```

**Replace: `roles/nginx_proxy_manager_config/tasks/discover_container.yml`**

```yaml
---
# Discover NPM container (standalone Docker)

- name: Get NPM container ID
  ansible.builtin.shell: |
    docker ps --filter "name=npm" --filter "status=running" --format '{%raw%}{{.ID}}{%endraw%}' | head -n 1
  register: npm_container_id_result
  changed_when: false
  failed_when: npm_container_id_result.stdout == ""
  delegate_to: "{{ npm_config_target_node }}"

- name: Set NPM container facts
  ansible.builtin.set_fact:
    npm_container_id: "{{ npm_container_id_result.stdout | trim }}"
    cacheable: true

- name: Display discovered NPM container info
  ansible.builtin.debug:
    msg: |
      NPM Container Discovery:
      - Container ID: {{ npm_container_id }}
      - Target Node: {{ npm_config_target_node }}
```

### Step 2.9: Update Wait-for-Service Tasks

**Replace: `roles/jellyfin_config/tasks/wait_for_service.yml`**

Remove Swarm service verification (`docker service ls`, `docker service ps`):

```yaml
---
# Jellyfin service readiness check (standalone Docker)

- name: Initial wait for Jellyfin service to stabilize
  ansible.builtin.pause:
    seconds: "{{ jellyfin_config_startup_wait }}"
    prompt: "Waiting for Jellyfin to initialize..."
  when: jellyfin_config_display_results | default(true)

- name: Wait for Jellyfin web interface to be accessible
  ansible.builtin.wait_for:
    port: "{{ jellyfin_config_web_port }}"
    host: "{{ target_host | default(ansible_host) }}"
    delay: 10
    timeout: "{{ jellyfin_config_readiness_timeout }}"
    msg: "Jellyfin web interface did not become accessible within {{ jellyfin_config_readiness_timeout }} seconds"

- name: Display web interface ready status
  ansible.builtin.debug:
    msg: "Jellyfin web interface is accessible on port {{ jellyfin_config_web_port }}"
  when: jellyfin_config_display_results | default(true)

- name: Ensure container facts are available
  ansible.builtin.include_tasks: discover_container.yml
  when: jellyfin_container_id is not defined

- name: Check Jellyfin container logs for errors
  ansible.builtin.shell: |
    docker logs --tail 50 {{ jellyfin_container_id }} 2>&1
  register: jellyfin_logs
  changed_when: false
  failed_when: false
  delegate_to: "{{ jellyfin_config_target_node }}"

- name: Validate no fatal errors in logs
  ansible.builtin.assert:
    that:
      - "'readonly database' not in jellyfin_logs.stdout"
    fail_msg: "Jellyfin has fatal errors - check logs"
    success_msg: "No fatal errors detected in Jellyfin logs"
  failed_when: false
  when: jellyfin_config_display_results | default(true)
```

**Replace: `roles/pihole_config/tasks/wait_for_service.yml`**

```yaml
---
# Pi-hole service readiness check (standalone Docker)

- name: Wait for Pi-hole web interface to be accessible
  ansible.builtin.wait_for:
    port: "{{ pihole_config_web_port }}"
    host: "{{ target_host | default(ansible_host) }}"
    delay: 15
    timeout: "{{ pihole_config_readiness_timeout }}"
    msg: "Pi-hole web interface did not become accessible within {{ pihole_config_readiness_timeout }} seconds"

- name: Display web interface ready status
  ansible.builtin.debug:
    msg: "Pi-hole web interface is accessible on port {{ pihole_config_web_port }}"
  when: pihole_config_display_results | default(true)

- name: Ensure container facts are available
  ansible.builtin.include_tasks: discover_container.yml
  when: pihole_container_id is not defined

- name: Wait for Pi-hole FTL to be fully initialized
  ansible.builtin.shell: |
    docker exec {{ pihole_container_id }} pihole status
  register: pihole_status
  until: >
    'Pi-hole blocking is enabled' in pihole_status.stdout or
    'enabled' in pihole_status.stdout
  retries: "{{ pihole_config_ftl_retries }}"
  delay: "{{ pihole_config_ftl_delay }}"
  changed_when: false
  delegate_to: "{{ pihole_config_target_node }}"

- name: Display FTL ready status
  ansible.builtin.debug:
    msg: "Pi-hole FTL service is fully initialized and running"
  when: pihole_config_display_results | default(true)
```

### Step 2.10: Update `tasks/post_setup_openvpn.yml`

Change container discovery from Swarm service name to standalone container name:

```yaml
# In tasks/post_setup_openvpn.yml, change:
#   --filter "name=vpn-stack_openvpn-as"
# To:
#   --filter "name=openvpn-as"
```

### Step 2.11: Update `tasks/post_setup_npm.yml`

Remove Swarm-specific variable references:

```yaml
# Change references from:
#   npm_config_swarm_manager: "{{ npm_swarm_manager | default('pi4_01') }}"
# To: (remove entirely, not needed)

# Change:
#   npm_config_service_name: "{{ npm_service_name | default('npm-stack_npm') }}"
# To:
#   npm_config_service_name: "{{ npm_service_name | default('npm') }}"
```

### Step 2.12: Update `tasks/post_setup_jellyfin.yml`

Remove Swarm-specific references. The file uses `import_role` which inherits the updated role defaults.

### Step 2.13: Update `destroy.yml`

Replace Swarm-specific destruction with standalone container cleanup:

- Remove `docker service ls` / `docker service rm` commands
- Remove `docker stack ls` / `docker stack rm` commands  
- Replace with `docker compose down` and `docker rm -f`
- Remove `docker swarm leave` commands

---

## Phase 3: Deploy Everything Fresh

With Swarm dismantled and all code updated, run the full deployment:

```bash
cd /home/thatsmidnight/projects/Homelab-Ansible

# Validate syntax first
make validate

# Test connectivity
make test

# Full deployment
make deploy
```

This will:

1. Install Docker on all nodes (already installed, idempotent)
2. Setup SSD and NFS (already configured, idempotent)
3. Deploy Portainer CE + agents on all nodes
4. Register all nodes as Portainer agent endpoints
5. Deploy all stacks via Portainer API (using existing volumes with data intact)
6. Run post-setup configuration for all services

---

## Phase 4: Verify Everything

```bash
# 1. Verify Swarm is fully inactive on all nodes
for host in 192.168.1.10 192.168.1.12 192.168.1.11; do
  echo "=== $host ==="
  ssh thatsmidnight@$host "docker info --format '{{.Swarm.LocalNodeState}}'"
  # Must output: "inactive"
done

# 2. Verify all containers are running
echo "=== pi4_01 ===" && ssh thatsmidnight@192.168.1.10 "docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}'"
echo "=== lenovo_server ===" && ssh thatsmidnight@192.168.1.12 "docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}'"

# 3. Verify service functionality
echo "Pi-hole:" && curl -s -o /dev/null -w "%{http_code}" http://192.168.1.12:8081/admin
echo ""
echo "Jellyfin:" && curl -s -o /dev/null -w "%{http_code}" http://192.168.1.12:8096/health
echo ""
echo "NPM:" && curl -s -o /dev/null -w "%{http_code}" http://192.168.1.10:8181
echo ""
echo "Portainer:" && curl -sk -o /dev/null -w "%{http_code}" https://192.168.1.10:9443/api/status
echo ""
echo "OpenVPN:" && curl -sk -o /dev/null -w "%{http_code}" https://192.168.1.10:943

# 4. Verify Portainer endpoints
PORTAINER_TOKEN=$(curl -sk https://192.168.1.10:9443/api/auth \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"YOUR_PASSWORD"}' | python3 -c "import sys,json; print(json.load(sys.stdin)['jwt'])")

curl -sk https://192.168.1.10:9443/api/endpoints \
  -H "Authorization: Bearer $PORTAINER_TOKEN" | python3 -m json.tool

# 5. Verify data survived (spot check)
# Pi-hole should still have configured adlists
curl -s "http://192.168.1.12:8081/admin/api.php?getQuerySources&auth=$(curl -s 'http://192.168.1.12:8081/admin/api.php?auth' | python3 -c 'import sys,json; print(json.load(sys.stdin).get("token",""))')" | head -5

# Jellyfin should still have libraries
curl -s http://192.168.1.12:8096/health

# NPM should still have proxy hosts
echo "NPM proxy hosts check - log into http://192.168.1.10:8181 and verify"

# 6. Verify idempotency
make deploy
# Second run should show minimal/no changes
```

---

## Phase 5: Update Documentation

### Step 5.1: Update `.github/copilot-instructions.md`

Apply these changes throughout the file:

1. **Infrastructure section**: Remove all Swarm terminology
   - Replace "Docker Swarm cluster" → "Portainer-managed Docker environment"
   - Remove "Swarm manager", "Swarm worker" role descriptions
   - Remove hostname mapping (`midnight-laptop` ↔ `lenovo_server`) — no longer relevant

2. **Remove entire sections**:
   - "Docker Swarm Gotchas & Best Practices"
   - "Critical: Container Execution Delegation" (no longer needed — containers run where you expect)
   - "Ansible Hostname vs Swarm Hostname Mismatch"
   - "Swarm Service Status Interpretation"
   - "Managing Duplicate Swarm Nodes"

3. **Update Container Discovery Best Practices**:

   ```yaml
   # Pattern for container discovery (standalone Docker)
   - name: Get container ID
     ansible.builtin.shell: docker ps --filter "name=myservice" --filter "status=running" --format '{{.ID}}' | head -n 1
     delegate_to: "{{ target_node }}"
   ```

4. **Update Stack Deployment description**:
   - Replace "docker stack deploy" → "Portainer API standalone stack deployment"
   - Remove SwarmID references

5. **Update inventory groups**:
   - Remove `manager_nodes`, `worker_nodes`
   - Add `portainer_server`, `portainer_agents`

### Step 5.2: Update Role READMEs

Update README files for `pihole_config`, `jellyfin_config`, and `nginx_proxy_manager_config` to remove Swarm references and document the standalone Docker discovery pattern.

---

## Phase 6: Clean Up Old Files

After everything is verified working, delete the old Swarm-era files:

```bash
# These files are no longer needed if you replaced them in-place (Step 2).
# If you created new files alongside old ones, clean up:

# Deprecated inventory group references should be removed from inventory.yml
# (manager_nodes, worker_nodes)

# Remove any leftover Swarm network artifacts on nodes
for host in 192.168.1.10 192.168.1.12 192.168.1.11; do
  ssh thatsmidnight@$host "docker network prune -f"
done
```

---

## Rollback Plan

If deployment fails after teardown:

1. **Volumes are safe**: They were never deleted. Even after Swarm teardown, volumes persist on disk.
2. **Restore from backup**: If any volume was accidentally deleted:

   ```bash
   ssh thatsmidnight@<host> "sudo tar xzf /tmp/<backup>.tar.gz -C /var/lib/docker/volumes"
   ```

3. **Rebuild Swarm** (emergency fallback):

   ```bash
   # On pi4_01:
   docker swarm init --advertise-addr 192.168.1.10
   # Get join token, then on workers:
   docker swarm join --token <token> 192.168.1.10:2377
   ```

4. **Revert code**: Use git to restore original files:

   ```bash
   git checkout -- inventory.yml main.yml vars.yml tasks/ templates/ roles/
   make deploy
   ```

---

## File Summary: What Changes

| File | Action | Description |
| ------ | -------- | ------------- |
| `inventory.yml` | REPLACE | Remove `manager_nodes`/`worker_nodes`; add `portainer_server`/`portainer_agents` |
| `main.yml` | REPLACE | Remove Swarm init/join plays; use `portainer_server` host group |
| `vars.yml` | MODIFY | Remove `*_swarm_manager`, `*_target_host`; update service names |
| `tasks/portainer.yml` | REPLACE | Standalone Portainer + agent deployment |
| `tasks/deploy_stacks.yml` | REPLACE | Portainer API standalone stack deployment |
| `templates/pihole-compose.yml.j2` | REPLACE | Remove `deploy:`, add `container_name:`, `restart:`, external volumes |
| `templates/jellyfin-compose.yml.j2` | REPLACE | Remove `deploy:`, add `container_name:`, `restart:`, external volumes |
| `templates/npm-compose.yml.j2` | REPLACE | Remove `deploy:`, add `container_name:`, `restart:`, external volumes |
| `templates/openvpn-compose.yml.j2` | REPLACE | Remove `deploy:`, add `container_name:`, `restart:`, external volumes |
| `roles/pihole_config/defaults/main.yml` | MODIFY | Remove `pihole_config_swarm_manager` |
| `roles/pihole_config/tasks/discover_container.yml` | REPLACE | Use `docker ps` instead of Swarm inspect |
| `roles/pihole_config/tasks/wait_for_service.yml` | REPLACE | Remove Swarm service checks |
| `roles/jellyfin_config/defaults/main.yml` | MODIFY | Remove `jellyfin_config_swarm_manager` |
| `roles/jellyfin_config/tasks/discover_container.yml` | REPLACE | Use `docker ps` instead of Swarm inspect |
| `roles/jellyfin_config/tasks/wait_for_service.yml` | REPLACE | Remove Swarm service checks |
| `roles/nginx_proxy_manager_config/defaults/main.yml` | MODIFY | Remove `npm_config_swarm_manager` |
| `roles/nginx_proxy_manager_config/tasks/discover_container.yml` | REPLACE | Use `docker ps` instead of Swarm inspect |
| `tasks/post_setup_openvpn.yml` | MODIFY | Update container filter name |
| `tasks/post_setup_npm.yml` | MODIFY | Remove Swarm manager references |
| `destroy.yml` | MODIFY | Replace Swarm destruction with standalone cleanup |
| `.github/copilot-instructions.md` | MODIFY | Remove all Swarm references, update patterns |

---

## Estimated Timeline

| Phase | Duration | Services Affected |
| ------- | ---------- | ------------------- |
| Pre-Migration Backup | 5 min | None |
| Phase 1: Tear Down | 5 min | **ALL services down** |
| Phase 2: Update Code | 15–30 min | All services still down |
| Phase 3: Deploy Fresh | 5–10 min | Services coming up |
| Phase 4: Verify | 5 min | All services should be up |
| **Total downtime** | **~30–50 min** | |
