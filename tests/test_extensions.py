# -*- coding: utf-8 -*-
"""Tests des extensions : int8 + index, LRU Mo + gc, KV par préfixe (llama-server mocké), sync."""
import base64, io, json, os, shutil, sqlite3, struct, sys, tempfile, threading, time, unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.environ["SEEDMESH_NO_EMB"] = "1"
import seedmesh_cache as sc, kv_server, sync

class Fake:
    model_name = "fake"; available = True
    def encode(self, t):
        v = [1.0, 0.2, 0.0] if "chat" in t else [0.0, 0.3, 1.0]
        n = sum(x * x for x in v) ** .5; return [x / n for x in v]

def mk(db, **kw):
    c = sc.SeedMeshCache(db, **kw); c.embedder = Fake(); return c

class Base(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp(); self.db = os.path.join(self.d, "c.db")

class TestInt8(Base):
    def test_quantize_roundtrip(self):
        v = [0.5, -0.25, 0.1, -1.0]
        b, s = sc.quantize(v)
        self.assertEqual(len(b), 4)
        for a, x in zip(v, sc.dequantize(b, s)): self.assertAlmostEqual(a, x, delta=s)
        self.assertGreater(sc.cosine(v, sc.dequantize(b, s)), 0.999)

    def test_put_int8_et_index(self):
        c = mk(self.db); c.put("le chat dort", "zzz")
        row = c.conn.execute("SELECT LENGTH(embedding), emb_scale FROM entries").fetchone()
        self.assertEqual(row[0], 3); self.assertIsNotNone(row[1])
        self.assertEqual(len(c.index), 1)  # index mis à jour sur put, sans rechargement
        self.assertEqual(c.get("un chat")["match"], "semantic")
        self.assertIsNone(c.get("voiture"))

    def test_fallback_pur_python(self):
        np_ = sc._np; sc._np = None
        try:
            c = mk(self.db); c.put("le chat dort", "zzz"); self.assertEqual(c.get("un chat")["response"], "zzz")
        finally: sc._np = np_

    def test_migration_v2_float32_vers_int8(self):
        conn = sqlite3.connect(self.db); sc._m1(conn); sc._m2(conn); conn.execute("PRAGMA user_version=2")
        v = Fake().encode("chat")
        conn.execute("INSERT INTO entries(prompt_hash,prompt,response,model,params_json,embedding,emb_model,created_at) "
                     "VALUES(?,?,?,?,?,?,?,0)", (sc.make_hash("le chat"), "le chat", "miaou", "", "{}",
                                                 struct.pack("<3f", *v), "fake"))
        conn.commit(); conn.close()
        c = mk(self.db)
        st = c.stats(); self.assertEqual(st["schema_version"], 3)
        self.assertEqual(c.conn.execute("SELECT LENGTH(embedding) FROM entries").fetchone()[0], 3)
        self.assertEqual(len(c.index), 1)  # index chargé au démarrage
        self.assertEqual(c.get("chat noir")["response"], "miaou")

class TestLRU(Base):
    def test_plafond_mo_apres_put(self):
        c = sc.SeedMeshCache(self.db, use_embeddings=False, max_mb=0.01)  # ~10 Ko
        for i in range(40):
            c.put(f"p{i}", "x" * 500); c.conn.execute("UPDATE entries SET created_at=? WHERE prompt=?", (i, f"p{i}")); c.conn.commit()
        self.assertLessEqual(c.size_bytes(), 0.01 * 1048576)
        self.assertIsNotNone(c.get("p39")); self.assertIsNone(c.get("p0"))

    def test_lru_garde_les_recemment_lus(self):
        c = sc.SeedMeshCache(self.db, use_embeddings=False)
        for i in range(5): c.put(f"p{i}", "y" * 1000)
        for i in range(5): c.conn.execute("UPDATE entries SET created_at=? WHERE prompt=?", (i, f"p{i}"))
        c.conn.commit(); c.get("p0")  # p0 devient le plus récent
        c.evict_to_size(2.5 * 1220 / 1048576)
        left = {r[0] for r in c.conn.execute("SELECT prompt FROM entries")}
        self.assertEqual(left, {"p0", "p4"})

    def test_gc_kv(self):
        kv = os.path.join(self.d, "kv"); os.makedirs(kv)
        keep, orphan, slot = (os.path.join(kv, n) for n in ("keep.bin", "orphan.bin", "slot.bin"))
        for p in (keep, orphan, slot): open(p, "wb").write(b"x")
        c = sc.SeedMeshCache(self.db, use_embeddings=False)
        c.kv_put("a", keep, "m"); c.kv_put("b", os.path.join(kv, "absent.bin"), "m")
        c.conn.execute("INSERT INTO kv_prefixes VALUES('h','m','slot.bin',2,0,NULL)"); c.conn.commit()
        r = c.gc(kv_dir=kv)
        self.assertEqual((r["dead_kv_rows"], r["orphan_files"]), (1, 1))
        self.assertTrue(os.path.exists(keep) and os.path.exists(slot) and not os.path.exists(orphan))

def serve_mock(handler_state):
    class H(BaseHTTPRequestHandler):
        def log_message(self, *a): pass
        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            handler_state["calls"].append((self.path, body))
            if "action=restore" in self.path and body["filename"] not in handler_state["files"]:
                self.send_response(400); self.end_headers(); return
            if "action=save" in self.path: handler_state["files"].add(body["filename"])
            out = {"content": f" réponse {len(handler_state['calls'])} "} if self.path == "/completion" else {"ok": True}
            b = json.dumps(out).encode(); self.send_response(200); self.send_header("Content-Length", str(len(b)))
            self.end_headers(); self.wfile.write(b)
    srv = ThreadingHTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, f"http://127.0.0.1:{srv.server_address[1]}"

class TestPrefixKV(Base):
    def test_restore_plus_long_prefixe(self):
        st = {"calls": [], "files": set()}; srv, url = serve_mock(st)
        try:
            c = sc.SeedMeshCache(self.db, use_embeddings=False)
            kv = kv_server.ServerPrefixKV(c, url, "m.gguf")
            t1 = [{"role": "user", "content": "Bonjour"}]
            a1, r1 = kv.complete("sys", t1)
            self.assertIsNone(r1)
            self.assertEqual([p for p, _ in st["calls"]], ["/completion", "/slots/0?action=save"])
            t2 = t1 + [{"role": "assistant", "content": a1}, {"role": "user", "content": "Et ensuite ?"}]
            st["calls"].clear(); a2, r2 = kv.complete("sys", t2)
            self.assertEqual(r2, 2)  # préfixe système + 2 tours restauré
            self.assertEqual(st["calls"][0][0], "/slots/0?action=restore")
            self.assertEqual(st["calls"][1][1]["id_slot"], 0)
            self.assertTrue(st["calls"][1][1]["prompt"].startswith(kv_server.render("sys", t2[:2])))
            self.assertEqual(c.conn.execute("SELECT COUNT(*) FROM kv_prefixes").fetchone()[0], 2)
            # fichier perdu côté serveur -> ligne supprimée, génération quand même
            st["files"].clear(); st["calls"].clear()
            kv.complete("sys", t2 + [{"role": "assistant", "content": a2}, {"role": "user", "content": "?"}])
            self.assertEqual([p for p, _ in st["calls"]][1:], ["/completion", "/slots/0?action=save"])
        finally: srv.shutdown()

    def test_hash_prefixes_cumulatifs(self):
        t = [{"role": "user", "content": "a"}, {"role": "assistant", "content": "b"}]
        self.assertEqual(kv_server.prefix_hashes("m", "s", t)[:2], kv_server.prefix_hashes("m", "s", t[:1]))

    def test_agent_mode_server_cache(self):
        import agent
        st = {"calls": [], "files": set()}; srv, url = serve_mock(st)
        try:
            c = sc.SeedMeshCache(self.db, use_embeddings=False)
            ag = agent.Agent(c, model_path="", system="sys")
            t = [{"role": "user", "content": "Q"}]
            a = ag.ask_server(url, t); n = len(st["calls"])
            self.assertEqual(ag.ask_server(url, t), a); self.assertEqual(len(st["calls"]), n)  # 2e appel = cache
        finally: srv.shutdown()

class TestSync(Base):
    def test_export_since_import_idempotent(self):
        a = mk(self.db); a.put("le chat", "r1"); t = time.time() + 0.01; time.sleep(0.02); a.put("autre", "r2")
        buf = io.StringIO(); self.assertEqual(a.export_jsonl(buf, since=t), 1)
        full = io.StringIO(); a.export_jsonl(full)
        b = mk(os.path.join(self.d, "b.db"))
        s1 = b.import_jsonl(io.StringIO(full.getvalue())); s2 = b.import_jsonl(io.StringIO(full.getvalue()))
        self.assertEqual((s1["inserted"], s2["inserted"], s2["updated"]), (2, 0, 2))
        self.assertEqual(b.get("un chat")["response"], "r1")  # embedding importé + index rechargé

    def test_merge_hits_max_et_embedding_incompatible(self):
        a = mk(self.db); a.put("x", "r")
        a.conn.execute("UPDATE entries SET hits=7, last_hit=100"); a.conn.commit()
        rec = next(a.iter_records())
        b = sc.SeedMeshCache(os.path.join(self.d, "b.db"), use_embeddings=False); b.put("x", "r")
        b.conn.execute("UPDATE entries SET hits=3, last_hit=200"); b.conn.commit()
        b.merge_records([rec])
        self.assertEqual(tuple(b.conn.execute("SELECT hits, last_hit FROM entries").fetchone()), (7, 200))
        c = mk(os.path.join(self.d, "c2.db")); c.embedder.model_name = "autre-modele"
        c.merge_records([rec]); self.assertIsNone(c.conn.execute("SELECT embedding FROM entries").fetchone()[0])
        rec2 = dict(rec, response="pirate", prompt="falsifié"); self.assertEqual(c.merge_records([rec2])["skipped"], 1)

    def test_sync_http_push_pull(self):
        remote = sc.SeedMeshCache(os.path.join(self.d, "r.db"), use_embeddings=False)
        remote.put("distant", "R")
        th = threading.Thread(target=sc.serve, args=(remote, "127.0.0.1", 18766), daemon=True); th.start(); time.sleep(0.3)
        local = sc.SeedMeshCache(self.db, use_embeddings=False); local.put("local", "L")
        state = os.path.join(self.d, "state.json")
        r = sync.sync(local, "http://127.0.0.1:18766", "both", state)
        self.assertEqual((r["push"]["inserted"], r["pull"]["inserted"]), (1, 1))
        self.assertEqual(local.get("distant")["response"], "R")
        r2 = sync.sync(local, "http://127.0.0.1:18766", "both", state)  # incrémental
        self.assertEqual(r2["pull"]["inserted"], 0)
        self.assertIn("distant", {x[0] for x in local.conn.execute("SELECT prompt FROM entries")})

import warnings; warnings.simplefilter("ignore", ResourceWarning)

if __name__ == "__main__":
    unittest.main(verbosity=2)
