---
name: ansible-deploy-gate
description: >-
  Execute the mandatory safe, idempotent Ansible deployment workflow for
  Homelab-Ansible on monolith (192.168.1.17): lint, --check dry-run, pre-flight
  DNS/Docker health check, tagged apply, idempotency re-run, and post-flight
  verification.
---

# Ansible Deploy Gate (`monolith`)

Use this skill for every Ansible role, template, or playbook change targeting `monolith` (`192.168.1.17`).

## Pre-Check Guardrails
- Confirm zero edits to Pi-hole, Unbound, Nginx Proxy Manager, Docker daemon config, or host firewall/networking roles.
- Confirm zero reads/edits of `vault.yml`, `.vault_pass`, or `.env`.
- Confirm all host changes are codified in Ansible (no ad-hoc SSH edits).
- Identify the narrowest playbook tag for the change (e.g., `ai_stack`, `audiobookshelf`, `dispatcharr`).

## Gate Sequence

### 1. Syntax & Lint
Run syntax check and `ansible-lint` on the playbook and modified roles:
```bash
ansible-playbook main.yml --syntax-check
ansible-lint main.yml roles/<target_role>/
```
Fix all lint errors before proceeding.

### 2. Dry-Run (`--check --diff`)
Preview changes against `monolith` without mutating host state:
```bash
ansible-playbook main.yml --tags <target_tag> --check --diff
```
Review the diff carefully to confirm no core infrastructure (`pihole`, `proxy`, `/var/lib/docker`, `/mnt/ollama_storage`) is unexpectedly modified or recreated.

### 3. Pre-Flight Network & Container Health Check (Mandatory)
Verify live DNS and reverse proxy health BEFORE applying:
```bash
dig @192.168.1.17 google.com +short +time=2
ssh monolith "docker ps --format '{{.Names}} {{.Status}}'"
```
**Gate:** `dig` must return an IPv4/IPv6 address, and `docker ps` must show `pihole` and `proxy` (NPM) as `Up`. If either fails, **STOP immediately** and report exact output.

### 4. Scoped Tagged Apply
Apply only the targeted tag:
```bash
ansible-playbook main.yml --tags <target_tag>
```
Verify `failed=0` and `unreachable=0`.

### 5. Idempotency Re-Run Gate (Mandatory)
Re-run the **exact same command** a second time:
```bash
ansible-playbook main.yml --tags <target_tag>
```
**Gate:** Must finish with `changed=0` and `failed=0`. If `changed>0`, fix task idempotency (`creates`/`removes`, state check, or `changed_when`) and repeat from Step 1.

### 6. Post-Flight Network & Container Health Check (Mandatory)
Re-verify core network services after apply:
```bash
dig @192.168.1.17 google.com +short +time=2
ssh monolith "docker ps --format '{{.Names}} {{.Status}}'"
```
If either fails, **STOP immediately** and report exact output.

### 7. Commit & Knowledge Sync
- Create an atomic commit on the active feature branch (e.g., `feat/jarvis-voice-pipeline`).
- If NPM routing is needed, document exact hostname/port/flags in `MANUAL_NPM_STEPS.md`.
- If architecture, hardware, ports, or milestones changed, invoke the global `wiki-maintainer` skill to update `/home/thatsmidnight/projects/My-LLM-Wiki/` via a `wiki/*` branch and `~/.local/bin/wiki-pr`.
