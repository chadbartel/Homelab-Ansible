# HTTPS setup for homelab services ("Not Secure" remediation)

Your services show "Not Secure" in the browser because they are served over **HTTP** (no TLS). This doc explains how to serve them over **HTTPS** using Nginx Proxy Manager (NPM) and Let's Encrypt.

## Important: Port Forwarding vs NPM Proxy Configuration

**Two separate concepts:**

1. **Router Port Forwarding** (already working if you can reach NPM):
   - Your router forwards external ports 80/443 → your manager node (192.168.1.10) where NPM runs.
   - This is already configured if you can access `http://pihole.chadbartel.duckdns.org` and see the NPM "Congratulations!" page.
   - **You don't need to change router port forwarding** - it's working!

2. **NPM Proxy Host Configuration** (what's missing):
   - NPM needs to know that `pihole.chadbartel.duckdns.org` should forward to the `pihole` container.
   - This is configured via Ansible's `post_setup_npm.yml` task, which creates "proxy hosts" in NPM.
   - If you see the NPM default page, the proxy host hasn't been created yet (or needs to be re-created).

## How it works

1. **NPM** listens on port 443 (HTTPS) and 80 (HTTP) on the manager node.
2. External traffic arrives via router port forwarding (80/443 → manager node).
3. NPM checks the `Host` header (e.g. `pihole.chadbartel.duckdns.org`) and matches it to a configured proxy host.
4. NPM forwards the request to the backend container (e.g. `pihole:80` on the Docker network).
5. For HTTPS, NPM terminates TLS (with a Let's Encrypt cert) and forwards to the backend over HTTP internally.
6. The browser sees a valid HTTPS connection to NPM; the internal hop stays HTTP.

## Prerequisites

- **Router Port Forwarding** (should already be set up):
  - External port 80 → manager node (192.168.1.10) port 80
  - External port 443 → manager node (192.168.1.10) port 443
  - If you can reach NPM, this is already working!

- **DNS**: Each subdomain (e.g. `pihole.chadbartel.duckdns.org`, `jellyfin.chadbartel.duckdns.org`) must resolve to your public IP (where your router port forwards). With Duck DNS, add a CNAME or A record per subdomain pointing to your public IP (or use a wildcard `*.chadbartel.duckdns.org` if your provider supports it).

## Step 1: Ensure NPM Proxy Hosts Are Created

**If you see the NPM "Congratulations!" page** when accessing `http://pihole.chadbartel.duckdns.org`, it means the proxy host hasn't been created in NPM yet.

**Fix:** Re-run the NPM post-setup task to create the proxy hosts:

```bash
ansible-playbook main.yml --tags post_setup,npm
```

Or run the full post-setup:

```bash
ansible-playbook main.yml --tags post-setup
```

This will create proxy hosts in NPM for all services listed in `host_vars/pi4_01.yml` → `proxy_hosts`. After this, `http://pihole.chadbartel.duckdns.org` should forward to Pi-hole instead of showing the default NPM page.

## Option A: Configure HTTPS in NPM (recommended, manual)

1. **Log in to NPM**  
   `http://<manager-ip>:8181` (or `http://proxy.chadbartel.duckdns.org:8181`).

2. **Create a proxy host per service** (if not already created by Ansible):
   - Hosts → Add Proxy Host
   - **Domain names**: e.g. `pihole.chadbartel.duckdns.org`
   - **Scheme**: HTTP
   - **Forward hostname**: `pihole` (Docker service name on `proxy-network`)
   - **Forward port**: `80` (Pi-hole's container port; use the service's container port, not the host-published one)
   - Save.

3. **Request a Let's Encrypt certificate** for that proxy host:
   - Edit the proxy host → **SSL** tab
   - Enable **SSL Certificate**: Let's Encrypt
   - Enter your email, accept ToS
   - Enable **Force SSL** so HTTP redirects to HTTPS
   - Save. NPM will request the cert; ensure DNS and ports 80/443 are correct or it will fail.

4. **Repeat** for each service (e.g. `jellyfin.chadbartel.duckdns.org` → `jellyfin:8096`, `home.chadbartel.duckdns.org` → `home:80`, etc.).

5. **Use the HTTPS URL**  
   e.g. `https://pihole.chadbartel.duckdns.org/admin` instead of `http://...:8081/admin`. The browser will show a secure connection once the cert is issued.

## Option B: Ensure Ansible creates the proxy hosts (already in place)

The playbook already creates NPM proxy hosts from `proxy_hosts` (e.g. in `host_vars/pi4_01.yml`). Each entry has:

- `domain`: e.g. `jellyfin.chadbartel.duckdns.org`
- `forward_host` / `forward_port`: Docker service name and port
- `certificate_id`: NPM certificate ID (0 = no cert; set to a valid cert ID after you create one in NPM)
- `ssl_forced`: set when a cert is used

So:

1. **Add proxy hosts in Ansible** for any service you want behind NPM (e.g. Pi-hole is in `host_vars/lenovo_server.yml` but NPM runs on the manager; if you want Pi-hole via NPM on the manager, add the same proxy host to `host_vars/pi4_01.yml`).
2. **Create at least one certificate in NPM** (SSL Certificates → Add → Let's Encrypt, e.g. for `pihole.chadbartel.duckdns.org`).
3. **Set `ssl_certificate_id`** in `vars.yml` to that certificate's ID (visible in NPM SSL Certificates list), then re-run the post-setup so proxy hosts use that cert and force SSL.

After that, re-running the NPM post-setup will attach the chosen cert to all proxy hosts that use `ssl_certificate_id`.

## Option C: Automate Let's Encrypt via NPM API (future)

NPM exposes an API. It is possible to add Ansible tasks that:

- Call NPM to create a Let's Encrypt certificate for a domain.
- Update proxy hosts to use that certificate and enable "Force SSL".

That would require using NPM' certificate and proxy-host API endpoints (and handling idempotency). If you want to go that route, we can design those tasks next; otherwise Option A or B is enough to fix "Not Secure" for all services.

## Summary

| Step | Action |
|------|--------|
| 1 | Ensure DNS for `*.chadbartel.duckdns.org` (or each subdomain) points to your NPM host. |
| 2 | In NPM, add/confirm proxy hosts for each service (Ansible can create them via `proxy_hosts`). |
| 3 | In NPM, request a Let's Encrypt certificate for each domain (or one wildcard if you use it). |
| 4 | Enable "Force SSL" on each proxy host and, if using Ansible, set `ssl_certificate_id` in `vars.yml`. |
| 5 | Use `https://service.chadbartel.duckdns.org` instead of `http://IP:port`. |

Once NPM has valid certs and "Force SSL" is on, the "Not Secure" warning goes away for those URLs.
