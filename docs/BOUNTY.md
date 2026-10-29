# SeedMesh — Programme de bounty (BROUILLON, non publié)

> Statut : brouillon en attente de validation par KIDAOUENE Samir. Rien n'a été publié ni soumis. Les montants ci-dessous sont des **propositions**.

## 1. Présentation
SeedMesh est un **cache sémantique local** pour un LLM exécuté en local (llama.cpp). Il fonctionne sur Linux, Windows (PowerShell 7) et Android via Termux. Une question déjà posée, avec les mêmes paramètres, est servie depuis SQLite en **~89 ms** au lieu de **4 à 4,2 s** de génération, mesure faite sur un Xeon de 8 vCPU avec Qwen2.5-1.5B Q4_K_M. Les paramètres sont figés (seed 42, température 0), ce qui rend la génération rejouable : voir REPRODUCIBILITY.md. Licence : Apache 2.0.

## 2. Composants (existants et testés sur la box)
| Composant | Rôle | État |
|---|---|---|
| `seedmesh_cache.py` | Cache SQLite WAL, schéma v3, hash d'entrée, embeddings int8, LRU, CLI, HTTP `/lookup /put /put_batch /export /stats` | 19 tests verts |
| `agent.py` | Agent llama.cpp : cache, `--kv` (prompt-cache), `--refine N` (Self-Refine), `--server` (slots KV llama-server) | testé sur la box |
| `kv_server.py` | Sauvegarde et restauration des préfixes KV via `/slots` | testé (préfixe de 2 tours restauré) |
| `sync.py`, `Sync-SeedMesh.ps1` | Sync JSONL idempotente entre machines | testé |
| `SeedMesh-Agent.ps1`, `Install-SeedMesh.ps1` | Windows / PowerShell 7, hash identique à Python | 5 tests (pwsh 7.4.6 Linux) ; installation Windows en cours chez Samir |
| `install_termux.sh` | Android/Termux | **non testé sur un appareil réel** |
| `repro_check.py` | Manifeste de reproductibilité + prompts golden | testé sur la box |
| `android/` | Scripts Termux:Boot, ADB (réversible), squelette de module Magisk | syntaxe vérifiée (`bash -n`), ADB testé sur un mock ; **pas sur appareil** |

## 3. Pourquoi ça intéresse un dev
- Un projet petit et lisible (Python stdlib + numpy optionnel), sans service cloud obligatoire.
- Des problèmes concrets et bornés : sécurité HTTP, recherche ANN, embeddings sans PyTorch, tests sur téléphone.
- Un terrain de jeu pour le LLM on-device (voir AOSP_PROPOSAL.md et ANDROID_NATIF.md).

## 4. Tâches proposées et critères d'acceptation
Toutes les tâches exigent : une PR avec tests ; `python -m pytest tests/` vert ; le hash de parité PS/Python inchangé (`tests/check_ps_parity.ps1`), sauf si la tâche bumpe le schéma avec une migration ; la doc mise à jour ; une licence Apache 2.0 compatible (pas de dépendance GPL ou non commerciale).

| ID | Tâche | Critères d'acceptation | Taille → montant proposé |
|---|---|---|---|
| B1 | **Auth HTTP par token** sur le serveur de cache | En-tête `Authorization: Bearer` obligatoire dès que `--host` ≠ 127.0.0.1 ; token généré avec `secrets.token_urlsafe(32)` et stocké en 0600 ; comparaison à temps constant (`hmac.compare_digest`) ; refus de démarrer sur 0.0.0.0 sans token ; `sync.py` et le script PS envoient le token ; tests 401/200 | M → 100 € |
| B2 | **Index ANN** | Option HNSW (par ex. hnswlib, Apache 2.0) ou IVF numpy ; recall@10 ≥ 0,95 face au scan exact sur 100 k vecteurs ; latence et RAM mesurées ; repli automatique sur le scan exact | L → 200 € |
| B3 | **Embeddings on-device sans torch** | Via `llama-server --embeddings` (GGUF) **ou** ONNX Runtime ; aucun import de torch ; `emb_model` versionné dans la base ; similarité cosinus ≥ 0,98 avec la référence sentence-transformers sur 200 phrases, ou bien un nouveau modèle documenté avec réindexation | L → 200 € |
| B4 | **Tests Termux sur appareil réel** | Rapport : appareil, SoC, version d'Android et de Termux (F-Droid ou GitHub), `install_termux.sh` de bout en bout, tok/s, latence hit/miss, `repro_check.py manifest` joint, comportement face au phantom process killer, test de `android/termux_boot_seedmesh.sh` | S → 50 € par appareil distinct (3 max) |
| B5 | **Benchmark reproductible** | Script `bench.py` : N prompts, latences P50/P95 hit/miss, tok/s, RAM ; sortie JSON horodatée avec le manifeste `repro.json` ; écart-type rapporté ; exécution identique Linux/Termux | M → 100 € |
| B6 | **Chat template côté serveur** | Utiliser `/v1/chat/completions` ou `/apply-template` de llama-server au lieu du gabarit texte `### role` ; préfixes KV toujours restaurés ; hash inchangé ou schéma bumpé avec migration ; tests | M → 75 € |
| B7 | Expiration (TTL) et chiffrement au repos (optionnels) | TTL par entrée et `--max-age` ; chiffrement optionnel (SQLCipher ou AES-GCM applicatif) documenté | M → 100 € |

Barème code : **S 25-50 €, M 75-150 €, L 150-300 €** (plafond 300 € par tâche).

## 5. Sécurité — barème proposé
Périmètre : le code de ce dépôt. **Hors périmètre** : l'absence d'auth HTTP sur 127.0.0.1 (limite connue, voir B1), llama.cpp lui-même (à signaler en amont), le modèle (hallucinations), les services tiers, l'ingénierie sociale, le DoS par volume.

| Sévérité (CVSS 3.1 indicatif) | Exemple pour SeedMesh | Montant proposé |
|---|---|---|
| Basse (0,1-3,9) | Fuite d'information mineure dans les logs | 50 € |
| Moyenne (4,0-6,9) | Path traversal sur `--kv`/`--slot`, injection JSONL à l'import | 100-150 € |
| Haute (7,0-8,9) | Empoisonnement du cache à distance malgré le token (après B1), contournement de la vérification de hash à l'import | 250-350 € |
| Critique (9,0-10) | Exécution de code à distance via le serveur HTTP ou la sync | 500 € |

Signalement privé uniquement (SECURITY.md) ; divulgation coordonnée sous 90 jours.

## 6. Budget — transparence
Samir dispose d'un **budget actuel d'environ 0 €**. En conséquence :
- **Enveloppe totale plafonnée** : proposition de 0 € tant qu'aucun financement n'existe, puis un plafond fixé par Samir (par exemple 500 € par an) s'il obtient un sponsor ou une subvention (voir PLATFORMS.md : Open Collective, GitHub Sponsors, Liberapay ; NLnet écarté).
- **Option symbolique** : en l'absence de fonds, les bounties sont versés en **reconnaissance** (crédit dans le README, NOTICE et CHANGELOG ; mention « Hall of Fame » sécurité ; statut de mainteneur), sans paiement.
- Les montants affichés ne sont **dus que si l'enveloppe est financée** et si la tâche est acceptée ; règle « premier arrivé, premier servi » sur une PR acceptée.

## 7. Plateformes
Canaux pour payer des contributeurs : Algora (`/bounty` sur une issue GitHub) ou IssueHunt ; HackerOne Community Edition pour la sécurité (gratuit pour l'open source éligible : licence OSI, projet actif depuis au moins 3 mois, SECURITY.md ; frais de 5 % sur les primes versées). Détail et vérifications : PLATFORMS.md. Pour Android : ANDROID_NATIF.md ; pour une éventuelle voie AOSP : AOSP_PROPOSAL.md.

## 8. Règles
1. Annoncer la tâche dans l'issue avant de commencer ; une seule personne par tâche pendant 14 jours.
2. Code original sous Apache 2.0 (DCO `Signed-off-by` demandé) ; pas de code généré copié d'une source incompatible.
3. Les tests, les mesures et le manifeste `repro.json` sont fournis, sans chiffres non reproductibles.
4. Aucune collecte de données ni télémétrie ajoutée.
5. Décision finale : le mainteneur (Samir). Paiement sous 30 jours après la fusion, **si l'enveloppe est financée**.
6. Pas de bounty pour des failles exploitées hors de son propre environnement.

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
