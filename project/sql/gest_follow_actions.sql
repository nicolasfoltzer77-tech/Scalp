UPDATE signals
SET status='FOLLOW'
WHERE status='OPENED'
AND uid IN (
    SELECT uid FROM follower_events
);
