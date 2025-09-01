#!/usr/bin/env bash
set -euo pipefail

PROFILE="${1:-modéré}"          # conservateur | modéré | agressif
DURATION_MIN="${2:-0}"          # 0 = infini
INTERVAL="${INTERVAL_SEC:-}"    # override via env, sinon auto
SYMBOLS="${SYMBOLS:-}"          # ex: "BTCUSDT ETHUSDT SOLUSDT"
OPEN="${OPEN:-1}"               # 1 = ouvrir positions simulées

# Interval auto par profil si non fourni
if [[ -z "${INTERVAL}" ]]; then
  case "$PROFILE" in
    conservateur) INTERVAL=60 ;;
    modéré)       INTERVAL=30 ;;
    agressif)     INTERVAL=10 ;;
    *)            INTERVAL=30 ;;
  esac
fi

ARGS=( --profile "$PROFILE" --duration-min "$DURATION_MIN" --interval-sec "$INTERVAL" )
[[ -n "$SYMBOLS" ]] && ARGS+=( --symbols $SYMBOLS )
[[ "${OPEN}" == "1" ]] && ARGS+=( --open )

echo "[run_loop] profile=$PROFILE interval=${INTERVAL}s duration_min=$DURATION_MIN symbols=${SYMBOLS:-default} open=$OPEN"
PYTHONPATH=. exec python3 bin/loop_worker.py "${ARGS[@]}"
