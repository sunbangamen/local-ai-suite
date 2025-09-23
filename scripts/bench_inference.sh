#!/usr/bin/env bash
set -euo pipefail

# Simple llama.cpp speed benchmark via LiteLLM gateway.
# - Varies n-gpu-layers over a small set
# - Keeps ctx-size=4096, parallel=2
# - Requires docker + the Phase 2 stack running

BASE_COMPOSE="docker/compose.p2.yml"
OVERRIDE_FILE="docker/compose._bench.override.yml"

PROMPT=${PROMPT:-"한 줄 자기소개 해줘"}
MODEL=${MODEL:-"qwen2.5-14b-instruct"}
TOKENS=${TOKENS:-128}
TEMP=${TEMP:-0.2}

test_speed() {
  local ngl="$1"
  cat > "$OVERRIDE_FILE" << YAML
services:
  inference:
    command: [
      "--host","0.0.0.0",
      "--port","8001",
      "--model","/models/qwen2.5-14b-instruct-q4_k_m.gguf",
      "--parallel","2",
      "--ctx-size","4096",
      "--n-gpu-layers","$ngl",
      "--timeout","600"
    ]
YAML

  echo "\n==> Restarting inference with n-gpu-layers=$ngl"
  docker compose -f "$BASE_COMPOSE" -f "$OVERRIDE_FILE" up -d inference >/dev/null

  # Wait for model to load
  for i in $(seq 1 40); do
    out=$(curl -s http://localhost:8001/health || true)
    echo "health: $out"
    echo "$out" | grep -q '"status":"ok"' && break
    sleep 5
  done

  echo "--> Measuring speed via gateway"
  resp=$(curl -sS -H "Content-Type: application/json" \
    -d "{\"model\":\"$MODEL\",\"messages\":[{\"role\":\"user\",\"content\":\"Hello\"}],\"max_tokens\":$TOKENS,\"temperature\":$TEMP}" \
    http://localhost:8000/v1/chat/completions)

  python3 - << 'PY' <<< "$resp"
import json, sys
try:
    r=json.loads(sys.stdin.read())
    t=r.get('timings',{})
    print(f"RESULT n_gpu_layers={t.get('n_gpu_layers','?')} predicted_per_second={t.get('predicted_per_second')} tok/s predicted_per_token_ms={t.get('predicted_per_token_ms')} ms predicted_n={t.get('predicted_n')}")
except Exception as e:
    print("RESULT error:", e)
    print("RAW:", sys.stdin.read())
PY
}

echo "# Benchmark: MODEL=$MODEL TOKENS=$TOKENS TEMP=$TEMP PROMPT='$PROMPT'"
for ngl in 22 24 26; do
  test_speed "$ngl"
done

# Restore base (compose.p2.yml contains the desired default)
docker compose -f "$BASE_COMPOSE" up -d inference >/dev/null
echo "\nDone."

