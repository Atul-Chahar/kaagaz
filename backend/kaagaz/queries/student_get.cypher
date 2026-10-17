// Student graph: the student node.
MATCH (s:Student {id: $student_id})
RETURN s.id AS id, s.label AS label, s.created_at AS created_at
