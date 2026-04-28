#!/usr/bin/python
# -*- coding: utf-8 -*-

# Copyright: (c) 2024, Homelab-Ansible Contributors
# GNU General Public License v3.0+ (see LICENSE or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r"""
---
module: docker_exec_lineinfile
short_description: Manage lines in files inside Docker containers
description:
  - This module ensures a particular line is present or absent in a file inside a Docker container.
  - Similar to ansible.builtin.lineinfile but executes inside a container via docker exec.
  - Useful for managing configuration files in containers without mounting volumes.
  - Provides true idempotency by checking file contents before making changes.
version_added: "1.0.0"
options:
  container_id:
    description:
      - The ID or name of the Docker container.
    required: true
    type: str
  path:
    description:
      - Path to the file inside the container to modify.
    required: true
    type: str
  line:
    description:
      - The line to insert/ensure is present in the file.
      - Required when state=present.
    type: str
  regexp:
    description:
      - Regular expression to look for in the file.
      - If provided, will replace the matching line instead of adding new one.
    type: str
  state:
    description:
      - Whether the line should be present or absent.
    choices: [ present, absent ]
    default: present
    type: str
  create:
    description:
      - Create the file if it doesn't exist.
    type: bool
    default: false
  backup:
    description:
      - Create a backup file including the timestamp information.
    type: bool
    default: false
author:
  - Homelab-Ansible Contributors
notes:
  - Requires docker command to be available on the target host.
  - Container must be running.
  - This module uses docker exec under the hood.
"""

EXAMPLES = r"""
- name: Ensure dns-forward-max setting is present
  docker_exec_lineinfile:
    container_id: "{{ pihole_container_id }}"
    path: /etc/dnsmasq.d/misc.dnsmasq_lines
    line: "dns-forward-max=300"
    state: present
    create: true

- name: Ensure cache-size setting is present
  docker_exec_lineinfile:
    container_id: "pihole-abc123"
    path: /etc/dnsmasq.d/misc.dnsmasq_lines
    line: "cache-size=10000"
    state: present

- name: Remove a specific setting
  docker_exec_lineinfile:
    container_id: "{{ pihole_container_id }}"
    path: /etc/dnsmasq.d/misc.dnsmasq_lines
    line: "dns-forward-max=300"
    state: absent

- name: Replace line matching regexp
  docker_exec_lineinfile:
    container_id: "{{ pihole_container_id }}"
    path: /etc/dnsmasq.d/misc.dnsmasq_lines
    regexp: '^dns-forward-max='
    line: "dns-forward-max=500"
    state: present
"""

RETURN = r"""
changed:
  description: Whether the file was modified
  returned: always
  type: bool
  sample: true
msg:
  description: Human-readable message about what was done
  returned: always
  type: str
  sample: "Line added to file"
backup_file:
  description: Path to backup file if backup was requested
  returned: when backup=true and file was changed
  type: str
  sample: "/tmp/misc.dnsmasq_lines.backup.20240216120000"
"""

import re
import subprocess
from ansible.module_utils.basic import AnsibleModule


def docker_exec(container_id, command):
    """Execute command in Docker container and return output."""
    cmd = ["docker", "exec", container_id, "sh", "-c", command]
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, check=False
        )
        return result.returncode, result.stdout, result.stderr
    except Exception as e:
        return 1, "", str(e)


def file_exists(container_id, path):
    """Check if file exists in container."""
    rc, stdout, stderr = docker_exec(
        container_id, f"test -f {path} && echo exists || echo missing"
    )
    return "exists" in stdout


def read_file(container_id, path):
    """Read file contents from container."""
    rc, stdout, stderr = docker_exec(
        container_id, f"cat {path} 2>/dev/null || true"
    )
    if rc == 0:
        return stdout
    return ""


def write_file(container_id, path, content):
    """Write content to file in container."""
    rc, stdout, stderr = docker_exec(
        container_id, f"cat > {path} << 'EOF'\n{content}EOF"
    )
    return rc == 0


def create_backup(container_id, path):
    """Create a backup of the file."""
    import datetime

    timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
    backup_path = f"{path}.backup.{timestamp}"
    rc, stdout, stderr = docker_exec(container_id, f"cp {path} {backup_path}")
    if rc == 0:
        return backup_path
    return None


def line_present(lines, line, regexp=None):
    """Check if line is present in the list of lines."""
    if regexp:
        pattern = re.compile(regexp)
        for existing_line in lines:
            if pattern.match(existing_line.rstrip("\n")):
                return True, existing_line.rstrip("\n")
        return False, None
    else:
        return line in [ln.rstrip("\n") for ln in lines], None


def ensure_line_present(
    container_id, path, line, regexp, create, backup, check_mode
):
    """Ensure line is present in file."""
    result = {"changed": False, "msg": ""}

    # Check if file exists
    exists = file_exists(container_id, path)

    if not exists:
        if not create:
            result["msg"] = f"File {path} does not exist and create=false"
            return result

        # Create new file with the line
        if not check_mode:
            success = write_file(container_id, path, line + "\n")
            if not success:
                result["msg"] = f"Failed to create file {path}"
                return result

        result["changed"] = True
        result["msg"] = "File created with line"
        return result

    # Read existing content
    content = read_file(container_id, path)
    lines = content.splitlines(keepends=True)

    # Check if line already present
    present, matching_line = line_present(lines, line, regexp)

    if present:
        # Line already exists
        if regexp and matching_line != line:
            # Line matches regexp but is different - replace it
            if not check_mode:
                # Create backup if requested
                if backup:
                    backup_file = create_backup(container_id, path)
                    if backup_file:
                        result["backup_file"] = backup_file

                # Replace the matching line
                new_lines = []
                for existing_line in lines:
                    if regexp and re.match(regexp, existing_line.rstrip("\n")):
                        new_lines.append(line + "\n")
                    else:
                        new_lines.append(existing_line)

                new_content = "".join(new_lines)
                success = write_file(container_id, path, new_content)
                if not success:
                    result["msg"] = f"Failed to update file {path}"
                    return result

            result["changed"] = True
            result["msg"] = "Line replaced (regexp matched)"
            return result
        else:
            # Exact line already present
            result["changed"] = False
            result["msg"] = "Line already present"
            return result

    # Line not present - add it
    if not check_mode:
        # Create backup if requested
        if backup:
            backup_file = create_backup(container_id, path)
            if backup_file:
                result["backup_file"] = backup_file

        # Add the line
        new_content = content
        if not content.endswith("\n") and content:
            new_content += "\n"
        new_content += line + "\n"

        success = write_file(container_id, path, new_content)
        if not success:
            result["msg"] = f"Failed to update file {path}"
            return result

    result["changed"] = True
    result["msg"] = "Line added to file"
    return result


def ensure_line_absent(container_id, path, line, regexp, check_mode):
    """Ensure line is absent from file."""
    result = {"changed": False, "msg": ""}

    # Check if file exists
    exists = file_exists(container_id, path)

    if not exists:
        result["msg"] = f"File {path} does not exist"
        return result

    # Read existing content
    content = read_file(container_id, path)
    lines = content.splitlines(keepends=True)

    # Check if line is present
    present, _ = line_present(lines, line, regexp)

    if not present:
        result["changed"] = False
        result["msg"] = "Line already absent"
        return result

    # Remove the line
    if not check_mode:
        new_lines = []
        for existing_line in lines:
            if regexp:
                if not re.match(regexp, existing_line.rstrip("\n")):
                    new_lines.append(existing_line)
            else:
                if existing_line.rstrip("\n") != line:
                    new_lines.append(existing_line)

        new_content = "".join(new_lines)
        success = write_file(container_id, path, new_content)
        if not success:
            result["msg"] = f"Failed to update file {path}"
            return result

    result["changed"] = True
    result["msg"] = "Line removed from file"
    return result


def run_module():
    module_args = dict(
        container_id=dict(type="str", required=True),
        path=dict(type="str", required=True),
        line=dict(type="str", required=False),
        regexp=dict(type="str", required=False),
        state=dict(
            type="str", default="present", choices=["present", "absent"]
        ),
        create=dict(type="bool", default=False),
        backup=dict(type="bool", default=False),
    )

    result = dict(
        changed=False,
        msg="",
    )

    module = AnsibleModule(argument_spec=module_args, supports_check_mode=True)

    container_id = module.params["container_id"]
    path = module.params["path"]
    line = module.params["line"]
    regexp = module.params["regexp"]
    state = module.params["state"]
    create = module.params["create"]
    backup = module.params["backup"]

    # Validation
    if state == "present" and not line:
        module.fail_json(msg="line is required when state=present")

    try:
        if state == "present":
            result = ensure_line_present(
                container_id,
                path,
                line,
                regexp,
                create,
                backup,
                module.check_mode,
            )
        else:
            result = ensure_line_absent(
                container_id, path, line, regexp, module.check_mode
            )

        module.exit_json(**result)

    except Exception as e:
        module.fail_json(msg=f"Error: {str(e)}", **result)


def main():
    run_module()


if __name__ == "__main__":
    main()
