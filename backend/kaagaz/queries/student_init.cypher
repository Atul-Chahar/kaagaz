// Student graph: create the student node once (each student has a separate graph kaagaz:student:<id>).
MERGE (s:Student {id: $student_id})
ON CREATE SET s.label = $label, s.created_at = $now
RETURN s.id AS id, s.label AS label, s.created_at AS created_at
