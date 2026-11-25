---
trigger: model_decision
description: "Apply when configuring or tuning Ollama, Open WebUI, Whisper STT, Kokoro-FastAPI TTS, or GPU/CPU allocations on monolith."
---

# Monolith AI Stack Hardware & VRAM Tuning

## Hardware Budget (`monolith` — `192.168.1.17`)
- **GPU:** NVIDIA RTX 2070 SUPER (**8 GB VRAM**). Reserve GPU exclusively for `ollama` within the Jarvis AI stack—do not assign NVIDIA device reservations to Open WebUI, Whisper STT, or Kokoro-FastAPI TTS.
- **CPU:** AMD Ryzen 9 5900XT (**16-core / 32-thread**). Pin Whisper STT (`int8`) and Kokoro-FastAPI TTS workloads strictly to CPU.

## Ollama (8 GB VRAM Guardrails)
Maintain these required tuning variables in `roles/ai_stack/defaults/main.yml` and `roles/ai_stack/templates/ollama-compose.yml.j2`:
- `OLLAMA_FLASH_ATTENTION=1` — Reduces KV-cache memory footprint.
- `OLLAMA_KV_CACHE_TYPE=q8_0` — Quantized KV cache to fit larger contexts within 8 GB VRAM.
- `OLLAMA_MAX_LOADED_MODELS=1` — Prevents concurrent model loads from triggering OOM or host RAM thrashing.
- `OLLAMA_NUM_PARALLEL=1` — Caps parallel request slots for predictable VRAM ceiling.
- `OLLAMA_KEEP_ALIVE=15m` — Releases VRAM after idle windows.
- **Container Memory:** Limit `12G`, reservation `2G`.
- **GPU Reservation (Compose V2):** Use `deploy.resources.reservations.devices` (`driver: nvidia`, `count: 1`, `capabilities: [gpu]`)—never deprecated `runtime: nvidia`.
- **Storage Mount:** Preserve `/mnt/ollama_storage/ollama/data:/root/.ollama` on the dedicated 2 TB SSD (verify `mountpoint -q /mnt/ollama_storage` before starting). Never relocate model storage to the OS drive.

## CPU-Pinned Voice & Frontend Services
- **Open WebUI (`open-webui-stack`):**
  - No GPU reservation; memory limit `4G`, reservation `1G`.
  - Preserve `/opt/open-webui/data:/app/backend/data`.
  - Connect to Ollama over external `homelab-bridge` (`OLLAMA_BASE_URL=http://ollama:11434`).
  - Target CPU Whisper STT with `WHISPER_COMPUTE_TYPE=int8` (note: align `ai_stack_open_webui_whisper_compute_type` to `int8` when configuring voice STT so CPU inference stays fast and VRAM stays 100% free for Ollama).
- **Kokoro-FastAPI TTS (`kokoro-fastapi`):**
  - Pin exclusively to CPU image/runtime (no NVIDIA device reservation).
  - Deploy in an isolated Compose project under `/opt/docker-stacks` attached to `homelab-bridge` so restarts/`remove_orphans: true` never touch `pihole-stack` or `npm-stack`.

## Idempotent Model Pulls
- Before running `ollama pull <model>`, check `ollama list` (or `GET http://127.0.0.1:11434/api/tags`) and set `changed_when` accurately so repeat playbook runs report `changed=0`.
