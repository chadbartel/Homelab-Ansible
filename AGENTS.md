# Monolith Homelab Rules (WSL2 -> 192.168.1.17)

## Critical Network Protection
- `monolith` (192.168.1.17) is the live DNS (Pi-hole/Unbound) and reverse proxy (Nginx Proxy Manager) for the entire network.
- NEVER modify Pi-hole, Unbound, Nginx Proxy Manager, Docker daemon config, or host firewall/networking roles.
- Keep the Jarvis/AI stack (`ollama`, `open-webui`, `kokoro-fastapi`) isolated from core infrastructure Compose projects so restarts or `--remove-orphans` never touch Pi-hole, Unbound, or NPM.
- Preserve existing Ollama and Open WebUI data mounts on the dedicated 2 TB SSD—do not relocate model storage to the OS drive or create duplicate containers.
- If a new Nginx Proxy Manager proxy host or SSL route is needed, document the exact target port/hostname in `MANUAL_NPM_STEPS.md` and continue—do not touch NPM containers.

## Secrets Handling
- NEVER read, decrypt, edit, or commit Ansible Vault files, `.vault_pass`, or `.env` files.
- If a new secret is needed, reference it via `{{ vault_my_secret }}` in templates/vars, document the required key name in `SECRETS_TODO.md`, and continue with non-blocked tasks.

## Hardware Guardrails (`monolith`)
- GPU: RTX 2070 SUPER (8 GB VRAM). Reserve GPU exclusively for Ollama (`OLLAMA_FLASH_ATTENTION=1`, `OLLAMA_KV_CACHE_TYPE=q8_0`, `OLLAMA_MAX_LOADED_MODELS=1`).
- CPU: Ryzen 9 5900XT (16-core). Pin Whisper STT (`int8`) and Kokoro-FastAPI TTS to CPU.

## Ansible Best Practices & Idempotency Gate
- Every change on `monolith` MUST be codified in Ansible roles/templates first—never make ad-hoc config edits over SSH.
- Always run playbooks scoped with `--tags` (e.g., `ansible-playbook site.yml --tags ai_stack`).
- For CLI tasks like `ollama pull`, check `ollama list` first (or use accurate `changed_when` logic) so repeated runs report `changed=0`.
- After applying any playbook change, run it a SECOND time and verify `changed=0` and `failed=0` to prove idempotency.
- Commit clean, atomic Git commits on the `feat/jarvis-voice-pipeline` branch after each verified milestone.

## Mandatory Pre- and Post-Flight Health Check
Before and after every playbook apply, verify core network services are untouched:
1. `dig @192.168.1.17 google.com +short +time=2` returns an IP.
2. `ssh monolith "docker ps --format '{{.Names}} {{.Status}}'"` confirms Pi-hole and Nginx Proxy Manager remain Up.
If either check fails, STOP immediately and report the exact output.