#!/usr/bin/env bash
set -euo pipefail

# Compile tous les fichiers systemd scalp-* en un seul fichier texte
# Usage:
#   ./scalp_systemd_bundle.sh
#   ./scalp_systemd_bundle.sh /chemin/output.txt
#
# Output par défaut: /opt/scalp/project/scalp-systemd.bundle.txt

OUT="${1:-/opt/scalp/project/scalp-systemd.bundle.txt}"

mkdir -p "$(dirname "$OUT")"

TMP="$(mktemp)"
trap 'rm -f "$TMP"' EXIT

HOST="$(hostname || true)"
NOW="$(date -Is || true)"

{
  echo "SCALP systemd bundle"
  echo "host=$HOST"
  echo "generated_at=$NOW"
  echo
  echo "=== systemctl --version ==="
  systemctl --version 2>/dev/null || true
  echo
  echo "=== systemctl --failed ==="
  systemctl --failed --no-pager -l 2>/dev/null || true
  echo
  echo "=== list-unit-files (scalp-*) ==="
  systemctl list-unit-files --type=service --no-pager 2>/dev/null | awk 'NR==1||NR==2{print;next} {print}' | grep -E '^scalp-.*\.service' || true
  echo
} > "$TMP"

# Récupère la liste des unités scalp-*.service connues
mapfile -t UNITS < <(systemctl list-unit-files --type=service --no-pager 2>/dev/null | awk '{print $1}' | grep -E '^scalp-.*\.service$' || true)

# Si aucune trouvée via list-unit-files, fallback sur /etc/systemd/system
if [ "${#UNITS[@]}" -eq 0 ]; then
  if ls /etc/systemd/system/scalp-*.service >/dev/null 2>&1; then
    while IFS= read -r f; do
      UNITS+=("$(basename "$f")")
    done < <(ls -1 /etc/systemd/system/scalp-*.service)
  fi
fi

# Dedup
if [ "${#UNITS[@]}" -gt 0 ]; then
  mapfile -t UNITS < <(printf "%s\n" "${UNITS[@]}" | sort -u)
fi

{
  echo "=== units_count=${#UNITS[@]} ==="
  echo
} >> "$TMP"

for u in "${UNITS[@]}"; do
  {
    echo "################################################################################"
    echo "UNIT: $u"
    echo "################################################################################"
    echo
    echo "---- systemctl status $u ----"
    systemctl status "$u" --no-pager -l 2>/dev/null || true
    echo
    echo "---- systemctl cat $u ----"
    systemctl cat "$u" 2>/dev/null || true
    echo
    echo "---- drop-in directories (if any) ----"
    if [ -d "/etc/systemd/system/${u}.d" ]; then
      echo "DIR: /etc/systemd/system/${u}.d"
      ls -la "/etc/systemd/system/${u}.d" 2>/dev/null || true
      echo
      for d in /etc/systemd/system/"${u}".d/*.conf; do
        [ -f "$d" ] || continue
        echo "FILE: $d"
        sed -n '1,260p' "$d" 2>/dev/null || true
        echo
      done
    else
      echo "(none)"
    fi
    echo
    echo "---- journalctl (last 120 lines) ----"
    journalctl -u "$u" -n 120 --no-pager 2>/dev/null || true
    echo
    echo
  } >> "$TMP"
done

mv -f "$TMP" "$OUT"
chmod 0644 "$OUT"

echo "OK: bundle écrit dans: $OUT"
