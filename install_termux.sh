#!/data/data/com.termux/files/usr/bin/bash
# Installation SeedMesh sur Termux (Android, CPU ARM64) avec la MÊME config que la box.
# Usage : bash install_termux.sh        (depuis le dossier du projet)
set -euo pipefail
SRC="$(cd "$(dirname "$0")" && pwd)"
ROOT="${ROOT:-$HOME/seedmesh}"
THREADS="${THREADS:-4}"            # 4 grands cœurs typiques ; ajuster selon le SoC
MODEL_URL="https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct-GGUF/resolve/main/qwen2.5-1.5b-instruct-q4_k_m.gguf"
MODEL="$ROOT/models/qwen2.5-1.5b-instruct-q4_k_m.gguf"
pkg update -y
pkg install -y python sqlite clang cmake git curl
mkdir -p "$ROOT"/{models,app,data/kv,data/logs}
# llama.cpp : compilation native (pas de binaire Android officiel)
if [ ! -x "$ROOT/llama.cpp/build/bin/llama-completion" ]; then
  [ -d "$ROOT/llama.cpp" ] || git clone --depth 1 https://github.com/ggml-org/llama.cpp "$ROOT/llama.cpp"
  cmake -S "$ROOT/llama.cpp" -B "$ROOT/llama.cpp/build" -DCMAKE_BUILD_TYPE=Release -DLLAMA_CURL=OFF
  cmake --build "$ROOT/llama.cpp/build" -j"$THREADS" --target llama-completion llama-server
fi
BIN="$ROOT/llama.cpp/build/bin"
[ -s "$MODEL" ] || curl -fL -o "$MODEL" "$MODEL_URL"
cp "$SRC"/*.py "$SRC"/README.md "$ROOT/app/"; cp -r "$SRC/tests" "$ROOT/app/"
# optionnel (lourd, torch) : pip install numpy sentence-transformers  -> all-MiniLM-L6-v2 recommandé sur Android
cat > "$ROOT/config.json" <<JSON
{
  "version": 1,
  "providers": [
    {"name": "local", "priority": 1, "type": "llama.cpp", "model": "$MODEL",
     "llama_completion_bin": "$BIN/llama-completion", "llama_server_bin": "$BIN/llama-server",
     "server_url": "http://127.0.0.1:8080"},
    {"name": "cloud", "priority": 2, "type": "remote", "note": "seulement si le local échoue ou est insuffisant"}
  ],
  "sampling": {"seed": 42, "temp": 0.0, "top_p": 0.9, "top_k": 40, "repeat_penalty": 1.1,
               "ctx": 4096, "n_predict": 512, "threads": $THREADS},
  "chat_template": true,
  "seedmesh_home": "$ROOT/data",
  "cache_server": "http://127.0.0.1:8765",
  "max_mb": 256
}
JSON
install -m 755 "$SRC/seedmesh.sh" "$ROOT/seedmesh"
sed -i "s#ROOT=\"\${SEEDMESH_ROOT:-/opt/seedmesh}\"#ROOT=\"\${SEEDMESH_ROOT:-$ROOT}\"#" "$ROOT/seedmesh"
ln -sf "$ROOT/seedmesh" "$PREFIX/bin/seedmesh"
if ! grep -q SEEDMESH_ROOT "$HOME/.bashrc" 2>/dev/null; then cat >> "$HOME/.bashrc" <<ENV
export SEEDMESH_ROOT=$ROOT SEEDMESH_HOME=$ROOT/data SEEDMESH_CONFIG=$ROOT/config.json SEEDMESH_MAX_MB=256
export SEEDMESH_MODEL=$MODEL SEEDMESH_LLAMA_BIN=$BIN/llama-completion SEEDMESH_PROVIDER_PRIORITY=local
ENV
fi
echo "OK. Relancer Termux (ou 'source ~/.bashrc'), puis : seedmesh status ; seedmesh ask \"Bonjour\""
echo "Astuce : 'termux-wake-lock' avant 'seedmesh start' pour garder llama-server actif écran éteint."
