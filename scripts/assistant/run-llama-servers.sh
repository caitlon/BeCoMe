#!/usr/bin/env bash
# Start the three local llama-server processes the local assistant needs.
# Models download from the Hugging Face Hub on first start (about 3.6 GB for the
# default set). Stop everything with Ctrl-C: the trap kills the whole group.
#
# The chat model is swappable for the answer evaluation's measurement E: CHAT_HF and CHAT_ALIAS
# name another GGUF repository and its alias, and any arguments to this script go
# to the chat process only, such as the extra flags Qwen3.5-9B needs.
set -euo pipefail

command -v llama-server >/dev/null || { echo "llama-server not found: brew install llama.cpp" >&2; exit 1; }

CHAT_HF="${CHAT_HF:-unsloth/Qwen3-4B-Instruct-2507-GGUF:Q4_K_M}"
CHAT_ALIAS="${CHAT_ALIAS:-Qwen/Qwen3-4B-Instruct-2507}"

trap 'kill 0' EXIT INT TERM

llama-server -hf "$CHAT_HF" --alias "$CHAT_ALIAS" --jinja -c 16384 --port 8081 "$@" &
llama-server -hf ggml-org/bge-m3-Q8_0-GGUF \
  --alias BAAI/bge-m3 --embedding --pooling cls -c 8192 -b 8192 -ub 8192 --port 8082 &
llama-server -hf gpustack/bge-reranker-v2-m3-GGUF:Q4_K_M \
  --alias BAAI/bge-reranker-v2-m3 --embedding --pooling rank --port 8083 &

wait
