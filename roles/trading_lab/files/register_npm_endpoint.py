#!/usr/bin/env python3
"""Idempotently upload a SAN self-signed TLS cert and register a single NPM HTTPS proxy host.

Safety invariants:
- NEVER restarts or modifies the Nginx Proxy Manager container.
- NEVER modifies or deletes any proxy host belonging to another domain.
- Reads credentials exclusively from environment variables (never CLI args or stdout).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
import uuid
from pathlib import Path
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


def _http_multipart_upload(
    url: str,
    token: str,
    files: dict[str, tuple[str, bytes]],
    timeout: int = 30,
) -> Any:
    boundary = f"----TradingLabBoundary{uuid.uuid4().hex}"
    chunks: list[bytes] = []
    for field_name, (filename, content) in files.items():
        chunks.append(f"--{boundary}\r\n".encode("utf-8"))
        chunks.append(
            f'Content-Disposition: form-data; name="{field_name}"; filename="{filename}"\r\n'.encode(
                "utf-8"
            )
        )
        chunks.append(b"Content-Type: application/x-pem-file\r\n\r\n")
        chunks.append(content)
        chunks.append(b"\r\n")
    chunks.append(f"--{boundary}--\r\n".encode("utf-8"))
    body = b"".join(chunks)

    req = urllib.request.Request(
        url,
        data=body,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
            "Content-Type": f"multipart/form-data; boundary={boundary}",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8")
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        err_body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"NPM API POST {url} failed ({exc.code}): {err_body}") from exc


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
    parser = argparse.ArgumentParser(description="Register Trading Lab cert and proxy host in NPM")
    parser.add_argument("--api-url", required=True)
    parser.add_argument("--domain", required=True)
    parser.add_argument("--forward-host", required=True)
    parser.add_argument("--forward-port", type=int, required=True)
    parser.add_argument("--cert-name", required=True)
    parser.add_argument("--cert-path", required=True)
    parser.add_argument("--key-path", required=True)
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
    cert_action = "unchanged"
    proxy_action = "unchanged"

    certs = _http_json(f"{base_url}/nginx/certificates", method="GET", token=token)
    existing_cert = next(
        (
            c
            for c in certs
            if c.get("provider") == "other" and c.get("nice_name") == args.cert_name
        ),
        None,
    )

    cert_id: int | None
    if existing_cert is not None:
        cert_id = int(existing_cert["id"])
    else:
        changed = True
        cert_action = "would_create" if args.check else "created"
        if args.check:
            cert_id = None
        else:
            cert_bytes = Path(args.cert_path).read_bytes()
            key_bytes = Path(args.key_path).read_bytes()
            created_cert = _http_json(
                f"{base_url}/nginx/certificates",
                method="POST",
                token=token,
                payload={"provider": "other", "nice_name": args.cert_name},
            )
            cert_id = int(created_cert["id"])
            try:
                _http_multipart_upload(
                    f"{base_url}/nginx/certificates/{cert_id}/upload",
                    token=token,
                    files={
                        "certificate": ("certificate.crt", cert_bytes),
                        "certificate_key": ("certificate.key", key_bytes),
                    },
                )
            except Exception:
                # Roll back empty custom cert record if upload failed
                try:
                    _http_json(
                        f"{base_url}/nginx/certificates/{cert_id}",
                        method="DELETE",
                        token=token,
                    )
                except Exception:
                    pass
                raise

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
        "certificate_id": int(cert_id) if cert_id is not None else 0,
        "ssl_forced": True,
        "http2_support": True,
        "block_exploits": True,
        "allow_websocket_upgrade": True,
        "caching_enabled": False,
        "hsts_enabled": False,
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
        if cert_id is None or not _proxy_matches(existing_host, desired_host):
            changed = True
            proxy_action = "would_update" if args.check else "updated"
            if not args.check:
                _http_json(
                    f"{base_url}/nginx/proxy-hosts/{proxy_host_id}",
                    method="PUT",
                    token=token,
                    payload=desired_host,
                )

    print(
        json.dumps(
            {
                "changed": changed,
                "cert_action": cert_action,
                "proxy_action": proxy_action,
                "cert_id": cert_id,
                "proxy_host_id": proxy_host_id,
                "domain": args.domain,
            }
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
