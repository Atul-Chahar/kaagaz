// Student graph: conditional requirements the student said apply to them.
MATCH (s:Student {id: $student_id})-[ap:APPLIES]->(a:Applies)
RETURN a.doc_id AS doc_id, a.added_at AS added_at
ORDER BY a.doc_id
