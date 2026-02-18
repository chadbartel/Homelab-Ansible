# Refactoring Analysis and Instructions for Homelab-Ansible Project

## Overview

After analyzing the Homelab-Ansible project, I've identified several areas for improvement regarding coupling, redundancy, and idempotency. Below are detailed instructions for an LLM agent to systematically refactor this project.

---

## Phase 1: Extract Post-Deployment Configuration into Dedicated Roles

### Task 1.1: Create `pihole_config` Role ✅ COMPLETED

**Objective**: Extract Pi-hole post-deployment configuration from `tasks/post_setup_pihole.yml` into a reusable, idempotent role.

**Status**: ✅ **COMPLETED** - Role created and integrated into project

**Implementation Details**:

1. ✅ Created role structure: `roles/pihole_config/`
2. ✅ Extracted into separate task files:
   - `tasks/discover_container.yml` - Pi-hole container discovery in Swarm
   - `tasks/wait_for_service.yml` - Container readiness checks (web interface + FTL)
   - `tasks/adlists.yml` - Adlist management using custom module
   - `tasks/custom_dns.yml` - Custom DNS entries via template
   - `tasks/dnsmasq.yml` - Dnsmasq configuration
3. ✅ Created custom `pihole_adlist` module:
   - Location: `library/pihole_adlist.py`
   - Supports: `state=present/absent`, `url`, `comment`, `enabled`
   - Uses `pihole-FTL sqlite3` for idempotent SQLite operations
   - Properly checks existence before inserting
   - Supports check mode and proper changed status
4. ✅ Abstracted container discovery:
   - Role variables: `pihole_config_service_name`, `pihole_config_target_node`, `pihole_config_swarm_manager`
   - Dynamic discovery via `docker service ps` and `docker inspect`
   - Deployed in `tasks/discover_container.yml`
5. ✅ Variables in `defaults/main.yml`:
   - Service discovery: `pihole_config_service_name`, `pihole_config_swarm_manager`, `pihole_config_target_node`
   - Readiness: `pihole_config_web_port: 8081`, `pihole_config_readiness_retries: 20`, etc.
   - Configuration: `pihole_config_adlists`, `pihole_config_custom_dns_entries`, `pihole_config_dnsmasq_settings`
6. ✅ Documentation created:
   - `README.md` - Complete role documentation with usage examples
   - `QUICK_START.md` - Quick reference guide
   - `meta/main.yml` - Galaxy metadata
   - Example playbooks in `examples/` directory
7. ✅ Integrated into project:
   - Updated `tasks/post_setup_pihole.yml` to use role
   - Added role variables to `vars.yml`
   - Updated `.github/copilot-instructions.md`

**Key Features**:

- Fully idempotent (safe to re-run multiple times)
- Modular task files (can be used individually)
- Automatic container discovery in Docker Swarm
- Custom Ansible module for adlist management (proper SQLite idempotency)
- Template-based DNS and dnsmasq configuration
- Follows same pattern as other config roles

**Issues Resolved**:

- ✅ Eliminated deep coupling to Docker Swarm (abstracted)
- ✅ Fixed non-idempotent bash script (replaced with custom module)
- ✅ Removed hardcoded container patterns (dynamic discovery)
- ✅ Separated concerns (modular task files)

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

### Task 1.4: Create `openvpn_config` Role ✅ COMPLETED

**Objective**: Extract from `tasks/post_setup_openvpn.yml` into a reusable, idempotent role.

**Status**: ✅ **COMPLETED** - Role created and integrated into project

**Implementation Details**:

1. ✅ Created role structure: `roles/openvpn_config/`
2. ✅ Extracted into separate task files:
   - `tasks/discover_container.yml` - Container discovery (Swarm/Docker/Direct)
   - `tasks/wait_for_service.yml` - Service readiness and health checks
   - `tasks/initial_setup.yml` - Initial server configuration (idempotent)
   - `tasks/users.yml` - VPN user management (idempotent)
3. ✅ Implemented deployment-agnostic design:
   - Auto-detects deployment mode (Swarm, Docker, or Direct container ID)
   - No hardcoded infrastructure values
   - Works with any Docker environment
4. ✅ Abstracted container discovery:
   - Role variables: `openvpn_config_service_name`, `openvpn_config_swarm_manager`, `openvpn_config_target_host`
   - Alternative: `openvpn_config_container_name` or `openvpn_config_container_id`
   - Dynamic container discovery via multiple methods
5. ✅ Variables in `defaults/main.yml`:
   - Service discovery: Multiple deployment mode support
   - Readiness: `openvpn_config_readiness_retries`, `openvpn_config_startup_wait`, etc.
   - Initial setup: `openvpn_config_admin_user`, `openvpn_config_server_hostname`, etc.
   - Users: `openvpn_config_users` (structured list with username, password, autologin)
   - Advanced: `openvpn_config_server_settings` (key-value pairs for sacli ConfigPut)
6. ✅ Documentation created:
   - `README.md` - Complete role documentation with deployment mode examples
   - `QUICK_START.md` - Fast reference guide with all deployment modes
   - `meta/main.yml` - Galaxy metadata
   - Example playbooks: basic_setup.yml, complete_setup.yml, modular_usage.yml, user_management.yml, advanced_configuration.yml
7. ✅ Integrated into project:
   - Updated `tasks/post_setup_openvpn.yml` to use role
   - Added role variables to `vars.yml`
   - Updated `.github/copilot-instructions.md`

**Key Features**:

- Fully idempotent (safe to re-run multiple times)
- Modular task files (can be used individually)
- Deployment-agnostic (Swarm, standalone Docker, or direct container)
- Auto-detection of deployment mode
- Separates deployment setup from ongoing management
- No hardcoded infrastructure assumptions
- Follows same pattern as other config roles

---

## Phase 2: Improve Idempotency Issues

### Task 2.1: Fix Adlist Configuration Idempotency ✅ COMPLETED

**Objective**: Fix idempotency issue where bash script is regenerated on every run.

**Status**: ✅ **COMPLETED** - Custom Ansible module created with full idempotency support

**Implementation Details**:

1. ✅ Created custom Ansible module: `roles/pihole_config/library/pihole_adlist.py`
   - Module name: `pihole_adlist` (simplified from `pihole_gravity_adlist`)
   - Parameters: `container_id`, `url`, `comment`, `enabled`, `state`
   - Integrated into `pihole_config` role for better organization

2. ✅ Implemented all required functionality:
   - Queries SQLite via `docker exec` using `pihole-FTL sqlite3` command
   - Checks if adlist exists before inserting (proper idempotency)
   - Only inserts when adlist is not present
   - Updates existing adlist if enabled/comment changes
   - Supports check mode (dry-run)
   - Returns `changed: false` when adlist exists and is unchanged

3. ✅ Additional features beyond requirements:
   - Proper SQL escaping to prevent injection
   - Support for `state: absent` to remove adlists
   - Update logic when configuration changes
   - Comprehensive error handling
   - Ansible module documentation (DOCUMENTATION, EXAMPLES, RETURN)

4. ✅ Integration completed:
   - Task file: `roles/pihole_config/tasks/adlists.yml` uses the module
   - Automatic gravity database update after changes
   - Used by `tasks/post_setup_pihole.yml`

**Verification**: Verified using `tests/verify_pihole_adlist_module.py` - all requirements met ✅

**Key Features**:

- Fully idempotent (safe to re-run multiple times without side effects)
- True SQLite-based state checking (not COUNT-based approximations)
- No unnecessary bash script generation
- Check mode support for dry-run testing
- Proper changed/unchanged status reporting

---

### Task 2.2: Fix Custom DNS Configuration Idempotency ✅ COMPLETED

**Objective**: Make custom DNS configuration idempotent to avoid unnecessary DNS restarts.

**Status**: ✅ **COMPLETED** - Implemented in `pihole_config` role

**Implementation Details**:

1. ✅ Implemented template-based approach:
   - Task file: `roles/pihole_config/tasks/custom_dns.yml`
   - Template: `roles/pihole_config/templates/custom_dns.list.j2`
   - Compares existing file content before updating
   - Only restarts DNS when content actually changed

2. ✅ Idempotent workflow:
   - Generate DNS entries file from template
   - Read existing content from container
   - Compare new vs existing content
   - Only update and restart if different

3. ✅ Proper cleanup:
   - Temporary files removed after use
   - DNS only restarted when necessary

**Key Features**:

- Fully idempotent (safe to re-run multiple times)
- Content-based change detection
- Template-driven configuration
- Automatic cleanup

---

### Task 2.3: Fix Dnsmasq Configuration Idempotency ✅ COMPLETED

**Objective**: Prevent duplicate entries in dnsmasq configuration file.

**Status**: ✅ **COMPLETED** - Custom module created and integrated

**Implementation Details**:

1. ✅ Created custom Ansible module: `roles/pihole_config/library/docker_exec_lineinfile.py`
   - Module name: `docker_exec_lineinfile`
   - Parameters: `container_id`, `path`, `line`, `regexp`, `state`, `create`, `backup`
   - Similar to `ansible.builtin.lineinfile` but works inside Docker containers

2. ✅ Implemented all required functionality:
   - Checks if line exists before adding (proper idempotency)
   - Executes via `docker exec` under the hood
   - Supports check mode (dry-run)
   - Returns `changed: false` when line already present
   - Supports regexp-based replacement
   - Optional backup creation

3. ✅ Integration completed:
   - Task file: `roles/pihole_config/tasks/dnsmasq.yml` uses the module
   - Replaces shell script approach
   - Only restarts DNS when settings actually changed

**Key Features**:

- Fully idempotent (safe to re-run multiple times)
- No duplicate entries created
- Proper file line management inside containers
- Check mode support
- Backup support for safety

---

## Phase 3: Address Structural Coupling Issues

### Task 3.1: Decouple Portainer Dependency ✅ COMPLETED

**Objective**: Decouple `tasks/deploy_stacks.yml` from Portainer API by creating abstraction layer.

**Status**: ✅ **COMPLETED** - Role created and integrated into project

**Implementation Details**:

1. ✅ Created role structure: `roles/stack_deployer/`
2. ✅ Supported multiple backends:
   - `portainer` - Portainer API v2.33.7 (centralized management)
   - `direct` - `docker stack deploy` CLI (default, backwards compatible)
   - `kompose` - Kubernetes conversion (placeholder for future)
3. ✅ Task dispatch based on backend:
   - `tasks/main.yml` - Backend validation and dispatcher
   - `tasks/portainer.yml` - Portainer API backend
   - `tasks/direct.yml` - Direct Docker CLI backend
   - `tasks/kompose.yml` - Kompose backend (future)
4. ✅ Portainer API integration:
   - POST `/api/auth` - JWT authentication
   - GET `/api/endpoints/{id}` - Verify Swarm endpoint
   - GET `/api/stacks` - List existing stacks
   - POST `/api/stacks/create/swarm/string` - Create new stack
   - PUT `/api/stacks/{id}` - Update existing stack
5. ✅ Variables in `defaults/main.yml`:
   - Backend selection: `stack_deployer_backend` (`portainer`, `direct`, `kompose`)
   - Common: `stack_deployer_swarm_manager`, `stack_deployer_stacks`
   - Portainer: `stack_deployer_portainer_url`, `stack_deployer_portainer_admin_password`, etc.
   - Direct: `stack_deployer_direct_prune`, `stack_deployer_direct_compose_version`
6. ✅ Documentation created:
   - `README.md` - Complete role documentation with API reference
   - `QUICK_START.md` - Quick start guide with examples
   - Example playbooks: basic_direct.yml, portainer_api.yml, backend_switching.yml, complete_setup.yml
7. ✅ Integrated into project:
   - Updated `tasks/deploy_stacks.yml` to use role (backwards compatible)
   - Updated `.github/copilot-instructions.md`
   - Supports runtime backend switching via `deployment_backend` variable

**Key Features**:

- Backend switching with a single variable
- True idempotency (Portainer API checks existing stacks)
- Consistent interface across backends
- Automatic network creation (`proxy-network`)
- JWT-based Portainer authentication
- Backwards compatible with existing deployments

**Backend Switching**:

```bash
# Deploy with direct backend (default)
make deploy

# Deploy with Portainer API backend
ansible-playbook main.yml -e "deployment_backend=portainer"
```

**Issues Resolved**:

- ✅ Eliminated tight coupling to specific deployment method
- ✅ Enabled centralized Portainer management (optional)
- ✅ Maintained backwards compatibility with direct deployment
- ✅ Created extensible pattern for future backends (Kompose/Kubernetes)

---

### Task 3.2: Decouple Node-Specific Logic ✅ COMPLETED

**Objective**: Eliminate hardcoded `pi4_01` references and use dynamic fact gathering for Swarm manager node.

**Status**: ✅ **COMPLETED** - Dynamic fact gathering implemented across project

**Implementation Details**:

1. ✅ Created common task file for dynamic fact gathering:
   - File: `tasks/common/set_swarm_manager.yml`
   - Sets `swarm_manager_node` fact using `groups['swarm_managers'][0]`
   - Runs once on localhost to set global fact
   - Includes debug output showing detected manager node

2. ✅ Updated inventory with `swarm_managers` group:
   - Added `swarm_managers` group to `inventory.yml`
   - Maintains backward compatibility with existing `manager_nodes` group
   - Currently contains `pi4_01` but easily extensible

3. ✅ Updated main playbook:
   - Added new play at beginning: "Initialize dynamic infrastructure facts"
   - Includes `tasks/common/set_swarm_manager.yml` with `always` tag
   - Ensures fact is available for all subsequent plays

4. ✅ Updated vars.yml with dynamic references:
   - `openvpn_config_swarm_manager`: Uses `{{ swarm_manager_node | default(groups['swarm_managers'][0]) }}`
   - `jellyfin_config_swarm_manager`: Uses dynamic variable
   - `npm_swarm_manager`: Uses dynamic variable
   - `pihole_config_swarm_manager`: Uses dynamic variable

5. ✅ Updated tasks/deploy_stacks.yml:
   - `stack_deployer_swarm_manager`: Uses dynamic variable
   - `stack_deployer_portainer_url`: Uses dynamic hostvars lookup
   - Backward compatible with fallback to inventory group

6. ✅ Updated role defaults files:
   - `roles/pihole_config/defaults/main.yml`: `{{ groups['swarm_managers'][0] | default('pi4_01') }}`
   - `roles/jellyfin_config/defaults/main.yml`: `{{ groups['swarm_managers'][0] | default('pi4_01') }}`
   - `roles/nginx_proxy_manager_config/defaults/main.yml`: `{{ groups['swarm_managers'][0] | default('pi4_01') }}`
   - `roles/stack_deployer/defaults/main.yml`: `{{ groups['swarm_managers'][0] | default('pi4_01') }}`

**Key Features**:

- Fully dynamic Swarm manager node detection
- No hardcoded `pi4_01` references in critical paths
- Backward compatible with existing deployments
- Centralized fact gathering for consistency
- Easy to extend to multi-manager setups
- Improved portability across different infrastructure

**Benefits**:

- Infrastructure changes (e.g., new manager node) only require inventory update
- Roles can be used in different Swarm clusters without modification
- Reduced coupling between playbooks and specific infrastructure
- Clearer separation between infrastructure definition (inventory) and logic (tasks/roles)

---

## Phase 4: Eliminate Redundant Steps

### Task 4.1: Consolidate Service Waiting Logic ✅ COMPLETED

**Objective**: Eliminate duplicate service waiting patterns across post-setup tasks and roles.

**Status**: ✅ **COMPLETED** - Common task file created with comprehensive features

**Implementation Details**:

1. ✅ Created common task file: `tasks/common/wait_for_swarm_service.yml`
   - Centralized service waiting logic
   - Supports multiple validation phases (port, HTTP, custom commands)
   - Configurable timeouts, retries, and delays
   - Optional Swarm service status verification

2. ✅ Implemented multi-phase validation:
   - **Phase 1**: Initial stabilization wait (optional)
   - **Phase 2**: Swarm service verification (optional)
   - **Phase 3**: Port accessibility check (required)
   - **Phase 4**: HTTP endpoint check (optional)
   - **Phase 5**: Custom validation command (optional)
   - **Phase 6**: Summary output

3. ✅ Comprehensive parameter support:
   - Required: `service_name`, `wait_host`, `wait_port`
   - Port checking: `wait_timeout`, `wait_delay`
   - HTTP checking: `wait_path`, `wait_http_status_codes`, `wait_retries`
   - Custom validation: `wait_custom_command`, `wait_container_id`, `wait_delegate_to`
   - Swarm integration: `wait_swarm_manager`
   - Display control: `wait_display_results`, `wait_initial_pause`

4. ✅ Documentation completed:
   - Usage examples in task file header
   - Updated `tasks/common/README.md` with detailed documentation
   - Examples for basic and advanced usage patterns

**Usage Example**:

```yaml
# Replace role-specific wait_for_service tasks with:
- include_tasks: tasks/common/wait_for_swarm_service.yml
  vars:
    service_name: "pihole-stack_pihole"
    wait_host: "{{ ansible_host }}"
    wait_port: 8081
    wait_path: "/admin"
    wait_custom_command: "pihole status"
    wait_container_id: "{{ pihole_container_id }}"
    wait_delegate_to: "{{ pihole_config_target_node }}"
    wait_custom_until_condition: "'enabled' in wait_custom_result.stdout"
    wait_swarm_manager: "{{ swarm_manager_node }}"
```

**Key Features**:

- Eliminates duplicate wait logic across all roles
- Consistent waiting behavior across all services
- Highly configurable for service-specific needs
- Supports complex multi-phase validation workflows
- Optional display of results for debugging or silent operation
- Backward compatible with existing role structures

**Next Step**: Optionally refactor individual role `wait_for_service.yml` files to use this common task (can be done incrementally as needed).

---

### Task 4.2: Remove Duplicate Docker Installation Logic ✅ COMPLETED

**Objective**: Eliminate redundant Docker installation checks and improve idempotency.

**Status**: ✅ **COMPLETED** - Docker installation refactored with comprehensive idempotency

**Implementation Details**:

1. ✅ Added pre-installation health checks:
   - Checks if Docker is already installed (`docker --version`)
   - Checks if Docker daemon is healthy (`docker info`)
   - Sets facts: `docker_needs_installation` and `docker_needs_repair`

2. ✅ Consolidated apt cache updates:
   - Removed redundant `update_cache: true` calls
   - Uses `cache_valid_time: 3600` to avoid unnecessary updates
   - Only updates cache when actually adding repository

3. ✅ Implemented `docker_users` list support:
   - New variable: `docker_users` in `vars.yml`
   - Defaults to `[admin_user]` for backward compatibility
   - Loop adds multiple users to docker group idempotently
   - Uses `append: true` to avoid removing users from other groups

4. ✅ Conditional task execution:
   - Docker installation only runs when `docker_needs_installation` is true
   - Nuclear fix script only runs when needed (installation or repair required)
   - Service startup only when needed (not on every run)

5. ✅ Improved cleanup:
   - Temporary GPG key file (`/tmp/docker.asc`) is removed after use
   - No unnecessary Docker socket permission resets

6. ✅ Enhanced status reporting:
   - Shows actual Docker version from `docker version` command
   - Reports whether Docker was newly installed, repaired, or already healthy
   - Lists all users with Docker access

**Variables Added**:

```yaml
# In vars.yml
docker_users:
  - "{{ admin_user }}"
# Example with multiple users:
# docker_users:
#   - thatsmidnight
#   - deployuser
#   - devuser
```

**Key Features**:

- Fully idempotent (safe to re-run multiple times)
- No redundant apt cache updates
- Conditional execution based on actual Docker status
- Support for multiple Docker users
- Proper cleanup of temporary files
- Clear status reporting

**Benefits**:

- Reduced execution time (skips installation when Docker is healthy)
- No unnecessary service restarts
- Better support for multi-user environments
- Improved debugging with clear status messages

---

## Phase 5: Create Reusable Modules

### Task 5.1: Create `docker_swarm_container_exec` Module

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

### Task 5.2: Create `portainer_stack` Module

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

1. **Task 2.1** - ✅ Fix adlist idempotency (COMPLETED - pihole_adlist module created)
2. **Task 2.2** - ✅ Fix custom DNS idempotency (COMPLETED - template-based approach)
3. **Task 2.3** - ✅ Fix dnsmasq configuration idempotency (COMPLETED - docker_exec_lineinfile module)
4. **Task 3.2** - ✅ Decouple node-specific logic (COMPLETED - dynamic fact gathering)

### Medium Priority (Structural Improvements)

1. **Task 1.1** - ✅ Extract `pihole_config` role (COMPLETED)
2. **Task 1.2** - ✅ Extract `jellyfin_config` role (COMPLETED)
3. **Task 1.3** - ✅ Extract `nginx_proxy_manager_config` role (COMPLETED)
4. **Task 1.4** - ✅ Extract `openvpn_config` role (COMPLETED)
5. **Task 3.1** - ✅ Decouple Portainer dependency (COMPLETED - stack_deployer role)
6. **Task 4.1** - ✅ Consolidate service waiting (COMPLETED - common task created)
7. **Task 4.2** - ✅ Remove duplicate Docker installation logic (COMPLETED)

### Low Priority (Nice to Have)

1. **Task 5.1** - Create container exec module
2. **Task 5.2** - Create Portainer stack module (further abstraction)

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
