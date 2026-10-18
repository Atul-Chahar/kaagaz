// Student graph: the student's tasks, by due date.
MATCH (:Student {id: $student_id})-[:HAS_TASK]->(t:Task)
RETURN properties(t) AS task
ORDER BY t.status DESC, t.due, t.id
