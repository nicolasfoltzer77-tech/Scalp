#!/usr/bin/env bash
set -euo pipefail

DATA="/opt/scalp/project/data"
LOG="/opt/scalp/project/logs/dash.log"
now_s=$(date +%s)
ts_now="$(date '+%Y-%m-%d %H:%M:%S')"
printf "\n===== SCALP PIPE HEALTH %s =====\n" "$(date '+%H:%M:%S')" | tee -a "$LOG"

check_db() {
    local name="$1" file="$2" table="$3" ts_col="$4"
    if [[ ! -f "$file" ]]; then
        printf "%-10s ❌ no DB found\n" "$name" | tee -a "$LOG"
        return
    fi
    local count ts_last age_s h m s age_hms status
    count=$(sqlite3 "$file" "SELECT COUNT(*) FROM $table;")
    ts_last=$(sqlite3 "$file" "SELECT MAX($ts_col)/1000 FROM $table;")
    [[ -z "$ts_last" || "$ts_last" == "0" ]] && ts_last=$now_s
    age_s=$(( now_s - ${ts_last%.*:-0} ))
    h=$((age_s/3600)); m=$(( (age_s%3600)/60 )); s=$((age_s%60))
    age_hms=$(printf "%02dh%02dm%02ds" "$h" "$m" "$s")

    if (( age_s < 10 )); then status="✅"
    elif (( age_s < 60 )); then status="⚠️"
    else status="❌"
    fi

    printf "%-10s %s  %4s recs | last=%s | age=%s\n" \
        "$name" "$status" "$count" "$(date '+%H:%M:%S' -d @$ts_last 2>/dev/null || date -r "$ts_last" '+%H:%M:%S')" "$age_hms" \
        | tee -a "$LOG"
}

check_db "opener"   "$DATA/opener.db"   "trades_open_init" "ts_create"
check_db "follower" "$DATA/follower.db" "trades_follow"    "ts_update"
check_db "closer"   "$DATA/closer.db"   "trades_close"     "ts_close"
check_db "recorder" "$DATA/recorder.db" "trades_record"    "ts_record"

printf "==============================================\n" | tee -a "$LOG"
echo "" >> "$LOG"

