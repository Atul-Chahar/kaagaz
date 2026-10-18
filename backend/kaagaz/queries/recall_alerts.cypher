// Student graph: alerts, newest first.
MATCH (:Student {id: $student_id})-[:ALERTED]->(a:Alert)
RETURN properties(a) AS alert
ORDER BY a.at DESC
LIMIT $limit
