#!/usr/bin/env python3
"""Idempotently register a single NPM HTTPS proxy host using the Let's Encrypt wildcard cert.

Safety invariants:
- NEVER restarts or modifies the Nginx Proxy Manager container.
- NEVER modifies or deletes any proxy host belonging to another domain.
- Resolves the existing Let's Encrypt certificate (`provider == "letsencrypt"`)
  covering `*.<local_domain>` (or `<domain>`) — never creates untrusted self-signed certs.
- Optionally removes a specified legacy custom self-signed cert record once no longer attached.
- Reads credentials exclusively from environment variables (never CLI args or stdout).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from typing import Any


def _http_json(
    url: str,
    method: str = "GET",
    token: str | None = None,
    payload: dict[str, Any] | None = None,
    timeout: int = 30,
) -> Any:
    headers = {"Accept": "application/json"}
    data: bytes | None = None
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if payload is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(payload).encode("utf-8")

    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8")
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"NPM API {method} {url} failed ({exc.code}): {body}") from exc


def _find_letsencrypt_cert(
    certs: list[dict[str, Any]],
    domain: str,
    local_domain: str,
) -> dict[str, Any] | None:
    wildcard = f"*.{local_domain}"
    for cert in certs:
        if cert.get("provider") != "letsencrypt":
            continue
        names = list(cert.get("domain_names") or [])
        if wildcard in names or domain in names:
            return cert
    return None


def _proxy_matches(existing: dict[str, Any], desired: dict[str, Any]) -> bool:
    if list(existing.get("domain_names") or []) != desired["domain_names"]:
        return False
    if str(existing.get("forward_scheme", "")) != desired["forward_scheme"]:
        return False
    if str(existing.get("forward_host", "")) != desired["forward_host"]:
        return False
    if int(existing.get("forward_port") or 0) != desired["forward_port"]:
        return False
    if int(existing.get("certificate_id") or 0) != desired["certificate_id"]:
        return False
    if int(existing.get("access_list_id") or 0) != desired["access_list_id"]:
        return False
    for flag in (
        "ssl_forced",
        "http2_support",
        "hsts_enabled",
        "hsts_subdomains",
        "block_exploits",
        "allow_websocket_upgrade",
        "caching_enabled",
        "enabled",
    ):
        if bool(existing.get(flag)) != bool(desired[flag]):
            return False
    if (existing.get("advanced_config") or "") != desired["advanced_config"]:
        return False
    return True


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Register Trading Lab HTTPS proxy host in NPM using Let's Encrypt wildcard cert"
    )
    parser.add_argument("--api-url", required=True)
    parser.add_argument("--domain", required=True)
    parser.add_argument("--local-domain", required=True)
    parser.add_argument("--forward-host", required=True)
    parser.add_argument("--forward-port", type=int, required=True)
    parser.add_argument("--cleanup-legacy-cert-name", default="")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()

    email = os.environ.get("NPM_ADMIN_EMAIL", "").strip()
    password = os.environ.get("NPM_ADMIN_PASSWORD", "")
    if not email or not password:
        print(json.dumps({"error": "Missing NPM_ADMIN_EMAIL or NPM_ADMIN_PASSWORD"}))
        return 1

    base_url = args.api_url.rstrip("/")
    auth = _http_json(
        f"{base_url}/tokens",
        method="POST",
        payload={"identity": email, "secret": password},
    )
    token = auth.get("token")
    if not token:
        print(json.dumps({"error": "NPM authentication did not return a token"}))
        return 1

    changed = False
    proxy_action = "unchanged"
    legacy_cert_action = "none"

    certs = _http_json(f"{base_url}/nginx/certificates", method="GET", token=token)
    le_cert = _find_letsencrypt_cert(certs, args.domain, args.local_domain)
    if le_cert is None:
        raise RuntimeError(
            f"No Let's Encrypt certificate covering *.{args.local_domain} or {args.domain} "
            "found in Nginx Proxy Manager. Provision the wildcard cert via "
            "roles/nginx_proxy_manager_config/tasks/certificates.yml first."
        )

    cert_id = int(le_cert["id"])
    cert_nice_name = str(le_cert.get("nice_name") or "")

    hosts = _http_json(f"{base_url}/nginx/proxy-hosts", method="GET", token=token)
    matching_hosts = [
        h for h in hosts if args.domain in (h.get("domain_names") or [])
    ]
    if len(matching_hosts) > 1:
        raise RuntimeError(
            f"Refusing to modify multiple NPM proxy hosts matching {args.domain}"
        )

    existing_host = matching_hosts[0] if matching_hosts else None
    if existing_host is not None:
        host_domains = list(existing_host.get("domain_names") or [])
        if host_domains != [args.domain]:
            raise RuntimeError(
                f"Refusing to modify shared NPM proxy host with other domains: {host_domains}"
            )

    desired_host = {
        "domain_names": [args.domain],
        "forward_scheme": "http",
        "forward_host": args.forward_host,
        "forward_port": int(args.forward_port),
        "certificate_id": cert_id,
        "ssl_forced": True,
        "http2_support": True,
        "block_exploits": True,
        "allow_websocket_upgrade": True,
        "caching_enabled": False,
        "hsts_enabled": True,
        "hsts_subdomains": False,
        "access_list_id": 0,
        "enabled": True,
        "meta": {},
        "locations": [],
        "advanced_config": "",
    }

    proxy_host_id: int | None
    if existing_host is None:
        changed = True
        proxy_action = "would_create" if args.check else "created"
        if args.check:
            proxy_host_id = None
        else:
            created_host = _http_json(
                f"{base_url}/nginx/proxy-hosts",
                method="POST",
                token=token,
                payload=desired_host,
            )
            proxy_host_id = int(created_host["id"])
    else:
        proxy_host_id = int(existing_host["id"])
        if not _proxy_matches(existing_host, desired_host):
            changed = True
            proxy_action = "would_update" if args.check else "updated"
            if not args.check:
                _http_json(
                    f"{base_url}/nginx/proxy-hosts/{proxy_host_id}",
                    method="PUT",
                    token=token,
                    payload=desired_host,
                )

    # Clean up legacy custom self-signed cert record only if no other host references it.
    if args.cleanup_legacy_cert_name:
        legacy_cert = next(
            (
                c
                for c in certs
                if c.get("provider") == "other"
                and c.get("nice_name") == args.cleanup_legacy_cert_name
            ),
            None,
        )
        if legacy_cert is not None:
            legacy_id = int(legacy_cert["id"])
            in_use_by_other = any(
                int(h.get("certificate_id") or 0) == legacy_id
                and int(h.get("id") or 0) != (proxy_host_id or -1)
                for h in hosts
            )
            if not in_use_by_other:
                changed = True
                legacy_cert_action = "would_delete" if args.check else "deleted"
                if not args.check:
                    _http_json(
                        f"{base_url}/nginx/certificates/{legacy_id}",
                        method="DELETE",
                        token=token,
                    )

    print(
        json.dumps(
            {
                "changed": changed,
                "cert_provider": "letsencrypt",
                "cert_id": cert_id,
                "cert_nice_name": cert_nice_name,
                "proxy_action": proxy_action,
                "legacy_cert_action": legacy_cert_action,
                "proxy_host_id": proxy_host_id,
                "domain": args.domain,
            }
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
