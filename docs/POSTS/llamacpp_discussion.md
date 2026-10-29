# Discussions ggml-org/llama.cpp — PAS de texte prêt (règle vérifiée)
- CONTRIBUTING.md : « It is strictly prohibited to use AI to write your posts for you (bug reports, feature requests, pull request descriptions, Github discussions, responding to humans) ». Une IA non déclarée peut entraîner un **bannissement définitif**. Les soumissions automatisées sont interdites.
- AGENTS.md : un agent ne doit pas rédiger ces textes. **Je ne fournis donc qu'une fiche de faits** ; Samir écrit avec ses mots, en catégorie « Show and tell ».

## Fiche de faits
- Lien {REPO_URL} ; Apache 2.0 ; utilise llama.cpp b11921 (llama-completion `--prompt-cache --prompt-cache-all`, llama-server `--slot-save-path` + `POST /slots/{id}?action=save|restore`).
- Constat utile pour les mainteneurs : le nouveau `llama-cli` n'a plus `--prompt-cache` depuis b7348 ; SeedMesh passe par `llama-completion`.
- Mesure : non-déterminisme ponctuel à température 0, même build, même nombre de threads (1 prompt sur 5, 2 fois sur 5 régénérations). C'est une observation, pas un rapport de bug : ne pas ouvrir d'issue sans reproduction minimale.
- Chiffres : 22-25 tok/s, hit ~89 ms contre ~4 s (CPU Xeon 8 vCPU, Qwen2.5-1.5B Q4_K_M).
- Mentionner que le code de SeedMesh a été généré avec une IA.
