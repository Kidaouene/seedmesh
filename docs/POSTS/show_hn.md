# Hacker News « Show HN » — PAS de texte prêt (règle vérifiée)
- Règle HN : « Please don't put generated text in HN posts. Write your text yourself ». Les commentaires générés ou édités par IA sont aussi interdits.
- Règle Show HN : quelque chose que l'on **a fait soi-même**, essayable sans barrière, non trivial, « don't post quickly-generated one-offs ». Il faut être là pour répondre.
- ⚠️ Risque : le code est généré par IA et Samir ne code pas, donc il lui sera difficile de répondre aux questions techniques. **Je recommande d'attendre** un contributeur humain ou un vrai test sur téléphone.

## Fiche de faits (Samir écrit lui-même titre et texte)
- Titre : doit commencer par « Show HN: », sans majuscules ni points d'exclamation pour attirer l'œil. Contenu : nom + ce que ça fait.
- Lien : {REPO_URL}. Le README doit permettre d'essayer en quelques commandes (`install_linux.sh`).
- Chiffres réels : hit ~89 ms contre 4,0-4,2 s ; 22-25 tok/s ; Qwen2.5-1.5B Q4_K_M ; llama.cpp b11921 ; Xeon 8 vCPU.
- Point intéressant pour HN : le non-déterminisme mesuré à température 0 (2 écarts sur 5 régénérations).
- Limites à citer : pas d'auth HTTP, pas testé sur téléphone, pas de TTL, prompts en clair, code généré par IA (le dire en premier commentaire).
