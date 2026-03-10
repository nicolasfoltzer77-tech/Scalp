
/* =========================================
ATTACH DATABASES
========================================= */

ATTACH '/opt/scalp/project/data/triggers.db' AS trig;
ATTACH '/opt/scalp/project/data/opener.db'   AS opn;
ATTACH '/opt/scalp/project/data/closer.db'   AS cls;
ATTACH '/opt/scalp/project/data/follower.db' AS fol;


/* =========================================
TRIGGERS → GEST OPEN_REQ
========================================= */

INSERT INTO gest (
uid,
instId,
side,
ts_signal,
entry_price,
leverage,
margin_usd,
position_size,
stop_price,
take_profit,
universal_alpha,
market_regime,
session,
signal_source,
status,
step
)

SELECT
t.uid,
t.instId,
t.side,
strftime('%s','now')*1000,
t.entry_price,
t.leverage,
t.margin_usd,
t.position_size,
t.stop_price,
t.take_profit,
t.alpha,
t.market_regime,
t.session,
'trigger_queue',
'open_req',
0

FROM trig.trigger_queue t

WHERE t.status='NEW'

AND NOT EXISTS (
SELECT 1
FROM gest g
WHERE g.uid=t.uid
);


/* =========================================
OPENER ACK → OPEN_DONE
========================================= */

UPDATE gest
SET
status='open_done',
step=o.step
FROM opn.opener o
WHERE gest.uid=o.uid
AND o.status='open_done'
AND gest.status IN ('open_req','open_stdby');


/* =========================================
OPENER ACK → PYRAMIDE_DONE
========================================= */

UPDATE gest
SET
status='pyramide_done',
step=o.step
FROM opn.opener o
WHERE gest.uid=o.uid
AND o.status='pyramide_done'
AND gest.status='pyramide_req';


/* =========================================
CLOSER ACK → CLOSE_DONE
========================================= */

UPDATE gest
SET status='close_done'
FROM cls.closer c
WHERE gest.uid=c.uid
AND c.status='close_done'
AND gest.status='close_req';


/* =========================================
CLOSER ACK → PARTIAL_DONE
========================================= */

UPDATE gest
SET status='partial_done'
FROM cls.closer c
WHERE gest.uid=c.uid
AND c.status='partial_done'
AND gest.status='partial_req';


/* =========================================
FOLLOWER → FOLLOW STATE
========================================= */

UPDATE gest
SET
status='follow',
step=f.step
FROM fol.follower f
WHERE gest.uid=f.uid
AND f.status='follow'
AND gest.status IN (
'open_done',
'pyramide_done',
'partial_done'
);


/* =========================================
FOLLOWER → PYRAMIDE REQUEST
========================================= */

UPDATE gest
SET
status='pyramide_req',
ratio_to_add=f.ratio_to_add
FROM fol.follower f
WHERE gest.uid=f.uid
AND f.status='pyramide_req'
AND gest.status='follow';


/* =========================================
FOLLOWER → PARTIAL REQUEST
========================================= */

UPDATE gest
SET
status='partial_req',
ratio_to_close=f.ratio_to_close
FROM fol.follower f
WHERE gest.uid=f.uid
AND f.status='partial_req'
AND gest.status='follow';


/* =========================================
FOLLOWER → CLOSE REQUEST
========================================= */

UPDATE gest
SET
status='close_req',
ratio_to_close=1.0
FROM fol.follower f
WHERE gest.uid=f.uid
AND f.status='close_req'
AND gest.status='follow';

