// Student graph: documents the student has applied for, with the date.
MATCH (:Student {id: $student_id})-[:APPLIED]->(a:Application)
RETURN a.doc_id AS doc_id, a.applied_on AS applied_on, a.added_at AS added_at
ORDER BY a.applied_on
