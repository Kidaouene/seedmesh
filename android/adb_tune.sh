#!/usr/bin/env bash
# SeedMesh — réglages ADB réversibles (sans root). À lancer depuis un PC (adb) ou Termux (pkg install android-tools + adb pair/connect).
#   ./adb_tune.sh status          affiche les valeurs actuelles
#   ./adb_tune.sh apply           sauvegarde puis applique
#   ./adb_tune.sh revert          restaure la sauvegarde
#   ./adb_tune.sh compile PKG     cmd package compile -m speed-profile -f PKG (réversible : compile-reset)
# Rien ici ne touche à l'audio. Les gains de fluidité sont À MESURER (voir docs/ANDROID_NATIF.md).
set -euo pipefail
ADB="${ADB:-adb}"; BK="${BACKUP:-./adb_tune.backup}"
KEYS=(window_animation_scale transition_animation_scale animator_duration_scale settings_enable_monitor_phantom_procs)
sh_() { "$ADB" shell "$@" | tr -d '\r'; }
sdk() { sh_ getprop ro.build.version.sdk; }
status() {
  echo "SDK=$(sdk)"
  for k in "${KEYS[@]}"; do echo "global $k=$(sh_ settings get global "$k")"; done
  echo "max_phantom_processes=$(sh_ /system/bin/device_config get activity_manager max_phantom_processes || true)"
}
apply() {
  [ -e "$BK" ] && { echo "Sauvegarde $BK existe déjà : faites 'revert' d'abord."; exit 1; }
  for k in "${KEYS[@]}"; do echo "$k=$(sh_ settings get global "$k")"; done >"$BK"
  echo "max_phantom_processes=$(sh_ /system/bin/device_config get activity_manager max_phantom_processes || true)" >>"$BK"
  for k in window_animation_scale transition_animation_scale animator_duration_scale; do sh_ settings put global "$k" 0.5; done
  local s; s=$(sdk)
  if [ "$s" -ge 32 ]; then sh_ settings put global settings_enable_monitor_phantom_procs false; fi   # 12L/13/14+
  if [ "$s" -eq 31 ]; then sh_ /system/bin/device_config put activity_manager max_phantom_processes 2147483647; fi  # Android 12
  echo "Appliqué (sauvegarde : $BK)."; status
}
revert() {
  [ -e "$BK" ] || { echo "Pas de sauvegarde $BK."; exit 1; }
  while IFS='=' read -r k v; do
    if [ "$k" = max_phantom_processes ]; then
      if [ "$v" = null ] || [ -z "$v" ]; then sh_ /system/bin/device_config delete activity_manager max_phantom_processes || true
      else sh_ /system/bin/device_config put activity_manager max_phantom_processes "$v"; fi
    elif [ "$v" = null ] || [ -z "$v" ]; then sh_ settings delete global "$k"
    else sh_ settings put global "$k" "$v"; fi
  done <"$BK"
  rm -f "$BK"; echo "Restauré."; status
}
case "${1:-status}" in
  status) status ;; apply) apply ;; revert) revert ;;
  compile) sh_ cmd package compile -m speed-profile -f "${2:?paquet}" ;;
  compile-reset) sh_ cmd package compile --reset "${2:?paquet}" ;;
  *) echo "usage: $0 status|apply|revert|compile PKG|compile-reset PKG"; exit 2 ;;
esac
