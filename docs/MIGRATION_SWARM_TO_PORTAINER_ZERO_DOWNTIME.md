# Migration: Docker Swarm to Portainer-Only (Zero Downtime)

You are an expert in Docker Swarm, Ansible, and Portainer.

## Objective

Migrate the Homelab-Ansible project from Docker Swarm orchestration to Portainer-managed standalone Docker environments **without interrupting any currently running services**. After this migration, Portainer manages all nodes, stacks, and services directly. Portainer agents remain in use for multi-node management.

## Current Architecture

- **3-node cluster**:
  - `pi4_01` (192.168.1.10) — Swarm manager, runs Portainer CE + OpenVPN
  - `lenovo_server` (192.168.1.12, Swarm hostname: `midnight-laptop`) — Swarm worker, runs Pi-hole, NPM, Jellyfin
  - `pi3_01` (192.168.1.11, Swarm hostname: `midnightpi3-02`) — Swarm worker
- **Orchestration**: Docker Swarm with overlay network `proxy-network`
- **Stack deployment**: `docker stack deploy` via Ansible (previously Portainer API, now direct CLI)
- **Service discovery**: Swarm service inspect (`docker service ps`) to find containers
- **Networking**: Swarm overlay network (`proxy-network`, subnet `172.20.0.0/16`)
- **Portainer**: Running as a Swarm service (`portainer_portainer`) with Swarm agents (`portainer_agent`) deployed globally

## Target Architecture

- **3-node cluster**: Same physical nodes, same IPs
- **Orchestration**: Portainer CE managing standalone Docker endpoints via Portainer agents
- **Stack deployment**: Portainer API using Docker Compose (standalone, not Swarm stacks)
- **Service discovery**: `docker ps` directly on target node (no Swarm service inspect needed)
- **Networking**: Standard Docker bridge network (`proxy-network`) on each node, no overlay
- **Portainer**: Running as a standalone container on `pi4_01` with standalone agents on all nodes

## Critical Constraints

- **No service interruption**: Jellyfin, Pi-hole, NPM, OpenVPN must remain accessible throughout
- **Data preservation**: All Docker volumes must be preserved (they survive container recreation)
- **Network connectivity**: DNS (Pi-hole) and VPN (OpenVPN) are critical infrastructure — plan around them
- **NFS mounts**: Remain unchanged (not Swarm-dependent)
- **Ansible inventory hostnames**: Remain unchanged
- **Portainer agent secret**: Reuse existing `vault_portainer_agent_secret`

## Pre-Migration Checklist

Before starting, verify:

```bash
# From the Ansible control node (lenovo_server)
# 1. All nodes reachable
make test

# 2. All Swarm services running
ssh thatsmidnight@192.168.1.10 "docker service ls"

# 3. Portainer accessible
curl -sk https://192.168.1.10:9443/api/status

# 4. Note current volumes on each node
ssh thatsmidnight@192.168.1.10 "docker volume ls"
ssh thatsmidnight@192.168.1.12 "docker volume ls"
ssh thatsmidnight@192.168.1.11 "docker volume ls"

# 5. Backup Portainer data
ssh thatsmidnight@192.168.1.10 "sudo tar czf /tmp/portainer_data_backup.tar.gz /var/lib/docker/volumes/portainer_data"

# 6. Backup all service config volumes
ssh thatsmidnight@192.168.1.12 "sudo tar czf /tmp/pihole_backup.tar.gz /var/lib/docker/volumes/pihole-stack_pihole_etc /var/lib/docker/volumes/pihole-stack_pihole_dnsmasq"
ssh thatsmidnight@192.168.1.12 "sudo tar czf /tmp/npm_backup.tar.gz /var/lib/docker/volumes/npm-stack_npm_data /var/lib/docker/volumes/npm-stack_npm_letsencrypt"
ssh thatsmidnight@192.168.1.12 "sudo tar czf /tmp/jellyfin_backup.tar.gz /var/lib/docker/volumes/jellyfin-stack_jellyfin_config /var/lib/docker/volumes/jellyfin-stack_jellyfin_cache"
ssh thatsmidnight@192.168.1.10 "sudo tar czf /tmp/openvpn_backup.tar.gz /var/lib/docker/volumes/vpn-stack_openvpn_config"
```

---

## Phase 1: Prepare New Portainer Infrastructure (No Impact to Running Services)

### Step 1.1: Update Ansible Inventory

Modify `inventory.yml` to remove Swarm-specific groups and add Portainer-specific groups:

**File: `inventory.yml`**

Replace the `manager_nodes` and `worker_nodes` groups. Remove them entirely and add a `portainer_server` group. Keep `homelab_servers`, `nfs_client_nodes`, `arm_hosts`, `x86_hosts` unchanged.

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
          - name: pihole-stack
            compose_template: pihole-compose.yml.j2
          - name: vpn-stack
            compose_template: openvpn-compose.yml.j2
          - name: jellyfin-stack
            compose_template: jellyfin-compose.yml.j2

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

    # Portainer server node (replaces manager_nodes)
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

**Important**: Do NOT remove `manager_nodes` and `worker_nodes` yet. Keep them temporarily with a comment `# DEPRECATED - remove after migration` so existing playbook doesn't break during transition.

### Step 1.2: Create Standalone Compose Templates

Create new compose templates that use standard Docker Compose (no `deploy:` section, no overlay networks). These will live alongside the existing Swarm templates until cutover.

**File: `templates/standalone/pihole-compose.yml.j2`**

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
  pihole_dnsmasq:

networks:
  proxy-network:
    name: proxy-network
    driver: bridge
    ipam:
      config:
        - subnet: "172.20.0.0/16"
          gateway: "172.20.0.1"
```

**File: `templates/standalone/jellyfin-compose.yml.j2`**

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
    deploy:
      resources:
        limits:
          memory: 4G
        reservations:
          memory: 1G

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

volumes:
  jellyfin_config:
    driver: local
  jellyfin_cache:
    driver: local
  jellyfin_epg:
    driver: local

networks:
  proxy-network:
    name: proxy-network
    driver: bridge
    ipam:
      config:
        - subnet: "172.20.0.0/16"
          gateway: "172.20.0.1"
```

**File: `templates/standalone/npm-compose.yml.j2`**

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
  npm_letsencrypt:

networks:
  proxy-network:
    name: proxy-network
    driver: bridge
    ipam:
      config:
        - subnet: "172.20.0.0/16"
          gateway: "172.20.0.1"
```

**File: `templates/standalone/openvpn-compose.yml.j2`**

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
    driver: local

networks:
  proxy-network:
    name: proxy-network
    driver: bridge
    ipam:
      config:
        - subnet: "172.20.0.0/16"
          gateway: "172.20.0.1"
```

### Step 1.3: Create Standalone Portainer Deployment Task

**File: `tasks/portainer_standalone.yml`**

This replaces `tasks/portainer.yml`. It deploys Portainer as a standalone container (not a Swarm service) with agents on all nodes.

```yaml
---
# Portainer standalone deployment tasks (replaces Swarm-based portainer.yml)

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
- name: Create Portainer data volume
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
# Register Portainer Agent Endpoints
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
  when: item not in (existing_endpoints.json | map(attribute='Name') | list)
```

### Step 1.4: Create Standalone Stack Deployment Task

**File: `tasks/deploy_stacks_standalone.yml`**

This replaces `tasks/deploy_stacks.yml`. It deploys stacks via Portainer API to specific endpoints instead of using `docker stack deploy`.

```yaml
---
# Deploy Docker Compose stacks via Portainer API (standalone mode)

- name: Create proxy-network on target nodes
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

- name: Create temporary directory for stack compose files
  ansible.builtin.file:
    path: /tmp/docker-stacks
    state: directory
    mode: '0755'
  delegate_to: localhost
  become: false

- name: Template standalone stack compose files
  ansible.builtin.template:
    src: "standalone/{{ item.compose_template }}"
    dest: "/tmp/docker-stacks/{{ item.name }}.yml"
    mode: '0644'
  loop: "{{ portainer_stacks }}"
  delegate_to: localhost
  become: false

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

- name: Get Portainer endpoints
  ansible.builtin.uri:
    url: "https://{{ ansible_host }}:{{ portainer_host_port }}/api/endpoints"
    method: GET
    headers:
      Authorization: "Bearer {{ portainer_auth.json.jwt }}"
    validate_certs: false
    status_code: 200
  register: portainer_endpoints

- name: Map stack to target endpoint
  ansible.builtin.set_fact:
    stack_endpoint_map:
      npm-stack: "lenovo_server"
      pihole-stack: "lenovo_server"
      vpn-stack: "pi4_01"
      jellyfin-stack: "lenovo_server"

- name: Resolve endpoint IDs
  ansible.builtin.set_fact:
    endpoint_id_map: "{{ endpoint_id_map | default({}) | combine({item.Name: item.Id}) }}"
  loop: "{{ portainer_endpoints.json }}"

- name: Read compose file contents
  ansible.builtin.slurp:
    src: "/tmp/docker-stacks/{{ item.name }}.yml"
  register: compose_contents
  loop: "{{ portainer_stacks }}"
  delegate_to: localhost
  become: false

- name: Get existing stacks from Portainer
  ansible.builtin.uri:
    url: "https://{{ ansible_host }}:{{ portainer_host_port }}/api/stacks"
    method: GET
    headers:
      Authorization: "Bearer {{ portainer_auth.json.jwt }}"
    validate_certs: false
    status_code: 200
  register: existing_stacks

- name: Deploy stacks via Portainer API (standalone compose)
  ansible.builtin.uri:
    url: "https://{{ ansible_host }}:{{ portainer_host_port }}/api/stacks/create/standalone/string"
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
    url_username: ""
    url_password: ""
  loop: "{{ compose_contents.results }}"
  vars:
    target_node: "{{ stack_endpoint_map[item.item.name] }}"
    target_endpoint_id: "{{ endpoint_id_map[target_node] }}"
  when: item.item.name not in (existing_stacks.json | map(attribute='Name') | list)
  register: stack_deployment_result

- name: Display stack deployment results
  ansible.builtin.debug:
    msg: |
      Stack: {{ item.item.item.name }}
      Target Node: {{ stack_endpoint_map[item.item.item.name] }}
      Status: {{ 'Deployed' if item.changed | default(false) else 'Already exists' }}
  loop: "{{ stack_deployment_result.results | default([]) }}"
  when: item is not skipped
```

### Step 1.5: Ensure Jellyfin Volumes on Target Node

Create the standalone equivalent:

**File: `tasks/prepare_jellyfin_volumes.yml`**

```yaml
---
# Prepare Jellyfin volume directories on the target node
- name: Ensure Jellyfin volumes exist
  ansible.builtin.shell: |
    docker volume inspect jellyfin_config >/dev/null 2>&1 || docker volume create jellyfin_config
    docker volume inspect jellyfin_cache >/dev/null 2>&1 || docker volume create jellyfin_cache
    docker volume inspect jellyfin_epg >/dev/null 2>&1 || docker volume create jellyfin_epg
  register: jellyfin_volume_check
  changed_when: "'jellyfin' in jellyfin_volume_check.stdout"

- name: Ensure Jellyfin volume directories have correct ownership
  ansible.builtin.file:
    path: "{{ item }}"
    state: directory
    owner: "1000"
    group: "1000"
    mode: "0755"
    recurse: true
  loop:
    - "/var/lib/docker/volumes/jellyfin_config/_data"
    - "/var/lib/docker/volumes/jellyfin_cache/_data"
```

---

## Phase 2: Update Configuration Roles (No Impact to Running Services)

All role updates happen in code only — they aren't applied until the new playbook runs.

### Step 2.1: Update Container Discovery for All Roles

Each role's `discover_container.yml` must change from Swarm service inspection to direct `docker ps` on the target node.

**Replace: `roles/pihole_config/tasks/discover_container.yml`**

```yaml
---
# Pi-hole container discovery task (standalone Docker)
#
# Discovers the Pi-hole container on the target node using docker ps.
# No Swarm service inspection required.
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
# Jellyfin container discovery task (standalone Docker)
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

### Step 2.2: Update Role Defaults

Remove `_swarm_manager` variables from all role defaults since they're no longer needed.

**Update: `roles/pihole_config/defaults/main.yml`**

Remove `pihole_config_swarm_manager` variable. The `pihole_config_target_node` is sufficient since `docker ps` runs directly on the target.

**Update: `roles/jellyfin_config/defaults/main.yml`**

Remove `jellyfin_config_swarm_manager` variable. Remove Swarm service verification from `wait_for_service.yml`.

**Update: `roles/nginx_proxy_manager_config/defaults/main.yml`**

Remove `npm_config_swarm_manager` variable.

### Step 2.3: Update Wait-for-Service Tasks

**Replace: `roles/jellyfin_config/tasks/wait_for_service.yml`**

Remove Swarm-specific service verification. Keep port wait and log checks.

```yaml
---
# Jellyfin service readiness check task (standalone Docker)

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
# Pi-hole service readiness check task (standalone Docker)

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

### Step 2.4: Update vars.yml

**File: `vars.yml`**

Remove Swarm-specific variables:

```yaml
# REMOVE these lines:
# jellyfin_target_host: "midnight-laptop"
# pihole_target_host: "midnight-laptop"
# jellyfin_config_swarm_manager: "pi4_01"
# pihole_config_swarm_manager: "pi4_01"
# npm_swarm_manager: "pi4_01"

# KEEP these (they reference Ansible inventory hostnames, which are correct):
# jellyfin_config_target_node: "lenovo_server"
# pihole_config_target_node: "lenovo_server"
# npm_target_node: "lenovo_server"

# KEEP these (Swarm service names become container names — update to match):
# jellyfin_config_service_name: "jellyfin"  # Was "jellyfin-stack_jellyfin"
# pihole_config_service_name: "pihole"      # Was "pihole-stack_pihole"
# npm_service_name: "npm"                    # Was "npm-stack_npm"
```

### Step 2.5: Update post_setup_openvpn.yml

Replace Swarm container discovery with direct `docker ps`:

```yaml
# Replace this:
- name: Get OpenVPN container ID from Swarm service
  ansible.builtin.shell: |
    docker ps --filter "name=vpn-stack_openvpn-as" --format '{% raw %}{{.ID}}{% endraw %}' | head -n 1

# With this:
- name: Get OpenVPN container ID
  ansible.builtin.shell: |
    docker ps --filter "name=openvpn-as" --filter "status=running" --format '{% raw %}{{.ID}}{% endraw %}' | head -n 1
```

---

## Phase 3: Migrate Services Node by Node (Zero Downtime)

This is the critical phase. Services are migrated one at a time, per node. The key insight is:

1. **Docker volumes persist** when you remove Swarm stacks — data is not lost
2. **Services are recreated** as standalone containers using the same volumes
3. **Only one service is down at a time**, and only for seconds (container restart time)

### Step 3.1: Migrate lenovo_server Services (Pi-hole, NPM, Jellyfin)

These services run on `lenovo_server` (192.168.1.12). They are constrained to this node via Swarm placement, so their volumes are local.

**Execution order matters**: NPM first (least critical), then Jellyfin, then Pi-hole last (DNS is most critical).

**On the Swarm manager node (`pi4_01`):**

```bash
# 1. Remove NPM from Swarm (the Swarm service, not the container data)
ssh thatsmidnight@192.168.1.10 "docker service rm npm-stack_npm 2>/dev/null; docker stack rm npm-stack 2>/dev/null"

# Wait for Swarm to clean up
sleep 10
```

**On `lenovo_server` (192.168.1.12):**

```bash
# 2. Verify volumes survived
ssh thatsmidnight@192.168.1.12 "docker volume ls | grep npm"
# Should show: npm-stack_npm_data, npm-stack_npm_letsencrypt

# 3. Create the proxy-network as a bridge network (if it doesn't exist)
ssh thatsmidnight@192.168.1.12 "docker network create --driver bridge --subnet 172.20.0.0/16 --gateway 172.20.0.1 proxy-network 2>/dev/null || true"

# 4. Deploy NPM as standalone using the templated compose
# (Template the compose file first via Ansible, then deploy)
```

Use Ansible to template and deploy:

```bash
cd /home/thatsmidnight/projects/Homelab-Ansible
ansible-playbook -i inventory.yml --vault-password-file=.vault_pass -e @vars.yml -e @vault.yml \
  -e "target_host=lenovo_server" \
  migrate_npm.yml
```

Create a migration playbook for each service (or one combined one). The volumes from Swarm stacks are named `<stack-name>_<volume-name>` (e.g., `npm-stack_npm_data`). The standalone compose uses just `<project>_<volume>` (e.g., `npm-stack_npm_data` if the project name matches, or `npm_data` if not).

**CRITICAL VOLUME MAPPING**: To preserve data, either:

- Set `container_name` in the new compose AND use the same project name (`npm-stack`), OR
- Use explicit `external: true` volumes referencing the old Swarm volume names

The safest approach is to use **external volumes** in the standalone compose:

Update the standalone NPM compose to reference existing volumes:

```yaml
volumes:
  npm_data:
    external: true
    name: npm-stack_npm_data
  npm_letsencrypt:
    external: true
    name: npm-stack_npm_letsencrypt
```

Apply this same pattern to all standalone compose templates.

**Repeat for Jellyfin:**

```bash
# Remove Jellyfin from Swarm
ssh thatsmidnight@192.168.1.10 "docker service rm jellyfin-stack_jellyfin jellyfin-stack_epg-updater 2>/dev/null; docker stack rm jellyfin-stack 2>/dev/null"
sleep 10

# Verify volumes
ssh thatsmidnight@192.168.1.12 "docker volume ls | grep jellyfin"

# Deploy standalone Jellyfin (via Ansible or docker compose)
```

**Repeat for Pi-hole (last, because DNS):**

```bash
# Remove Pi-hole from Swarm
ssh thatsmidnight@192.168.1.10 "docker service rm pihole-stack_pihole 2>/dev/null; docker stack rm pihole-stack 2>/dev/null"
sleep 5

# IMMEDIATELY deploy standalone Pi-hole to minimize DNS downtime
# (have the compose ready on lenovo_server beforehand)
ssh thatsmidnight@192.168.1.12 "cd /tmp/docker-stacks && docker compose -f pihole-stack.yml -p pihole-stack up -d"
```

### Step 3.2: Migrate pi4_01 Services (OpenVPN, Portainer)

**OpenVPN:**

```bash
# Remove OpenVPN from Swarm
ssh thatsmidnight@192.168.1.10 "docker service rm vpn-stack_openvpn-as 2>/dev/null; docker stack rm vpn-stack 2>/dev/null"
sleep 10

# Create proxy-network on pi4_01
ssh thatsmidnight@192.168.1.10 "docker network create --driver bridge --subnet 172.20.0.0/16 --gateway 172.20.0.1 proxy-network 2>/dev/null || true"

# Deploy standalone OpenVPN
ssh thatsmidnight@192.168.1.10 "cd /tmp/docker-stacks && docker compose -f vpn-stack.yml -p vpn-stack up -d"
```

**Portainer** (migrate last — it's managing the migration):

```bash
# 1. Stop the Swarm Portainer service and agent
ssh thatsmidnight@192.168.1.10 "docker service rm portainer_portainer portainer_agent 2>/dev/null"
sleep 10

# 2. Deploy standalone Portainer + agents (via the Ansible task from Step 1.3)
ansible-playbook -i inventory.yml --vault-password-file=.vault_pass -e @vars.yml -e @vault.yml \
  migrate_portainer.yml
```

### Step 3.3: Dismantle Docker Swarm

Once all services are running as standalone containers:

```bash
# On worker nodes first
ssh thatsmidnight@192.168.1.12 "sudo docker swarm leave --force"
ssh thatsmidnight@192.168.1.11 "sudo docker swarm leave --force"

# On manager node last
ssh thatsmidnight@192.168.1.10 "sudo docker swarm leave --force"
```

### Step 3.4: Clean Up Swarm Artifacts

```bash
# On all nodes - remove orphaned overlay networks
for host in 192.168.1.10 192.168.1.12 192.168.1.11; do
  ssh thatsmidnight@$host "docker network prune -f"
done

# Remove ingress network remnants (if any)
for host in 192.168.1.10 192.168.1.12 192.168.1.11; do
  ssh thatsmidnight@$host "docker network rm ingress docker_gwbridge 2>/dev/null || true"
done
```

---

## Phase 4: Update main.yml Playbook

**File: `main.yml`**

Replace the entire playbook with the standalone version. Key changes:

1. **Remove**: "Setup Docker Swarm cluster" play (Swarm init)
2. **Remove**: "Join worker nodes to Swarm" play
3. **Replace**: "Deploy Portainer and stacks to the manager node" with standalone deployment
4. **Update**: Jellyfin volume prep to use standalone paths

The new main.yml should have these plays in order:

```yaml
---
# Main playbook for homelab deployment (Standalone Docker + Portainer)

# Play 1: Common setup + Docker install (UNCHANGED)
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

# Play 2: SSD media drive (UNCHANGED)
- name: Prepare SSD media drive on Storage Host (lenovo_server)
  hosts: lenovo_server
  become: true
  tasks:
    - name: Include SSD media drive setup tasks
      ansible.builtin.include_tasks: tasks/ssd_media_drive.yml
      tags: ["ssd-media", "storage"]

# Play 3: NFS server (UNCHANGED)
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

# Play 4: NFS clients (UNCHANGED)
- name: Setup NFS clients on other nodes
  hosts: nfs_client_nodes
  become: true
  vars_files:
    - vars.yml
    - vault.yml
  tasks:
    - name: Include NFS client tasks
      ansible.builtin.include_tasks: tasks/nfs_client.yml
      tags: ["nfs", "storage"]

# Play 5: Prepare Jellyfin volumes (UPDATED - no Swarm volume prefix)
- name: Prepare Jellyfin volume directories on worker node
  hosts: lenovo_server
  become: true
  vars_files:
    - vars.yml
    - vault.yml
  tasks:
    - name: Include Jellyfin volume preparation
      ansible.builtin.include_tasks: tasks/prepare_jellyfin_volumes.yml
      tags: ["jellyfin", "volumes", "prepare"]

# Play 6: Deploy Portainer + Agents (NEW - replaces Swarm setup + Portainer)
- name: Deploy Portainer and agents
  hosts: portainer_server
  become: true
  vars_files:
    - vars.yml
    - vault.yml
  tasks:
    - name: Deploy Portainer standalone
      ansible.builtin.include_tasks: tasks/portainer_standalone.yml
      tags: ["portainer", "deploy"]

# Play 7: Deploy stacks via Portainer API (NEW - replaces docker stack deploy)
- name: Deploy service stacks
  hosts: portainer_server
  become: true
  vars_files:
    - vars.yml
    - vault.yml
  tasks:
    - name: Deploy Docker Compose stacks via Portainer
      ansible.builtin.include_tasks: tasks/deploy_stacks_standalone.yml
      tags: ["stacks", "deploy"]
    - name: Run post-setup configuration
      ansible.builtin.include_tasks: tasks/post_setup.yml
      tags: ["post-setup", "configure"]
```

---

## Phase 5: Update destroy.yml

Update `destroy.yml` to remove Swarm-specific destruction commands. Replace `docker service rm`, `docker stack rm` with `docker compose down` and `docker rm -f` for standalone containers.

---

## Phase 6: Update vars.yml Final Cleanup

Remove all Swarm-related variables:

```yaml
# REMOVE:
jellyfin_target_host: "midnight-laptop"       # No longer needed (no placement constraints)
pihole_target_host: "midnight-laptop"          # No longer needed
jellyfin_config_swarm_manager: "pi4_01"        # No Swarm manager concept
pihole_config_swarm_manager: "pi4_01"          # No Swarm manager concept
npm_swarm_manager: "pi4_01"                    # No Swarm manager concept
jellyfin_config_service_name: "jellyfin-stack_jellyfin"  # Update to container name

# UPDATE service names to container names:
jellyfin_config_service_name: "jellyfin"       # Simple container name
pihole_config_service_name: "pihole"           # Simple container name
npm_service_name: "npm"                        # Simple container name
```

---

## Phase 7: Update copilot-instructions.md

Update `.github/copilot-instructions.md` to reflect the new architecture:

1. Remove all references to Docker Swarm
2. Remove "Ansible hostname vs Swarm hostname" section
3. Remove Swarm-specific gotchas
4. Update container discovery patterns to use `docker ps`
5. Update deployment description to reference Portainer API
6. Remove `manager_nodes` and `worker_nodes` group references
7. Add `portainer_server` and `portainer_agents` group documentation

---

## Phase 8: Validation

After all changes are complete:

```bash
# 1. Validate Ansible syntax
make validate

# 2. Test SSH connectivity
make test

# 3. Verify all services are running
ssh thatsmidnight@192.168.1.12 "docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}'"
ssh thatsmidnight@192.168.1.10 "docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}'"

# 4. Verify service functionality
curl -s http://192.168.1.12:8081/admin | head -5    # Pi-hole
curl -s http://192.168.1.12:8096/health              # Jellyfin
curl -sk https://192.168.1.10:9443/api/status         # Portainer
curl -s http://192.168.1.10:8181                      # NPM

# 5. Verify Portainer sees all endpoints
curl -sk https://192.168.1.10:9443/api/endpoints \
  -H "Authorization: Bearer <token>" | python3 -m json.tool

# 6. Verify Swarm is fully dismantled
for host in 192.168.1.10 192.168.1.12 192.168.1.11; do
  echo "=== $host ==="
  ssh thatsmidnight@$host "docker info --format '{{.Swarm.LocalNodeState}}'"
  # Should output: "inactive"
done

# 7. Run full deployment to verify idempotency
make deploy
# Second run should show minimal changes
make deploy
```

---

## Rollback Plan

If anything goes wrong during migration:

1. **Services still in Swarm**: If you haven't left Swarm yet, the old services can be redeployed with `docker stack deploy`
2. **Volumes**: Docker volumes are never deleted during this process — data is always safe
3. **Portainer data**: Restore from backup taken in pre-migration checklist
4. **Rejoin Swarm**: If needed, reinitialize Swarm on pi4_01 and rejoin workers
5. **Revert code**: All code changes are in separate files (standalone templates, new task files) — the originals remain until explicitly deleted in the final cleanup phase

---

## File Summary: What Changes

| File | Action | Description |
| ------ | -------- | ------------- |
| `inventory.yml` | MODIFY | Add `portainer_server`, `portainer_agents` groups; deprecate `manager_nodes`, `worker_nodes` |
| `main.yml` | MODIFY | Remove Swarm init/join plays; add Portainer standalone plays |
| `vars.yml` | MODIFY | Remove `*_swarm_manager`, `*_target_host` vars; update service names |
| `destroy.yml` | MODIFY | Replace Swarm destruction with standalone container cleanup |
| `tasks/portainer_standalone.yml` | CREATE | Standalone Portainer + agent deployment |
| `tasks/deploy_stacks_standalone.yml` | CREATE | Portainer API stack deployment |
| `tasks/prepare_jellyfin_volumes.yml` | CREATE | Standalone volume preparation |
| `templates/standalone/*.yml.j2` | CREATE | All 4 standalone compose templates |
| `roles/*/tasks/discover_container.yml` | MODIFY | Replace Swarm inspect with `docker ps` |
| `roles/*/tasks/wait_for_service.yml` | MODIFY | Remove Swarm service checks |
| `roles/*/defaults/main.yml` | MODIFY | Remove `*_swarm_manager` defaults |
| `tasks/post_setup_openvpn.yml` | MODIFY | Update container discovery |
| `.github/copilot-instructions.md` | MODIFY | Remove all Swarm references |
| `tasks/portainer.yml` | DELETE (after verified) | Old Swarm Portainer deployment |
| `tasks/deploy_stacks.yml` | DELETE (after verified) | Old Swarm stack deployment |
| `templates/*.yml.j2` (originals) | DELETE (after verified) | Old Swarm compose templates |
