// Student graph: forget an application (for example when it was recorded by mistake).
MATCH (:Student {id: $student_id})-[r:APPLIED]->(a:Application {doc_id: $doc_id})
DELETE r, a
RETURN count(a) AS removed
