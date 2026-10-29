#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Sync Termux <-> PC via HTTP (l'autre machine lance `seedmesh_cache.py serve --host 0.0.0.0`).
push : envoie les entrées locales modifiées depuis la dernière sync (/put_batch)
pull : récupère les entrées distantes (/export?since=) et les fusionne localement.
L'état (dernier horodatage par URL) est dans SEEDMESH_HOME/sync_state.json. Les fichiers KV ne sont jamais synchronisés.
"""
import argparse, json, os, sys, urllib.request
from seedmesh_cache import SeedMeshCache, DEFAULT_DB, HOME

STATE = os.path.join(HOME, "sync_state.json")

def _req(url, body=None, timeout=60):
    data = json.dumps(body).encode() if body is not None else None
    r = urllib.request.Request(url, data=data, method="POST" if data else "GET", headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(r, timeout=timeout) as resp:
        return json.loads(resp.read())

def load_state(path):
    try:
        with open(path, encoding="utf-8") as f: return json.load(f)
    except (OSError, ValueError): return {}

def sync(cache, url, mode="both", state_path=STATE, batch=500):
    url = url.rstrip("/"); st = load_state(state_path); s = st.get(url, {}); out = {}
    if mode in ("push", "both"):
        import time; now = time.time()
        recs = list(cache.iter_records(s.get("push_since"))); res = {"inserted": 0, "updated": 0, "skipped": 0}
        for i in range(0, len(recs), batch):
            r = _req(url + "/put_batch", {"records": recs[i:i + batch]})
            for k in res: res[k] += r.get(k, 0)
        s["push_since"] = now; out["push"] = dict(sent=len(recs), **res)
    if mode in ("pull", "both"):
        q = f"?since={s['pull_since']}" if s.get("pull_since") else ""
        r = _req(url + "/export" + q)
        out["pull"] = dict(received=len(r["records"]), **cache.merge_records(r["records"]))
        s["pull_since"] = r["now"]
    st[url] = s
    os.makedirs(os.path.dirname(state_path), exist_ok=True)
    with open(state_path, "w", encoding="utf-8") as f: json.dump(st, f, indent=1)
    return out

def main(argv=None):
    ap = argparse.ArgumentParser(description="Sync SeedMesh via HTTP")
    ap.add_argument("url"); ap.add_argument("mode", nargs="?", default="both", choices=["push", "pull", "both"])
    ap.add_argument("--db", default=DEFAULT_DB); ap.add_argument("--state", default=STATE)
    a = ap.parse_args(argv)
    print(json.dumps(sync(SeedMeshCache(a.db, use_embeddings=False), a.url, a.mode, a.state), ensure_ascii=False))

if __name__ == "__main__":
    sys.exit(main())
