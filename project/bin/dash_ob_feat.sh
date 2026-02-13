#!/usr/bin/env bash
set -euo pipefail

DB_OB="/opt/scalp/project/data/ob.db"
DB_B="/opt/scalp/project/data/b.db"

age() {
  ts_ms="$1"
  now_ms=$(($(date +%s) * 1000))
  echo $(( (now_ms - ts_ms) / 1000 ))
}

print_block() {
  local label="$1"
  echo "---- [$label] ----"
}

print_row() {
  local tf="$1"
  local rows="$2"
  local last_ts="$3"
  if [[ -z "$last_ts" || "$last_ts" == "0" ]]; then
      age_s="n/a"
  else
      age_s=$(age "$last_ts")
  fi
  printf "%-3s | rows=%-6s age=%4ss\n" "$tf" "$rows" "$age_s"
}

echo "==========================================="
echo "      MINI DASH — OB + FEAT (1m/3m/5m)"
echo "==========================================="

### OB ###
print_block "OB OHLCV"

for tf in 1m 3m 5m; do
    table="ohlcv_${tf}"
    rows=$(sqlite3 "$DB_OB" "SELECT COUNT(*) FROM $table;")
    last_ts=$(sqlite3 "$DB_OB" "SELECT MAX(ts) FROM $table;")
    print_row "$tf" "$rows" "$last_ts"
done

### FEAT ###
print_block "FEAT"

for tf in 1m 3m 5m; do
    table="feat_${tf}"
    rows=$(sqlite3 "$DB_B" "SELECT COUNT(*) FROM $table;")
    last_ts=$(sqlite3 "$DB_B" "SELECT MAX(ts) FROM $table;")
    print_row "$tf" "$rows" "$last_ts"
done

### STATUS ###
echo "---- [STATUS] ----"

ok=true
msg=""

# seuils
S1=120
S3=180
S5=300

check_tf() {
  local tf="$1"
  local ob_age="$2"
  local ft_age="$3"
  local max="$4"

  if (( ob_age > max )); then ok=false; msg="$msg ⚠️ OB ${tf} lag (${ob_age} s)\n"; fi
  if (( ft_age > max )); then ok=false; msg="$msg ⚠️ FEAT ${tf} lag (${ft_age} s)\n"; fi
}

ob1=$(age "$(sqlite3 "$DB_OB" "SELECT IFNULL(MAX(ts),0) FROM ohlcv_1m;")")
ft1=$(age "$(sqlite3 "$DB_B" "SELECT IFNULL(MAX(ts),0) FROM feat_1m;")")

ob3=$(age "$(sqlite3 "$DB_OB" "SELECT IFNULL(MAX(ts),0) FROM ohlcv_3m;")")
ft3=$(age "$(sqlite3 "$DB_B" "SELECT IFNULL(MAX(ts),0) FROM feat_3m;")")

ob5=$(age "$(sqlite3 "$DB_OB" "SELECT IFNULL(MAX(ts),0) FROM ohlcv_5m;")")
ft5=$(age "$(sqlite3 "$DB_B" "SELECT IFNULL(MAX(ts),0) FROM feat_5m;")")

check_tf 1m "$ob1" "$ft1" "$S1"
check_tf 3m "$ob3" "$ft3" "$S3"
check_tf 5m "$ob5" "$ft5" "$S5"

if $ok; then
    echo "🟢 OK"
else
    echo -e "$msg"
fi

echo "==========================================="
echo "             FIN MINI DASH"
echo "==========================================="


