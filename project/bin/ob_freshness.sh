#!/usr/bin/env bash
set -euo pipefail

DB_OB="/opt/scalp/project/data/ob.db"

# TF -> (table:limit_age)
declare -A TF_TABLES=(
    ["1m"]="ohlcv_1m:60"
    ["3m"]="ohlcv_3m:180"
    ["5m"]="ohlcv_5m:300"
)

now_ms=$(($(date +%s) * 1000))

echo "=== LAST OB CANDLES USED ==="
printf "%-3s %-19s %-7s %s\n" "tf" "last_ts" "age_s" "status"
echo "--  -------------------  -------  -------"

for tf in 1m 3m 5m; do
    entry="${TF_TABLES[$tf]}"
    table="${entry%%:*}"
    limit="${entry##*:}"

    last_ts=$(sqlite3 "$DB_OB" "SELECT MAX(ts) FROM $table;")

    if [[ -z "$last_ts" || "$last_ts" == "NULL" ]]; then
        printf "%-3s %-19s %-7s %s\n" "$tf" "---" "---" "❌"
        continue
    fi

    age=$(( (now_ms - last_ts) / 1000 ))
    last_human=$(date -d "@$((last_ts / 1000))" +"%Y-%m-%d %H:%M:%S")

    status="⚠️"
    if (( age < limit )); then
        status="✅"
    fi

    printf "%-3s %-19s %-7d %s\n" "$tf" "$last_human" "$age" "$status"
done


