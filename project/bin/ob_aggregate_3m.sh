#!/usr/bin/env bash
set -euo pipefail
DB="/opt/scalp/project/data/ob.db"
LOCK="/var/lock/ob_agg3m.lock"
LOG="/opt/scalp/project/logs/ob_agg3m.log"

exec /usr/bin/flock -n "$LOCK" bash -c "
  echo \"\$(date '+%F %T') [AGG3M] Start aggregation\" >> \$LOG
  sqlite3 \$DB '
    DELETE FROM ohlcv_3m;
    INSERT INTO ohlcv_3m (instId, ts, o, h, l, c, v)
    SELECT instId,
           (ts/180000)*180000 AS ts_group,
           first_value(o) OVER w AS o,
           MAX(h) OVER w AS h,
           MIN(l) OVER w AS l,
           last_value(c) OVER w AS c,
           SUM(v) OVER w AS v
    FROM ohlcv_1m
    WINDOW w AS (PARTITION BY instId, (ts/180000) ORDER BY ts ROWS BETWEEN 2 PRECEDING AND CURRENT ROW)
    GROUP BY instId, ts_group;
  '
  echo \"\$(date '+%F %T') [AGG3M] Done\" >> \$LOG
"

