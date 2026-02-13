#!/bin/bash

echo "===== PIPELINE HEALTH (WS → OA → FEAT → CTX) ====="

echo
/opt/scalp/project/bin/dash_ws_age.sh

echo
/opt/scalp/project/bin/dash_oa_age.sh

echo
echo "FEAT latest:"
sqlite3 /opt/scalp/project/data/a.db \
  "SELECT tf, datetime(MAX(ts)/1000,'unixepoch','localtime') FROM feat_5m UNION ALL
   SELECT tf, datetime(MAX(ts)/1000,'unixepoch','localtime') FROM feat_15m UNION ALL
   SELECT tf, datetime(MAX(ts)/1000,'unixepoch','localtime') FROM feat_30m;"

echo
echo "CTX latest:"
sqlite3 /opt/scalp/project/data/a.db \
  "SELECT datetime(MAX(ts_update)/1000,'unixepoch','localtime') FROM ctx_cache;"

