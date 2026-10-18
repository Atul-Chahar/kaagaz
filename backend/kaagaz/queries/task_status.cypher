// Student graph: mark a task done or open again.
MATCH (:Student {id: $student_id})-[:HAS_TASK]->(t:Task {id: $id})
SET t.status = $status, t.updated_at = $now
RETURN properties(t) AS task
