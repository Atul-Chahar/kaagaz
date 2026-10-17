// Student graph: every holding with when it was saved.
MATCH (s:Student {id: $student_id})-[holds:HOLDS]->(h:Holding)
RETURN h.doc_id AS doc_id, h.issued_on AS issued_on, h.added_at AS added_at
ORDER BY h.added_at, h.doc_id
