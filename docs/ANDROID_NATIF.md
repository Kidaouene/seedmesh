# SeedMesh sur Android — intégration par niveaux (BROUILLON)

> SeedMesh est une **couche au-dessus d'Android** : un cache LLM et un agent. Il **ne remplace pas** Android, ne modifie pas le système, et **n'agit pas sur l'audio**. Aucun test n'a encore été fait sur un appareil réel : tout ce qui suit est à valider (tâche B4 de BOUNTY.md). Les scripts sont dans `android/` ; leur syntaxe est vérifiée (`bash -n`), et `adb_tune.sh apply/revert` a été testé contre un faux `adb`.

## Niveau A — Termux, sans root (recommandé)
- **Installation** : Termux depuis F-Droid ou GitHub. La version Play Store est expérimentale, et Termux comme ses plugins doivent venir **de la même source**, faute de quoi on obtient `INSTALL_FAILED_SHARED_USER_INCOMPATIBLE`. Ensuite : `pkg install llama-cpp` (paquet officiel) ou `install_termux.sh`.
- **Termux:API** (optionnel) : notifications et `termux-wake-lock`.
- **Termux:Boot** : `android/termux_boot_seedmesh.sh` va dans `~/.termux/boot/`. Il prend un wake-lock, attend 20 s, puis lance `seedmesh start` (log dans `~/.seedmesh/boot.log`). **Retour arrière** : supprimer le fichier, puis `seedmesh stop`.
- **Phantom process killer (Android 12+)** : Android tue les processus enfants au-delà de 32, ou ceux qui consomment trop de CPU. Symptôme : `[Process completed (signal 9)]`. Contournements documentés par Termux (agnostic-apollo) :
  - **Android 14+** : Options développeur → « Désactiver les restrictions des processus enfants ». L'option **se réactive si les options développeur sont désactivées**.
  - **Android 12L/13/14+ via ADB** : `settings put global settings_enable_monitor_phantom_procs false`. Retour arrière : `settings delete global settings_enable_monitor_phantom_procs`.
  - **Android 12** : `device_config put activity_manager max_phantom_processes 2147483647`. Pour que Play Services ne le réinitialise pas : `device_config set_sync_disabled_for_tests persistent`, ce qui **bloque aussi d'autres mises à jour de configuration à distance**. Retour arrière : `device_config set_sync_disabled_for_tests none` et `device_config delete activity_manager max_phantom_processes`.
  - Le script `android/adb_tune.sh` applique la variante adaptée au SDK, avec sauvegarde et `revert`.
- **Limites** : l'optimisation batterie peut tuer Termux (il faut l'exempter manuellement) ; les surcouches OEM (MIUI, One UI…) sont plus agressives ; la RAM d'un téléphone limite le modèle (1,1 Go pour Qwen 1.5B Q4).

## Niveau B — ADB ou Shizuku, sans root
L'ADB tourne sous l'UID `shell` ; **Shizuku** donne ce même niveau de privilège aux applications. Sans root, Shizuku doit être **relancé après chaque redémarrage**, via le débogage sans fil.
| Commande | Effet | Retour arrière |
|---|---|---|
| `settings put global window_animation_scale 0.5` (+ `transition_animation_scale`, `animator_duration_scale`) | Animations plus courtes : **impression** de fluidité, aucun gain de calcul | `adb_tune.sh revert` (valeurs sauvegardées) |
| `cmd package compile -m speed-profile -f <pkg>` | Recompile une application avec ART selon son profil | `cmd package compile --reset <pkg>` |
| `cmd package bg-dexopt-job` | Force l'optimisation dex en arrière-plan (longue, consomme la batterie) | aucun nécessaire (ART refait ses choix) |
| `dumpsys gfxinfo <pkg> framestats`, `dumpsys meminfo`, `dumpsys batterystats` | **Mesure** (voir le protocole) | lecture seule |
| `cmd activity` (`get-standby-bucket`, `set-standby-bucket <pkg> active`) | Bucket de veille de Termux | `set-standby-bucket <pkg> <ancienne valeur>` |
- **Limites** : pas d'accès à `/proc/sys`, au CPU governor ni à zram ; certaines commandes varient selon l'OEM et la version ; les `settings` et `device_config` peuvent être remis à zéro par une mise à jour.

## Niveau C — Root (Magisk / KernelSU) et LSPosed
- **Module** `android/magisk_seedmesh/` (`module.prop`, `customize.sh`, `service.sh`, `uninstall.sh`, `META-INF`). **Il ne modifie pas `/system`.** `service.sh` attend `sys.boot_completed`, puis lance `seedmesh start` **sous l'UID de Termux**, pas en root.
- **Réglages optionnels**, désactivés par défaut et activés par `touch /data/adb/modules/seedmesh/enable_tuning` : swappiness 100 (utile avec zram ; la valeur d'origine est sauvegardée) et désactivation du phantom killer. `uninstall.sh` restaure le tout.
- **Volontairement absents** : les props `build.prop` et le CPU governor forcé (`performance`). Le gain est incertain, l'appareil chauffe davantage, le throttling thermique peut **réduire** les performances soutenues, et la batterie souffre. S'ils sont tentés, il faut les mesurer en A/B et toujours prévoir un retour arrière dans `uninstall.sh`. **Mode de secours** si une modification empêche le démarrage : Magisk permet de désactiver les modules depuis le recovery ou un safe mode (selon la version) ; KernelSU propose un mécanisme équivalent.
- **LSPosed** (framework Xposed sur Zygisk) : hooks **au niveau des applications** de son « scope », pas du système entier. Utile pour injecter un appel au cache dans **une** application donnée ; fragile à chaque mise à jour de cette application. Ce n'est pas recommandé pour SeedMesh.

## Niveau D — App Android native / AAR (cible propre)
llama.cpp via **JNI** (le dépôt fournit `docs/android.md` et un exemple Android) ; **foreground service** avec un type déclaré (exigé depuis Android 14) ; API **AIDL** + **ContentProvider** protégés par une permission `signature`, sans port TCP ; stockage interne exclu des sauvegardes. Architecture détaillée dans **AOSP_PROPOSAL.md §3**. C'est la seule voie compatible avec le Play Store et F-Droid sans root.

## Limites légales et techniques
- **Déverrouillage du bootloader** (nécessaire pour root) : **efface les données** ; peut **annuler ou limiter la garantie** selon le fabricant et le pays (en UE, la garantie légale de conformité ne disparaît pas automatiquement, mais le fabricant peut refuser une panne qu'il attribue à la modification) ; certains appareils (opérateurs, certains OEM) ne peuvent pas être déverrouillés.
- **Play Integrity** : les verdicts sont `MEETS_BASIC_INTEGRITY`, `MEETS_DEVICE_INTEGRITY` et `MEETS_STRONG_INTEGRITY`. Un bootloader déverrouillé fait en pratique **échouer DEVICE et STRONG**. Beaucoup d'**applications bancaires**, de paiement sans contact (Google Wallet), de streaming DRM ou de jeux refusent alors de fonctionner. Contourner ces vérifications (spoofing) viole les conditions de ces services ; **ce n'est pas proposé ici**. Les niveaux A, B et D n'affectent pas Play Integrity ; activer les options développeur ou le débogage USB peut gêner quelques applications bancaires.
- **ToS de Google Play** : une application publiée ne peut pas télécharger de **code exécutable** hors du Play Store (un modèle GGUF est une donnée, mais il faut le déclarer et le justifier) ; les foreground services doivent avoir un type justifié ; les permissions sensibles sont soumises à revue. F-Droid exige un consentement explicite pour tout binaire exécutable téléchargé.
- **Risque de brick** : nul aux niveaux A, B et D ; faible mais réel au niveau C (bootloop en cas de module défectueux, à récupérer via le safe mode ou le recovery). Il ne faut **jamais** flasher de partition (boot/vendor) sans sauvegarde de l'image d'origine.
- **Android 14+** : types de foreground service obligatoires ; restrictions sur le démarrage en arrière-plan et sur les broadcasts implicites ; `targetSdk` minimal imposé pour les applications installables ; limites accrues en arrière-plan. Termux, qui vise un `targetSdk` ancien, est concerné par ces évolutions.

## Workflow de modification rapide (toujours réversible)
```bash
# A — Termux
cp android/termux_boot_seedmesh.sh ~/.termux/boot/ && chmod +x ~/.termux/boot/termux_boot_seedmesh.sh
#   revert : rm ~/.termux/boot/termux_boot_seedmesh.sh
# B — ADB (PC ou Termux : pkg install android-tools ; adb pair/connect)
./android/adb_tune.sh status ; ./android/adb_tune.sh apply      # sauvegarde automatique
./android/adb_tune.sh revert                                    # restauration exacte
# C — Magisk/KernelSU : zipper le dossier, installer depuis l'application
cd android/magisk_seedmesh && zip -r ../seedmesh-magisk.zip . && cd -
#   revert : désinstaller le module dans Magisk (uninstall.sh restaure) → redémarrer
```
Règle : **une modification à la fois**, mesurée avant et après (protocole ci-dessous), avec sauvegarde.

## Honnêteté sur les gains
- Le gain démontré par SeedMesh concerne la **latence des réponses LLM répétées** (89 ms contre ~4 s sur la box). Ce n'est pas la fluidité de l'interface.
- Les réglages d'animation changent la **perception**, pas la puissance. Les réglages root (swappiness, governor) ont un effet **incertain**, à mesurer.
- Le **son** n'est pas concerné : la « meilleure qualité sonore » rapportée est un retour subjectif, non mesuré (voir le protocole ABX).

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
