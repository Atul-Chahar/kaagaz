// Student graph: the scheme the student is applying for, with the deadline they plan against.
MATCH (s:Student {id: $student_id})
MERGE (s)-[tg:TARGETS]->(t:Target {scheme_id: $scheme_id})
ON CREATE SET t.added_at = $now
SET t.deadline = $deadline, t.deadline_source = $deadline_source
RETURN t.scheme_id AS scheme_id, t.deadline AS deadline, t.added_at AS added_at
