// Student graph: the student says a conditional requirement applies to them (e.g. they live in a hostel).
MATCH (s:Student {id: $student_id})
MERGE (s)-[ap:APPLIES]->(a:Applies {doc_id: $doc_id})
ON CREATE SET a.added_at = $now
RETURN a.doc_id AS doc_id, a.added_at AS added_at
