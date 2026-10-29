#!/usr/bin/env bash
# Wrapper SeedMesh : modèle local en priorité 1, cache d'abord.
# seedmesh ask "prompt" [options agent.py] | status | start | stop | restart | gc | sync URL [push|pull|both] | cache <cmd>
set -euo pipefail
ROOT="${SEEDMESH_ROOT:-/opt/seedmesh}"
export SEEDMESH_CONFIG="${SEEDMESH_CONFIG:-$ROOT/config.json}"
export SEEDMESH_HOME="${SEEDMESH_HOME:-$ROOT/data}"
APP="$ROOT/app"; LOG="$SEEDMESH_HOME/logs"; PY="${SEEDMESH_PYTHON:-python3}"
umask 000  # DB/KV partagés entre tous les utilisateurs/bots
export SEEDMESH_MAX_MB="${SEEDMESH_MAX_MB:-512}"
cfg() { "$PY" -c "import json,sys;c=json.load(open('$SEEDMESH_CONFIG'));p=sorted(c['providers'],key=lambda p:p.get('priority',99))[0];s=c['sampling'];print(eval(sys.argv[1]))" "$1"; }
up() { curl -s -m 2 "$1" >/dev/null 2>&1; }

start() {
  mkdir -p "$LOG" "$SEEDMESH_HOME/kv"
  local surl; surl=$(cfg "p.get('server_url','http://127.0.0.1:8080')"); local port=${surl##*:}
  if up "$surl/health"; then echo "llama-server déjà actif ($surl)"; else
    setsid nohup "$(cfg "p['llama_server_bin']")" -m "$(cfg "p['model']")" --host 127.0.0.1 --port "$port" \
      -c "$(cfg "s['ctx']")" -t "$(cfg "s['threads']")" -np 1 --slot-save-path "$SEEDMESH_HOME/kv" \
      >"$LOG/llama-server.log" 2>&1 & echo $! >"$SEEDMESH_HOME/llama-server.pid"; echo "llama-server lancé ($surl, pid $!)"; fi
  local curl_; curl_=$(cfg "c.get('cache_server','http://127.0.0.1:8765')"); local cport=${curl_##*:}
  if up "$curl_/stats"; then echo "cache HTTP déjà actif ($curl_)"; else
    setsid nohup "$PY" "$APP/seedmesh_cache.py" --no-emb serve --host 127.0.0.1 --port "$cport" >"$LOG/cache-server.log" 2>&1 &
    echo $! >"$SEEDMESH_HOME/cache-server.pid"; echo "cache HTTP lancé ($curl_, pid $!)"; fi
}
stop() { for n in llama-server cache-server; do f="$SEEDMESH_HOME/$n.pid"; [ -f "$f" ] && kill "$(cat "$f")" 2>/dev/null && echo "$n arrêté"; rm -f "$f"; done; }

case "${1:-status}" in
  ask) shift; exec "$PY" "$APP/agent.py" "$@" ;;
  status)
    echo "config : $SEEDMESH_CONFIG"; echo "provider prioritaire : $(cfg "p['name']+' (priority '+str(p['priority'])+') -> '+p['model']")"
    echo "sampling : $(cfg "s")"
    surl=$(cfg "p.get('server_url','http://127.0.0.1:8080')"); curl_=$(cfg "c.get('cache_server','http://127.0.0.1:8765')")
    up "$surl/health" && echo "llama-server : OK ($surl)" || echo "llama-server : arrêté (seedmesh start)"
    up "$curl_/stats" && echo "cache HTTP   : OK ($curl_)" || echo "cache HTTP   : arrêté (seedmesh start)"
    "$PY" "$APP/seedmesh_cache.py" --no-emb stats ;;
  start) start ;;
  stop) stop ;;
  restart) stop; sleep 1; start ;;
  gc) shift; exec "$PY" "$APP/seedmesh_cache.py" --no-emb gc "$@" ;;
  sync) shift; exec "$PY" "$APP/sync.py" "$@" ;;
  cache) shift; exec "$PY" "$APP/seedmesh_cache.py" "$@" ;;
  *) echo "usage : seedmesh ask \"prompt\" [--kv] [--refine N] [--server URL] | status | start | stop | restart | gc | sync URL | cache <cmd>"; exit 2 ;;
esac
