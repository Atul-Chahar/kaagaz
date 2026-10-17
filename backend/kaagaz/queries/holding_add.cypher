// Student graph: record a document the student holds (idempotent).
MATCH (s:Student {id: $student_id})
MERGE (s)-[holds:HOLDS]->(h:Holding {doc_id: $doc_id})
ON CREATE SET h.added_at = $now
SET h.issued_on = $issued_on
RETURN h.doc_id AS doc_id, h.issued_on AS issued_on, h.added_at AS added_at
