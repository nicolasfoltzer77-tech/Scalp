ATTACH DATABASE '/opt/scalp/project/data/opener.db' AS opener;
ATTACH DATABASE '/opt/scalp/project/data/closer.db' AS closer;

-- ============================
-- OPENER -> EXEC
-- ============================

INSERT OR IGNORE INTO exec
(
exec_id,
uid,
instId,
side,
exec_type,
step,
qty,
lev,
status,
ts_created
)

SELECT

uid||':'||exec_type||':'||step,

uid,
instId,
side,
exec_type,
step,
qty,
lev,

'exec_req',

strftime('%s','now')*1000

FROM opener.opener
WHERE status IN ('open_req','pyramide_req');


-- ============================
-- CLOSER -> EXEC
-- ============================

INSERT OR IGNORE INTO exec
(
exec_id,
uid,
instId,
side,
exec_type,
step,
qty,
lev,
status,
reason,
ts_created
)

SELECT

uid||':'||
CASE
WHEN status='partial_req' THEN 'partial'
ELSE 'close'
END
||':'||step,

uid,
instId,
side,

CASE
WHEN status='partial_req' THEN 'partial'
ELSE 'close'
END,

step,
qty,
1,

'exec_req',

reason,

strftime('%s','now')*1000

FROM closer.closer
WHERE status IN ('partial_req','close_req');


DETACH DATABASE opener;
DETACH DATABASE closer;
