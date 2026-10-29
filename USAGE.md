# SeedMesh — utiliser le modèle local en priorité (pour les bots)

**Règle : provider `local` = priorité 1.** Tout bot de la box passe d'abord par SeedMesh ; un modèle distant
(priorité 2) n'est utilisé que si le local échoue, dépasse le temps, ou si la tâche dépasse clairement ses capacités
(raisonnement long, code complexe, faits récents). Config unique : `/opt/seedmesh/config.json`
(seed 42, temp 0.0, top_p 0.9, top_k 40, repeat_penalty 1.1, ctx 4096, n_predict 512, threads 4).

## Commandes
```bash
source /etc/profile.d/seedmesh.sh        # (shells non-login) — déjà chargé dans les shells login
seedmesh ask "ta question"               # cache -> sinon Qwen2.5-1.5B local ; même question = réponse identique
seedmesh ask "..." --system "Tu es concis." -n 256
seedmesh ask "..." --refine 1            # Self-Refine (critique + révision)
seedmesh ask "..." --kv --system "..."   # réutilise le KV du prompt système (llama-completion)
seedmesh ask "suite" --server http://127.0.0.1:8080 --history conv.json   # multi-tours, KV par préfixe (llama-server)
seedmesh ask "..." --no-cache            # force une génération (écrit quand même dans le cache)
seedmesh status | start | stop | restart | gc
```
## Depuis du code
- Python : `subprocess.run(["seedmesh","ask",prompt],capture_output=True,text=True).stdout`
- HTTP cache seul : `POST http://127.0.0.1:8765/lookup {"prompt":...}` / `/put` / `GET /stats`
- Génération directe : `POST http://127.0.0.1:8080/completion` ou `/v1/chat/completions` (OpenAI-compatible) avec
  `"seed":42,"temperature":0` — ⚠️ ne passe pas par le cache SeedMesh.

## Relancer les services (après reboot de la box)
`seedmesh start` (idempotent) : llama-server 127.0.0.1:8080 (`--slot-save-path /opt/seedmesh/data/kv`) et cache
HTTP 127.0.0.1:8765. Logs : `/opt/seedmesh/data/logs/`. Arrêt : `seedmesh stop`.

## Bonnes pratiques
- Modèle petit (1.5B) : bon pour reformuler, résumer, classer, extraire, réponses courtes ; vérifier les faits.
- Garder seed/params par défaut : sinon le hash change et le cache ne sert plus.
- Box partagée et chargée : ne pas monter `threads` au-delà de 4 (contention = 10× plus lent).
