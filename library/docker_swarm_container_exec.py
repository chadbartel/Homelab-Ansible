#!/usr/bin/python
# -*- coding: utf-8 -*-

# Copyright: (c) 2026, Homelab Ansible
# GNU General Public License v3.0+
# (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import subprocess
import shlex
from ansible.module_utils.basic import AnsibleModule

DOCUMENTATION = r"""
---
module: docker_swarm_container_exec
short_description: Execute commands in Docker containers with idempotency support
description:
    - Execute commands in Docker containers (standalone or Swarm)
    - Provides idempotency via creates/removes parameters
    - Supports working directory changes
    - Returns stdout, stderr, and return code
    - Useful for configuring services running in containers
version_added: "1.0.0"
options:
    container_id:
        description:
            - Docker container ID or name where command should execute
            - Can be full ID, short ID, or container name
        required: true
        type: str
    command:
        description:
            - Command to execute inside the container
            - Can be a string or list
        required: true
        type: raw
    chdir:
        description:
            - Change to this directory before running the command
        required: false
        type: str
    creates:
        description:
            - Path to a file in the container
            - If this file exists, the command will not run (idempotency)
            - Path is checked inside the container
        required: false
        type: str
    removes:
        description:
            - Path to a file in the container
            - If this file does NOT exist, the command will not run (idempotency)
            - Path is checked inside the container
        required: false
        type: str
    user:
        description:
            - Run command as this user inside the container
        required: false
        type: str
    environment:
        description:
            - Environment variables to set for the command
            - Provided as a dictionary
        required: false
        type: dict
        default: {}
    stdin:
        description:
            - String to pass to stdin of the command
        required: false
        type: str
author:
    - Homelab Ansible
notes:
    - Requires docker command to be available on the target host
    - Container must be running
    - This module executes commands via 'docker exec'
"""

EXAMPLES = r"""
# Simple command execution
- name: Check Pi-hole status
  docker_swarm_container_exec:
    container_id: "{{ pihole_container_id }}"
    command: "pihole status"
  register: pihole_status

# Command with idempotency using creates
- name: Initialize configuration (only if not already done)
  docker_swarm_container_exec:
    container_id: "{{ openvpn_container_id }}"
    command: "sacli --key 'host.name' --value 'vpn.example.com' ConfigPut"
    creates: "/usr/local/openvpn_as/.configured"

# Command with idempotency using removes
- name: Setup service (only if setup marker missing)
  docker_swarm_container_exec:
    container_id: "{{ service_container_id }}"
    command: "initialize-service.sh"
    removes: "/var/lib/service/.needs_setup"

# Command with working directory
- name: Run migration script
  docker_swarm_container_exec:
    container_id: "{{ app_container_id }}"
    command: "./migrate.sh"
    chdir: "/app/scripts"

# Command with specific user
- name: Run as specific user
  docker_swarm_container_exec:
    container_id: "{{ app_container_id }}"
    command: "whoami"
    user: "nginx"

# Command with environment variables
- name: Run with custom environment
  docker_swarm_container_exec:
    container_id: "{{ app_container_id }}"
    command: "printenv"
    environment:
      DEBUG: "true"
      LOG_LEVEL: "info"

# Complex command with multiple arguments
- name: Update gravity database
  docker_swarm_container_exec:
    container_id: "{{ pihole_container_id }}"
    command: "pihole -g"
  register: gravity_update
  changed_when: "'Update complete' in gravity_update.stdout"

# Using with loop for multiple commands
- name: Execute multiple sacli commands
  docker_swarm_container_exec:
    container_id: "{{ openvpn_container_id }}"
    command: "sacli --key '{{ item.key }}' --value '{{ item.value }}' ConfigPut"
  loop:
    - key: "vpn.daemon.0.listen.port"
      value: "1194"
    - key: "vpn.daemon.0.listen.protocol"
      value: "udp"
  loop_control:
    label: "{{ item.key }}"
"""

RETURN = r"""
stdout:
    description: Standard output from the command
    type: str
    returned: always
stderr:
    description: Standard error from the command
    type: str
    returned: always
rc:
    description: Return code from the command
    type: int
    returned: always
changed:
    description: Whether the command was executed (false if skipped due to creates/removes)
    type: bool
    returned: always
skipped:
    description: Whether the command was skipped due to creates/removes check
    type: bool
    returned: when command was skipped
msg:
    description: Human-readable message about execution status
    type: str
    returned: always
"""


def docker_exec_check(container_id, check_command):
    """
    Execute a check command in Docker container.
    Returns (success, stdout, stderr).
    """
    cmd = ["docker", "exec", container_id, "sh", "-c", check_command]
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, check=False, timeout=30
        )
        return (result.returncode == 0, result.stdout, result.stderr)
    except Exception as e:
        return (False, "", str(e))


def docker_exec_command(
    container_id, command, chdir=None, user=None, environment=None, stdin=None
):
    """
    Execute command in Docker container.
    Returns (rc, stdout, stderr).
    """
    # Build the command with optional chdir
    if chdir:
        if isinstance(command, list):
            shell_cmd = "cd {} && {}".format(
                shlex.quote(chdir), " ".join(shlex.quote(c) for c in command)
            )
        else:
            shell_cmd = "cd {} && {}".format(shlex.quote(chdir), command)
    else:
        if isinstance(command, list):
            shell_cmd = " ".join(shlex.quote(c) for c in command)
        else:
            shell_cmd = command

    # Build docker exec command
    docker_cmd = ["docker", "exec"]

    # Add user if specified
    if user:
        docker_cmd.extend(["--user", user])

    # Add environment variables if specified
    if environment:
        for key, value in environment.items():
            docker_cmd.extend(["-e", "{}={}".format(key, value)])

    # Add container and command
    docker_cmd.extend([container_id, "sh", "-c", shell_cmd])

    try:
        # Execute the command
        if stdin:
            result = subprocess.run(
                docker_cmd,
                input=stdin,
                capture_output=True,
                text=True,
                check=False,
                timeout=300,
            )
        else:
            result = subprocess.run(
                docker_cmd,
                capture_output=True,
                text=True,
                check=False,
                timeout=300,
            )
        return (result.returncode, result.stdout, result.stderr)
    except subprocess.TimeoutExpired:
        return (124, "", "Command timed out after 300 seconds")
    except Exception as e:
        return (1, "", str(e))


def main():
    module = AnsibleModule(
        argument_spec=dict(
            container_id=dict(type="str", required=True),
            command=dict(type="raw", required=True),
            chdir=dict(type="str", required=False),
            creates=dict(type="str", required=False),
            removes=dict(type="str", required=False),
            user=dict(type="str", required=False),
            environment=dict(type="dict", required=False, default={}),
            stdin=dict(type="str", required=False),
        ),
        supports_check_mode=True,
        mutually_exclusive=[["creates", "removes"]],
    )

    container_id = module.params["container_id"]
    command = module.params["command"]
    chdir = module.params["chdir"]
    creates = module.params["creates"]
    removes = module.params["removes"]
    user = module.params["user"]
    environment = module.params["environment"]
    stdin = module.params["stdin"]

    # Check if we should skip execution based on creates/removes
    if creates:
        # Skip if file exists
        success, stdout, stderr = docker_exec_check(
            container_id,
            "test -e {} && echo exists || echo missing".format(
                shlex.quote(creates)
            ),
        )
        if success and "exists" in stdout:
            module.exit_json(
                changed=False,
                skipped=True,
                msg="Skipped: file {} already exists (creates check)".format(
                    creates
                ),
                stdout="",
                stderr="",
                rc=0,
            )

    if removes:
        # Skip if file does not exist
        success, stdout, stderr = docker_exec_check(
            container_id,
            "test -e {} && echo exists || echo missing".format(shlex.quote(
                removes)
            ),
        )
        if success and "missing" in stdout:
            module.exit_json(
                changed=False,
                skipped=True,
                msg="Skipped: file {} does not exist (removes check)".format(
                    removes
                ),
                stdout="",
                stderr="",
                rc=0,
            )

    # Execute command in check mode (dry-run)
    if module.check_mode:
        module.exit_json(
            changed=True,
            skipped=False,
            msg="Would execute command (check mode)",
            stdout="",
            stderr="",
            rc=0,
        )

    # Execute the actual command
    rc, stdout, stderr = docker_exec_command(
        container_id,
        command,
        chdir=chdir,
        user=user,
        environment=environment,
        stdin=stdin,
    )

    # Determine if execution represents a change
    # Commands are assumed to change state unless explicitly marked as queries
    changed = True

    if rc != 0:
        module.fail_json(
            msg="Command failed with return code {}".format(rc),
            rc=rc,
            stdout=stdout,
            stderr=stderr,
            changed=changed,
        )

    module.exit_json(
        changed=changed,
        skipped=False,
        msg="Command executed successfully",
        rc=rc,
        stdout=stdout,
        stderr=stderr,
    )


if __name__ == "__main__":
    main()
