#!/usr/bin/python
# -*- coding: utf-8 -*-

# Copyright: (c) 2026, Homelab Ansible
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r"""
---
module: jellyfin_api
short_description: Interact with Jellyfin API endpoints
version_added: "1.0.0"
description:
    - Generic module to interact with any Jellyfin API endpoint
    - Handles authentication automatically
    - Supports all HTTP methods (GET, POST, PUT, DELETE, etc.)
    - Abstracts away the need to manually construct JSON request bodies
options:
    base_url:
        description:
            - Base URL of the Jellyfin server (e.g., http://localhost:8096)
        required: true
        type: str
    api_token:
        description:
            - API token for authentication
            - Can be obtained from Jellyfin Dashboard > API Keys
        required: false
        type: str
    username:
        description:
            - Username for authentication (alternative to api_token)
        required: false
        type: str
    password:
        description:
            - Password for authentication (used with username)
        required: false
        type: str
    endpoint:
        description:
            - API endpoint path (e.g., /Users, /Library/VirtualFolders)
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
        default: true
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
# Get system information
- name: Get Jellyfin system info
  jellyfin_api:
    base_url: "http://localhost:8096"
    api_token: "your-api-token"
    endpoint: "/System/Info"
    method: GET

# Create a new user
- name: Create Jellyfin user
  jellyfin_api:
    base_url: "http://localhost:8096"
    api_token: "{{ jellyfin_api_token }}"
    endpoint: "/Users/New"
    method: POST
    body:
      Name: "newuser"
      Password: "securepassword"

# Get all users
- name: List all Jellyfin users
  jellyfin_api:
    base_url: "{{ jellyfin_url }}"
    api_token: "{{ jellyfin_api_token }}"
    endpoint: "/Users"
    method: GET

# Update server configuration
- name: Update Jellyfin configuration
  jellyfin_api:
    base_url: "http://localhost:8096"
    api_token: "{{ jellyfin_api_token }}"
    endpoint: "/System/Configuration"
    method: POST
    body:
      EnableUPnP: true
      PublicPort: 8096

# Get library items with query parameters
- name: Get library items
  jellyfin_api:
    base_url: "{{ jellyfin_url }}"
    api_token: "{{ jellyfin_api_token }}"
    endpoint: "/Items"
    method: GET
    query_params:
      ParentId: "{{ library_id }}"
      Recursive: true

# Authenticate with username/password
- name: Get current user info
  jellyfin_api:
    base_url: "http://localhost:8096"
    username: "admin"
    password: "adminpass"
    endpoint: "/Users/Me"
    method: GET
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
"""

import json
from ansible.module_utils.basic import AnsibleModule
from ansible.module_utils.urls import fetch_url, url_argument_spec
from ansible.module_utils.six.moves.urllib.parse import urlencode


class JellyfinAPI:
    def __init__(self, module):
        self.module = module
        self.base_url = module.params["base_url"].rstrip("/")
        self.api_token = module.params.get("api_token")
        self.username = module.params.get("username")
        self.password = module.params.get("password")
        self.endpoint = module.params["endpoint"]
        self.method = module.params["method"]
        self.query_params = module.params.get("query_params", {})
        self.body = module.params.get("body", {})
        self.headers = module.params.get("headers", {})
        self.validate_certs = module.params["validate_certs"]
        self.timeout = module.params["timeout"]
        self.access_token = None

    def authenticate_with_credentials(self):
        """Authenticate using username and password to get access token"""
        auth_endpoint = "/Users/AuthenticateByName"
        auth_url = self.base_url + auth_endpoint

        auth_body = {"Username": self.username, "Pw": self.password}

        headers = {
            "Content-Type": "application/json",
            "X-Emby-Authorization": 'MediaBrowser Client="Ansible", Device="Server", DeviceId="ansible-module", Version="1.0.0"',
        }

        response, info = fetch_url(
            self.module,
            auth_url,
            data=json.dumps(auth_body),
            headers=headers,
            method="POST",
            timeout=self.timeout,
        )

        if info["status"] != 200:
            self.module.fail_json(
                msg="Authentication failed",
                status_code=info["status"],
                response=info.get("body", ""),
            )

        try:
            result = json.loads(response.read())
            self.access_token = result.get("AccessToken")
            if not self.access_token:
                self.module.fail_json(
                    msg="No access token returned from authentication"
                )
        except Exception as e:
            self.module.fail_json(
                msg="Failed to parse authentication response: %s" % str(e)
            )

    def build_headers(self):
        """Build request headers with authentication"""
        headers = {"Content-Type": "application/json", "Accept": "application/json"}

        # Add custom headers
        headers.update(self.headers)

        # Add authentication
        if self.api_token:
            headers["X-MediaBrowser-Token"] = self.api_token
        elif self.access_token:
            headers["X-MediaBrowser-Token"] = self.access_token

        # Add Emby authorization header
        auth_header = 'MediaBrowser Client="Ansible", Device="Server", DeviceId="ansible-module", Version="1.0.0"'
        if self.api_token:
            auth_header += ', Token="%s"' % self.api_token
        elif self.access_token:
            auth_header += ', Token="%s"' % self.access_token
        headers["X-Emby-Authorization"] = auth_header

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
        # Authenticate if using username/password
        if self.username and self.password and not self.access_token:
            self.authenticate_with_credentials()

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

        result = {"status_code": status_code, "response": {}, "msg": ""}

        # Read response body
        if response:
            try:
                body = response.read()
                if body:
                    result["response"] = json.loads(body)
            except Exception as e:
                result["response"] = body.decode("utf-8") if body else ""

        # Handle error responses
        if status_code >= 400:
            error_msg = "API request failed with status %d" % status_code
            if "body" in info:
                error_msg += ": %s" % info["body"]
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
        api_token=dict(type="str", required=False, no_log=True),
        username=dict(type="str", required=False),
        password=dict(type="str", required=False, no_log=True),
        endpoint=dict(type="str", required=True),
        method=dict(
            type="str", default="GET", choices=["GET", "POST", "PUT", "DELETE", "PATCH"]
        ),
        query_params=dict(type="dict", default={}),
        body=dict(type="dict", default={}),
        headers=dict(type="dict", default={}),
        timeout=dict(type="int", default=30),
    )

    module = AnsibleModule(
        argument_spec=argument_spec,
        required_one_of=[["api_token", "username"]],
        required_together=[["username", "password"]],
        supports_check_mode=True,
    )

    if module.check_mode:
        module.exit_json(changed=False)

    api = JellyfinAPI(module)
    result = api.make_request()

    if result.get("failed"):
        module.fail_json(**result)
    else:
        module.exit_json(**result)


if __name__ == "__main__":
    main()
