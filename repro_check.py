#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Manifeste de reproductibilité SeedMesh.

  python repro_check.py manifest -o repro.json [--golden docs/golden_prompts.json] [--threads N]
  python repro_check.py compare repro.json      [--threads N]   # code retour 0 si toutes les sorties golden identiques

Le manifeste fige : build llama.cpp, sha256 du GGUF, paramètres d'échantillonnage, version de schéma,
hash des fichiers du projet, environnement matériel (CPU/SIMD/threads) et, pour chaque prompt golden,
le prompt_hash SeedMesh + le sha256 de la sortie générée SANS cache.
"""
import argparse, hashlib, json, os, platform, subprocess, sys, time
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import agent, seedmesh_cache as sc

def sha256_file(p, buf=1 << 20):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(buf), b""): h.update(b)
    return h.hexdigest()

def cpu_info():
    info = {"machine": platform.machine(), "nproc": os.cpu_count()}
    try:
        txt = open("/proc/cpuinfo", encoding="utf-8", errors="replace").read()
        for l in txt.splitlines():
            if l.startswith("model name"): info["model"] = l.split(":", 1)[1].strip(); break
        flags = next((l.split(":", 1)[1].split() for l in txt.splitlines() if l.startswith(("flags", "Features"))), [])
        info["simd"] = sorted(f for f in set(flags) if f in {"avx", "avx2", "fma", "f16c", "avx512f", "avx512bw",
                              "avx512vnni", "avx_vnni", "neon", "asimd", "asimddp", "sve", "i8mm"})
    except OSError:
        info["model"] = platform.processor()
    return info

def llama_version(binp):
    try:
        r = subprocess.run([binp, "--version"], capture_output=True, text=True, timeout=30)
        return " | ".join(l.strip() for l in (r.stdout + r.stderr).splitlines() if l.startswith(("version", "built")))
    except Exception as e:
        return f"inconnu ({e})"

def build(golden_path, threads=None):
    g = json.load(open(golden_path, encoding="utf-8"))
    samp = dict(agent.SAMPLING); threads = threads or samp["threads"]
    model = agent.LLAMA_MODEL; binp = agent.LLAMA_BIN
    cache = sc.SeedMeshCache(":memory:" if False else os.path.join(os.environ.get("TMPDIR", "/tmp"), f"repro_{os.getpid()}.db"),
                             use_embeddings=False)
    ag = agent.Agent(cache, binp, model, g.get("n_predict", 64), samp["temp"], samp["ctx"], 600, g.get("system", ""),
                     sampling=samp, threads=threads, chat=agent.CONFIG.get("chat_template", True))
    ag.no_cache = True  # on mesure le modèle, pas le cache
    golden = []
    for p in g["prompts"]:
        t0 = time.time(); out = ag._run_llama(p); dt = time.time() - t0
        params = dict(ag.params, system=ag.system, step="answer"); params.update({"chat": True} if ag.chat else {})
        golden.append({"prompt": p, "prompt_hash": sc.make_hash(p, ag.model_id, params),
                       "output_sha256": hashlib.sha256(out.encode("utf-8")).hexdigest(),
                       "output": out, "seconds": round(dt, 2)})
    cache.close(); os.remove(cache.db_path)
    files = sorted(f for f in os.listdir(HERE) if f.endswith((".py", ".ps1", ".sh")))
    return {
        "manifest_version": 1, "created_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "seedmesh": {"schema_version": sc.SCHEMA_VERSION, "hash_algo": "sha256(NFC+espaces compactés | 0x1F | model | 0x1F | params JSON canonique)",
                     "files_sha256": {f: sha256_file(os.path.join(HERE, f)) for f in files}},
        "llama_cpp": {"bin": binp, "version": llama_version(binp)},
        "model": {"file": os.path.basename(model), "sha256": sha256_file(model), "size": os.path.getsize(model)},
        "sampling": dict(samp, threads=threads), "chat_template": ag.chat, "n_predict": g.get("n_predict", 64),
        "system": g.get("system", ""),
        "env": {"os": platform.platform(), "python": platform.python_version(), "cpu": cpu_info()},
        "golden": golden,
    }

def compare(ref, cur):
    """Retourne (ok, lignes) ; ok = toutes les sorties golden identiques."""
    lines, ok = [], True
    def chk(label, a, b, critical=False):
        nonlocal ok
        same = a == b
        if critical and not same: ok = False
        lines.append(f"{'OK ' if same else ('ÉCART' if critical else 'diff')} {label}" + ("" if same else f" : {a!r} -> {b!r}"))
    chk("modèle sha256", ref["model"]["sha256"], cur["model"]["sha256"], True)
    chk("llama.cpp", ref["llama_cpp"]["version"], cur["llama_cpp"]["version"])
    chk("schéma", ref["seedmesh"]["schema_version"], cur["seedmesh"]["schema_version"], True)
    chk("sampling", ref["sampling"], cur["sampling"])
    chk("CPU", ref["env"]["cpu"].get("model"), cur["env"]["cpu"].get("model"))
    chk("SIMD", ref["env"]["cpu"].get("simd"), cur["env"]["cpu"].get("simd"))
    for a, b in zip(ref["golden"], cur["golden"]):
        chk(f"prompt_hash « {a['prompt'][:30]} »", a["prompt_hash"], b["prompt_hash"], True)
        chk(f"sortie      « {a['prompt'][:30]} »", a["output_sha256"], b["output_sha256"], True)
    return ok, lines

def main():
    ap = argparse.ArgumentParser(description="Manifeste de reproductibilité SeedMesh")
    sp = ap.add_subparsers(dest="cmd", required=True)
    m = sp.add_parser("manifest"); m.add_argument("-o", "--out", default="repro.json")
    c = sp.add_parser("compare"); c.add_argument("manifest")
    for p in (m, c):
        p.add_argument("--golden", default=os.path.join(HERE, "docs", "golden_prompts.json"))
        p.add_argument("--threads", type=int)
    a = ap.parse_args()
    cur = build(a.golden, a.threads)
    if a.cmd == "manifest":
        json.dump(cur, open(a.out, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
        print(f"manifeste écrit : {a.out} ({len(cur['golden'])} prompts golden)")
        return 0
    ref = json.load(open(a.manifest, encoding="utf-8"))
    ok, lines = compare(ref, cur)
    print("\n".join(lines)); print("REPRODUCTIBLE" if ok else "NON REPRODUCTIBLE (voir ÉCART)")
    return 0 if ok else 1

if __name__ == "__main__":
    sys.exit(main())
