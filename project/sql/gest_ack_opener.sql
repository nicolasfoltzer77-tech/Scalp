UPDATE signals
SET status='OPENED'
WHERE status='SENT'
AND uid IN (
    SELECT uid FROM opener_ack
);
