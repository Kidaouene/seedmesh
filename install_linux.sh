#!/usr/bin/env bash
# Installation SeedMesh Linux (x86_64, CPU) : llama.cpp précompilé + Qwen2.5-1.5B-Instruct Q4_K_M + config globale.
# Usage : sudo ./install_linux.sh   (sans root : ROOT=$HOME/seedmesh ./install_linux.sh)
set -euo pipefail
ROOT="${ROOT:-/opt/seedmesh}"; SRC="$(cd "$(dirname "$0")" && pwd)"
LLAMA_TAG="${LLAMA_TAG:-b11921}"
MODEL_URL="https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct-GGUF/resolve/main/qwen2.5-1.5b-instruct-q4_k_m.gguf"
MODEL="$ROOT/models/qwen2.5-1.5b-instruct-q4_k_m.gguf"
THREADS="${THREADS:-4}"
mkdir -p "$ROOT"/{llama.cpp,models,app,data/kv,data/logs}
if [ ! -x "$ROOT/llama.cpp/current/llama-completion" ]; then
  curl -fL "https://github.com/ggml-org/llama.cpp/releases/download/$LLAMA_TAG/llama-$LLAMA_TAG-bin-ubuntu-x64.tar.gz" | tar xz -C "$ROOT/llama.cpp"
  ln -sfn "llama-$LLAMA_TAG" "$ROOT/llama.cpp/current"
fi
[ -s "$MODEL" ] || curl -fL -o "$MODEL" "$MODEL_URL"
cp "$SRC"/*.py "$SRC"/README.md "$ROOT/app/"; cp -r "$SRC/tests" "$ROOT/app/"
cat > "$ROOT/config.json" <<JSON
{
  "version": 1,
  "providers": [
    {"name": "local", "priority": 1, "type": "llama.cpp", "model": "$MODEL",
     "llama_completion_bin": "$ROOT/llama.cpp/current/llama-completion",
     "llama_server_bin": "$ROOT/llama.cpp/current/llama-server",
     "server_url": "http://127.0.0.1:8080"},
    {"name": "cloud", "priority": 2, "type": "remote", "note": "seulement si le local échoue ou est insuffisant"}
  ],
  "sampling": {"seed": 42, "temp": 0.0, "top_p": 0.9, "top_k": 40, "repeat_penalty": 1.1,
               "ctx": 4096, "n_predict": 512, "threads": $THREADS},
  "chat_template": true,
  "seedmesh_home": "$ROOT/data",
  "cache_server": "http://127.0.0.1:8765",
  "max_mb": 512
}
JSON
install -m 755 "$SRC/seedmesh.sh" "$ROOT/seedmesh"
sed -i "s#ROOT=\"\${SEEDMESH_ROOT:-/opt/seedmesh}\"#ROOT=\"\${SEEDMESH_ROOT:-$ROOT}\"#" "$ROOT/seedmesh"
ENVSH="export SEEDMESH_ROOT=$ROOT SEEDMESH_HOME=$ROOT/data SEEDMESH_CONFIG=$ROOT/config.json SEEDMESH_MAX_MB=512
export SEEDMESH_MODEL=$MODEL SEEDMESH_LLAMA_BIN=$ROOT/llama.cpp/current/llama-completion SEEDMESH_PROVIDER_PRIORITY=local"
if [ "$(id -u)" = 0 ]; then
  ln -sf "$ROOT/seedmesh" /usr/local/bin/seedmesh
  echo "$ENVSH" > /etc/profile.d/seedmesh.sh; chmod 644 /etc/profile.d/seedmesh.sh
  chmod -R a+rwX "$ROOT/data"; chmod -R a+rX "$ROOT"
else
  mkdir -p "$HOME/.local/bin"; ln -sf "$ROOT/seedmesh" "$HOME/.local/bin/seedmesh"
  grep -q SEEDMESH_ROOT "$HOME/.bashrc" 2>/dev/null || echo "$ENVSH" >> "$HOME/.bashrc"
fi
echo "OK. Ouvrir un nouveau shell puis : seedmesh status ; seedmesh start ; seedmesh ask \"Bonjour\""
