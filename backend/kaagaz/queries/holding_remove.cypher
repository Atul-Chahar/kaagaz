// Student graph: forget a holding.
MATCH (s:Student {id: $student_id})-[holds:HOLDS]->(h:Holding {doc_id: $doc_id})
DELETE holds, h
RETURN count(h) AS removed
