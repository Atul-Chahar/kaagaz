// Agents graph: remove a student from the shared registry (when they delete their memory).
MATCH (st:StudentRef {id: $student_id})
DETACH DELETE st
RETURN 1 AS done
