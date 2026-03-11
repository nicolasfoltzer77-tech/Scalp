ATTACH DATABASE '/opt/scalp/project/data/triggers.db' AS trg;

UPDATE trg.trigger_queue
SET status='INGESTED'
WHERE status='NEW'
AND uid IN (
    SELECT uid FROM gest
);

DETACH DATABASE trg;
