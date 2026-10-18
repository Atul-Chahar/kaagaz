// Student graph: an agent leaves an alert for the student (idempotent by id).
MATCH (s:Student {id: $student_id})
MERGE (s)-[:ALERTED]->(a:Alert {id: $id})
ON CREATE SET a.at = $now, a.kind = $kind, a.scheme_id = $scheme_id, a.finding_id = $finding_id,
  a.message = $message, a.before = $before, a.after = $after, a.seen = false
RETURN a.id AS id
