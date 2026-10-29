# r/LocalLLaMA — post prêt (flair suggéré : « Resources » ou « Other »)
Prérequis : karma minimum du sub (règles d'avril 2026) ; être là pour répondre aux commentaires.

**Title:** SeedMesh: a small SQLite response cache for llama.cpp with deterministic keys (89 ms hit vs ~4 s generation on a 1.5B model)

**Body:**
> **AI disclosure:** the code and this post were drafted with an AI assistant. I reviewed and tested it, and the numbers below come from real runs. Feel free to judge it on that basis.

I wanted repeated prompts to my local model to return instantly and identically, on Linux, Windows (PowerShell 7) and Termux. So I built SeedMesh (Apache-2.0): {REPO_URL}

What it does:
- Caches answers in SQLite (WAL). Key = sha256(NFC-normalized prompt | model file | canonical JSON of sampling params incl. seed, temp, top_p, top_k, repeat_penalty, system prompt). Python and PowerShell produce the same hash.
- Optional semantic lookup with int8 embeddings, LRU size cap, JSONL sync between machines.
- llama.cpp KV reuse: `--prompt-cache` for llama-completion, `/slots` save/restore for llama-server with prefix hashes.
- `repro_check.py`: writes a manifest (llama.cpp build, GGUF sha256, params, CPU/SIMD) plus output hashes for golden prompts, and compares runs.

Real numbers (8-vCPU Xeon server, AVX-512, Qwen2.5-1.5B-Instruct Q4_K_M, llama.cpp b11921, 4 threads):
- cache hit ~89 ms vs 4.0–4.2 s generation
- 22–25 tok/s generation, 130–260 tok/s prompt processing

Things that surprised me / limitations:
- Even with seed 42 and temp 0 on the same machine and build, outputs were **not always bit-identical**. One golden prompt differed twice in 5 re-runs (quotes vs no quotes). The cache is what gives repeatability, not the sampler.
- Not tested on a real Android phone yet (Termux scripts are untested on hardware).
- The cache HTTP server has no auth (binds to 127.0.0.1), there's no TTL, and prompts are stored in clear text.
- A 1.5B model is often wrong; the cache will happily serve wrong answers forever.

Feedback welcome, especially from people running llama.cpp on phones.
