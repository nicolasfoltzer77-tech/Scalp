ATTACH DATABASE '/opt/scalp/project/data/gest.db' AS gestdb;

INSERT OR IGNORE INTO opener
(
uid,
instId,
side,
qty,
lev,
exec_type,
step,
status
)

SELECT
uid,
instId,
side,
position_size,
leverage,
'open',
step,
'open_req'

FROM gestdb.gest
WHERE status='open_req';

DETACH DATABASE gestdb;
