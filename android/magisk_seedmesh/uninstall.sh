#!/system/bin/sh
# Appelé par Magisk/KernelSU à la désinstallation du module : remet ce que service.sh a pu changer.
MODDIR=${0%/*}
[ -f "$MODDIR/orig_swappiness" ] && cat "$MODDIR/orig_swappiness" >/proc/sys/vm/swappiness
settings delete global settings_enable_monitor_phantom_procs
rm -f /data/local/tmp/seedmesh_module.log
