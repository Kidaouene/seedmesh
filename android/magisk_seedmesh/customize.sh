# Installateur Magisk : aucun fichier système remplacé.
ui_print "- SeedMesh launcher : lance 'seedmesh start' (Termux) au boot"
ui_print "- Réglages optionnels : touch /data/adb/modules/seedmesh/enable_tuning"
set_perm "$MODPATH/service.sh" 0 0 0755
set_perm "$MODPATH/uninstall.sh" 0 0 0755
