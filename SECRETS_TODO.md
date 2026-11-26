# Pending Vault Secrets (`SECRETS_TODO.md`)

Add the following optional/recommended keys to `vault.yml` using `ansible-vault edit vault.yml` when ready. All keys below have safe fallbacks so `ansible-playbook main.yml --tags trading_lab` remains deployable and idempotent immediately.

## Trading Lab (`roles/trading_lab`)

| Vault Variable | Required? | Purpose | Fallback Behavior When Unset |
| --- | --- | --- | --- |
| `vault_alpaca_api_key` | Optional (Paper Trading API) | Alpaca Paper Trading API Key ID (`paper-api.alpaca.markets`) | App automatically runs in **Internal Virtual Ledger Mode** backed by TimescaleDB (`trading-lab-db`) |
| `vault_alpaca_secret_key` | Optional (Paper Trading API) | Alpaca Paper Trading API Secret Key (`paper-api.alpaca.markets`) | App automatically runs in **Internal Virtual Ledger Mode** backed by TimescaleDB (`trading-lab-db`) |
| `vault_trading_lab_db_password` | Recommended | PostgreSQL/TimescaleDB password for `trading_lab` database user | Uses deterministic internal default (`trading_lab_timescale_2026`) so repeated runs do not cause DB auth drift |

## Existing Vault Keys Reused (Already Present in `vault.yml` / `vars.yml`)

- `vault_pihole_admin_password` (via `pihole_web_password`) — Used by `roles/trading_lab` to idempotently register the local DNS A record via Pi-hole v6 REST API (`/api/config/dns/hosts`).
- `vault_npm_admin_password` (via `npm_admin_password`) — Used by `roles/trading_lab` to idempotently resolve the existing Let's Encrypt wildcard certificate (`*.chadbartel.duckdns.org`) and register the HTTPS proxy host via Nginx Proxy Manager REST API.
