// Student graph: remember a computed plan, so a later visit can say what changed.
MATCH (s:Student {id: $student_id})
CREATE (s)-[snap:PLANNED]->(:PlanSnapshot {at: $now, scheme_id: $scheme_id, verdict: $verdict,
  critical_days: $critical_days, exact: $exact, json: $json})
RETURN $now AS at
