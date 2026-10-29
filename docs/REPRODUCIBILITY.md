# SeedMesh — Reproductibilité (BROUILLON)

## 1. Ce qui est figé
| Élément | Valeur de référence (box, 2026-10-29) |
|---|---|
| llama.cpp | build **b11921**, commit `7a2e5aba9`, version 0.7.0-dev, GNU 11.4.0, binaire CPU x64 officiel |
| Modèle | `qwen2.5-1.5b-instruct-q4_k_m.gguf` (Qwen/Qwen2.5-1.5B-Instruct-GGUF), 1 117 320 736 octets |
| sha256 du GGUF | `6a1a2eb6d15622bf3c96857206351ba97e1af16c30d7a74ee38970e434e9407e` |
| Échantillonnage | seed 42, temp 0.0, top_p 0.9, top_k 40, repeat_penalty 1.1, ctx 4096, n_predict 512 (64 pour les prompts golden) |
| Threads / batch | threads 4 (choisi car la box était chargée : avec 8 threads on tombait à 0,23 tok/s) ; batch = valeurs par défaut de llama.cpp b11921, non surchargées |
| Gabarit | `chat_template: true` (llama-completion `-st -sys`) |
| Schéma SQLite | `PRAGMA user_version = 3` (migrations v1→v2→v3) |
| Matériel | Intel Xeon 8 vCPU, AVX2 + AVX-512, 15 Go de RAM |

Ces valeurs sont lues depuis `/opt/seedmesh/config.json`, et `repro_check.py` les enregistre dans le manifeste.

## 2. Hash d'entrée (clé de cache) — définition exacte
```
prompt_hash = sha256( normalize(prompt) + "\x1f" + model + "\x1f" + params_json ).hexdigest()
normalize   = Unicode NFC, strip(), séquences d'espaces → un seul espace, CASSE CONSERVÉE
model       = nom de fichier du .gguf (pas son sha256, voir limite §4)
params_json = json.dumps(params, sort_keys=True, separators=(",",":"), ensure_ascii=False), encodé en UTF-8
params      = {temp, n_predict, ctx, seed, top_p, top_k, repeat_penalty, system, step ∈ {answer, critique, revise, server}} + {"chat": true} si gabarit
```
`threads` **n'entre pas** dans le hash : choix délibéré pour partager le cache entre machines, au prix de la limite §4. L'implémentation PowerShell produit le même hash (vecteur de test `tests/check_ps_parity.ps1`, hash `04456b35…a29`).

## 3. Vérifier : `repro_check.py`
```bash
python repro_check.py manifest -o repro.json          # génère sans cache les 5 prompts golden (docs/golden_prompts.json)
python repro_check.py compare repro.json               # régénère et compare ; code retour 0 = identique
python repro_check.py compare repro.json --threads 2   # teste la sensibilité au nombre de threads
```
Le manifeste contient : la version de llama.cpp, le sha256 et la taille du GGUF, l'échantillonnage, la version de schéma, le sha256 de chaque fichier du projet, l'OS, Python, le modèle de CPU et les extensions SIMD, ainsi que, pour chaque prompt golden, `prompt_hash`, `output_sha256`, la sortie et la durée. Exemple réel : `docs/repro.example.json`.

### Résultats mesurés sur la box (2026-10-29, ~13:40 heure de Paris)
- Le modèle, le schéma et les **5 `prompt_hash` sont identiques** sur toutes les exécutions : c'est déterministe, en pur calcul.
- J'ai généré un manifeste de référence, puis 4 régénérations avec 4 threads et 1 avec 2 threads. Sur ces 5 comparaisons, il y a eu **2 écarts, toujours sur le même prompt** (« Traduis en anglais… », avec 4 threads), et dans les deux cas une seule différence : la sortie était entourée de guillemets ou non. Les 4 autres prompts étaient identiques à chaque fois, y compris avec 2 threads.
- **Conclusion honnête** : même avec seed et température 0, sur une même machine, avec le même build et le même nombre de threads, la sortie **n'est pas garantie bit à bit**. Cause probable, non prouvée : à température 0, deux tokens presque à égalité basculent selon l'ordre des réductions flottantes en multithread. `repro_check.py` le détecte et le signale ; c'est précisément son rôle.

## 4. Limites du déterminisme
- **CPU / SIMD** : AVX2, AVX-512, NEON (ARM) et i8mm empruntent des chemins de calcul différents, avec des arrondis différents. On ne peut pas attendre une sortie identique entre x86 et un téléphone ARM.
- **GPU** : CUDA, Vulkan et OpenCL ne sont pas déterministes en général (atomics, kernels) ; non testés ici.
- **Nombre de threads et ordre des réductions** : voir les mesures du §3.
- **Build** : tout changement de version de llama.cpp, de compilateur ou de flags peut changer les sorties. Il faut épingler b11921.
- **Modèle** : le hash utilise le *nom* du fichier ; un GGUF réquantifié sous le même nom donnerait de fausses correspondances de cache. Il faut donc vérifier le sha256 (manifeste). Piste : inclure le sha256 du modèle dans le hash (bump du schéma v4).
- **Le cache est la vraie garantie** : une fois une réponse en cache, elle est resservie à l'identique, partout où la base est synchronisée. Le déterminisme de la génération n'est qu'un « best effort ».
- **Schéma** : un bump de `user_version` est accompagné d'une migration ; les anciens hashes restent valides tant que la définition du §2 ne change pas.

## Limites et risques (à lire avant toute utilisation)

1. **Pas d'authentification HTTP.** Le serveur de cache (`seedmesh_cache.py serve`, port 8765) et `llama-server` (8080) n'ont ni token ni TLS. Ils écoutent sur `127.0.0.1` par défaut ; les exposer (`--host 0.0.0.0`, redirection de port, Tailscale…) permet à n'importe qui sur le réseau de lire tout le cache et d'y écrire (empoisonnement). Correctif prévu : tâche B1 de BOUNTY.md.
2. **ToS et licences des modèles.** Seul Qwen2.5-1.5B-Instruct (Apache 2.0) a été vérifié. Qwen2.5-3B est sous Qwen Research License (non commerciale), Qwen2.5-72B sous Qwen License (seuil de 100 M MAU). Tout modèle substitué doit être revérifié. Le fournisseur distant de secours (priorité 2) a ses propres CGU, dont la rétention des prompts.
3. **Rate limits du fournisseur distant.** Le repli cloud est soumis à des quotas, à des coûts et à des pannes ; SeedMesh n'a ni backoff avancé ni budget de dépense. Un hit de cache n'appelle pas le fournisseur, mais un miss le fait.
4. **Fiabilité factuelle du modèle 1.5B.** C'est un petit modèle quantifié en Q4 : il produit des hallucinations, des erreurs de calcul et des erreurs de dates. Le cache fige aussi les mauvaises réponses : une erreur mise en cache est resservie à l'identique, et le déterminisme (seed 42, température 0) ne la rend pas « vraie ».
5. **Cache périmé.** Aucune expiration (TTL) n'existe. Une réponse dépendante du temps (« quelle version est la dernière ? ») reste figée. Le LRU (`max_mb`) n'évince que par taille. Contournements : `--no-cache`, `seedmesh gc`, `prune`.
6. **Vie privée.** Les prompts et réponses sont stockés **en clair** dans SQLite (`/opt/seedmesh/data` ou `~/.seedmesh`), dans l'export JSONL de synchronisation, et dans les fichiers KV, qui contiennent l'état du contexte. Il n'y a pas de chiffrement au repos. Ne pas y mettre de secrets. La sync copie ces données sur les autres machines.
7. **Termux n'est pas un canal officiel.** Termux n'est pas une application Google. La version Play Store est expérimentale ; les sources recommandées sont F-Droid et GitHub, et Termux comme ses plugins doivent provenir de la même source (signature commune). Android peut tuer les processus en arrière-plan (phantom process killer depuis Android 12, voir ANDROID_NATIF.md). **Aucun test n'a été fait sur un appareil Android réel** à ce jour.
8. **« Qualité sonore » et « fluidité ».** L'amélioration du son rapportée par Samir est un **retour subjectif, non mesuré**. SeedMesh est un cache texte/LLM : il ne touche ni au mixeur audio, ni aux codecs, ni au DSP, et ne peut pas améliorer le son. Pour objectiver la fluidité ou le son, voir le protocole ci-dessous ; tant qu'il n'est pas appliqué, **rien n'est revendiqué**.

### Protocole de mesure (fluidité / son) — rien n'est revendiqué avant application
- **Conditions** : même appareil, batterie > 50 %, en charge ou non mais identique entre essais, mode avion, 10 minutes de repos, même température. Mesures **A/B/A** : SeedMesh arrêté, puis démarré, puis arrêté ; au moins 5 répétitions par condition.
- **Fluidité UI** : `adb shell dumpsys gfxinfo <pkg> reset`, scénario scripté (`adb shell input swipe …` × 50), puis `dumpsys gfxinfo <pkg> framestats`. On compare le % de frames janky et les P50, P90 et P99 du temps de frame. Trace système : `perfetto` (catégories gfx, sched, freq) sur 30 s.
- **Latence SeedMesh** : `python repro_check.py` et `seedmesh ask` en mode chronométré, en comparant hit et miss (sur la box : 89 ms en hit contre 4,0 à 4,2 s en génération).
- **Son, en aveugle** : test ABX (par ex. l'outil ABX de foobar2000 sur PC à partir d'enregistrements, ou un tiers qui active ou non SeedMesh sans le dire). Il faut au moins 16 essais ; on ne conclut que si p < 0,05 (≥ 12/16 corrects). Mesure objective : enregistrement en boucle (loopback) ou par micro calibré, comparaison des spectres et du niveau RMS. **Hypothèse nulle attendue : aucune différence**, sauf effet indirect de la charge CPU (dropouts audio si le CPU est saturé, ce qui dégraderait plutôt le son).
