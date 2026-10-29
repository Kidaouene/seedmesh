# LinuxFr.org — journal (publication sans modération préalable ; aucune règle IA trouvée, mais public critique envers les LLM : déclaration en tête)

**Titre :** SeedMesh : un cache SQLite pour LLM local (llama.cpp), et pourquoi « seed 42 + température 0 » ne suffit pas

> **Transparence** : le code de SeedMesh et ce journal ont été rédigés avec l'aide d'un assistant IA. Les chiffres viennent de mesures réelles sur un serveur ; je les ai vérifiés.

Bonjour 'nal,

SeedMesh ({REPO_URL}, licence Apache 2.0) met en cache les réponses d'un modèle local llama.cpp dans SQLite. Une question déjà posée, avec exactement les mêmes paramètres, revient en **~89 ms** au lieu de **4 à 4,2 s** de génération. Mesure faite sur un Xeon de 8 vCPU, avec Qwen2.5-1.5B-Instruct Q4_K_M et llama.cpp b11921.

**Ce qu'il y a dedans**
- La clé est `sha256(prompt normalisé NFC | fichier du modèle | JSON canonique des paramètres)` ; implémentations Python et PowerShell 7 identiques.
- Embeddings int8 optionnels, plafond de taille LRU, synchronisation JSONL entre Linux, Windows et Termux.
- Réutilisation du cache KV de llama.cpp (`--prompt-cache`, `/slots` de llama-server).
- `repro_check.py` : un manifeste (build, sha256 du GGUF, paramètres, CPU/SIMD, hash des sorties de prompts de référence).

**La surprise** : avec seed 42 et température 0, sur la même machine et le même build, un des 5 prompts de référence a donné **deux fois** une sortie différente sur 5 régénérations (des guillemets en plus ou en moins). La reproductibilité vient donc du cache, pas de l'échantillonneur.

**Limites, sans fard**
- Pas encore testé sur un vrai téléphone Android (Termux).
- Le serveur HTTP n'a pas d'authentification : il écoute sur 127.0.0.1, ne l'exposez pas.
- Pas de TTL ; les prompts sont stockés en clair.
- Un modèle de 1,5 milliard de paramètres se trompe souvent, et le cache resservira l'erreur.
- Le repli vers un fournisseur cloud est soumis à ses quotas.

Retours et critiques bienvenus, surtout de la part de ceux qui font tourner llama.cpp sur ARM.
