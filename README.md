# SeedMesh

Local response cache + agent for llama.cpp — Linux, Windows (PowerShell 7), Android/Termux. Apache-2.0.
**Français : [README.fr.md](README.fr.md)** · Usage: [USAGE.md](USAGE.md) (FR)

> **AI disclosure:** this code and its documentation were generated with an AI assistant (Grok Bot) and tested on a Linux server. Review before relying on it.

## What it does
- **Exact cache** in SQLite (WAL, schema v3). Key = `sha256(NFC-normalized prompt | 0x1F | model file | 0x1F | canonical JSON of sampling params)`. The Python and PowerShell implementations produce the same hash.
- **Optional semantic lookup** with int8-quantized embeddings, plus an **LRU size cap** (`max_mb`).
- **KV reuse**: llama-completion `--prompt-cache`, or llama-server `/slots` save/restore by prefix hash.
- **Sync** between machines via idempotent JSONL (`/export`, `/put_batch`).
- **Reproducibility manifest**: `repro_check.py manifest|compare`.

## Measured (8-vCPU Xeon, AVX-512, Qwen2.5-1.5B-Instruct Q4_K_M, llama.cpp b11921, 4 threads)
| | |
|---|---|
| Cache hit | ~89 ms |
| Generation (miss) | 4.0–4.2 s |
| Generation speed | 22–25 tok/s |
| Determinism | Keys are stable; outputs at seed 42 / temp 0 are **not always bit-identical** (see docs/REPRODUCIBILITY.md) |

## Quick start (Linux)
```bash
sudo ./install_linux.sh      # downloads llama.cpp b11921 + model into /opt/seedmesh
seedmesh start
seedmesh ask "What is the capital of France?"
```
Windows: `Install-SeedMesh.ps1` (PowerShell 7). Termux: `install_termux.sh` (**untested on real devices**).

## Limitations
No HTTP auth (binds to 127.0.0.1) · no TTL · prompts stored in clear text · small models are often wrong, and the cache keeps serving those wrong answers · the cloud fallback is subject to provider rate limits · Termux is not an official Google channel.

## Docs (French)
`docs/` : REPRODUCIBILITY, BOUNTY, PLATFORMS, ANDROID_NATIF, AOSP_PROPOSAL, AOSP_SUBMISSION, POSTS/ · `android/` scripts (with revert) · [SECURITY.md](SECURITY.md) · [LICENSE](LICENSE) · [NOTICE](NOTICE)
