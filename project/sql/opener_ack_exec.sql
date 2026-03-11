ATTACH DATABASE '/opt/scalp/project/data/exec.db' AS execdb;

-- ACK OPEN
UPDATE opener
SET status='open_done'
WHERE exec_type='open'
AND (uid,step) IN
(
SELECT uid,step
FROM execdb.exec
WHERE status='done'
AND exec_type='open'
);

-- ACK PYRAMIDE
UPDATE opener
SET status='pyramide_done'
WHERE exec_type='pyramide'
AND (uid,step) IN
(
SELECT uid,step
FROM execdb.exec
WHERE status='done'
AND exec_type='pyramide'
);

DETACH DATABASE execdb;
