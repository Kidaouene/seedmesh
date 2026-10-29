# -*- coding: utf-8 -*-
"""Parité Python <-> PowerShell (ignoré si pwsh / sqlite3 absents).
SEEDMESH_PWSH=/chemin/pwsh SEEDMESH_SQLITE=/chemin/sqlite3 python tests/test_powershell.py"""
import json, os, shutil, sqlite3, struct, subprocess, sys, tempfile, threading, time, unittest
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT); os.environ["SEEDMESH_NO_EMB"] = "1"
import seedmesh_cache as sc
PWSH = os.environ.get("SEEDMESH_PWSH") or shutil.which("pwsh")
SQLITE = os.environ.get("SEEDMESH_SQLITE") or shutil.which("sqlite3")

@unittest.skipUnless(PWSH and SQLITE, "pwsh ou sqlite3 absent")
class TestPS(unittest.TestCase):
    def setUp(self):
        self.home = tempfile.mkdtemp(); self.db = os.path.join(self.home, "cache.db")
        self.model = os.path.join(self.home, "m.gguf"); open(self.model, "w").close()
        self.count = os.path.join(self.home, "count")
        self.fake = os.path.join(self.home, "fake-llama")
        with open(self.fake, "w") as f:  # faux llama-completion : compte les appels
            f.write(f'#!/bin/sh\necho x >> "{self.count}"\necho "réponse simulée"\n')
        os.chmod(self.fake, 0o755)
        self.cfg = os.path.join(self.home, "config.json")
        json.dump({"providers": [{"name": "local", "priority": 1, "model": self.model}],
                   "sampling": {"seed": 42, "temp": 0.0, "top_p": 0.9, "top_k": 40, "repeat_penalty": 1.1,
                                "ctx": 4096, "n_predict": 512, "threads": 2}, "chat_template": True}, open(self.cfg, "w"))
        self.env = dict(os.environ, SEEDMESH_CONFIG=self.cfg, SEEDMESH_HOME=self.home, SEEDMESH_SQLITE=SQLITE, SEEDMESH_LLAMA_BIN=self.fake)

    def ps(self, script, *args):
        r = subprocess.run([PWSH, "-NoProfile", "-File", os.path.join(ROOT, script), *args],
                           capture_output=True, text=True, env=self.env, timeout=120)
        self.assertEqual(r.returncode, 0, r.stderr + r.stdout); return r.stdout.strip()

    def calls(self):
        return len(open(self.count).read().split()) if os.path.exists(self.count) else 0

    def test_parite_hash_et_schema(self):
        out = self.ps("SeedMesh-Agent.ps1", "  Explique   le KV ", "-Model", self.model, "-System", "Tu es \"bref\"\nété")
        self.assertEqual(out, "réponse simulée"); self.assertEqual(self.calls(), 1)
        self.ps("SeedMesh-Agent.ps1", "Explique le KV", "-Model", self.model, "-System", "Tu es \"bref\"\nété")
        self.assertEqual(self.calls(), 1)  # cache hit côté PS
        c = sc.SeedMeshCache(self.db, use_embeddings=False)
        self.assertEqual(c.stats()["schema_version"], 3)
        p = {"n_predict": 512, "temp": 0.0, "ctx": 4096, "system": "Tu es \"bref\"\nété", "step": "answer",
             "seed": 42, "top_p": 0.9, "top_k": 40, "repeat_penalty": 1.1, "chat": True}
        self.assertEqual(c.get("Explique le KV", "m.gguf", p)["response"], "réponse simulée")  # même hash
        cols = [r[1] for r in c.conn.execute("PRAGMA table_info(entries)")]
        self.assertIn("emb_scale", cols)

    def test_parite_agent_py(self):
        """agent.py (même config) doit retrouver l'entrée écrite par PowerShell, sans appeler llama."""
        self.ps("SeedMesh-Agent.ps1", "Bonjour", "-System", "S")
        r = subprocess.run([sys.executable, os.path.join(ROOT, "agent.py"), "Bonjour", "--system", "S",
                            "--db", self.db, "--no-emb", "--bin", "/bin/false"], capture_output=True, text=True, env=self.env)
        self.assertEqual((r.returncode, r.stdout.strip()), (0, "réponse simulée"), r.stderr)
        self.assertEqual(self.calls(), 1)

    def test_migration_v2_par_ps_puis_python(self):
        conn = sqlite3.connect(self.db); sc._m1(conn); sc._m2(conn); conn.execute("PRAGMA user_version=2")
        conn.execute("INSERT INTO entries(prompt_hash,prompt,response,embedding,emb_model,created_at) VALUES('h','p','r',?,'fake',0)",
                     (struct.pack("<2f", 0.6, 0.8),)); conn.commit(); conn.close()
        self.ps("SeedMesh-Agent.ps1", "-Gc")
        c = sc.SeedMeshCache(self.db, use_embeddings=False)
        self.assertEqual(c.conn.execute("SELECT LENGTH(embedding) FROM entries").fetchone()[0], 2)  # converti int8

    def test_gc_et_lru_ps(self):
        c = sc.SeedMeshCache(self.db, use_embeddings=False)
        for i in range(30): c.put(f"p{i}", "z" * 1000)
        c.conn.execute("UPDATE entries SET created_at=id"); c.conn.commit()
        kv = os.path.join(self.home, "kv"); os.makedirs(kv, exist_ok=True)
        open(os.path.join(kv, "orphan.bin"), "w").close(); c.kv_put("x", os.path.join(kv, "absent.bin"), "m")
        self.env["SEEDMESH_MAX_MB"] = "0.01"
        out = self.ps("SeedMesh-Agent.ps1", "-Gc")
        self.assertIn("orphan_files", out)
        ref = sc.SeedMeshCache(os.path.join(self.home, "ref.db"), use_embeddings=False)
        for i in range(30): ref.put(f"p{i}", "z" * 1000)
        ref.conn.execute("UPDATE entries SET created_at=id"); ref.conn.commit(); ref.evict_to_size(0.01)
        q = "SELECT prompt FROM entries ORDER BY id"
        self.assertEqual([r[0] for r in c.conn.execute(q)], [r[0] for r in ref.conn.execute(q)])  # même LRU
        self.assertFalse(os.path.exists(os.path.join(kv, "orphan.bin")))
        self.assertEqual(c.conn.execute("SELECT COUNT(*) FROM kv_snapshots").fetchone()[0], 0)

    def test_sync_ps(self):
        rdb = os.path.join(self.home, "remote.db")
        remote = sc.SeedMeshCache(rdb, use_embeddings=False); remote.put("distant", "R")
        remote.conn.execute("UPDATE entries SET embedding=?, emb_scale=0.01, emb_model='fake'", (b"\x01\x02",)); remote.conn.commit()
        threading.Thread(target=sc.serve, args=(remote, "127.0.0.1", 18767), daemon=True).start(); time.sleep(0.3)
        self.ps("SeedMesh-Agent.ps1", "local", "-Model", self.model)
        self.ps("Sync-SeedMesh.ps1", "-Url", "http://127.0.0.1:18767")
        self.ps("Sync-SeedMesh.ps1", "-Url", "http://127.0.0.1:18767")  # idempotent
        loc = sc.SeedMeshCache(self.db, use_embeddings=False)
        self.assertEqual(loc.get("distant")["response"], "R")
        self.assertEqual(loc.conn.execute("SELECT embedding FROM entries WHERE prompt='distant'").fetchone()[0], b"\x01\x02")
        self.assertEqual(remote.conn.execute("SELECT COUNT(*) FROM entries").fetchone()[0], 2)
        self.assertEqual(loc.conn.execute("SELECT COUNT(*) FROM entries").fetchone()[0], 2)

import warnings; warnings.simplefilter("ignore", ResourceWarning)
if __name__ == "__main__":
    unittest.main(verbosity=2)
