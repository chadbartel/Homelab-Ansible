# Refactoring Analysis and Instructions for Homelab-Ansible Project

## Overview

After analyzing the Homelab-Ansible project, I've identified several areas for improvement regarding coupling, redundancy, and idempotency. Below are detailed instructions for an LLM agent to systematically refactor this project.

---

## Phase 1: Extract Post-Deployment Configuration into Dedicated Roles

### Task 1.1: Create `pihole_config` Role

**Objective**: Extract Pi-hole post-deployment configuration from `tasks/post_setup_pihole.yml` into a reusable, idempotent role.

**Issues Identified**:

- Deep coupling to Docker Swarm and specific node (`pi4_01`)
- Non-idempotent bash script creating SQLite entries (uses `COUNT(*)` check but regenerates script every time)
- Hardcoded container name patterns and service discovery logic
- Mixed concerns: container readiness, adlist management, DNS configuration

**Instructions**:

1. Create role structure: `roles/pihole_config/`
2. Move the following into separate task files:
   - `tasks/wait_for_service.yml` - Container readiness checks (make abstract for any service)
   - `tasks/adlists.yml` - Adlist management (use pihole-FTL API if available)
   - `tasks/custom_dns.yml` - Custom DNS entries
   - `tasks/dnsmasq.yml` - Dnsmasq configuration
3. Replace bash script with Ansible SQLite module or create custom `pihole_adlist` module:

   ```python
   # library/pihole_adlist.py
   # Should support: state=present/absent, url, comment, enabled
   # Uses pihole-FTL sqlite3 command for idempotent operations
   ```

4. Abstract container discovery:
   - Use role variables: `pihole_config_service_name`, `pihole_config_target_node`
   - Create `tasks/discover_container.yml` that can be reused
5. Variables to extract to `defaults/main.yml`:
   - `pihole_config_web_port: 8081`
   - `pihole_config_readiness_retries: 20`
   - `pihole_config_adlists: []` (structured list)

---

### Task 1.2: Create `jellyfin_config` Role ✅ COMPLETED

**Objective**: Extract from `tasks/post_setup_jellyfin.yml` into a reusable, idempotent role.

**Status**: ✅ **COMPLETED** - Role created and integrated into project

**Implementation Details**:

1. ✅ Created role structure: `roles/jellyfin_config/`
2. ✅ Extracted into separate task files:
   - `tasks/discover_container.yml` - Jellyfin container discovery in Swarm
   - `tasks/wait_for_service.yml` - Service readiness and health checks
   - `tasks/setup_wizard.yml` - Initial setup wizard completion (idempotent)
   - `tasks/api_keys.yml` - API key creation/retrieval (idempotent)
   - `tasks/libraries.yml` - Media library configuration
3. ✅ Implemented idempotent operations:
   - Setup wizard checks `/Startup/Configuration` endpoint (200 = needs setup, 404 = already done)
   - API key creation queries existing keys and returns existing if found
   - Uses `jellyfin` role for library management (inherits its idempotency)
4. ✅ Abstracted container discovery:
   - Role variables: `jellyfin_config_service_name`, `jellyfin_config_target_node`, `jellyfin_config_swarm_manager`
   - Dynamic container discovery via `docker service ps` and `docker inspect`
5. ✅ Variables in `defaults/main.yml`:
   - Service discovery: `jellyfin_config_service_name`, `jellyfin_config_swarm_manager`, `jellyfin_config_target_node`
   - Readiness: `jellyfin_config_readiness_retries`, `jellyfin_config_startup_wait`, etc.
   - Setup wizard: `jellyfin_config_server_name`, `jellyfin_config_ui_culture`, etc.
   - Admin user: `jellyfin_config_admin_user`, `jellyfin_config_admin_password`
   - Libraries: `jellyfin_config_libraries` (structured list with name, type, paths)
6. ✅ Documentation created:
   - `README.md` - Complete role documentation with usage examples
   - `QUICK_START.md` - Quick reference guide
   - `meta/main.yml` - Galaxy metadata
   - Example playbooks in `examples/` directory
7. ✅ Integrated into project:
   - Updated `tasks/post_setup_jellyfin.yml` to use role
   - Added role variables to `vars.yml`
   - Updated `.github/copilot-instructions.md`

**Key Features**:

- Fully idempotent (safe to re-run multiple times)
- Modular task files (can be used individually)
- Automatic container discovery in Docker Swarm
- Separates deployment setup from ongoing management
- Follows same pattern as `pihole_config` role

---

### Task 1.3: Create `nginx_proxy_manager_config` Role ✅ COMPLETED

**Objective**: Extract from `tasks/post_setup_npm.yml`.

**Status**: ✅ **COMPLETED** - Role created and integrated into project

**Implementation Details**:

1. ✅ Created role structure: `roles/nginx_proxy_manager_config/`
2. ✅ Extracted into separate task files:
   - `tasks/discover_container.yml` - NPM container discovery in Swarm
   - `tasks/wait_for_service.yml` - NPM API readiness checks
   - `tasks/proxy_hosts.yml` - Reverse proxy host management (idempotent)
3. ✅ Implemented true idempotency:
   - Queries existing proxy hosts via GET `/api/nginx/proxy-hosts`
   - Creates only new hosts (checks by domain name)
   - Updates existing hosts if configuration changed
4. ✅ Abstracted SSL certificate management:
   - Per-host SSL certificate ID configuration
   - Default SSL settings with per-host overrides
   - Automatic SSL/TLS settings (forced HTTPS, HSTS, HTTP/2)
5. ✅ Variables in `defaults/main.yml`:
   - Service discovery: `npm_config_service_name`, `npm_config_swarm_manager`, `npm_config_target_node`
   - Authentication: `npm_config_admin_email`, `npm_config_admin_password`
   - Proxy hosts: `npm_config_proxy_hosts` (structured list)
   - SSL defaults: `npm_config_default_ssl_cert_id`, `npm_config_ssl_forced`, etc.
6. ✅ Documentation created:
   - `README.md` - Complete role documentation
   - `QUICK_START.md` - Quick reference guide
   - `meta/main.yml` - Galaxy metadata
   - Example playbooks: basic_setup.yml, ssl_setup.yml, advanced_setup.yml, modular_usage.yml, complete_setup.yml
7. ✅ Integrated into project:
   - Updated `tasks/post_setup_npm.yml` to use role
   - Added role variables to `vars.yml`
   - Updated `.github/copilot-instructions.md`

**Key Features**:

- Fully idempotent (safe to re-run multiple times)
- API-based configuration (NPM REST API)
- Automatic container discovery in Docker Swarm
- Modular task files (can be used individually)
- Per-host SSL/TLS configuration
- WebSocket support, exploit blocking, caching options

---

### Task 1.4: Create `openvpn_config` Role

**Objective**: Extract from `tasks/post_setup_openvpn.yml`.

**Instructions**:

1. Separate client certificate generation from server configuration
2. Make certificate generation idempotent (check if cert exists with same CN)

---

## Phase 2: Create Generic Service Deployment Role

### Task 2.1: Create `docker_swarm_service` Role

**Objective**: Abstract common patterns from `tasks/deploy_stacks.yml` and post-setup tasks.

**Issues Identified**:

- Repeated pattern: wait for service → get container ID → execute commands
- Tight coupling to Portainer API for deployment
- No abstraction for service readiness checks

**Instructions**:

1. Create role structure: `roles/docker_swarm_service/`
2. Task files:
   - `tasks/deploy_stack.yml` - Deploys via Portainer API
   - `tasks/wait_for_service.yml` - Generic service readiness check
   - `tasks/get_container.yml` - Container discovery and facts gathering
   - `tasks/execute_command.yml` - Execute command in container with retries
3. Create custom module `library/docker_swarm_service_info.py`:

   ```python
   # Returns service info, container IDs, node placement
   # Parameters: service_name, swarm_manager_host
   # Returns: container_id, node, replicas, state
   ```

4. Variables to define:

   ```yaml
   docker_swarm_service_name: ""
   docker_swarm_service_stack_file: ""
   docker_swarm_service_wait_port: null
   docker_swarm_service_readiness_command: "echo ready"
   docker_swarm_service_readiness_pattern: "ready"
   ```

---

## Phase 3: Improve Idempotency Issues

### Task 3.1: Fix Adlist Configuration Idempotency

**Current Issue**: Script in `post_setup_pihole.yml` generates and copies bash script every run.

**Instructions**:

1. Create Ansible module `library/pihole_gravity_adlist.py`:

   ```python
   # Module interface:
   # - name: Manage Pi-hole adlist
   #   pihole_gravity_adlist:
   #     url: "https://example.com/list.txt"
   #     comment: "Example List"
   #     enabled: true
   #     state: present
   #     container_id: "{{ container_id }}"
   #     delegate_host: "pi4_01"
   ```

2. Module should:
   - Query SQLite via `docker exec` to check existence
   - Only insert if not present (proper idempotency)
   - Support check mode
   - Return `changed: false` when adlist exists

---

### Task 3.2: Fix Custom DNS Configuration Idempotency

**Current Issue**: Always writes `/etc/pihole/custom.list` and restarts DNS.

**Instructions**:

1. Use `ansible.builtin.lineinfile` or `ansible.builtin.blockinfile` instead of shell script
2. Template-based approach:

   ```yaml
   - name: Configure Pi-hole custom DNS entries
     ansible.builtin.template:
       src: pihole_custom_dns.list.j2
       dest: /tmp/custom.list
     delegate_to: localhost
     
   - name: Copy custom DNS to container
     ansible.builtin.copy:
       src: /tmp/custom.list
       dest: /etc/pihole/custom.list
     delegate_to: "{{ pihole_container_id }}"
     notify: restart pihole dns
   ```

3. Only restart DNS when file actually changes

---

### Task 3.3: Fix Dnsmasq Configuration Idempotency

**Current Issue**: Always appends to `misc.dnsmasq_lines`, creating duplicates.

**Instructions**:

1. Use `ansible.builtin.lineinfile`:

   ```yaml
   - name: Configure dnsmasq max concurrent queries
     ansible.builtin.lineinfile:
       path: /etc/dnsmasq.d/misc.dnsmasq_lines
       line: "dns-forward-max=300"
       state: present
       create: yes
     # Execute via docker exec wrapper or create module
   ```

2. Create helper module `library/docker_exec_lineinfile.py` that wraps lineinfile for container files

---

## Phase 4: Address Structural Coupling Issues

### Task 4.1: Decouple Portainer Dependency

**Issue**: `tasks/deploy_stacks.yml` is tightly coupled to Portainer API.

**Instructions**:

1. Create abstraction layer: `roles/stack_deployer/`
2. Support multiple backends:
   - `stack_deployer_backend: portainer` (current)
   - `stack_deployer_backend: docker_cli` (alternative)
   - `stack_deployer_backend: kompose` (future)
3. Task dispatch based on backend:

   ```yaml
   - name: Deploy stack via selected backend
     include_tasks: "backends/{{ stack_deployer_backend }}.yml"
   ```

---

### Task 4.2: Decouple Node-Specific Logic

**Issue**: Tasks hardcoded to `pi4_01` as manager node.

**Instructions**:

1. Use inventory group `swarm_managers` instead of hardcoded hostname
2. Create dynamic fact gathering:

   ```yaml
   - name: Set swarm manager fact
     set_fact:
       swarm_manager_node: "{{ groups['swarm_managers'][0] }}"
   ```

3. Replace all `delegate_to: pi4_01` with `delegate_to: "{{ swarm_manager_node }}"`

---

## Phase 5: Eliminate Redundant Steps

### Task 5.1: Consolidate Service Waiting Logic

**Issue**: Each post-setup task repeats service waiting pattern.

**Instructions**:

1. Create include task file: `tasks/common/wait_for_swarm_service.yml`
2. Parameters:

   ```yaml
   required_vars:
     - service_name
     - target_port
     - target_host
     - max_retries
   ```

3. Replace all wait blocks with:

   ```yaml
   - include_tasks: tasks/common/wait_for_swarm_service.yml
     vars:
       service_name: "pihole-stack_pihole"
       target_port: 8081
   ```

---

### Task 5.2: Remove Duplicate Docker Installation Logic

**Instructions**:

1. Review `tasks/docker.yml` for redundant checks
2. Ensure `docker_users` loop doesn't re-add existing users (use `state: present`)
3. Verify Docker socket permissions aren't reset unnecessarily

---

## Phase 6: Create Reusable Modules

### Task 6.1: Create `docker_swarm_container_exec` Module

**Objective**: Replace repeated shell commands with proper module.

**Module Specification**:

```python
# library/docker_swarm_container_exec.py
"""
Parameters:
  - service_name: Docker Swarm service name
  - command: Command to execute
  - chdir: Working directory (optional)
  - creates: File that indicates command already ran (idempotency)
  - swarm_manager: Host to execute on
  
Returns:
  - stdout, stderr, rc, changed
"""
```

---

### Task 6.2: Create `portainer_stack` Module

**Objective**: Replace API calls in `deploy_stacks.yml` with declarative module.

**Module Specification**:

```python
# library/portainer_stack.py
"""
Parameters:
  - name: Stack name
  - compose_file: Path to compose file
  - state: present/absent
  - endpoint_id: Portainer endpoint ID
  - swarm_id: Swarm ID
  - base_url: Portainer URL
  - api_token: Authentication token
  
Idempotency: Check if stack exists, compare compose content hash
"""
```

---

## Implementation Priority

### High Priority (Immediate Impact)

1. **Task 3.1** - Fix adlist idempotency (most obvious issue)
2. **Task 3.2** - Fix custom DNS idempotency
3. **Task 5.1** - Consolidate service waiting (reduce duplication)
4. **Task 4.2** - Decouple node-specific logic (portability)

### Medium Priority (Structural Improvements)

1. **Task 1.1** - ✅ Extract `pihole_config` role (COMPLETED)
2. **Task 1.2** - ✅ Extract `jellyfin_config` role (COMPLETED)
3. **Task 2.1** - Create `docker_swarm_service` role
4. **Task 6.1** - Create container exec module

### Low Priority (Nice to Have)

1. **Task 4.1** - Decouple Portainer dependency
2. **Task 1.2-1.4** - Extract other service config roles
3. **Task 6.2** - Create Portainer stack module

---

## Validation Steps

After each phase, the LLM agent should:

1. Run `make validate` to check syntax
2. Run `make test` to verify connectivity
3. Run playbook in check mode: `ansible-playbook main.yml --check`
4. Verify idempotency: Run playbook twice, second run should show minimal changes
5. Update documentation in affected README files
6. Update `.github/copilot-instructions.md` with new role structure

---

## Expected Outcomes

- **Reduced Coupling**: Services configurable independently of Swarm/Portainer
- **Improved Idempotency**: All tasks safely re-runnable without side effects
- **Reusability**: Roles publishable to Ansible Galaxy
- **Maintainability**: Clear separation of concerns, easier debugging
- **Portability**: Less hardcoded assumptions about infrastructure

---

## Notes for LLM Agent

When implementing these refactoring tasks:

1. **Work incrementally** - Complete one phase before moving to the next
2. **Test after each change** - Use the validation steps to ensure nothing breaks
3. **Maintain backward compatibility** - Keep old task files until new roles are proven
4. **Document as you go** - Update README files for each new role created
5. **Use existing patterns** - Follow the structure of `roles/jellyfin/` and `roles/jellyctl/` as templates
6. **Preserve secrets handling** - Maintain vault variable usage patterns
7. **Keep CI/CD in mind** - Ensure changes work with existing Makefile targets

---

## Related Documentation

- [SSH Setup Guide](../SSH-SETUP.md)
- [SSD Media Drive Setup](SSD_MEDIA_DRIVE_SETUP.md)
- [HTTPS Setup](HTTPS_SETUP.md)
- [Jellyfin Role README](../roles/jellyfin/README.md)
- [Jellyctl Role README](../roles/jellyctl/README.md)
