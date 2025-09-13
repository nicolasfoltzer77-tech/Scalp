#!/usr/bin/env bash
set -uo pipefail

ENV_SRC="/etc/scalp.env"
ENV_DST="/opt/scalp/scalp.env"
GUARD="/opt/scalp/tools/bitget_env_check.py"

TIMERS=("scalp-ohlcv.timer" "scalp-heatmap.timer")
SERVICES=("scalp-telegram-bot.service")

emoji_ok="✅"; emoji_info="🔧"; emoji_lock="🔒"; emoji_unlock="🔓"; emoji_play="▶️"; emoji_stop="⏹️"; emoji_note="📝"

now_hhmm(){ date +%H:%M; }
now_build(){ date +%H%M; }

has_cmd(){ command -v "$1" >/dev/null 2>&1; }

is_immutable(){
  has_cmd lsattr || return 1
  [[ -f "$ENV_DST" ]] || return 1
  lsattr -d "$ENV_DST" 2>/dev/null | awk '{print $1}' | grep -q 'i'
}

unlock_env(){
  $SUDO chattr -i "$ENV_DST" 2>/dev/null || true
  $SUDO chattr -a "$ENV_DST" 2>/dev/null || true
}

lock_env(){
  $SUDO chattr +i "$ENV_DST" 2>/dev/null || true
}

ensure_env_file(){
  [[ -f "$ENV_DST" ]] || : >"$ENV_DST"
}

bump_version(){
  local hhmm build tmp new
  hhmm="$(now_hhmm)"
  build="$(now_build)"
  tmp="$(mktemp)"

  # base: contenu actuel
  cat "$ENV_DST" >"$tmp"

  # VERSION
  if grep -qE '^VERSION=' "$tmp"; then
    sed -E -i "s/^VERSION=.*/VERSION=${hhmm//:/}/" "$tmp"
  else
    printf "\nVERSION=%s\n" "${hhmm//:/}" >>"$tmp"
  fi

  # BUILD
  if grep -qE '^BUILD=' "$tmp"; then
    sed -E -i "s/^BUILD=.*/BUILD=${build}/" "$tmp"
  else
    printf "BUILD=%s\n" "$build" >>"$tmp"
  fi

  # n’écrit que si différent
  if ! cmp -s "$tmp" "$ENV_DST"; then
    cp -f "$tmp" "$ENV_DST"
  fi
  rm -f "$tmp"
  echo "$emoji_ok VERSION=$(printf '%s' "$hhmm") (BUILD=$build)"
}

run_guard(){
  [[ -x "$GUARD" ]] || { echo "$emoji_note guard manquant, skip."; return 0; }
  if is_immutable; then
    echo "$emoji_lock env verrouillé, skip normalisation."
    return 0
  fi
  echo "🔍 Normalisation/env check…"
  # Le script python écrit /opt/scalp/scalp.env seulement si nécessaire
  /usr/bin/python3 "$GUARD" || true
}

unit_exists(){ systemctl list-unit-files "$1" --no-legend 2>/dev/null | grep -q "$1"; }

stop_all(){
  echo "$emoji_stop Stop timers/services…"
  for t in "${TIMERS[@]}"; do unit_exists "$t" && systemctl disable --now "$t" 2>/dev/null || true; done
  for s in "${SERVICES[@]}"; do unit_exists "$s" && systemctl stop "$s" 2>/dev/null || true; done
}

start_all(){
  echo "$emoji_play Restart services/timers…"
  for s in "${SERVICES[@]}"; do unit_exists "$s" && systemctl enable --now "$s" 2>/dev/null || true; done
  for t in "${TIMERS[@]}"; do
    if unit_exists "$t"; then systemctl enable --now "$t" 2>/dev/null || true; else
      # fallback one-shot si pas de timer
      base="${t%.timer}"
      unit_exists "$base.service" && systemctl start "$base.service" 2>/dev/null || true
    fi
  done
}

summary(){
  echo "🧾 Résumé:"
  unit_exists scalp-telegram-bot.service && systemctl --no-pager --lines=0 status scalp-telegram-bot.service || true
  unit_exists scalp-ohlcv.timer && systemctl --no-pager --lines=0 status scalp-ohlcv.timer || true
  unit_exists scalp-heatmap.timer && systemctl --no-pager --lines=0 status scalp-heatmap.timer || true
  echo "$emoji_ok Deploy terminé. VERSION=$(now_hhmm)"
}

main(){
  export SUDO=""
  [[ $EUID -ne 0 ]] && SUDO="sudo"

  echo "== SCALP deploy =="
  ensure_env_file

  local was_locked=0
  if is_immutable; then
    was_locked=1
    echo "$emoji_unlock unlock env…"
    unlock_env
  fi

  run_guard
  bump_version

  # si précédemment verrouillé -> re-lock
  if (( was_locked == 1 )); then
    echo "$emoji_lock lock env…"
    lock_env
  fi

  echo "$emoji_info systemd reload…"
  systemctl daemon-reload

  stop_all
  start_all
  summary
}

main "$@"
