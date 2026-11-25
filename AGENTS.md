# Monolith Homelab Rules (WSL2 -> 192.168.1.17)

## Critical Network Protection
- `monolith` (192.168.1.17) is the live DNS (Pi-hole/Unbound) and reverse proxy (Nginx Proxy Manager) for the entire network.
- NEVER modify Pi-hole, Unbound, Nginx Proxy Manager, Docker daemon config, or host firewall/networking roles.
- Keep the Jarvis/AI stack (`ollama`, `open-webui`, `kokoro-fastapi`) in its own dedicated Docker Compose project and directory (e.g., `/opt/stacks/ai-assistant/compose.yml`) so `--remove-orphans` or restarts never touch core infrastructure.
- If a new Nginx Proxy Manager proxy host or SSL route is needed, document the exact target port/hostname in `MANUAL_NPM_STEPS.md` and continue—do not touch NPM containers.

## Ansible Best Practices & Idempotency Gate
- Every change on `monolith` MUST be codified in Ansible roles/templates first—never make ad-hoc config edits over SSH.
- Always run playbooks scoped with `--tags` (e.g., `ansible-playbook site.yml --tags ai_stack`).
- After applying any playbook change, run it a SECOND time and verify `changed=0` and `failed=0` to prove idempotency.
- Commit clean, atomic Git commits on a feature branch (e.g., `feat/jarvis-voice-pipeline`) after each verified milestone.

## Mandatory Pre- and Post-Flight Health Check
Before and after every playbook apply, verify core network services are untouched:
1. `dig @192.168.1.17 google.com +short +time=2` returns an IP.
2. `ssh monolith "docker ps --format '{{.Names}} {{.Status}}'"` confirms Pi-hole and Nginx Proxy Manager remain Up.
If either check fails, STOP immediately and report the exact output.