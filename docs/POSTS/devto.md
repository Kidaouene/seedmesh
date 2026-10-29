# dev.to — article prêt
Règles : déclaration obligatoire (tag `#abotwrotethis` ou mention dans le texte) ; vérifier les faits ; pas d'article dont le but principal est la promotion. L'angle est donc **technique** : ce que l'on apprend sur le déterminisme.

---
title: "Seed 42, temperature 0, same machine — and my local LLM still wasn't deterministic"
tags: llm, llamacpp, reproducibility, abotwrotethis
---

> This article was written with the help of an AI assistant. The measurements were run and checked on a real server; the project code was also AI-generated and tested.

I built a small response cache for llama.cpp (SeedMesh, https://github.com/Kidaouene/seedmesh) and wanted to prove that "same input → same output". Setup:

- Qwen2.5-1.5B-Instruct Q4_K_M (sha256 `6a1a2eb6…407e`), llama.cpp b11921, CPU only, 8-vCPU Xeon with AVX-512
- seed 42, temp 0.0, top_p 0.9, top_k 40, repeat_penalty 1.1, 4 threads, chat template on
- 5 short "golden" prompts, 64 tokens max, generated **without** cache

## The tool
`repro_check.py manifest` stores the llama.cpp version, the GGUF sha256, the sampling params, the CPU model and SIMD flags, and for each prompt the cache key plus the sha256 of the output. `repro_check.py compare` regenerates everything and diffs it.

## Results
- Cache keys: identical every time (pure hashing; Python and PowerShell agree).
- Outputs: across 5 re-runs (4 with 4 threads, 1 with 2 threads), **one prompt differed twice**. "Translate to English: …" came back with surrounding quotes in one run and without them in another. The other 4 prompts were identical every time, even with 2 threads.

## Why (probably)
With greedy-ish decoding, two nearly tied tokens can flip when floating-point reductions happen in a different order across threads. I haven't proven that's the cause here. Different SIMD paths (AVX2 vs AVX-512 vs ARM NEON) and different builds make cross-machine bit-exactness even less likely.

## Takeaway
If you need repeatable answers from a local model, **cache the answer** and key it on everything that matters (normalized prompt, model, all sampling params). Then keep a manifest so you can tell *why* two machines disagree. The sampler alone won't give you that guarantee.

Measured cost/benefit on this box: cache hit ~89 ms vs 4.0–4.2 s generation.

Limitations: not tested on phones yet; cached wrong answers stay wrong; no TTL; the cache stores prompts in clear text.
