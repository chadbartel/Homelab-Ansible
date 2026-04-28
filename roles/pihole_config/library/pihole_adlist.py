#!/usr/bin/python
# -*- coding: utf-8 -*-

# Copyright: (c) 2026, Homelab Ansible
# GNU General Public License v3.0+
# (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import absolute_import, division, print_function
__metaclass__ = type

import subprocess
from ansible.module_utils.basic import AnsibleModule

DOCUMENTATION = r'''
---
module: pihole_adlist
short_description: Manage Pi-hole adlists (block lists)
description:
    - Manage Pi-hole adlists in the gravity database
    - Supports adding, removing, and updating adlists
    - Idempotent operations - only makes changes when necessary
    - Works with Pi-hole running in Docker containers
version_added: "1.0.0"
options:
    container_id:
        description:
            - Docker container ID or name where Pi-hole is running
        required: true
        type: str
    url:
        description:
            - URL of the adlist (block list)
        required: true
        type: str
    comment:
        description:
            - Comment/description for the adlist
        required: false
        type: str
        default: ""
    enabled:
        description:
            - Whether the adlist should be enabled
        required: false
        type: bool
        default: true
    state:
        description:
            - Whether the adlist should be present or absent
        required: false
        type: str
        choices: ['present', 'absent']
        default: present
author:
    - Homelab Ansible
'''

EXAMPLES = r'''
# Add a new adlist
- name: Add AdGuard DNS adlist
  pihole_adlist:
    container_id: "abc123def456"
    url: "https://v.firebog.net/hosts/AdguardDNS.txt"
    comment: "AdGuard DNS"
    enabled: true
    state: present

# Remove an adlist
- name: Remove adlist
  pihole_adlist:
    container_id: "abc123def456"
    url: "https://example.com/old-list.txt"
    state: absent

# Add multiple adlists
- name: Configure Pi-hole adlists
  pihole_adlist:
    container_id: "{{ pihole_container_id }}"
    url: "{{ item.url }}"
    comment: "{{ item.comment }}"
    enabled: "{{ item.enabled }}"
    state: present
  loop:
    - url: "https://adaway.org/hosts.txt"
      comment: "AdAway"
      enabled: true
    - url: "https://v.firebog.net/hosts/Easylist.txt"
      comment: "EasyList"
      enabled: true
'''

RETURN = r'''
changed:
    description: Whether the adlist was changed
    type: bool
    returned: always
message:
    description: Human-readable message about what happened
    type: str
    returned: always
adlist:
    description: Details about the adlist
    type: dict
    returned: success
    contains:
        url:
            description: The URL of the adlist
            type: str
        comment:
            description: The comment/description
            type: str
        enabled:
            description: Whether the adlist is enabled
            type: bool
        id:
            description: Database ID of the adlist (if present)
            type: int
'''


def run_docker_exec(container_id, command):
    """Execute a command inside the Docker container"""
    try:
        result = subprocess.run(
            ['docker', 'exec', container_id, 'bash', '-c', command],
            capture_output=True,
            text=True,
            check=True
        )
        return result.stdout.strip(), None
    except subprocess.CalledProcessError as e:
        return None, str(e)


def check_adlist_exists(container_id, url):
    """Check if an adlist exists in the database"""
    command = f"""pihole-FTL sqlite3 /etc/pihole/gravity.db \
"SELECT id, enabled, comment FROM adlist WHERE address='{url}';" """
    
    stdout, error = run_docker_exec(container_id, command)
    
    if error:
        return None, error
    
    if stdout:
        # Format: id|enabled|comment
        parts = stdout.split('|')
        return {
            'id': int(parts[0]),
            'enabled': bool(int(parts[1])),
            'comment': parts[2] if len(parts) > 2 else ''
        }, None
    
    return None, None


def add_adlist(container_id, url, comment, enabled):
    """Add a new adlist to the database"""
    import time
    timestamp = int(time.time())
    enabled_val = 1 if enabled else 0
    
    # Escape single quotes for SQL
    url_escaped = url.replace("'", "''")
    comment_escaped = comment.replace("'", "''")
    
    command = f"""pihole-FTL sqlite3 /etc/pihole/gravity.db \
"INSERT INTO adlist (address, enabled, comment, date_added, date_modified) \
VALUES ('{url_escaped}', {enabled_val}, '{comment_escaped}', {timestamp}, {timestamp});" """
    
    stdout, error = run_docker_exec(container_id, command)
    
    if error:
        return False, error
    
    return True, None


def update_adlist(container_id, adlist_id, comment, enabled):
    """Update an existing adlist"""
    import time
    timestamp = int(time.time())
    enabled_val = 1 if enabled else 0
    
    # Escape single quotes for SQL
    comment_escaped = comment.replace("'", "''")
    
    command = f"""pihole-FTL sqlite3 /etc/pihole/gravity.db \
"UPDATE adlist SET enabled={enabled_val}, comment='{comment_escaped}', \
date_modified={timestamp} WHERE id={adlist_id};" """
    
    stdout, error = run_docker_exec(container_id, command)
    
    if error:
        return False, error
    
    return True, None


def remove_adlist(container_id, adlist_id):
    """Remove an adlist from the database"""
    command = f"""pihole-FTL sqlite3 /etc/pihole/gravity.db \
"DELETE FROM adlist WHERE id={adlist_id};" """
    
    stdout, error = run_docker_exec(container_id, command)
    
    if error:
        return False, error
    
    return True, None


def main():
    module = AnsibleModule(
        argument_spec=dict(
            container_id=dict(type='str', required=True),
            url=dict(type='str', required=True),
            comment=dict(type='str', default=''),
            enabled=dict(type='bool', default=True),
            state=dict(type='str', default='present', choices=['present', 'absent'])
        ),
        supports_check_mode=True
    )
    
    container_id = module.params['container_id']
    url = module.params['url']
    comment = module.params['comment']
    enabled = module.params['enabled']
    state = module.params['state']
    
    # Check if adlist exists
    existing_adlist, error = check_adlist_exists(container_id, url)
    
    if error:
        module.fail_json(msg=f"Failed to check adlist existence: {error}")
    
    changed = False
    message = ""
    
    if state == 'present':
        if existing_adlist is None:
            # Adlist doesn't exist, add it
            if not module.check_mode:
                success, error = add_adlist(container_id, url, comment, enabled)
                if not success:
                    module.fail_json(msg=f"Failed to add adlist: {error}")
            
            changed = True
            message = f"Added adlist: {comment if comment else url}"
            
        else:
            # Adlist exists, check if update needed
            needs_update = False
            
            if existing_adlist['enabled'] != enabled:
                needs_update = True
            
            if comment and existing_adlist['comment'] != comment:
                needs_update = True
            
            if needs_update:
                if not module.check_mode:
                    success, error = update_adlist(
                        container_id,
                        existing_adlist['id'],
                        comment,
                        enabled
                    )
                    if not success:
                        module.fail_json(msg=f"Failed to update adlist: {error}")
                
                changed = True
                message = f"Updated adlist: {comment if comment else url}"
            else:
                message = f"Adlist already present: {comment if comment else url}"
    
    else:  # state == 'absent'
        if existing_adlist is not None:
            # Adlist exists, remove it
            if not module.check_mode:
                success, error = remove_adlist(container_id, existing_adlist['id'])
                if not success:
                    module.fail_json(msg=f"Failed to remove adlist: {error}")
            
            changed = True
            message = f"Removed adlist: {comment if comment else url}"
        else:
            message = f"Adlist already absent: {comment if comment else url}"
    
    result = {
        'changed': changed,
        'message': message,
        'adlist': {
            'url': url,
            'comment': comment,
            'enabled': enabled,
            'id': existing_adlist['id'] if existing_adlist else None
        }
    }
    
    module.exit_json(**result)


if __name__ == '__main__':
    main()
