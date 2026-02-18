#!/usr/bin/python
# -*- coding: utf-8 -*-

# Copyright: (c) 2026, Homelab Ansible
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r"""
---
module: pihole_api
short_description: Interact with Pi-hole API v6.0 endpoints
version_added: "1.0.0"
description:
    - Generic module to interact with any Pi-hole API endpoint
    - Handles session-based authentication automatically
    - Supports all HTTP methods (GET, POST, PUT, DELETE, PATCH)
    - Abstracts away the need to manually construct JSON request bodies
    - Compatible with Pi-hole API v6.0
options:
    base_url:
        description:
            - Base URL of the Pi-hole API (e.g., http://192.168.1.12:8081/api)
            - Should include the /api path
        required: true
        type: str
    password:
        description:
            - Pi-hole web password (FTLCONF_webserver_api_password)
            - Used to create a session via POST /auth
        required: false
        type: str
    session_id:
        description:
            - Existing session ID from previous authentication
            - Alternative to password - avoids creating new session each time
        required: false
        type: str
    endpoint:
        description:
            - API endpoint path (e.g., /auth, /config, /dns/blocking)
            - Should start with /
        required: true
        type: str
    method:
        description:
            - HTTP method to use
        required: false
        type: str
        default: GET
        choices: ['GET', 'POST', 'PUT', 'DELETE', 'PATCH']
    query_params:
        description:
            - Query parameters to append to the URL
            - Provided as a dictionary
        required: false
        type: dict
        default: {}
    body:
        description:
            - Request body data (for POST, PUT, PATCH requests)
            - Provided as a dictionary, will be automatically converted to JSON
        required: false
        type: dict
        default: {}
    headers:
        description:
            - Additional headers to send with the request
        required: false
        type: dict
        default: {}
    validate_certs:
        description:
            - Whether to validate SSL certificates
        required: false
        type: bool
        default: false
    timeout:
        description:
            - Request timeout in seconds
        required: false
        type: int
        default: 30

author:
    - Homelab Ansible
"""

EXAMPLES = r"""
# Authenticate and get session
- name: Create Pi-hole session
  pihole_api:
    base_url: "http://192.168.1.12:8081/api"
    password: "{{ vault_pihole_admin_password }}"
    endpoint: "/auth"
    method: POST
  register: pihole_session

# Get Pi-hole configuration using session
- name: Get Pi-hole config
  pihole_api:
    base_url: "http://192.168.1.12:8081/api"
    session_id: "{{ pihole_session.response.session.sid }}"
    endpoint: "/config"
    method: GET

# Update rate limit configuration
- name: Set rate limit
  pihole_api:
    base_url: "http://192.168.1.12:8081/api"
    session_id: "{{ pihole_session.response.session.sid }}"
    endpoint: "/config"
    method: PATCH
    body:
      dns:
        rateLimit:
          count: 10000
          interval: 60

# Get DNS blocking status
- name: Check DNS blocking
  pihole_api:
    base_url: "http://192.168.1.12:8081/api"
    session_id: "{{ pihole_session.response.session.sid }}"
    endpoint: "/dns/blocking"
    method: GET

# Get top clients statistics
- name: Get top clients
  pihole_api:
    base_url: "http://192.168.1.12:8081/api"
    session_id: "{{ pihole_session.response.session.sid }}"
    endpoint: "/stats/top_clients"
    method: GET
    query_params:
      count: 10

# Enable DNS blocking
- name: Enable blocking
  pihole_api:
    base_url: "http://192.168.1.12:8081/api"
    session_id: "{{ pihole_session.response.session.sid }}"
    endpoint: "/dns/blocking"
    method: POST
    body:
      blocking: true

# Create a group
- name: Create group
  pihole_api:
    base_url: "http://192.168.1.12:8081/api"
    session_id: "{{ pihole_session.response.session.sid }}"
    endpoint: "/groups"
    method: POST
    body:
      name: "family"
      description: "Family devices"

# Add domain to whitelist
- name: Whitelist domain
  pihole_api:
    base_url: "http://192.168.1.12:8081/api"
    session_id: "{{ pihole_session.response.session.sid }}"
    endpoint: "/domains/allow/exact"
    method: POST
    body:
      domain: "example.com"
      comment: "Whitelisted via API"
"""

RETURN = r"""
response:
    description: The API response data
    type: dict
    returned: success
status_code:
    description: HTTP status code of the response
    type: int
    returned: always
msg:
    description: Message describing what happened
    type: str
    returned: always
session_id:
    description: Session ID for future requests (only returned from POST /auth)
    type: str
    returned: when authenticating
"""

import json
from ansible.module_utils.basic import AnsibleModule
from ansible.module_utils.urls import fetch_url, url_argument_spec
from ansible.module_utils.six.moves.urllib.parse import urlencode


class PiHoleAPI:
    def __init__(self, module):
        self.module = module
        self.base_url = module.params["base_url"].rstrip("/")
        self.password = module.params.get("password")
        self.session_id = module.params.get("session_id")
        self.endpoint = module.params["endpoint"]
        self.method = module.params["method"]
        self.query_params = module.params.get("query_params", {})
        self.body = module.params.get("body", {})
        self.headers = module.params.get("headers", {})
        self.validate_certs = module.params["validate_certs"]
        self.timeout = module.params["timeout"]

    def authenticate(self):
        """Authenticate with password to get session ID"""
        auth_url = self.base_url + "/auth"

        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

        auth_body = {"password": self.password}

        response, info = fetch_url(
            self.module,
            auth_url,
            data=json.dumps(auth_body),
            headers=headers,
            method="POST",
            timeout=self.timeout,
        )

        if info["status"] not in [200, 201]:
            self.module.fail_json(
                msg="Pi-hole authentication failed",
                status_code=info["status"],
                response=info.get("body", ""),
            )

        try:
            result = json.loads(response.read())
            session_data = result.get("session", {})
            self.session_id = session_data.get("sid")
            if not self.session_id:
                self.module.fail_json(
                    msg="No session ID returned from authentication",
                    response=result
                )
            return self.session_id
        except Exception as e:
            self.module.fail_json(
                msg="Failed to parse authentication response: %s" % str(e)
            )

    def build_headers(self):
        """Build request headers with session authentication"""
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

        # Add custom headers
        headers.update(self.headers)

        # Add session cookie if we have a session ID
        if self.session_id:
            headers["Cookie"] = "sid=%s" % self.session_id

        return headers

    def build_url(self):
        """Build the complete URL with query parameters"""
        url = self.base_url + self.endpoint

        if self.query_params:
            # Filter out None values and convert booleans to lowercase strings
            clean_params = {}
            for key, value in self.query_params.items():
                if value is not None:
                    if isinstance(value, bool):
                        clean_params[key] = str(value).lower()
                    else:
                        clean_params[key] = value

            if clean_params:
                url += "?" + urlencode(clean_params)

        return url

    def make_request(self):
        """Make the API request"""
        # For authentication endpoint, handle specially
        if self.endpoint == "/auth" and self.method == "POST":
            if not self.password:
                self.module.fail_json(msg="Password required for authentication")
            
            session_id = self.authenticate()
            
            return {
                "status_code": 200,
                "response": {"session": {"sid": session_id}},
                "session_id": session_id,
                "msg": "Authentication successful",
                "changed": True,
            }

        # For other endpoints, ensure we have authentication
        if not self.session_id:
            if self.password:
                # Auto-authenticate if password provided
                self.authenticate()
            else:
                self.module.fail_json(
                    msg="Either session_id or password required for API calls"
                )

        # Build request components
        url = self.build_url()
        headers = self.build_headers()

        # Prepare request data
        data = None
        if self.method in ["POST", "PUT", "PATCH"] and self.body:
            data = json.dumps(self.body)

        # Make the request
        response, info = fetch_url(
            self.module,
            url,
            data=data,
            headers=headers,
            method=self.method,
            timeout=self.timeout,
        )

        # Parse response
        status_code = info["status"]

        result = {
            "status_code": status_code,
            "response": {},
            "msg": "",
        }

        # Read response body
        if response:
            try:
                body = response.read()
                if body:
                    result["response"] = json.loads(body)
            except Exception as e:
                # Some endpoints return non-JSON responses
                result["response"] = body.decode("utf-8") if body else ""

        # Handle error responses
        if status_code >= 400:
            error_msg = "Pi-hole API request failed with status %d" % status_code
            if "body" in info:
                error_msg += ": %s" % info["body"]
            elif result["response"]:
                error_msg += ": %s" % str(result["response"])
            result["msg"] = error_msg
            result["failed"] = True
            return result

        # Success
        result["msg"] = "API request successful"
        result["changed"] = self.method in ["POST", "PUT", "DELETE", "PATCH"]

        return result


def main():
    argument_spec = url_argument_spec()
    argument_spec.update(
        base_url=dict(type="str", required=True),
        password=dict(type="str", required=False, no_log=True),
        session_id=dict(type="str", required=False, no_log=True),
        endpoint=dict(type="str", required=True),
        method=dict(
            type="str",
            default="GET",
            choices=["GET", "POST", "PUT", "DELETE", "PATCH"],
        ),
        query_params=dict(type="dict", default={}),
        body=dict(type="dict", default={}),
        headers=dict(type="dict", default={}),
        timeout=dict(type="int", default=30),
    )

    module = AnsibleModule(
        argument_spec=argument_spec,
        required_one_of=[["password", "session_id"]],
        supports_check_mode=True,
    )

    if module.check_mode:
        module.exit_json(changed=False)

    api = PiHoleAPI(module)
    result = api.make_request()

    if result.get("failed"):
        module.fail_json(**result)
    else:
        module.exit_json(**result)


if __name__ == "__main__":
    main()
