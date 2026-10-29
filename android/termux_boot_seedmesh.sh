#!/data/data/com.termux/files/usr/bin/sh
# SeedMesh — démarrage au boot via Termux:Boot (app Termux:Boot, même source que Termux : F-Droid ou GitHub).
# Installation :  mkdir -p ~/.termux/boot && cp termux_boot_seedmesh.sh ~/.termux/boot/ && chmod +x ~/.termux/boot/termux_boot_seedmesh.sh
# Retour arrière : rm ~/.termux/boot/termux_boot_seedmesh.sh   (puis : seedmesh stop)
LOG="$HOME/.seedmesh/boot.log"; mkdir -p "$HOME/.seedmesh"
command -v termux-wake-lock >/dev/null 2>&1 && termux-wake-lock   # évite la mise en veille du CPU (Termux:API non requis)
sleep 20                                                          # laisse le système finir de démarrer
if command -v seedmesh >/dev/null 2>&1; then
  echo "$(date '+%F %T') seedmesh start" >>"$LOG"
  seedmesh start >>"$LOG" 2>&1
else
  echo "$(date '+%F %T') seedmesh introuvable dans PATH" >>"$LOG"
fi
