#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Agent local SeedMesh : cache d'abord, sinon llama.cpp ; Self-Refine et KV cache optionnels.

NB (llama.cpp >= b7348, déc. 2025) : l'ancien `llama-cli` est devenu `llama-completion`.
Le nouveau `llama-cli` est un client basé sur llama-server et N'A PLUS --prompt-cache.
Par défaut on utilise donc `llama-completion` (flags --prompt-cache / --prompt-cache-all / -no-cnv).
Mode --server URL : llama-server --slot-save-path DIR, KV par préfixe de conversation (kv_server.py).
"""
import argparse, hashlib, json, os, re, shutil, subprocess, sys
from seedmesh_cache import SeedMeshCache, DEFAULT_DB, HOME

# ---------------------------------------------------------------- configuration globale
# Ordre de priorité : arguments CLI > variables d'env > config.json > valeurs par défaut.
CONFIG_PATHS = [os.environ.get("SEEDMESH_CONFIG", ""), "/opt/seedmesh/config.json",
                os.path.join(os.path.expanduser("~"), ".seedmesh", "config.json")]
DEFAULT_SAMPLING = {"seed": 42, "temp": 0.0, "top_p": 0.9, "top_k": 40, "repeat_penalty": 1.1,
                    "ctx": 4096, "n_predict": 512, "threads": 4}
# Paramètres qui influencent la sortie => inclus dans le hash (threads exclu)
HASHED = {"seed": int, "top_p": float, "top_k": int, "repeat_penalty": float}

def load_config():
    for p in CONFIG_PATHS:
        if p and os.path.isfile(p):
            with open(p, encoding="utf-8") as f:
                cfg = json.load(f); cfg["_path"] = p; return cfg
    return {}

def local_provider(cfg):
    """Provider de priorité la plus haute (1 = local llama.cpp)."""
    provs = sorted(cfg.get("providers", []), key=lambda p: p.get("priority", 99))
    return provs[0] if provs else {}

CONFIG = load_config()
PROVIDER = local_provider(CONFIG)
SAMPLING = dict(DEFAULT_SAMPLING, **CONFIG.get("sampling", {}))

LLAMA_BIN = (os.environ.get("SEEDMESH_LLAMA_BIN") or PROVIDER.get("llama_completion_bin")
             or shutil.which("llama-completion") or shutil.which("llama-cli") or "llama-completion")
LLAMA_MODEL = os.environ.get("SEEDMESH_MODEL") or PROVIDER.get("model", "")
KV_DIR = os.path.join(HOME, "kv")

CRITIQUE_TPL = ("Question :\n{q}\n\nRéponse proposée :\n{a}\n\nCritique brièvement cette réponse "
                "(exactitude, clarté, complétude). Si elle est satisfaisante, réponds uniquement : OK")
REVISE_TPL = ("Question :\n{q}\n\nRéponse précédente :\n{a}\n\nCritique :\n{c}\n\n"
              "Réécris une réponse améliorée en tenant compte de la critique. Donne seulement la réponse.")

def clean_output(text):
    """Retire les messages techniques que llama-completion écrit sur stdout (session KV, fin de texte)."""
    lines = [l for l in text.splitlines() if not re.match(r"^\s*(llama_completion|main):\s", l)]
    return re.sub(r"\s*\[end of text\]\s*$", "", "\n".join(lines)).strip()

class Agent:
    def __init__(self, cache, bin_path=LLAMA_BIN, model_path=LLAMA_MODEL, n_predict=256, temp=0.2,
                 ctx=2048, timeout=300, system="", kv=False, verbose=False, sampling=None, threads=None,
                 chat=False):
        self.cache, self.bin, self.model_path = cache, bin_path, os.path.abspath(model_path) if model_path else ""
        self.params = {"n_predict": int(n_predict), "temp": float(temp), "ctx": int(ctx)}
        for k, typ in HASHED.items():  # seed/top_p/top_k/repeat_penalty -> dans le hash
            if sampling and sampling.get(k) is not None:
                self.params[k] = typ(sampling[k])
        self.threads, self.chat = threads, chat
        self.model_id = os.path.basename(self.model_path) or "unknown"
        self.timeout, self.system, self.kv, self.verbose = timeout, system, kv, verbose

    def log(self, *a):
        if self.verbose: print("[agent]", *a, file=sys.stderr)

    def _kv_file(self):
        """Fichier de session nommé par hash du préfixe système (+ modèle)."""
        ph = hashlib.sha256((self.model_id + "\x1f" + self.system).encode("utf-8")).hexdigest()[:32]
        path = self.cache.kv_get(ph, self.model_id)
        if not path:
            os.makedirs(KV_DIR, exist_ok=True)
            path = os.path.join(KV_DIR, f"{ph}.bin")
        return ph, path

    def _run_llama(self, prompt):
        if not self.model_path or not os.path.exists(self.model_path):
            raise SystemExit(f"Modèle introuvable : '{self.model_path}' (SEEDMESH_MODEL ou --model)")
        P = self.params
        cmd = [self.bin, "-m", self.model_path, "-n", str(P["n_predict"]), "--temp", str(P["temp"]),
               "-c", str(P["ctx"]), "--no-display-prompt"]
        if self.chat:  # gabarit de chat du modèle (instruct), un seul tour
            cmd += ["-st", "-p", prompt] + (["-sys", self.system] if self.system else [])
        else:          # complétion brute
            cmd += ["-no-cnv", "-p", (self.system + "\n\n" + prompt) if self.system else prompt]
        for k, flag in (("seed", "--seed"), ("top_p", "--top-p"), ("top_k", "--top-k"), ("repeat_penalty", "--repeat-penalty")):
            if k in P: cmd += [flag, str(P[k])]
        if self.threads: cmd += ["-t", str(self.threads)]
        ph = path = None
        if self.kv:
            ph, path = self._kv_file()
            # préfixe stable (système) en tête => llama.cpp réutilise les tokens communs du fichier
            cmd += ["--prompt-cache", path, "--prompt-cache-all"]
        self.log("exec:", " ".join(cmd[:4]), "...")
        try:
            out = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", stdin=subprocess.DEVNULL,
                                 errors="replace", timeout=self.timeout)
        except subprocess.TimeoutExpired:
            raise SystemExit(f"llama.cpp a dépassé le timeout ({self.timeout}s)")
        except FileNotFoundError:
            raise SystemExit(f"Binaire introuvable : {self.bin} (SEEDMESH_LLAMA_BIN ou --bin)")
        if out.returncode != 0:
            raise SystemExit(f"llama.cpp code {out.returncode} :\n{out.stderr[-800:]}")
        if self.kv and path and os.path.exists(path):
            self.cache.kv_put(ph, path, self.model_id)  # snapshot enregistré
        return clean_output(out.stdout)

    def ask_server(self, url, turns, slot=0):
        """Mode llama-server : cache réponse (clé = conversation rendue) puis KV par préfixe via slots."""
        from kv_server import ServerPrefixKV, render
        key = render(self.system, turns)
        params = dict(self.params, system=self.system, step="server")
        hit = self.cache.get(key, self.model_id, params)
        if hit:
            self.log(f"cache {hit['match']} ({hit['score']})"); return hit["response"]
        kv = ServerPrefixKV(self.cache, url, self.model_id, slot, self.timeout)
        extra = {k: self.params[k] for k in HASHED if k in self.params}
        ans, restored = kv.complete(self.system, turns, self.params["n_predict"], self.params["temp"], extra)
        self.log(f"préfixe restauré : {restored} tour(s)" if restored is not None else "aucun préfixe connu")
        self.cache.put(key, ans, self.model_id, params)
        return ans

    def ask(self, prompt, step="answer"):
        params = dict(self.params, system=self.system, step=step)
        if self.chat: params["chat"] = True
        hit = None if getattr(self, "no_cache", False) else self.cache.get(prompt, self.model_id, params)
        if hit:
            self.log(f"cache {hit['match']} ({hit['score']}) [{step}]")
            return hit["response"]
        resp = self._run_llama(prompt)
        self.cache.put(prompt, resp, self.model_id, params)
        return resp

    def refine(self, question, n):
        answer = self.ask(question, "answer")
        for i in range(n):
            crit = self.ask(CRITIQUE_TPL.format(q=question, a=answer), "critique")
            self.log(f"itération {i+1} critique : {crit[:80]!r}")
            if crit.strip().strip(".!").upper().startswith("OK"):
                break
            answer = self.ask(REVISE_TPL.format(q=question, a=answer, c=crit), "revise")
        return answer

def main(argv=None):
    ap = argparse.ArgumentParser(description="Agent local SeedMesh (cache + llama.cpp)")
    ap.add_argument("prompt")
    ap.add_argument("--db", default=DEFAULT_DB)
    ap.add_argument("--bin", default=LLAMA_BIN)
    ap.add_argument("--model", default=LLAMA_MODEL)
    ap.add_argument("--system", default=os.environ.get("SEEDMESH_SYSTEM", ""))
    ap.add_argument("-n", "--n-predict", type=int, default=SAMPLING["n_predict"])
    ap.add_argument("--temp", type=float, default=SAMPLING["temp"])
    ap.add_argument("--ctx", type=int, default=SAMPLING["ctx"])
    ap.add_argument("--seed", type=int, default=SAMPLING["seed"])
    ap.add_argument("--top-p", type=float, default=SAMPLING["top_p"])
    ap.add_argument("--top-k", type=int, default=SAMPLING["top_k"])
    ap.add_argument("--repeat-penalty", type=float, default=SAMPLING["repeat_penalty"])
    ap.add_argument("-t", "--threads", type=int, default=SAMPLING["threads"])
    ap.add_argument("--raw", action="store_true", help="complétion brute (-no-cnv) au lieu du gabarit de chat")
    ap.add_argument("--no-cache", action="store_true", help="ignore la lecture du cache (écrit quand même)")
    ap.add_argument("--timeout", type=int, default=300)
    ap.add_argument("--refine", type=int, default=0, metavar="N")
    ap.add_argument("--kv", action="store_true", help="active --prompt-cache (snapshot KV par préfixe système)")
    ap.add_argument("--server", metavar="URL", default=None, help="mode llama-server (KV par préfixe via /slots)")
    ap.add_argument("--slot", type=int, default=0)
    ap.add_argument("--history", help="JSON [{role,content},...] des tours précédents (mode --server)")
    ap.add_argument("--no-emb", action="store_true")
    ap.add_argument("--threshold", type=float, default=None)
    ap.add_argument("-v", "--verbose", action="store_true")
    a = ap.parse_args(argv)
    kw = {} if a.threshold is None else {"threshold": a.threshold}
    cache = SeedMeshCache(a.db, use_embeddings=not a.no_emb, **kw)
    samp = {"seed": a.seed, "top_p": a.top_p, "top_k": a.top_k, "repeat_penalty": a.repeat_penalty}
    chat = not a.raw and CONFIG.get("chat_template", True)
    ag = Agent(cache, a.bin, a.model, a.n_predict, a.temp, a.ctx, a.timeout, a.system, a.kv, a.verbose,
               sampling=samp, threads=a.threads, chat=chat)
    ag.no_cache = a.no_cache
    if CONFIG: ag.log("config :", CONFIG["_path"])
    if a.server:
        import json
        turns = json.load(open(a.history, encoding="utf-8")) if a.history else []
        print(ag.ask_server(a.server, turns + [{"role": "user", "content": a.prompt}], a.slot))
    else:
        print(ag.refine(a.prompt, a.refine) if a.refine > 0 else ag.ask(a.prompt))

if __name__ == "__main__":
    main()
