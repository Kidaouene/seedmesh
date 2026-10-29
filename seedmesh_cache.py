#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""SeedMesh - cache sémantique SQLite pour modèles locaux (Termux / Windows / Linux).

Lookup exact (sha256 du prompt normalisé + modèle + params), puis lookup
sémantique optionnel (sentence-transformers chargé paresseusement, fallback
silencieux si absent).

CLI : get | put | stats | prune | gc | export-jsonl [--since] | import-jsonl | serve
"""
import argparse, base64, hashlib, json, math, os, sqlite3, struct, sys, time, unicodedata

# Chemins absolus : expanduser fait UNE seule fois (évite les soucis de ~ sous Termux/PS)
HOME = os.path.abspath(os.environ.get("SEEDMESH_HOME") or os.path.join(os.path.expanduser("~"), ".seedmesh"))
DEFAULT_DB = os.path.join(HOME, "cache.db")
DEFAULT_EMB_MODEL = os.environ.get("SEEDMESH_EMB_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
DEFAULT_THRESHOLD = float(os.environ.get("SEEDMESH_THRESHOLD", "0.92"))
SCHEMA_VERSION = 3
MAX_MB = float(os.environ.get("SEEDMESH_MAX_MB", "0") or 0)  # 0 = illimité
ROW_OVERHEAD = 200  # octets estimés par ligne (index, en-têtes)

# ---------------------------------------------------------------- migrations
def _m1(c):
    c.executescript("""
    CREATE TABLE IF NOT EXISTS entries(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        prompt_hash TEXT NOT NULL UNIQUE,
        prompt TEXT NOT NULL,
        response TEXT NOT NULL,
        model TEXT NOT NULL DEFAULT '',
        params_json TEXT NOT NULL DEFAULT '{}',
        embedding BLOB,
        emb_model TEXT,
        created_at REAL NOT NULL,
        hits INTEGER NOT NULL DEFAULT 0,
        last_hit REAL);
    CREATE INDEX IF NOT EXISTS idx_entries_model ON entries(model);
    """)

def _m2(c):
    c.executescript("""
    CREATE TABLE IF NOT EXISTS kv_snapshots(
        prefix_hash TEXT NOT NULL,
        path TEXT NOT NULL,
        model TEXT NOT NULL DEFAULT '',
        created_at REAL NOT NULL,
        PRIMARY KEY(prefix_hash, model));
    CREATE INDEX IF NOT EXISTS idx_entries_last_hit ON entries(last_hit);
    """)

def _m3(c):
    """v3 : embeddings int8 (+ emb_scale), table kv_prefixes, conversion des float32 existants."""
    cols = [r[1] for r in c.execute("PRAGMA table_info(entries)")]
    if "emb_scale" not in cols:  # (peut déjà exister si PowerShell a migré)
        c.execute("ALTER TABLE entries ADD COLUMN emb_scale REAL")
    c.executescript("""
    CREATE TABLE IF NOT EXISTS kv_prefixes(
        prefix_hash TEXT NOT NULL, model TEXT NOT NULL DEFAULT '', slot_file TEXT NOT NULL,
        n_turns INTEGER NOT NULL, created_at REAL NOT NULL, last_used REAL,
        PRIMARY KEY(prefix_hash, model));
    """)
    convert_float_embeddings(c)

def convert_float_embeddings(c):
    """Convertit les BLOB float32 (emb_scale NULL) en int8 + scale. Idempotent."""
    rows = c.execute("SELECT id, embedding FROM entries WHERE embedding IS NOT NULL AND emb_scale IS NULL").fetchall()
    for rid, blob in rows:
        q, sc_ = quantize(unpack(blob))
        c.execute("UPDATE entries SET embedding=?, emb_scale=? WHERE id=?", (q, sc_, rid))
    return len(rows)

MIGRATIONS = {1: _m1, 2: _m2, 3: _m3}

def migrate(conn):
    v = conn.execute("PRAGMA user_version").fetchone()[0]
    for target in range(v + 1, SCHEMA_VERSION + 1):
        with conn:
            MIGRATIONS[target](conn)
            conn.execute(f"PRAGMA user_version={target}")
    return conn.execute("PRAGMA user_version").fetchone()[0]

# ---------------------------------------------------------------- utilitaires
def normalize(prompt):
    p = unicodedata.normalize("NFC", prompt).strip()
    return " ".join(p.split())

def canon_params(params):
    return json.dumps(params or {}, sort_keys=True, separators=(",", ":"), ensure_ascii=False)

def make_hash(prompt, model="", params=None):
    raw = normalize(prompt) + "\x1f" + (model or "") + "\x1f" + canon_params(params)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()

def pack(vec):
    return struct.pack(f"<{len(vec)}f", *vec)

def unpack(blob):
    return list(struct.unpack(f"<{len(blob)//4}f", blob))

def quantize(vec):
    """Quantification symétrique par vecteur : int8 = round(v / scale), scale = max|v| / 127."""
    m = max((abs(x) for x in vec), default=0.0)
    scale = (m / 127.0) or 1.0
    q = [max(-127, min(127, int(round(x / scale)))) for x in vec]
    return struct.pack(f"<{len(q)}b", *q), scale

def dequantize(blob, scale):
    return [x * scale for x in struct.unpack(f"<{len(blob)}b", blob)]

try:
    import numpy as _np
except Exception:
    _np = None

def cosine(a, b):
    if _np is not None:
        a, b = _np.asarray(a, dtype=_np.float32), _np.asarray(b, dtype=_np.float32)
        d = float(_np.linalg.norm(a) * _np.linalg.norm(b))
        return float(a @ b) / d if d else 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a)); nb = math.sqrt(sum(y * y for y in b))
    return dot / (na * nb) if na and nb else 0.0

class Embedder:
    """Charge sentence-transformers à la première utilisation ; None si indisponible."""
    _cache = {}
    def __init__(self, model_name=DEFAULT_EMB_MODEL):
        self.model_name = model_name
    def _load(self):
        if self.model_name in Embedder._cache:
            return Embedder._cache[self.model_name]
        m = None
        if os.environ.get("SEEDMESH_NO_EMB") != "1":
            try:
                from sentence_transformers import SentenceTransformer  # import paresseux
                m = SentenceTransformer(self.model_name, device="cpu")
            except Exception:
                m = None  # fallback silencieux
        Embedder._cache[self.model_name] = m
        return m
    @property
    def available(self):
        return self._load() is not None
    def encode(self, text):
        m = self._load()
        if m is None:
            return None
        return [float(x) for x in m.encode(normalize(text), normalize_embeddings=True)]

# ---------------------------------------------------------------- index mémoire
class EmbIndex:
    """Index int8 en mémoire, groupé par (model, params_json, emb_model). numpy si dispo, sinon listes."""
    def __init__(self):
        self.groups = {}  # clé -> {"ids": [], "vecs": [] | ndarray, "dirty": bool}
    def load(self, conn):
        self.groups = {}
        for rid, m, pj, em, blob, sc_ in conn.execute(
                "SELECT id, model, params_json, emb_model, embedding, emb_scale FROM entries "
                "WHERE embedding IS NOT NULL AND emb_scale IS NOT NULL"):
            self.add(rid, (m, pj, em), blob, sc_)
        return self
    def add(self, rid, key, blob, scale):
        g = self.groups.setdefault(key, {"ids": [], "rows": [], "mat": None})
        v = dequantize(blob, scale)
        n = math.sqrt(sum(x * x for x in v)) or 1.0
        v = [x / n for x in v]
        if rid in g["ids"]:
            g["rows"][g["ids"].index(rid)] = v
        else:
            g["ids"].append(rid); g["rows"].append(v)
        g["mat"] = None  # invalidation de la matrice numpy
    def remove_ids(self, ids):
        ids = set(ids)
        for g in self.groups.values():
            keep = [i for i, r in enumerate(g["ids"]) if r not in ids]
            if len(keep) != len(g["ids"]):
                g["ids"] = [g["ids"][i] for i in keep]; g["rows"] = [g["rows"][i] for i in keep]; g["mat"] = None
    def __len__(self):
        return sum(len(g["ids"]) for g in self.groups.values())
    def search(self, key, q):
        g = self.groups.get(key)
        if not g or not g["ids"]:
            return None, -1.0
        n = math.sqrt(sum(x * x for x in q)) or 1.0
        if _np is not None:
            if g["mat"] is None:
                g["mat"] = _np.asarray(g["rows"], dtype=_np.float32)
            s = g["mat"] @ (_np.asarray(q, dtype=_np.float32) / n)
            i = int(_np.argmax(s)); return g["ids"][i], float(s[i])
        best, bs = None, -1.0
        for rid, v in zip(g["ids"], g["rows"]):
            d = sum(a * b for a, b in zip(v, q)) / n
            if d > bs: best, bs = rid, d
        return best, bs

# ---------------------------------------------------------------- cache
class SeedMeshCache:
    def __init__(self, db_path=DEFAULT_DB, use_embeddings=True, emb_model=DEFAULT_EMB_MODEL,
                 threshold=DEFAULT_THRESHOLD, readonly=False, max_mb=None):
        self.db_path = os.path.abspath(db_path)
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        if readonly:
            self.conn = sqlite3.connect(f"file:{self.db_path}?mode=ro", uri=True, check_same_thread=False)
        else:
            self.conn = sqlite3.connect(self.db_path, timeout=10, check_same_thread=False)
            self.conn.execute("PRAGMA journal_mode=WAL")
            self.conn.execute("PRAGMA synchronous=NORMAL")
            migrate(self.conn)
        self.conn.row_factory = sqlite3.Row
        self.embedder = Embedder(emb_model) if use_embeddings else None
        self.threshold = threshold
        self.readonly = readonly
        self.max_mb = MAX_MB if max_mb is None else max_mb
        if not readonly:
            with self.conn:
                convert_float_embeddings(self.conn)  # float32 écrits par une vieille version
        self.index = EmbIndex().load(self.conn) if use_embeddings else EmbIndex()

    def close(self):
        self.conn.close()

    def _touch(self, row_id):
        if not self.readonly:
            with self.conn:
                self.conn.execute("UPDATE entries SET hits=hits+1, last_hit=? WHERE id=?", (time.time(), row_id))

    def get(self, prompt, model="", params=None, semantic=True):
        """Retourne dict {response, match: exact|semantic, score, id} ou None."""
        h = make_hash(prompt, model, params)
        r = self.conn.execute("SELECT id, response FROM entries WHERE prompt_hash=?", (h,)).fetchone()
        if r:
            self._touch(r["id"])
            return {"response": r["response"], "match": "exact", "score": 1.0, "id": r["id"], "prompt_hash": h}
        if not (semantic and self.embedder and self.embedder.available):
            return None
        q = self.embedder.encode(prompt)
        rid, score = self.index.search((model or "", canon_params(params), self.embedder.model_name), q)
        if rid is not None and score >= self.threshold:
            r = self.conn.execute("SELECT response FROM entries WHERE id=?", (rid,)).fetchone()
            if r:
                self._touch(rid)
                return {"response": r["response"], "match": "semantic", "score": round(score, 4), "id": rid}
        return None

    def put(self, prompt, response, model="", params=None, auto_gc=True):
        h = make_hash(prompt, model, params)
        emb, scale, emb_model = None, None, None
        if self.embedder and self.embedder.available:
            v = self.embedder.encode(prompt)
            if v:
                (emb, scale), emb_model = quantize(v), self.embedder.model_name
        pj = canon_params(params)
        with self.conn:
            self.conn.execute(
                "INSERT INTO entries(prompt_hash,prompt,response,model,params_json,embedding,emb_scale,emb_model,created_at,hits) "
                "VALUES(?,?,?,?,?,?,?,?,?,0) ON CONFLICT(prompt_hash) DO UPDATE SET response=excluded.response, "
                "embedding=COALESCE(excluded.embedding, entries.embedding), emb_scale=COALESCE(excluded.emb_scale, entries.emb_scale), "
                "emb_model=COALESCE(excluded.emb_model, entries.emb_model)",
                (h, prompt, response, model or "", pj, emb, scale, emb_model, time.time()))
        if emb is not None:  # mise à jour incrémentale de l'index
            rid = self.conn.execute("SELECT id FROM entries WHERE prompt_hash=?", (h,)).fetchone()[0]
            self.index.add(rid, (model or "", pj, emb_model), emb, scale)
        if auto_gc and self.max_mb:
            self.evict_to_size(self.max_mb)
        return h

    # ---- taille / LRU / gc
    def size_bytes(self):
        return self.conn.execute(
            "SELECT COALESCE(SUM(LENGTH(CAST(prompt AS BLOB))+LENGTH(CAST(response AS BLOB))+LENGTH(params_json)"
            "+COALESCE(LENGTH(embedding),0)+?),0) FROM entries", (ROW_OVERHEAD,)).fetchone()[0]

    def evict_to_size(self, max_mb):
        """Supprime les entrées les moins récemment utilisées jusqu'à passer sous max_mb (taille logique)."""
        limit = int(max_mb * 1024 * 1024); total = self.size_bytes()
        if total <= limit:
            return 0
        victims = []
        for rid, sz in self.conn.execute(
                "SELECT id, LENGTH(CAST(prompt AS BLOB))+LENGTH(CAST(response AS BLOB))+LENGTH(params_json)"
                "+COALESCE(LENGTH(embedding),0)+? FROM entries ORDER BY COALESCE(last_hit, created_at) ASC, id ASC",
                (ROW_OVERHEAD,)):
            if total <= limit: break
            victims.append(rid); total -= sz
        with self.conn:
            self.conn.executemany("DELETE FROM entries WHERE id=?", [(v,) for v in victims])
        self.index.remove_ids(victims)
        return len(victims)

    def gc(self, kv_dir=None, max_mb=None):
        """LRU + nettoyage KV : lignes pointant vers des fichiers absents, puis kv/*.bin non référencés."""
        kv_dir = kv_dir or os.path.join(HOME, "kv")
        evicted = self.evict_to_size(max_mb if max_mb is not None else self.max_mb) if (max_mb or self.max_mb) else 0
        dead = 0
        with self.conn:
            for ph, m, p in self.conn.execute("SELECT prefix_hash, model, path FROM kv_snapshots").fetchall():
                if not os.path.exists(p):
                    self.conn.execute("DELETE FROM kv_snapshots WHERE prefix_hash=? AND model=?", (ph, m)); dead += 1
        refs = {os.path.abspath(r[0]) for r in self.conn.execute("SELECT path FROM kv_snapshots")}
        # kv_prefixes : noms de fichiers côté llama-server (--slot-save-path), on garde ceux-là aussi
        refs |= {os.path.abspath(os.path.join(kv_dir, r[0])) for r in self.conn.execute("SELECT slot_file FROM kv_prefixes")}
        orphans = 0
        if os.path.isdir(kv_dir):
            for f in os.listdir(kv_dir):
                p = os.path.abspath(os.path.join(kv_dir, f))
                if f.endswith(".bin") and p not in refs:
                    os.remove(p); orphans += 1
        return {"evicted": evicted, "dead_kv_rows": dead, "orphan_files": orphans}

    # ---- sync JSONL
    def iter_records(self, since=None):
        sql = ("SELECT prompt_hash,prompt,response,model,params_json,embedding,emb_scale,emb_model,created_at,hits,last_hit "
               "FROM entries")
        args = ()
        if since is not None:
            sql += " WHERE MAX(created_at, COALESCE(last_hit, 0)) >= ?"; args = (since,)
        for r in self.conn.execute(sql + " ORDER BY id", args):
            d = dict(r); d["params"] = json.loads(d["params_json"])  # params_json canonique gardé pour PS
            e = d.pop("embedding")
            d["embedding_b64"] = base64.b64encode(e).decode() if e is not None and d["emb_scale"] is not None else None
            if d["embedding_b64"] is None: d["emb_scale"] = d["emb_model"] = None
            yield d

    def merge_records(self, records):
        """Import idempotent par prompt_hash : hits = max, last_hit = max, embedding si compatible."""
        stats = {"inserted": 0, "updated": 0, "skipped": 0}
        local_em = self.embedder.model_name if self.embedder else None
        with self.conn:
            for d in records:
                h = d["prompt_hash"]; pj = canon_params(d.get("params"))
                if make_hash(d["prompt"], d.get("model", ""), d.get("params")) != h:
                    stats["skipped"] += 1; continue  # enregistrement incohérent
                emb = base64.b64decode(d["embedding_b64"]) if d.get("embedding_b64") else None
                sc_, em = d.get("emb_scale"), d.get("emb_model")
                if emb is not None and (sc_ is None or (local_em and em != local_em)):
                    emb = sc_ = em = None  # embedding incompatible : ignoré
                cur = self.conn.execute("SELECT id, hits, last_hit, embedding, emb_model FROM entries WHERE prompt_hash=?", (h,)).fetchone()
                if cur is None:
                    self.conn.execute(
                        "INSERT INTO entries(prompt_hash,prompt,response,model,params_json,embedding,emb_scale,emb_model,created_at,hits,last_hit) "
                        "VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                        (h, d["prompt"], d["response"], d.get("model", ""), pj, emb, sc_, em,
                         d.get("created_at") or time.time(), int(d.get("hits") or 0), d.get("last_hit")))
                    stats["inserted"] += 1
                else:
                    lh = max([x for x in (cur["last_hit"], d.get("last_hit")) if x is not None], default=None)
                    take_emb = cur["embedding"] is None and emb is not None
                    self.conn.execute(
                        "UPDATE entries SET hits=MAX(hits,?), last_hit=?, embedding=CASE WHEN ? THEN ? ELSE embedding END, "
                        "emb_scale=CASE WHEN ? THEN ? ELSE emb_scale END, emb_model=CASE WHEN ? THEN ? ELSE emb_model END WHERE id=?",
                        (int(d.get("hits") or 0), lh, take_emb, emb, take_emb, sc_, take_emb, em, cur["id"]))
                    stats["updated"] += 1
        if self.embedder:
            self.index.load(self.conn)
        if self.max_mb:
            self.evict_to_size(self.max_mb)
        return stats

    def import_jsonl(self, f):
        return self.merge_records(json.loads(l) for l in f if l.strip())

    def stats(self):
        c = self.conn
        return {
            "db": self.db_path,
            "schema_version": c.execute("PRAGMA user_version").fetchone()[0],
            "entries": c.execute("SELECT COUNT(*) FROM entries").fetchone()[0],
            "with_embedding": c.execute("SELECT COUNT(*) FROM entries WHERE embedding IS NOT NULL").fetchone()[0],
            "total_hits": c.execute("SELECT COALESCE(SUM(hits),0) FROM entries").fetchone()[0],
            "kv_snapshots": c.execute("SELECT COUNT(*) FROM kv_snapshots").fetchone()[0],
            "kv_prefixes": c.execute("SELECT COUNT(*) FROM kv_prefixes").fetchone()[0],
            "size_mb": round(self.size_bytes() / 1048576, 3), "max_mb": self.max_mb,
            "index_vectors": len(self.index),
            "embeddings_available": bool(self.embedder and self.embedder.available),
            "numpy": _np is not None,
        }

    def prune(self, older_than_days=None, max_entries=None):
        """Supprime les entrées anciennes (dernier accès) et/ou garde les max_entries plus récemment utilisées (LRU)."""
        n = 0
        with self.conn:
            if older_than_days is not None:
                cut = time.time() - older_than_days * 86400
                n += self.conn.execute("DELETE FROM entries WHERE COALESCE(last_hit, created_at) < ?", (cut,)).rowcount
            if max_entries is not None:
                n += self.conn.execute(
                    "DELETE FROM entries WHERE id NOT IN (SELECT id FROM entries "
                    "ORDER BY COALESCE(last_hit, created_at) DESC LIMIT ?)", (max_entries,)).rowcount
        if n: self.index.load(self.conn)
        return n

    def export_jsonl(self, out, since=None):
        k = 0
        for d in self.iter_records(since):
            out.write(json.dumps(d, ensure_ascii=False) + "\n"); k += 1
        return k

    # ---- KV snapshots (fichiers de session llama.cpp)
    def kv_get(self, prefix_hash, model=""):
        r = self.conn.execute("SELECT path FROM kv_snapshots WHERE prefix_hash=? AND model=?", (prefix_hash, model or "")).fetchone()
        return r["path"] if r and os.path.exists(r["path"]) else None

    def kv_put(self, prefix_hash, path, model=""):
        with self.conn:
            self.conn.execute("INSERT OR REPLACE INTO kv_snapshots(prefix_hash,path,model,created_at) VALUES(?,?,?,?)",
                              (prefix_hash, os.path.abspath(path), model or "", time.time()))

# ---------------------------------------------------------------- serveur HTTP
def serve(cache, host="127.0.0.1", port=8765):
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
    import threading
    lock = threading.Lock()

    class H(BaseHTTPRequestHandler):
        def _send(self, code, obj):
            b = json.dumps(obj, ensure_ascii=False).encode("utf-8")
            self.send_response(code); self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b)
        def log_message(self, *a): pass
        def do_GET(self):
            from urllib.parse import urlparse, parse_qs
            u = urlparse(self.path)
            if u.path == "/stats":
                with lock: return self._send(200, cache.stats())
            if u.path == "/export":  # pull incrémental : /export?since=<epoch>
                since = parse_qs(u.query).get("since", [None])[0]
                with lock: recs = list(cache.iter_records(float(since) if since else None))
                return self._send(200, {"records": recs, "now": time.time()})
            self._send(404, {"error": "not found"})
        def do_POST(self):
            try:
                n = int(self.headers.get("Content-Length", "0"))
                body = json.loads(self.rfile.read(n) or b"{}")
                if self.path == "/lookup":
                    with lock:
                        r = cache.get(body["prompt"], body.get("model", ""), body.get("params"), body.get("semantic", True))
                    return self._send(200, {"hit": bool(r), **(r or {})})
                if self.path == "/put":
                    with lock:
                        h = cache.put(body["prompt"], body["response"], body.get("model", ""), body.get("params"))
                    return self._send(200, {"ok": True, "prompt_hash": h})
                if self.path == "/put_batch":
                    with lock: st = cache.merge_records(body["records"])
                    return self._send(200, {"ok": True, **st})
                self._send(404, {"error": "not found"})
            except (KeyError, ValueError) as e:
                self._send(400, {"error": f"requête invalide: {e}"})
    srv = ThreadingHTTPServer((host, port), H)
    print(f"SeedMesh cache sur http://{host}:{port} (db={cache.db_path})", file=sys.stderr)
    try: srv.serve_forever()
    except KeyboardInterrupt: pass

# ---------------------------------------------------------------- CLI
def main(argv=None):
    ap = argparse.ArgumentParser(description="Cache sémantique SeedMesh")
    ap.add_argument("--db", default=DEFAULT_DB)
    ap.add_argument("--no-emb", action="store_true", help="désactive les embeddings")
    ap.add_argument("--threshold", type=float, default=DEFAULT_THRESHOLD)
    ap.add_argument("--model", default="")
    ap.add_argument("--params", default="{}", help="JSON des paramètres de génération")
    sp = ap.add_subparsers(dest="cmd", required=True)
    g = sp.add_parser("get"); g.add_argument("prompt"); g.add_argument("--exact", action="store_true")
    p = sp.add_parser("put"); p.add_argument("prompt"); p.add_argument("response")
    sp.add_parser("stats")
    pr = sp.add_parser("prune"); pr.add_argument("--days", type=float); pr.add_argument("--max", type=int)
    ex = sp.add_parser("export-jsonl"); ex.add_argument("-o", "--out"); ex.add_argument("--since", type=float, help="epoch (s)")
    im = sp.add_parser("import-jsonl", aliases=["merge"]); im.add_argument("file")
    gc_ = sp.add_parser("gc"); gc_.add_argument("--max-mb", type=float); gc_.add_argument("--kv-dir")
    sv = sp.add_parser("serve"); sv.add_argument("--host", default="127.0.0.1"); sv.add_argument("--port", type=int, default=8765)
    a = ap.parse_args(argv)
    c = SeedMeshCache(a.db, use_embeddings=not a.no_emb, threshold=a.threshold)
    params = json.loads(a.params)
    if a.cmd == "get":
        r = c.get(a.prompt, a.model, params, semantic=not a.exact)
        if not r: return 1
        print(r["response"]); print(f"[{r['match']} {r['score']}]", file=sys.stderr)
    elif a.cmd == "put":
        print(c.put(a.prompt, a.response, a.model, params))
    elif a.cmd == "stats":
        print(json.dumps(c.stats(), indent=2, ensure_ascii=False))
    elif a.cmd == "prune":
        print(f"{c.prune(a.days, a.max)} entrée(s) supprimée(s)")
    elif a.cmd == "export-jsonl":
        if a.out:
            with open(a.out, "w", encoding="utf-8") as f: n = c.export_jsonl(f, a.since)
        else: n = c.export_jsonl(sys.stdout, a.since)
        print(f"{n} entrée(s) exportée(s)", file=sys.stderr)
    elif a.cmd in ("import-jsonl", "merge"):
        with open(a.file, encoding="utf-8") as f: print(json.dumps(c.import_jsonl(f), ensure_ascii=False))
    elif a.cmd == "gc":
        print(json.dumps(c.gc(a.kv_dir, a.max_mb), ensure_ascii=False))
    elif a.cmd == "serve":
        serve(c, a.host, a.port)
    return 0

if __name__ == "__main__":
    sys.exit(main())
