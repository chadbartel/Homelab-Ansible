# Monolith Homelab Rules (WSL2 -> 192.168.1.17)

## Critical Network Protection (Non-Negotiable)
- `monolith` (`192.168.1.17`) is the live LAN DNS (Pi-hole/Unbound) and reverse proxy (Nginx Proxy Manager) for the entire network.
- NEVER restart, stop, recreate, or modify existing Pi-hole, Unbound, or Nginx Proxy Manager containers/routes. You MAY add new internal DNS records in Pi-hole and register new HTTPS proxy hosts in Nginx Proxy Manager exclusively via their REST APIs (or existing repo conventions) using Ansible Vault variables.
- **Trusted Let's Encrypt TLS Standard (Non-Negotiable):** For all `*.chadbartel.duckdns.org` proxy hosts in Nginx Proxy Manager, ALWAYS attach the existing Let's Encrypt wildcard certificate (`*.chadbartel.duckdns.org`, `provider: letsencrypt`, provisioned via DuckDNS DNS-01 in `roles/nginx_proxy_manager_config/tasks/certificates.yml`) with `ssl_forced: true`, `http2_support: true`, and `hsts_enabled: true`. NEVER generate or upload untrusted self-signed certificates when Let's Encrypt wildcard TLS is available, and ALWAYS verify HTTPS endpoints with strict TLS verification (`curl -fsSL`, never `-k`) so untrusted certs fail immediately.
- Keep the Jarvis/AI stack (`ollama`, `open-webui`, `kokoro-fastapi`) in isolated Compose projects (`/opt/docker-stacks`) so restarts or `--remove-orphans` never touch `pihole-stack` or `npm-stack`.
- Preserve existing Ollama (`/mnt/ollama_storage/ollama/data` on dedicated 2 TB SSD) and Open WebUI (`/opt/open-webui/data`) data mounts—never relocate model storage to the OS drive or create duplicate containers.
- If a new Nginx Proxy Manager proxy host or SSL route is needed, document exact hostname, upstream container/port, and flags in `MANUAL_NPM_STEPS.md` and continue—never touch NPM containers.

## Secrets Handling (Non-Negotiable)
- **NEVER** read, decrypt, edit, or commit Ansible Vault files (`vault.yml`), `.vault_pass`, or `.env` files.
- If a new secret is needed, reference it via `{{ vault_my_secret }}` in templates/vars, document the required key name in `SECRETS_TODO.md`, and continue non-blocked tasks.

## Mandatory Pre- and Post-Flight Health Check
Before AND after every playbook apply, verify core network services remain untouched:
1. `dig @192.168.1.17 google.com +short +time=2` returns an IP.
2. `ssh monolith "docker ps --format '{{.Names}} {{.Status}}'"` confirms `pihole` and `proxy` (NPM) remain `Up`.

If either check fails, **STOP immediately** and report the exact output.

## Ansible & Git Discipline
- Codify every change to `monolith` in Ansible roles/templates first—never make ad-hoc config edits over SSH.
- Always run playbooks scoped with `--tags` (e.g., `ansible-playbook main.yml --tags ai_stack`).
- Guard CLI tasks (`ollama pull`, `docker exec`) with state checks and accurate `changed_when` so repeated runs report `changed=0`.
- Prove idempotency after every apply by running the tagged command a SECOND time (`changed=0`, `failed=0`).
- Commit clean, atomic Git commits on the active feature branch (e.g., `feat/jarvis-voice-pipeline`) after each verified milestone.
- Run Python unit tests (`pytest`) and `ansible-lint` locally in WSL2; validate Docker Compose configs syntactically or on `monolith` (`ssh monolith "docker compose -f ... config --quiet"`) instead of running local Docker in WSL2.

## Hardware & Progressive Disclosure Pointers
- **Hardware Summary:** RTX 2070 SUPER (8 GB VRAM, reserved exclusively for Ollama in the AI stack) + Ryzen 9 5900XT (16-core CPU, pinned for Whisper STT `int8` and Kokoro-FastAPI TTS).
- **Detailed AI/VRAM Tuning:** Load `.agents/rules/ai-stack-vram.md` when editing AI stack roles, templates, or GPU/CPU resource allocations.
- **Deployment Runbook:** Activate `.agents/skills/ansible-deploy-gate/SKILL.md` for the full `lint -> --check -> DNS/Docker health check -> tagged apply -> idempotency re-run` gate.
- **Shared Architecture Wiki:** Read `/home/thatsmidnight/projects/My-LLM-Wiki/Wiki/index.md` (and `Wiki/entities/Monolith.md`, `Wiki/entities/Homelab-Ansible.md`); publish updates only via `wiki/*` branches and `~/.local/bin/wiki-pr`.
