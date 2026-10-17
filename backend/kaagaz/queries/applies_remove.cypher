// Student graph: a conditional requirement does not apply to the student after all.
MATCH (s:Student {id: $student_id})-[ap:APPLIES]->(a:Applies {doc_id: $doc_id})
DELETE ap, a
RETURN count(a) AS removed
