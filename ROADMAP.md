# Jarvis Voice Pipeline Roadmap (`monolith`)

Target Host: `monolith` (`192.168.1.17`)
Hardware: NVIDIA RTX 2070 SUPER (8 GB VRAM) + AMD Ryzen 9 5900XT (16-core / 32-thread CPU)
Branch: `feat/jarvis-voice-pipeline`
Scoped Apply Command: `ansible-playbook main.yml --tags ai_stack`

## Architecture & Guardrails
- **Core Network Isolation**: `ollama-stack`, `kokoro-fastapi-stack`, and `open-webui-stack` are managed exclusively by the dedicated `roles/ai_stack` role (tagged `ai_stack`), completely isolated from `pihole-stack`, `npm-stack`, `jellyfin-stack`, and `bazarr-stack`.
- **Storage Guardrail**: `monolith`'s OS root volume `/` has only ~9.3 GB free while `/opt/ollama/data` currently consumes 13 GB on `/`. The dedicated 2 TB NVMe SSD (`nvme1n1`, Samsung 990 PRO) is already mounted at `/mnt/ollama_storage` with 1.7 TB free. Milestone 1 idempotently migrates existing Ollama data (`/opt/ollama/data`) to `/mnt/ollama_storage/ollama/data` (preserving all existing models and keys, leaving `/opt/ollama/data` untouched as a backup) so new models never touch the OS drive. Open WebUI retains its existing `/opt/open-webui/data` mount.
- **GPU Exclusivity (RTX 2070 SUPER, 8 GB VRAM)**: Reserved solely for Ollama (`OLLAMA_FLASH_ATTENTION=1`, `OLLAMA_KV_CACHE_TYPE=q8_0`, `OLLAMA_MAX_LOADED_MODELS=1`, `OLLAMA_NUM_PARALLEL=1`).
- **CPU Offloading (Ryzen 9 5900XT)**: Whisper STT (`int8`) in Open WebUI and Kokoro-FastAPI ONNX TTS (`ghcr.io/remsky/kokoro-fastapi-cpu:latest`) run strictly on CPU.
- **Idempotency & Health Gate**: Every milestone passes `ansible-lint`, `ansible-playbook main.yml --check --diff --tags ai_stack`, pre/post-flight DNS (`dig @192.168.1.17 google.com`) & Docker (`pihole` / `proxy`) checks, apply + second-run `changed=0` verification, and live inference / `ollama ps` `100% GPU` verification.

## Milestones

- [x] **Milestone 1: Create Isolated `ai_stack` Role, Migrate Ollama Data to 2 TB NVMe SSD, and Tune Ollama for 8 GB VRAM**
  - Create `roles/ai_stack` (defaults, tasks, templates, meta) and wire it into `main.yml` under tag `ai_stack` (removing `ollama-stack` and `open-webui-stack` from `portainer_stacks` in `vars.yml` to prevent duplicate management).
  - Idempotently copy existing `/opt/ollama/data` contents to `/mnt/ollama_storage/ollama/data` on the dedicated 2 TB NVMe SSD (`nvme1n1`), preserving existing models and keys.
  - Tune Ollama Compose template for 8 GB VRAM (`OLLAMA_FLASH_ATTENTION=1`, `OLLAMA_KV_CACHE_TYPE=q8_0`, `OLLAMA_MAX_LOADED_MODELS=1`, `OLLAMA_NUM_PARALLEL=1`, `OLLAMA_KEEP_ALIVE=15m`, 12 GB container RAM limit, native healthcheck).
  - Verify `ansible-lint`, `--check --diff --tags ai_stack`, pre/post-flight DNS & NPM checks, apply + re-run (`changed=0`), and inference + `ollama ps` (`100% GPU`).

- [x] **Milestone 2: Idempotently Pull & Verify Unlocked Multimodal and 8B Abliterated Text Models**
  - Add idempotent model provisioning tasks (`roles/ai_stack/tasks/models.yml`) checking `ollama list` before pulling so repeated runs report `changed=0`.
  - Pull unlocked multimodal model: `huihui_ai/gemma-4-abliterated:E4b-qat` (6.29 GB Q4_K_M + multimodal projector, fits 100% in 8 GB VRAM).
  - Pull 8B abliterated text model: `huihui_ai/qwen3-abliterated:8b-v2` (5.03 GB Q4_K_M, fast conversational inference with generous KV cache headroom).
  - Verify `ansible-lint`, `--check --diff --tags ai_stack`, pre/post-flight DNS & NPM checks, apply + re-run (`changed=0`), and inference + `ollama ps` (`100% GPU`, max 1 loaded model) for both models.

- [x] **Milestone 3: Deploy CPU-Pinned Kokoro-FastAPI TTS Container**
  - Add isolated `kokoro-fastapi-stack` Compose template (`ghcr.io/remsky/kokoro-fastapi-cpu:latest`) and tasks in `roles/ai_stack`, pinned strictly to CPU with Ryzen 9 5900XT ONNX thread tuning (`ONNX_NUM_THREADS=8`, `ONNX_INTER_OP_THREADS=4`, `ONNX_EXECUTION_MODE=parallel`), attached to `homelab-bridge` on port `8880` with container healthcheck.
  - Document optional NPM proxy host details in `MANUAL_NPM_STEPS.md` without modifying NPM.
  - Verify `ansible-lint`, `--check --diff --tags ai_stack`, pre/post-flight DNS & NPM checks, apply + re-run (`changed=0`), live Kokoro `/health`, `/v1/audio/voices`, and `/v1/audio/speech` synthesis on CPU, and Ollama `100% GPU` status.

- [ ] **Milestone 4: Configure Open WebUI CPU `int8` Whisper STT & Kokoro-FastAPI TTS Integration**
  - Update `roles/ai_stack/templates/open-webui-compose.yml.j2` (preserving `/opt/open-webui/data` mount): set `WHISPER_COMPUTE_TYPE=int8`, `AUDIO_STT_ENGINE=""`, `WHISPER_MODEL=base`, and wire Kokoro-FastAPI OpenAI-compatible TTS (`AUDIO_TTS_ENGINE=openai`, `AUDIO_TTS_OPENAI_API_BASE_URL=http://kokoro-fastapi:8880/v1`, `AUDIO_TTS_OPENAI_API_KEY=not-needed`, `AUDIO_TTS_MODEL=kokoro`, `AUDIO_TTS_VOICE=bm_george`).
  - Verify `ansible-lint`, `--check --diff --tags ai_stack`, pre/post-flight DNS & NPM checks, apply + re-run (`changed=0`), Open WebUI health and internal network reachability to `kokoro-fastapi:8880` and `ollama:11434`, Ollama `100% GPU` via `ollama ps`, and `nvidia-smi` confirming only Ollama uses GPU.
