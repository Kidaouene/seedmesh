#!/system/bin/sh
# Exécuté par Magisk/KernelSU en fin de boot (late_start service). Ne touche pas à /system.
MODDIR=${0%/*}
LOG=/data/local/tmp/seedmesh_module.log
TERMUX=/data/data/com.termux/files
until [ "$(getprop sys.boot_completed)" = 1 ]; do sleep 5; done
sleep 15
echo "$(date) boot" >>"$LOG"
# --- Réglages OPTIONNELS : actifs seulement si le fichier $MODDIR/enable_tuning existe ---
if [ -f "$MODDIR/enable_tuning" ]; then
  echo "$(cat /proc/sys/vm/swappiness)" >"$MODDIR/orig_swappiness"
  echo 100 >/proc/sys/vm/swappiness 2>>"$LOG"          # non persistant : disparaît au reboot suivant si le module est retiré
  settings put global settings_enable_monitor_phantom_procs false
  echo "$(date) tuning appliqué" >>"$LOG"
fi
# --- Lancement de SeedMesh dans l'environnement Termux, sous l'UID de Termux ---
if [ -x "$TERMUX/usr/bin/seedmesh" ]; then
  TUID=$(stat -c %u "$TERMUX")
  su "$TUID" -c "export PREFIX=$TERMUX/usr HOME=$TERMUX/home PATH=$TERMUX/usr/bin:\$PATH LD_PRELOAD=$TERMUX/usr/lib/libtermux-exec.so; seedmesh start" >>"$LOG" 2>&1
else
  echo "$(date) seedmesh absent de Termux" >>"$LOG"
fi
