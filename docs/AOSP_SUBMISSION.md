# Soumettre SeedMesh à Android / AOSP — canal et message (BROUILLON, rien n'est envoyé)

## 1. Quel canal (vérifié sur source.android.com le 2026-10-29)
| Canal | Pour quoi | Conditions | Adapté ici ? |
|---|---|---|---|
| **Gerrit** `android-review.googlesource.com` | **Patchs de code uniquement**, envoyés par `repo upload` et relus par les code owners | Compte Google + **CLA Google signé** (individuel ou entreprise) | **Non** : il n'y a pas de patch AOSP, et une proposition n'est pas un patch |
| **Google Issue Tracker** | Bugs et **demandes de fonctionnalité AOSP** (« Google Issue Tracker is a tool used by Google to track AOSP issues and feature requests ») | Compte Google ; chercher d'abord les doublons (issues ouvertes **et** fermées) et mettre une étoile s'il en existe une | **Oui** |
| Android VRP (Bug Hunters) | Failles de sécurité | PoC | Non |

**Composant recommandé** : **Platform → Framework** (`component=192705`). Pour une demande d'API ou de plateforme, la doc AOSP indique : « si vous ne savez pas lequel choisir, utilisez Framework ».
**URL de création** : https://issuetracker.google.com/issues/new?component=192705
Dans le formulaire, choisir le type **« Feature Request »** s'il est proposé (champ *Type*), sinon l'indiquer dans le titre. Recherche préalable : https://issuetracker.google.com/issues?q=componentid:192705%20cache (essayer aussi les mots-clés « LLM cache », « AICore cache », « on-device inference cache »).

**À savoir**
- Les issues du composant public sont **visibles publiquement**, et le nom ou l'email du compte peut apparaître.
- Aucune règle sur l'IA n'a été trouvée pour l'Issue Tracker (« non précisé »). Par honnêteté, le message ci-dessous déclare l'usage d'une IA.
- **Une réponse ou une adoption est peu probable.** La plupart des demandes de fonctionnalité restent en priorité P3 ou P4 sans suite, et Google a déjà AICore, ML Kit GenAI et LiteRT. L'intérêt réaliste est de laisser une trace publique et d'obtenir d'éventuelles étoiles.
- **Fortement recommandé avant l'envoi** : un **dépôt public** (GitHub) pour que le lien soit consultable. Une demande sans code consultable a encore moins de chances d'être lue.

## 2. Message en anglais, prêt à coller (remplacer `https://github.com/Kidaouene/seedmesh`)

**Title**
```
Feature request: optional on-device response cache API for local LLM inference (AICore / LiteRT clients)
```

**Description**
```
Summary
Apps that run local LLMs on Android (llama.cpp, LiteRT, AICore/Gemini Nano) recompute identical
prompts again and again. I propose an optional, app-scoped response cache API (or a documented
reference library) so repeated prompts with identical parameters return a stored answer instead
of re-running inference.

Problem
- On-device generation is slow and battery-hungry (seconds per answer on mid-range CPUs).
- Each app re-implements ad-hoc caching, usually without deterministic keys, size limits,
  versioning or privacy controls.
- There is no platform guidance on caching generative outputs safely.

Proposal
1. A cache keyed by a canonical hash: sha256(NFC-normalized prompt | model id | canonical JSON of
   sampling parameters incl. seed, temperature, top_p, top_k, system prompt).
2. Per-app storage only (no cross-app sharing by default, to avoid leaking prompts between apps),
   excluded from backups, optional Keystore-backed encryption at rest.
3. Size cap with LRU eviction, optional TTL, explicit invalidation when the model changes.
4. Optional semantic lookup (int8 embeddings) as a separate, opt-in mode.
5. Exposed either as a Jetpack/AAR library (preferred, no platform change) or, if there is
   interest, as an optional layer on top of AICore.

Reference implementation (prototype, not Android-native yet)
- SeedMesh: https://github.com/Kidaouene/seedmesh (Apache-2.0). SQLite cache + llama.cpp agent, Linux/Windows/Termux.
- Measured on an 8-vCPU x86 server, Qwen2.5-1.5B-Instruct Q4_K_M, llama.cpp b11921:
  cache hit ~89 ms vs ~4.0-4.2 s generation.
- Proposed Android architecture: foreground service (declared FGS type), AIDL + ContentProvider
  protected by a signature permission, no TCP port, app-internal storage.

Honest limitations
- Not tested on a real Android device yet (only Linux; Termux scripts untested on hardware).
- Even with seed 42 and temperature 0, outputs are not bit-exact across runs/threads/CPUs
  (we measured occasional differences); the cache, not the generation, provides repeatability.
- Cached answers can be stale or wrong (small models hallucinate); cache entries store prompts
  in clear text unless encrypted.
- The prototype HTTP server has no authentication (bound to 127.0.0.1).
- The prototype code and this text were prepared with the help of an AI assistant.

License: Apache-2.0. I am happy to adapt the library to Jetpack conventions if useful.
```

## 3. Version courte en français (pour Samir, à ne pas envoyer)
- **Titre** : demande de fonctionnalité pour une API optionnelle de cache de réponses, pour l'inférence LLM locale sur Android.
- **Idée** : quand une app pose deux fois la même question à un LLM local avec les mêmes réglages, elle relit la réponse stockée (~89 ms) au lieu de recalculer (~4 s).
- **Garde-fous** : cache par application et non partagé, exclu des sauvegardes, chiffrement possible, taille plafonnée, invalidation quand le modèle change.
- **Forme** : de préférence une bibliothèque (Jetpack/AAR), sans modifier Android ; éventuellement une couche au-dessus d'AICore.
- **Limites dites franchement** : pas testé sur un vrai téléphone, sorties pas parfaitement identiques, réponses pouvant être fausses ou périmées, serveur de démo sans authentification, préparation assistée par IA.

## 4. Étapes exactes (c'est Samir qui les fait)
1. **Créer le dépôt GitHub public** de SeedMesh (contenu de seedmesh.zip, licence Apache 2.0, README avec déclaration d'usage de l'IA) et noter son URL. *Recommandé avant tout envoi.*
2. Se connecter avec un compte Google sur https://issuetracker.google.com.
3. Chercher les doublons : `componentid:192705 cache`, « on-device LLM cache », « AICore », issues ouvertes **et** fermées. S'il existe déjà une demande proche, **ajouter une étoile** et un commentaire court plutôt que d'en créer une nouvelle.
4. Ouvrir https://issuetracker.google.com/issues/new?component=192705. Vérifier que le composant affiché est bien « Android Public Tracker › … › Framework » ; choisir le type « Feature Request » si le champ existe.
5. Coller le titre et la description du §2, remplacer `https://github.com/Kidaouene/seedmesh`, relire, puis **Create**.
6. Noter le numéro de l'issue et activer les notifications. Ne pas relancer de façon répétée. Sans réponse, c'est normal.
7. Pas de Gerrit ni de CLA à cette étape. Ils ne seront utiles que si un ingénieur Google demande un patch.

