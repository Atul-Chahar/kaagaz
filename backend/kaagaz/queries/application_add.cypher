// Student graph: the student applied for a document on a date (idempotent per document; a later call moves the date).
MATCH (s:Student {id: $student_id})
MERGE (s)-[:APPLIED]->(a:Application {doc_id: $doc_id})
ON CREATE SET a.added_at = $now
SET a.applied_on = $applied_on
RETURN a.doc_id AS doc_id, a.applied_on AS applied_on, a.added_at AS added_at
