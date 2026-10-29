# SeedMesh — Proposition pour Android / AOSP (BROUILLON, rien n'est soumis)

## 1. Réalité du processus AOSP (vérifié sur source.android.com, 2026-10)
- Les contributions passent par **Gerrit** (`android-review.googlesource.com`), sont envoyées avec `repo upload`, puis relues par les **code owners** (« Suggest owners »).
- Il faut d'abord signer le **CLA Google** : Individual CLA, ou Corporate CLA si l'on contribue au nom d'un employeur.
- Depuis 2026, le code source d'AOSP n'est publié **qu'aux T2 et T4** (modèle *trunk stable*), et l'on contribue sur `android-latest-release`. Google n'accepte pas les modifications des flags de release.
- **Chances réalistes** : un nouveau service système de cache LLM, venu d'un contributeur externe sans sponsor chez Google, a une **probabilité très faible** d'être accepté. Les fonctionnalités de cette taille sont conçues en interne, et l'IA on-device de Google passe déjà par d'autres briques :
  - **AICore + Gemini Nano**, exposés via les **ML Kit GenAI APIs** (prompt, résumé, embeddings + AppSearch) ;
  - **NNAPI est déprécié depuis Android 15** ;
  - **LiteRT** (ex-TensorFlow Lite), version 2.3.0 du 2026-10-07 avec l'API `CompiledModel`, est la voie recommandée pour l'inférence.
- Les failles AOSP relèvent de l'**Android VRP** (Google Bug Hunters). Ce programme paie des vulnérabilités, **pas des propositions de projet** : SeedMesh n'y est pas éligible en tant que projet.

## 2. Voie proposée (réaliste)
1. **Bibliothèque AAR open source** (Apache 2.0) utilisable par n'importe quelle application, sans root ni modification du système. Distribution via Maven Central ou JitPack, plus une application de démonstration sur F-Droid (llama.cpp est sous MIT et compatible ; le modèle est téléchargé en tant que donnée, avec consentement explicite).
2. **Adoption et mesures** : benchmarks publics sur des appareils réels (B4/B5 de BOUNTY.md) et manifestes `repro.json`.
3. **Éventuellement** : un échange en amont (issue ou discussion publique, contact avec l'équipe AICore/ML Kit) pour proposer une **API de cache de réponses** au-dessus d'AICore, plutôt qu'un patch AOSP. Patch Gerrit uniquement si un owner Google le sponsorise.

## 3. Architecture cible (AAR + service on-device)
```
App cliente ──AIDL (bind)──► SeedMeshService (foreground service, process :seedmesh)
            └─ContentProvider (lecture seule, URI content://<pkg>.seedmesh/entries)
SeedMeshService
 ├─ CacheStore : SQLite (Room ou SQLite brut), schéma v3 identique à Python → même prompt_hash
 ├─ Embeddings : llama.cpp --embeddings (JNI) ou LiteRT ; int8 symétrique
 ├─ Inference  : llama.cpp via JNI (CPU NEON ; GPU Vulkan ou OpenCL expérimentaux) ; ou AICore si disponible
 ├─ KV store   : fichiers de slots dans le stockage interne de l'app (noBackup)
 └─ Sync       : JSONL /export?since= vers un pair choisi par l'utilisateur, désactivée par défaut
```
- **Stockage** : stockage interne de l'app (`/data/data/<pkg>`), exclu des sauvegardes (`android:allowBackup=false` ou règles de backup). Chiffrement optionnel via une clé dans Android Keystore.
- **Permissions** : permission personnalisée `signature` ou `knownSigner` pour l'AIDL et le ContentProvider (`android:permission`, `readPermission`) ; aucune permission INTERNET si la sync est désactivée ; `FOREGROUND_SERVICE` + le type `specialUse` ou `dataSync` (Android 14+ exige un type de service de premier plan déclaré).
- **Sécurité** : isolation par application ; vérification de l'UID appelant (`Binder.getCallingUid()`) ; pas de partage de cache entre applications par défaut, car un cache commun ferait fuiter les prompts d'une application à l'autre ; quotas par appelant ; validation des chemins (KV) ; aucun port TCP ouvert (l'AIDL remplace le HTTP sans authentification de la version Termux).
- **Cycle de vie** : modèle chargé à la demande, libéré sur `onTrimMemory` ; pas de service permanent hors usage (batterie, restrictions en arrière-plan).
- Détails par niveaux (Termux, ADB, root, app native) : **ANDROID_NATIF.md**. Canal et message de soumission : **AOSP_SUBMISSION.md**. Tâches finançables : **BOUNTY.md**.

## 4. Pourquoi pas directement dans AOSP
- La taille et la maintenance (modèle de 1 Go, ABI llama.cpp mouvante) sont incompatibles avec la cadence de la plateforme.
- Google a déjà une pile (AICore, LiteRT) ; un second runtime LLM système ferait doublon.
- Les questions de licences de modèles et de vie privée sont plus simples à gérer au niveau d'une application, avec un consentement explicite.

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
