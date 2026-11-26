# Autonomous Paper-Trading Lab Roadmap (`monolith`)

- **Target Host:** `monolith` (`192.168.1.17`)
- **Branch:** `feat/trading-lab`
- **Scoped Ansible Command:** `.venv/bin/ansible-playbook main.yml --tags trading_lab`
- **Internal Endpoint:** `https://trading.chadbartel.duckdns.org` (Pi-hole v6 local DNS -> `192.168.1.17` -> Nginx Proxy Manager Let's Encrypt wildcard TLS `*.chadbartel.duckdns.org` with HSTS -> `http://trading-lab-app:8085` over `homelab-bridge`)
- **Persistent Storage Root (2 TB NVMe SSD):** `/mnt/ollama_storage/trading_lab/`
  - `/mnt/ollama_storage/trading_lab/app/` — staged application source & Dockerfile
  - `/mnt/ollama_storage/trading_lab/timescaledb/` — TimescaleDB/PostgreSQL 16 data volume
  - `/mnt/ollama_storage/trading_lab/logs/` — application & scheduler logs
  - `/mnt/ollama_storage/trading_lab/artifacts/` — weekend reflection & heuristic artifacts
  - `/mnt/ollama_storage/trading_lab/certs/` — SAN-enabled self-signed TLS cert & key

## Non-Negotiable Architecture & Guardrails

1. **Storage Isolation (NVMe SSD Only):** `/` on `monolith` has < 5 GB free. Every persistent volume, database directory, log file, TLS cert, and staged build artifact for `trading_lab` lives strictly under `/mnt/ollama_storage/trading_lab/` (1.7 TB free).
2. **Hardware Isolation:**
   - All `trading_lab` containers (`trading-lab-app`, `trading-lab-db`) are pinned strictly to CPU (AMD Ryzen 9 5900XT) with explicit memory/CPU limits and ZERO NVIDIA GPU reservations.
   - LLM news/catalyst thesis generation and weekend reflection route over Docker network `homelab-bridge` to the existing `ollama` container (`http://ollama:11434`, RTX 2070 SUPER 8 GB VRAM).
3. **Core Network Isolation:** `trading-lab-stack` deploys as an isolated Docker Compose V2 project under `/opt/docker-stacks/trading-lab-stack.yml`. Existing `pihole`, `proxy` (NPM), `ollama`, `open-webui`, `kokoro-fastapi`, `jellyfin`, `bazarr`, `dispatcharr`, `audiobookshelf`, and `portainer` containers and existing proxy hosts are never restarted, stopped, or modified.
4. **Deterministic Financial Safety (`RiskGate`):**
   - Paper-only hard assertion (`paper=True`, `paper-api.alpaca.markets`, or internal virtual ledger mode).
   - Ticker allowlist enforcement.
   - Hard max 5.0% single-position cap.
   - Mandatory stop-loss on every buy order.
   - Daily drawdown kill-switch blocking new buys on breach.
5. **Validate-Before-Ansible & Idempotency Gate:** Local `poetry run pytest`, static checks, and Compose validation pass before Ansible changes; every Ansible apply passes `ansible-lint`, `--check --diff`, pre/post-flight DNS & Docker checks, and a second idempotent run (`changed=0`, `failed=0`).

## Milestones

- [x] **Milestone 1: Discovery, Clean Branch (`feat/trading-lab`), Roadmap & Secrets Checklist**
  - Inspect `Homelab-Ansible` and `My-LLM-Wiki` (`Wiki/index.md`, `Monolith.md`, `Homelab-Ansible.md`) without reading vault or `.env` files.
  - Create branch `feat/trading-lab` off latest clean `main`.
  - Document architecture plan in `ROADMAP_TRADING_LAB.md` and optional vault variables in `SECRETS_TODO.md`.

- [x] **Milestone 2: Python 3.12 SOLID Paper-Trading Application (`apps/trading_lab`) & Unit Test Suite**
  - Poetry-managed Python 3.12 package with strict SOLID interfaces: `MarketDataProvider`, `NewsProvider`, `QuantitativeAnalyzer`, `LLMThesisEngine`, `RiskGate`, `BrokerExecutor`, `TradeLedgerRepository`, `ReflectionService`.
  - `alpaca-py >= 0.45.0` paper integration with clean automatic virtual ledger fallback when Alpaca keys are not set in vault.
  - Pure deterministic math (`RSI`, `ATR`, `SMA`, `EMA`, realized volatility) with zero LLM involvement.
  - Structured Ollama JSON thesis engine & weekend reflection heuristic weight tuner.
  - FastAPI web dashboard + JSON status/trigger APIs + built-in APScheduler (weekday market-hours cycle + weekend reflection).
  - Comprehensive `pytest` unit test suite with shared `conftest.py` fixtures (math, risk rejections, LLM JSON/fallback, ledger persistence, API/scheduler).

- [x] **Milestone 3: Containerization, Local Compose Validation & App QA Gate**
  - Production multi-stage / slim Python 3.12 Dockerfile and local `docker-compose.yml` validation.
  - Independent SOLID/security review and local end-to-end smoke test of full pipeline -> DB -> FastAPI dashboard & scheduler.

- [x] **Milestone 4: Isolated Ansible Role (`roles/trading_lab`) & Idempotent Deployment**
  - Create `roles/trading_lab` tagged `trading_lab` in `main.yml`.
  - Verify `/mnt/ollama_storage` mountpoint, create `/mnt/ollama_storage/trading_lab/{app,timescaledb,logs,artifacts,certs}`, sync app source, build/deploy CPU-only Compose V2 stack (`trading-lab-db` TimescaleDB PG16 + `trading-lab-app` on port `8085`).
  - Pass `ansible-lint`, `--check --diff`, pre/post-flight DNS & Docker health checks, apply, and second-run `changed=0` verification.

- [x] **Milestone 5: Internal Endpoint Registration (Pi-hole v6 + Let's Encrypt Wildcard TLS + NPM API)**
  - Idempotently add local DNS A record `192.168.1.17 trading.chadbartel.duckdns.org` via Pi-hole v6 REST API (`/api/config/dns/hosts`, with automatic fallback to `/api/config/misc/dnsmasq_lines` when `FTLCONF_dns_hosts` is env-locked).
  - Resolve and attach the existing trusted Let's Encrypt wildcard certificate (`*.chadbartel.duckdns.org`, `provider: letsencrypt`) via NPM REST API with `ssl_forced: true`, `http2_support: true`, `hsts_enabled: true` (cleaning up any legacy custom self-signed cert without touching other proxy hosts).
  - Verify `dig @192.168.1.17 trading.chadbartel.duckdns.org +short` == `192.168.1.17` and strict TLS `curl -fsSL https://trading.chadbartel.duckdns.org` (no `-k`) returns HTTP 200 with Trading Lab dashboard content (failing on untrusted certs, NPM landing page, or 502/404).
  - Prove full role idempotency (`changed=0`, `failed=0`) on second tagged run.

- [x] **Milestone 6: Live End-to-End Pipeline Verification on `monolith`**
  - Execute a live trading cycle and weekend reflection cycle on `monolith` hitting live Ollama on RTX 2070 SUPER.
  - Verify market/news ingest, deterministic indicators, Ollama JSON thesis, RiskGate evaluations/rejections, paper/virtual order execution, TimescaleDB hypertable/ledger writes, SPY benchmark comparison, live HTTPS dashboard rendering, and scheduler health.
  - Confirm core services (`pihole`, `proxy`, `ollama`, `open-webui`, `kokoro-fastapi`, `jellyfin`) and existing routes remain untouched and healthy.

- [x] **Milestone 7: Shared Wiki Sync (`My-LLM-Wiki`)**
  - Document `trading_lab` architecture, `/mnt/ollama_storage/trading_lab` storage paths, schedule, ports, internal DNS/NPM endpoint, and benchmark dashboard in `My-LLM-Wiki` on branch `wiki/trading-lab` published via `~/.local/bin/wiki-pr` (merged PR: https://github.com/chadbartel/My-LLM-Wiki/pull/15).
