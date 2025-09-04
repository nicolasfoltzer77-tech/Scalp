#!/usr/bin/env bash
set -euo pipefail

# -----------------------------------------------------------
# SCALP — Désactivation CRON (+ timers systemd) avec backup
# Usage:
#   ./disable_cron.sh           # dry-run (montre ce qui serait fait)
#   ./disable_cron.sh --apply   # applique réellement
#   ./disable_cron.sh --restore /root/cron_backup_YYYYmmdd_HHMMSS  # restaure
# Cible par défaut: éléments liés à "scalp|balance|bitget|dashboard|webhook"
# Pour TOUT désactiver, ajoutez --all
# -----------------------------------------------------------

APPLY=0
RESTORE_DIR=""
MATCH='scalp|balance|bitget|dashboard|webhook'
ALL=0
for a in "$@"; do
  case "$a" in
    --apply) APPLY=1 ;;
    --all) ALL=1 ;;
    --restore) shift; RESTORE_DIR="${1:-}";;
  esac
done

TS=$(date +%Y%m%d_%H%M%S)
BK="/root/cron_backup_${TS}"
mkdir -p "$BK"

say(){ printf "%s\n" "$*"; }
doit(){ if [[ $APPLY -eq 1 ]]; then eval "$*"; else echo "[dry-run] $*"; fi; }

if [[ -n "$RESTORE_DIR" ]]; then
  say "== RESTORE depuis $RESTORE_DIR =="
  if [[ ! -d "$RESTORE_DIR" ]]; then echo "Répertoire invalide"; exit 1; fi
  # Restaurer crontab root
  if [[ -f "$RESTORE_DIR/root.cron" ]]; then
    doit "crontab '$RESTORE_DIR/root.cron'"
  fi
  # Restaurer /etc/cron.d
  if [[ -d "$RESTORE_DIR/cron.d" ]]; then
    doit "cp -a '$RESTORE_DIR/cron.d/.' /etc/cron.d/"
  fi
  # Restaurer daily/hourly si sauvegardés
  for d in cron.daily cron.hourly; do
    if [[ -d "$RESTORE_DIR/$d" ]]; then
      doit "cp -a '$RESTORE_DIR/$d/.' '/etc/$d/'"
    fi
  end
  # Réactiver timers sauvegardés
  if [[ -f "$RESTORE_DIR/timers.list" ]]; then
    while read -r t; do [[ -n "$t" ]] && doit "systemctl enable --now '$t'"; done < "$RESTORE_DIR/timers.list"
  fi
  say "Restauration programmée (mode ${APPLY:+APPLY}/${APPLY:+"APPLY" -eq 1})"
  exit 0
fi

say "== SCALP — Désactivation CRON (mode: $([[ $APPLY -eq 1 ]] && echo APPLY || echo DRY-RUN)) =="

# 1) Sauvegarde crontab root
say "-- Backup crontab root -> $BK/root.cron"
crontab -l > "$BK/root.cron" 2>/dev/null || touch "$BK/root.cron"

# 2) Désactivation crontab root
TMP="$BK/root.cron.new"
if [[ $ALL -eq 1 ]]; then
  # commenter toutes les lignes non commentées
  awk '{ if ($0 ~ /^[[:space:]]*#/) print $0; else print "# " $0 }' "$BK/root.cron" > "$TMP"
else
  # commenter uniquement les lignes qui matchent le PATTERN
  awk -v pat="$MATCH" 'BEGIN{IGNORECASE=1}
    { if ($0 ~ pat && $0 !~ /^[[:space:]]*#/) print "# " $0; else print $0 }' "$BK/root.cron" > "$TMP"
fi
if [[ $APPLY -eq 1 ]]; then crontab "$TMP"; fi
say "Crontab root ${APPLY:+appliquée}${APPLY:+"appliquée"} (sinon dry-run)."

# 3) /etc/cron.d : backup + disable fichiers ciblés
say "-- /etc/cron.d"
mkdir -p "$BK/cron.d"
if [[ -d /etc/cron.d ]]; then
  cp -a /etc/cron.d/* "$BK/cron.d/" 2>/dev/null || true
  if [[ $ALL -eq 1 ]]; then
    # tout désactiver en renommant *.disabled
    for f in /etc/cron.d/*; do
      [[ -f "$f" ]] || continue
      doit "mv '$f' '${f}.disabled'"
    done
  else
    # ne cibler que ceux qui matchent
    for f in /etc/cron.d/*; do
      [[ -f "$f" ]] || continue
      if egrep -qi "$MATCH" "$f"; then
        doit "mv '$f' '${f}.disabled'"
      fi
    done
  fi
fi

# 4) cron.daily / cron.hourly : backup + disable ciblé
for d in cron.daily cron.hourly; do
  say "-- /etc/$d"
  mkdir -p "$BK/$d"
  cp -a /etc/$d/* "$BK/$d/" 2>/dev/null || true
  if [[ $ALL -eq 1 ]]; then
    for f in /etc/$d/*; do [[ -f "$f" && -x "$f" ]] && doit "chmod -x '$f'"; done
  else
    for f in /etc/$d/*; do
      [[ -f "$f" ]] || continue
      if egrep -qi "$MATCH" "$f"; then doit "chmod -x '$f'"; fi
    done
  fi
done

# 5) Timers systemd apparentés
say "-- systemd timers"
TIMERS_FILE="$BK/timers.list"
systemctl list-timers --all --no-pager | awk '{print $1}' \
  | egrep -i 'scalp|balance|webhook' | tee "$TIMERS_FILE" || true
while read -r t; do
  [[ -n "$t" ]] || continue
  doit "systemctl disable --now '$t'"
done < "$TIMERS_FILE" || true

# 6) Résumé
say "== Sauvegarde: $BK =="
say "Pour RESTAURER: $0 --restore $BK --apply"
