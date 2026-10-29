# XDA Forums — PAS de texte prêt (règle vérifiée)
- Règle 15 : « Using AI to generate post content in the forums is NOT permitted. » Samir doit écrire lui-même.
- Sous-forum : « Themes and Apps », ou le forum Magisk/modules de l'appareil concerné. Pas de « Development » sans release testée.

## Fiche de faits à reformuler soi-même
- Contenu : `android/termux_boot_seedmesh.sh`, `android/adb_tune.sh` (status/apply/revert, sauvegarde automatique), module Magisk `android/magisk_seedmesh` (ne touche pas `/system`, lance SeedMesh sous l'UID de Termux, réglages optionnels désactivés par défaut, `uninstall.sh` restaure).
- **Non testé sur appareil** : à dire clairement, ou poster seulement après un test.
- Avertissements obligatoires : déverrouiller le bootloader efface les données et casse Play Integrity (DEVICE/STRONG), donc les applications bancaires ; risque de bootloop au niveau root (safe mode/recovery).
- Aucun gain de « fluidité » ni de son revendiqué ; protocole de mesure dans `docs/ANDROID_NATIF.md`.
- Déclarer que le code a été généré avec une IA.
