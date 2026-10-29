# r/selfhosted — commentaire pour le mégathread « New Project » du vendredi
Règles : projets nouveaux uniquement dans le mégathread ; déclarer l'usage de l'IA (le bot le demande) ; auto-promo : compte de ≥ 30 jours, ≤ 10 % de posts promotionnels, exception FLOSS si l'on reste actif dans les commentaires.

**Comment:**
> **SeedMesh** – self-hosted response cache for local LLMs (llama.cpp) — https://github.com/Kidaouene/seedmesh — Apache-2.0, no cloud required, no paywall.
>
> **AI involvement:** the code and docs were generated with an AI assistant, then tested by me on a Linux server (19 Python tests + 5 PowerShell parity tests). Not yet tested on real Android hardware.
>
> - SQLite cache keyed by a canonical hash (prompt + model + sampling params). Repeated questions come back in ~89 ms instead of ~4 s (1.5B Q4 model, 8-vCPU server).
> - Small HTTP API (`/lookup /put /export`) bound to 127.0.0.1. **No auth yet**, so don't expose it.
> - JSONL sync between machines (Linux / Windows PowerShell 7 / Termux), installers for each.
> - Reproducibility manifest (`repro_check.py`) recording llama.cpp build, model sha256 and output hashes.
>
> Limitations: no TTL, prompts stored unencrypted, the local fallback to a cloud provider is subject to its rate limits.
