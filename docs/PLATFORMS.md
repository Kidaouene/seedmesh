# SeedMesh — Plateformes (BROUILLON, recherche du 2026-10-29 ; rien n'est publié ni soumis)

SeedMesh est un **outil local open source** (Apache 2.0), pas un service cloud. Les bug bounties d'entreprise (Google, Meta, Bugcrowd…) paient pour des failles **dans leurs propres produits** : ils ne financent pas SeedMesh.

Vérification : ✔ = vérifié par recherche web aujourd'hui ; ~ = connu, mais pas revérifié aujourd'hui.

Colonne « IA » : règle sur l'usage d'une IA **pour préparer la soumission** (texte du post, de la PR ou de la demande).
- **Interdit** : l'IA ne doit pas écrire le texte.
- **Toléré** : autorisé, avec déclaration.
- **Non précisé** : aucune règle trouvée.

Fait important pour toutes les plateformes : **le code de SeedMesh a été généré par un agent IA**. Il faut le déclarer partout où l'IA est réglementée.

## 1. Canaux pour PAYER des contributeurs
| Plateforme | Type | Ce qu'elle accepte | Éligibilité | IA pour la soumission | Pertinence |
|---|---|---|---|---|---|
| Algora ✔ | Gratuit pour poster ; frais sur les paiements ~ | Bounties sur des issues GitHub (`/bounty 100`) | Dépôt GitHub public | Non précisé | **Haute** (tâches B1 à B7), une fois l'enveloppe financée |
| IssueHunt ✔ | Frais sur les montants ~ | Bounties sur des issues GitHub | Dépôt GitHub | Non précisé | Moyenne |
| Opire, BountyHub, TaskBounty ✔ | Variable | Bounties sur des issues | GitHub | Non précisé | Faible |
| HackerOne Community Edition ✔ | **Gratuit** pour l'open source ; 5 % de frais sur les primes | Programme de vulnérabilités ou de bounty | Licence OSI, projet actif ≥ 3 mois, `SECURITY.md`, approbation discrétionnaire | Non précisé | **Haute** pour la sécurité, après 3 mois d'activité |
| GitHub Security Advisories ~ | Gratuit | Signalement privé, CVE, sans paiement | Dépôt GitHub | Non précisé | **Haute** dès maintenant (canal de SECURITY.md) |
| Bugcrowd / Intigriti / YesWeHack ✔ | **Payant**, offres entreprise | Programmes gérés | Organisations | Non précisé | **Ne s'applique pas** (coût, conçus pour des services en ligne) |
| Gitcoin ✔ | — | Bounties repris par Buidlbox ; grants web3 | Web3 et biens publics | Non précisé | Faible |
| Polar ✔ | — | **Issue funding fermé** (avril 2025) | — | — | **Ne s'applique plus** |

## 2. Programmes qui pourraient PAYER Samir (dons, subventions, primes)
| Plateforme | Type | Ce qu'elle accepte | Éligibilité | IA pour la soumission | Pertinence |
|---|---|---|---|---|---|
| GitHub Sponsors ~ | Gratuit ; 0 % de frais (comptes personnels) | Dons | Pays pris en charge | Non précisé | Moyenne |
| Liberapay ~ | Gratuit (association à but non lucratif, frais de paiement Stripe ou PayPal seulement) ; recommandé par F-Droid ✔ | Dons récurrents | Tous | Non précisé | Moyenne |
| Open Collective (Open Source Collective) ✔ | Frais de l'hôte fiscal ~ | Budget transparent, dons | Projet open source actif et original, licence approuvée, idéalement plusieurs administrateurs ✔ | Non précisé | Moyenne : pour **financer l'enveloppe** des bounties |
| **NLnet / Restack** ✔ | Subvention de 5 000 à 50 000 € | R&D de l'Open Internet Stack | Dimension européenne | **IA INTERDITE** pour la rédaction (proposition « par des humains », journal de prompts obligatoire) ; projets d'IA **hors périmètre** (sauf > 1 M d'utilisateurs) ; code « vibecodé » non éligible | **Ne s'applique pas** (dossier annulé par Samir) |
| Prototype Fund ✔ | Subvention | Logiciel open source d'intérêt public | Résidence fiscale en Allemagne | Non précisé | **Non éligible** (résidence) |
| Google Android VRP ✔ | Google paie | Failles avec PoC dans AOSP et les appareils Google | Chercheurs | Non précisé | **Ne s'applique pas** au projet (pas de propositions) |
| Meta Bug Bounty ~ | Meta paie | Failles dans les produits Meta | Chercheurs | Non précisé | **Ne s'applique pas** |
| huntr ✔ | — | Programme OSS fermé le 2026-06-30 ; devenu une plateforme de compétitions de sécurité IA | — | — | **Ne s'applique plus** |

## 3. Visibilité gratuite et canaux de contribution
| Canal | Ce qui y est accepté | Éligibilité / règles | IA pour la soumission | Pertinence |
|---|---|---|---|---|
| **Google Issue Tracker (Android)** ✔ | Bugs et **demandes de fonctionnalité AOSP** | Compte Google | Non précisé | Voie correcte pour une proposition : voir **AOSP_SUBMISSION.md** |
| AOSP Gerrit ✔ | **Patchs de code uniquement** | CLA Google + compte Google, `repo upload`, revue par les owners | Non précisé | Faible (pas pour une proposition) |
| GitHub (dépôt, Discussions) ~ | Code, issues, discussions | Compte GitHub | Non précisé au niveau de la plateforme | **Prérequis** à tout le reste |
| **Discussions llama.cpp** ✔ | « Show and tell », demandes | — | **Interdit** : l'IA ne doit pas écrire les posts (issues, feature requests, descriptions de PR, discussions) ; le code IA est toléré s'il est **déclaré** et compris ligne par ligne ; PR automatisées = risque de bannissement | Haute, mais **Samir doit écrire lui-même** |
| r/LocalLLaMA ✔ | Projets d'IA locale | Karma minimum (règles d'avril 2026), règle 3 contre le contenu « low effort » | **Interdit sans déclaration** : un post écrit par un LLM et non déclaré est banni ; un usage réfléchi est accepté | Haute |
| r/selfhosted ✔ | Projets auto-hébergés | Mégathread « New Project » du vendredi ; un bot demande de déclarer l'usage de l'IA ; auto-promotion : compte ≥ 30 jours, ≤ 10 % de posts promotionnels (exception pour le FLOSS) | **Toléré avec déclaration** (+ tag) | Moyenne (SeedMesh s'auto-héberge) |
| r/androiddev ~ | Développement Android | Règles d'auto-promotion (non vérifiées) | Non précisé (non vérifié) | Faible tant qu'il n'y a pas d'AAR |
| r/termux ~ | Usage de Termux | — | Non précisé (non vérifié) | Haute après un test sur appareil réel |
| Hacker News « Show HN » ✔ | Projet **utilisable**, fait par soi, non trivial (« pas de one-off généré rapidement ») | Être présent pour répondre | **Interdit** : pas de texte généré dans les posts ni les commentaires | Moyenne (risque : code généré par IA, projet jeune) |
| dev.to ✔ | Articles | — | **Toléré avec déclaration** (`#ABotWroteThis`), mais pas pour promouvoir ; les commentaires IA sont interdits | Moyenne |
| XDA Forums ✔ | Mods, modules Magisk, applications | Bon sous-forum | **Interdit** (règle 15) | Moyenne pour `android/` |
| Product Hunt ✔ | Lancements de produits | — | Commentaires IA interdits ; texte de lancement non précisé | Faible |
| Hugging Face (Spaces, forum) ~ | Démos, posts | Compte HF | Non précisé | Faible à moyenne |
| F-Droid ✔ | Applications FLOSS compilées depuis les sources | Politique d'inclusion ; politique IA intérimaire 2026 : développement assisté par IA **toléré** avec revue humaine et tests ; les applications LLM peuvent recevoir un tag « anti-feature » | Toléré | Plus tard (application du niveau D) |

## 4. Recommandation (à trancher par Samir)
1. **D'abord** : un dépôt GitHub public et propre, avec un README qui **déclare l'usage d'une IA** pour le code et les docs.
2. Sécurité : GitHub Security Advisories, puis HackerOne Community Edition après 3 mois.
3. Visibilité : r/selfhosted (mégathread du vendredi, tag IA) et r/LocalLLaMA (avec déclaration). Sur HN, XDA et les discussions llama.cpp, le texte doit être **écrit par Samir**, sans IA.
4. Financement : GitHub Sponsors ou Liberapay ; Open Collective si l'enveloppe des bounties doit être transparente.
5. Android : une demande de fonctionnalité sur l'Issue Tracker (AOSP_SUBMISSION.md), sans attente d'adoption.

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
