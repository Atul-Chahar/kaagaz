// Student graph: the student has seen their alerts.
MATCH (:Student {id: $student_id})-[:ALERTED]->(a:Alert)
WHERE a.seen = false
SET a.seen = true
RETURN count(a) AS n
