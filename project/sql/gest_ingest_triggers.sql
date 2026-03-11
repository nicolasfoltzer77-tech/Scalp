
ATTACH DATABASE '/opt/scalp/project/data/triggers.db' AS trg;

INSERT OR IGNORE INTO gest (

uid,
instId,
side,

entry_price,
leverage,

margin_usd,
position_size,

alpha,

status,

ts_signal,
ts_created

)

SELECT

uid,
instId,
side,

entry_price,
leverage,

margin_usd,
position_size,

alpha,

'open_req',

ts_signal,
ts_created

FROM trg.trigger_queue
WHERE status='NEW';

DETACH DATABASE trg;

