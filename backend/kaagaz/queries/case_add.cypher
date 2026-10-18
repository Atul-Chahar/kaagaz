// Student graph: the caseworker agent records one review of the student's case.
MATCH (s:Student {id: $student_id})
CREATE (s)-[:REVIEWED]->(c:CaseReview {id: $id, at: $now, scheme_id: $scheme_id, today: $today,
  verdict: $verdict, stamp: $stamp, critical_days: $critical_days, days_left: $days_left, decision: $decision,
  json: $json})
RETURN c.id AS id
