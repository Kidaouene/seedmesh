# -*- coding: utf-8 -*-
"""Cache KV par préfixe de conversation via les slots de llama-server.

llama-server -m model.gguf --slot-save-path <SEEDMESH_HOME>/kv  [-np 1]
  POST /slots/{id}?action=save    {"filename": "<hash>.bin"}
  POST /slots/{id}?action=restore {"filename": "<hash>.bin"}
  POST /completion {"prompt":..., "id_slot": id, "cache_prompt": true, "n_predict":..., "temperature":...}

Principe : chaque préfixe de conversation (système + tours 1..k) a un hash cumulatif.
Avant la requête on restaure le plus long préfixe connu (table kv_prefixes), on génère,
puis on sauvegarde l'état du slot sous le hash de la conversation complète (réponse incluse).
"""
import hashlib, json, time, urllib.request

def render(system, turns):
    """Gabarit texte simple et STABLE (le préfixe doit être identique token pour token)."""
    out = f"### system\n{system}\n" if system else ""
    for t in turns:
        out += f"### {t['role']}\n{t['content']}\n"
    return out

def prefix_hashes(model, system, turns):
    """h[k] = hash du préfixe système + turns[:k] (k = 0..len). Chaînage cumulatif."""
    h = hashlib.sha256((model + "\x1f" + system).encode("utf-8"))
    out = [h.hexdigest()]
    for t in turns:
        h.update(("\x1e" + t["role"] + "\x1f" + t["content"]).encode("utf-8"))
        out.append(h.copy().hexdigest())
    return out

class ServerPrefixKV:
    def __init__(self, cache, url, model_id, slot=0, timeout=300):
        self.cache, self.url, self.model, self.slot, self.timeout = cache, url.rstrip("/"), model_id, slot, timeout

    def _post(self, path, body):
        req = urllib.request.Request(self.url + path, data=json.dumps(body).encode(), method="POST",
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=self.timeout) as r:
            return json.loads(r.read() or b"{}")

    def longest_known(self, hashes):
        for k in range(len(hashes) - 1, -1, -1):
            r = self.cache.conn.execute("SELECT slot_file FROM kv_prefixes WHERE prefix_hash=? AND model=?",
                                        (hashes[k], self.model)).fetchone()
            if r:
                return k, r[0]
        return -1, None

    def _record(self, h, fname, n_turns):
        with self.cache.conn:
            self.cache.conn.execute(
                "INSERT INTO kv_prefixes(prefix_hash,model,slot_file,n_turns,created_at,last_used) VALUES(?,?,?,?,?,?) "
                "ON CONFLICT(prefix_hash,model) DO UPDATE SET last_used=excluded.last_used",
                (h, self.model, fname, n_turns, time.time(), time.time()))

    def complete(self, system, turns, n_predict=256, temperature=0.2, extra=None):
        """turns = [{"role": "user"|"assistant", "content": str}, ...] ; le dernier est la question."""
        hs = prefix_hashes(self.model, system, turns)
        k, fname = self.longest_known(hs)
        restored = None
        if fname:
            try:
                self._post(f"/slots/{self.slot}?action=restore", {"filename": fname})
                restored = k
                with self.cache.conn:
                    self.cache.conn.execute("UPDATE kv_prefixes SET last_used=? WHERE prefix_hash=? AND model=?",
                                            (time.time(), hs[k], self.model))
            except Exception:
                with self.cache.conn:  # fichier disparu côté serveur : on oublie la ligne
                    self.cache.conn.execute("DELETE FROM kv_prefixes WHERE prefix_hash=? AND model=?", (hs[k], self.model))
        prompt = render(system, turns) + "### assistant\n"
        r = self._post("/completion", {"prompt": prompt, "id_slot": self.slot, "cache_prompt": True,
                                       "n_predict": n_predict, "temperature": temperature, **(extra or {})})
        answer = (r.get("content") or "").strip()
        full = turns + [{"role": "assistant", "content": answer}]
        h_full = prefix_hashes(self.model, system, full)[-1]
        fname = f"{h_full[:32]}.bin"
        try:
            self._post(f"/slots/{self.slot}?action=save", {"filename": fname})
            self._record(h_full, fname, len(full))
        except Exception:
            pass  # sauvegarde best-effort
        return answer, restored
