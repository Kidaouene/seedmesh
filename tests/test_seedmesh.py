# -*- coding: utf-8 -*-
"""Tests : put/get exact, fallback sans embeddings, migration de schéma, prune, KV."""
import os, sqlite3, sys, tempfile, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["SEEDMESH_NO_EMB"] = "1"
import seedmesh_cache as sc

class T(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp(); self.db = os.path.join(self.d, "c.db")

    def test_put_get_exact(self):
        c = sc.SeedMeshCache(self.db)
        c.put("Bonjour  le monde ", "salut", "m.gguf", {"temp": 0.2})
        r = c.get("bonjour le monde", "m.gguf", {"temp": 0.2})
        self.assertIsNone(r)  # casse différente -> pas d'exact
        r = c.get("  Bonjour le   monde", "m.gguf", {"temp": 0.2})
        self.assertEqual((r["response"], r["match"]), ("salut", "exact"))
        self.assertIsNone(c.get("Bonjour le monde", "autre.gguf", {"temp": 0.2}))
        self.assertIsNone(c.get("Bonjour le monde", "m.gguf", {"temp": 0.7}))
        self.assertEqual(c.stats()["total_hits"], 1)

    def test_fallback_sans_embeddings(self):
        c = sc.SeedMeshCache(self.db, use_embeddings=True)
        self.assertFalse(c.embedder.available)
        c.put("a", "b")
        self.assertIsNone(c.get("a?", semantic=True))
        self.assertEqual(c.stats()["with_embedding"], 0)

    def test_semantique_avec_faux_embedder(self):
        class Fake:
            model_name = "fake"; available = True
            def encode(self, t): return [1.0, 0.0] if "chat" in t else [0.0, 1.0]
        c = sc.SeedMeshCache(self.db); c.embedder = Fake()
        c.put("le chat dort", "zzz")
        r = c.get("un chat qui dort")
        self.assertEqual(r["match"], "semantic")
        self.assertIsNone(c.get("voiture"))

    def test_cosine_pur_python(self):
        np_ = sc._np; sc._np = None
        try: self.assertAlmostEqual(sc.cosine([1, 0], [1, 1]), 0.7071, places=3)
        finally: sc._np = np_

    def test_migration_v1_vers_v2(self):
        conn = sqlite3.connect(self.db); sc._m1(conn); conn.execute("PRAGMA user_version=1")
        conn.execute("INSERT INTO entries(prompt_hash,prompt,response,created_at) VALUES(?,?,?,0)",
                     (sc.make_hash("x"), "x", "y")); conn.commit(); conn.close()
        c = sc.SeedMeshCache(self.db)
        self.assertEqual(c.stats()["schema_version"], sc.SCHEMA_VERSION)
        self.assertEqual(c.get("x")["response"], "y")
        c.kv_put("abc", self.db, "m"); self.assertEqual(c.kv_get("abc", "m"), os.path.abspath(self.db))

    def test_prune_lru(self):
        c = sc.SeedMeshCache(self.db)
        for i in range(5): c.put(f"p{i}", "r")
        c.get("p0")
        self.assertEqual(c.prune(max_entries=2), 3)
        self.assertIsNotNone(c.get("p0"))

if __name__ == "__main__":
    unittest.main(verbosity=2)
