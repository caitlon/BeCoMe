#!/usr/bin/env bash
# Start the four local llama-server processes the local assistant needs: the chat
# model for query transforms (:8081), embeddings (:8082), rerank (:8083) and the
# answer model (:8084).
# Models download from the Hugging Face Hub on first start (about 3.6 GB for the
# chat, embedding and rerank set, plus about 10 GB for the answer model, which also
# stays in memory while it runs). Stop everything with Ctrl-C: the trap kills the
# whole group.
#
# All four servers always start, so indexing and the retrieval evaluation load the answer
# model too, though neither uses it.
#
# CHAT_HF and CHAT_ALIAS swap the query-transform and indexing model for another GGUF
# repository and its alias; ANSWER_HF and ANSWER_ALIAS swap the answer model the same way.
# Any arguments to this script go to the 4B chat server only.
set -euo pipefail

command -v llama-server >/dev/null || { echo "llama-server not found: brew install llama.cpp" >&2; exit 1; }

CHAT_HF="${CHAT_HF:-unsloth/Qwen3-4B-Instruct-2507-GGUF:Q4_K_M}"
CHAT_ALIAS="${CHAT_ALIAS:-Qwen/Qwen3-4B-Instruct-2507}"
ANSWER_HF="${ANSWER_HF:-bartowski/Qwen_Qwen3.5-9B-GGUF:Q8_0}"
ANSWER_ALIAS="${ANSWER_ALIAS:-Qwen/Qwen3.5-9B}"

trap 'kill 0' EXIT INT TERM

llama-server -hf "$CHAT_HF" --alias "$CHAT_ALIAS" --jinja -c 16384 --port 8081 "$@" &
llama-server -hf ggml-org/bge-m3-Q8_0-GGUF \
  --alias BAAI/bge-m3 --embedding --pooling cls -c 8192 -b 8192 -ub 8192 --port 8082 &
llama-server -hf gpustack/bge-reranker-v2-m3-GGUF:Q4_K_M \
  --alias BAAI/bge-reranker-v2-m3 --embedding --pooling rank --port 8083 &
# The repository also holds a vision projector, which --no-mmproj keeps from loading; thinking
# is off because the answer is measured without it.
llama-server -hf "$ANSWER_HF" --alias "$ANSWER_ALIAS" --jinja --reasoning off --no-mmproj \
  -c 16384 --port 8084 &

wait
