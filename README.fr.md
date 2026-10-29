# SeedMesh — cache sémantique + agent local (Termux / Windows)

| Fichier | Rôle |
|---|---|
| `seedmesh_cache.py` | Cache SQLite (WAL, schéma versionné `PRAGMA user_version`), lookup exact + sémantique optionnel, CLI, mini-serveur HTTP |
| `agent.py` | Cache → sinon llama.cpp ; `--refine N` (Self-Refine) ; `--kv` (snapshot KV par préfixe système) |
| `SeedMesh-Agent.ps1` | Équivalent PowerShell 7 (même DB, même hash, exact uniquement) |
| `kv_server.py` | KV cache par préfixe de conversation via les slots de `llama-server` (`agent.py --server URL`) |
| `sync.py` / `Sync-SeedMesh.ps1` | Synchronisation HTTP push/pull Termux ↔ PC (KV exclus) |
| `tests/test_seedmesh.py` | Tests unitaires de base (stdlib) |
| `tests/test_extensions.py` | int8 + index, LRU Mo + gc, KV préfixe (llama-server mocké), sync |
| `tests/test_powershell.py` | Parité Python ↔ PowerShell de bout en bout (ignoré si pwsh/sqlite3 absents) |
| `tests/check_ps_parity.ps1` | Vérifie syntaxe .ps1 + hash identique à Python |

## ⚠️ llama.cpp : `llama-cli` vs `llama-completion`
Depuis la build **b7348 (déc. 2025)**, l'ancien `llama-cli` a été renommé **`llama-completion`** ; le nouveau `llama-cli`
est un client basé sur `llama-server` qui **n'a plus `--prompt-cache`**. Les scripts utilisent donc `llama-completion` par défaut
(`SEEDMESH_LLAMA_BIN` pour forcer un autre binaire, p.ex. un vieux `llama-cli` < b7348).
Flags utilisés : `-m -p -n --temp -c --no-display-prompt -no-cnv --prompt-cache FICHIER --prompt-cache-all`.

**Alternative serveur** (KV gardé en RAM entre requêtes) : `llama-server -m model.gguf --slot-save-path ~/.seedmesh/kv`
(`--cache-prompt` actif par défaut), puis `POST /slots/0?action=save` `{"filename":"<prefix_hash>.bin"}` et
`POST /slots/0?action=restore` avec le même nom. La table `kv_snapshots` sert aussi à indexer ces fichiers.

## Installation Termux (Android)
```bash
pkg update && pkg install python sqlite clang git cmake
# llama.cpp
git clone https://github.com/ggml-org/llama.cpp && cd llama.cpp && cmake -B build && cmake --build build -j4 --target llama-completion
export SEEDMESH_LLAMA_BIN=$HOME/llama.cpp/build/bin/llama-completion
export SEEDMESH_MODEL=$HOME/models/qwen2.5-1.5b-instruct-q4_k_m.gguf
# optionnel : embeddings (lourd : torch). Sur Android, rester sur un modèle léger :
pip install numpy sentence-transformers   # modèle par défaut : all-MiniLM-L6-v2 (~90 Mo, 384 dim)
python agent.py "Explique le KV cache" --kv --refine 2 -v
```
Sans `sentence-transformers` (ou avec `SEEDMESH_NO_EMB=1` / `--no-emb`), le cache fonctionne en exact seul, silencieusement.

## Installation Windows (PowerShell 7+)
1. `winget install Microsoft.PowerShell SQLite.SQLite` (ou `sqlite3.exe` dans le PATH / `$env:SEEDMESH_SQLITE`).
2. Binaires llama.cpp (release `*-bin-win-*.zip`) → `$env:SEEDMESH_LLAMA_BIN="C:\llama\llama-completion.exe"`.
3. `.\SeedMesh-Agent.ps1 "Explique le KV cache" -Model C:\models\m.gguf -Kv -Refine 2 -Verbose`
La version Python marche aussi telle quelle sous Windows (`py agent.py ...`). Les deux partagent la même DB si
`SEEDMESH_HOME` pointe au même endroit.

## Configuration globale (`config.json`) et seed
`agent.py` et `SeedMesh-Agent.ps1` lisent `SEEDMESH_CONFIG`, sinon `/opt/seedmesh/config.json`
(Windows : `%ProgramData%\SeedMesh\config.json`), sinon `~/.seedmesh/config.json`. Priorité : CLI > env > config > défauts.
- `providers` : triés par `priority` ; le n°1 (`local`, llama.cpp) fournit `model`, `llama_completion_bin`, `llama_server_bin`, `server_url`.
- `sampling` : `seed` (42), `temp` (0.0), `top_p`, `top_k`, `repeat_penalty`, `ctx`, `n_predict`, `threads`.
  `seed/top_p/top_k/repeat_penalty` sont passés à llama (`--seed --top-p --top-k --repeat-penalty`) **et inclus dans le hash** ;
  `threads` n'en fait pas partie.
- `chat_template` (true) : `llama-completion -st -sys … -p …` applique le gabarit de chat du modèle instruct
  (`--raw` pour la complétion brute) ; `"chat": true` est alors ajouté aux params hachés.
Installeurs : `install_linux.sh` (box, /opt/seedmesh), `install_termux.sh`, `Install-SeedMesh.ps1` ; wrapper `seedmesh.sh`.

## Variables d'environnement
`SEEDMESH_HOME` (défaut `~/.seedmesh`, résolu une fois en absolu) · `SEEDMESH_MODEL` · `SEEDMESH_LLAMA_BIN` ·
`SEEDMESH_SYSTEM` · `SEEDMESH_MAX_MB` (0 = illimité) · `SEEDMESH_EMB_MODEL` · `SEEDMESH_THRESHOLD` (défaut 0.92) · `SEEDMESH_NO_EMB=1` · `SEEDMESH_SQLITE` (PS).

## Schéma (user_version = 3)
- `entries(id, prompt_hash UNIQUE, prompt, response, model, params_json, embedding BLOB NULL, emb_model, created_at, hits, last_hit)`
  + `emb_scale REAL` (v3) : embedding = int8 signé, `valeur ≈ int8 × emb_scale`
- `kv_snapshots(prefix_hash, path, model, created_at)` PK (prefix_hash, model) — mode llama-completion `--kv`
- `kv_prefixes(prefix_hash, model, slot_file, n_turns, created_at, last_used)` PK (prefix_hash, model) — mode `--server`

Migrations v1→v2→v3 automatiques à l'ouverture (Python et PowerShell). La conversion float32 → int8 est faite par
Python (à la migration et à chaque ouverture pour les lignes `emb_scale IS NULL`) ; PowerShell ajoute seulement la colonne.

`prompt_hash = sha256( normalize(prompt) + "\x1f" + model + "\x1f" + params_json )` où normalize = NFC + trim + espaces compactés
(casse conservée) et `params_json` = JSON canonique (clés triées, séparateurs `,` `:`, UTF-8 non échappé).
`model` = nom de fichier du .gguf. L'agent ajoute `system` et `step` (answer/critique/revise) dans les params.
Embeddings : int8 avec quantification symétrique par vecteur (`scale = max|v|/127`, 4× plus compact que float32) ;
index en mémoire chargé au démarrage (matrice numpy float32, ou listes en pur Python), mis à jour à chaque `put`,
rechargé après `prune`/import ; la recherche sémantique ne compare que même `model`, `params_json`, `emb_model`.
⚠️ Parité Python/PS : passer `temp` comme flottant (PS écrit `1.0`, comme Python).

## CLI cache
```bash
python seedmesh_cache.py put "question" "réponse" --model m.gguf
python seedmesh_cache.py get "question" --model m.gguf     # code retour 1 si miss
python seedmesh_cache.py stats
python seedmesh_cache.py prune --days 30 --max 5000         # âge + LRU
python seedmesh_cache.py gc --max-mb 50                     # LRU par taille + nettoyage KV
python seedmesh_cache.py export-jsonl -o dump.jsonl [--since EPOCH]
python seedmesh_cache.py import-jsonl dump.jsonl            # alias : merge
```

## Éviction LRU par taille (`SEEDMESH_MAX_MB`)
Si `SEEDMESH_MAX_MB` (ou `-MaxMB` en PS) > 0, chaque `put` supprime les entrées les moins récemment utilisées
(`COALESCE(last_hit, created_at)`) jusqu'à repasser sous le plafond. La taille est **logique** :
octets de prompt + réponse + params + embedding + 200 o/ligne (le fichier .db ne rétrécit qu'après `VACUUM`).
`gc` (`seedmesh_cache.py gc` / `SeedMesh-Agent.ps1 -Gc`) fait l'éviction + supprime les lignes `kv_snapshots` dont le fichier
n'existe plus + supprime les `kv/*.bin` référencés ni par `kv_snapshots` ni par `kv_prefixes`. Python et PS
suppriment exactement les mêmes lignes (testé).

## KV par préfixe de conversation (llama-server)
```bash
llama-server -m model.gguf --slot-save-path ~/.seedmesh/kv -np 1 --port 8080
python agent.py "Et ensuite ?" --server http://127.0.0.1:8080 --history conv.json --system "Tu es concis" -v
```
`conv.json` = `[{"role":"user","content":"..."},{"role":"assistant","content":"..."}]`. Fonctionnement :
1. hash cumulatif de chaque préfixe (`modèle + système`, puis `+ tour 1`, `+ tour 2`…) ;
2. le plus long préfixe connu dans `kv_prefixes` est restauré (`POST /slots/0?action=restore {"filename":…}`) ;
   si le serveur ne trouve plus le fichier, la ligne est supprimée et on continue sans ;
3. `POST /completion` avec `id_slot` et `cache_prompt: true` (le serveur ne recalcule que la suite) ;
4. sauvegarde du slot sous le hash de la conversation **réponse incluse** (`action=save`) → le tour suivant repart de là.
Le rendu texte est un gabarit fixe (`### role\n…`) pour que le préfixe soit identique token pour token.
La réponse finale est aussi mise en cache (clé = conversation rendue, `step=server`).
Lancer `--slot-save-path` sur `SEEDMESH_HOME/kv` pour que `gc` reconnaisse ces fichiers.

## Synchronisation Termux ↔ PC
- **Merge idempotent** par `prompt_hash` : insertion si absent ; sinon `hits = max`, `last_hit = max`, réponse locale conservée,
  embedding importé seulement si la ligne locale n'en a pas **et** que `emb_model` est identique (sinon ignoré).
  Un enregistrement dont le hash ne correspond pas à (prompt, model, params) est rejeté (`skipped`).
- **HTTP** : sur une machine `python seedmesh_cache.py serve --host 0.0.0.0 --port 8765`, sur l'autre :
  `python sync.py http://IP:8765 both` ou `.\Sync-SeedMesh.ps1 -Url http://IP:8765 -Mode both`.
  Incrémental : l'état (`push_since` horloge locale, `pull_since` horloge du serveur) est dans `SEEDMESH_HOME/sync_state.json`.
  Les fichiers KV ne sont **jamais** synchronisés (liés au modèle, à la build et au matériel).
  ⚠️ Le serveur n'a pas d'authentification : à n'utiliser que sur un LAN de confiance / VPN (Tailscale, WireGuard).
- **Syncthing** (sans serveur HTTP) : ne synchronisez **jamais** `cache.db` directement (WAL + écritures concurrentes = corruption).
  Synchronisez un dossier d'échange :
  ```bash
  # Termux (cron/termux-job-scheduler) : export de ses entrées, import de celles du PC
  python seedmesh_cache.py export-jsonl -o ~/Sync/seedmesh/termux.jsonl
  python seedmesh_cache.py import-jsonl ~/Sync/seedmesh/pc.jsonl
  ```
  et l'inverse côté PC (`pc.jsonl` / `termux.jsonl`). Chaque appareil n'écrit que son propre fichier → aucun conflit
  Syncthing ; l'import étant idempotent, réimporter le même fichier est sans effet. Ignorer `kv/` dans `.stignore`.

## Self-Refine (`--refine N`)
générer → critiquer (« réponds uniquement OK si satisfaisant ») → réviser ; arrêt dès que la critique commence par `OK`
ou après N tours. Chaque étape est mise en cache (clé incluant `step`) : relancer la même question ne coûte rien.
Conseil mobile : N=1 ou 2, `-n 256`, modèle 1–3B Q4.

## Interface SeedMesh
**Option A — lecture directe SQLite (recommandée sur le même appareil)** :
```python
import sqlite3, seedmesh_cache as sc
con = sqlite3.connect(f"file:{sc.DEFAULT_DB}?mode=ro", uri=True)
h = sc.make_hash(prompt, "m.gguf", {"ctx":2048,"n_predict":256,"step":"answer","system":"","temp":0.2})
row = con.execute("SELECT response FROM entries WHERE prompt_hash=?", (h,)).fetchone()
```
Ou `SeedMeshCache(readonly=True)`. Le mode WAL permet de lire pendant que l'agent écrit.

**Option B — mini-serveur HTTP local** : `python seedmesh_cache.py serve --port 8765` (127.0.0.1 par défaut, aucune auth :
ne pas exposer sur le réseau sans proxy authentifié).

| Route | Requête | Réponse |
|---|---|---|
| `POST /lookup` | `{"prompt":str, "model":str?, "params":obj?, "semantic":bool?=true}` | `{"hit":true,"response":str,"match":"exact"\|"semantic","score":float,"id":int}` ou `{"hit":false}` |
| `POST /put` | `{"prompt":str, "response":str, "model":str?, "params":obj?}` | `{"ok":true,"prompt_hash":str}` |
| `POST /put_batch` | `{"records":[enregistrement export-jsonl,…]}` | `{"ok":true,"inserted":n,"updated":n,"skipped":n}` |
| `GET /export?since=EPOCH` | — | `{"records":[…],"now":float}` |
| `GET /stats` | — | `{"entries":int,"with_embedding":int,"total_hits":int,"kv_snapshots":int,"kv_prefixes":int,"size_mb":float,"max_mb":float,"index_vectors":int,"schema_version":int,...}` |
Erreurs : 400 `{"error":...}` (JSON invalide / champ manquant), 404 route inconnue.
```bash
curl -s localhost:8765/lookup -d '{"prompt":"question","model":"m.gguf"}'
```

## Tests
```bash
python tests/test_seedmesh.py && python tests/test_extensions.py
SEEDMESH_PWSH=pwsh SEEDMESH_SQLITE=sqlite3 python tests/test_powershell.py   # bout en bout PS (faux llama)
pwsh -File tests/check_ps_parity.ps1   # même hash que Python attendu
```
Format d'un enregistrement JSONL : `prompt_hash, prompt, response, model, params, params_json, embedding_b64 (int8, base64 | null),
emb_scale, emb_model, created_at, hits, last_hit`.

## Documentation et licence
- Licence : Apache 2.0 (`LICENSE`, `NOTICE`). Sécurité : `SECURITY.md`.
- `docs/` : BOUNTY, REPRODUCIBILITY (+ `repro_check.py`), AOSP_PROPOSAL, AOSP_SUBMISSION, ANDROID_NATIF (+ `android/`), PLATFORMS. Brouillons non publiés.
