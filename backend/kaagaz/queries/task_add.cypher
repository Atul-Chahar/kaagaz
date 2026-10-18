// Student graph: a task the student approved (apply for a document, gather one, or a plan-B checkpoint).
MATCH (s:Student {id: $student_id})
MERGE (s)-[:HAS_TASK]->(t:Task {id: $id})
ON CREATE SET t.kind = $kind, t.title = $title, t.doc_id = $doc_id, t.scheme_id = $scheme_id, t.due = $due,
  t.reason = $reason, t.status = 'open', t.created_at = $now, t.from_proposal = $from_proposal
RETURN properties(t) AS task
