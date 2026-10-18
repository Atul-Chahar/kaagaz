// Student graph: the most recent saved plan for one scheme, with its stamp (used to say what a rule change did).
MATCH (:Student {id: $student_id})-[:PLANNED]->(p:PlanSnapshot {scheme_id: $scheme_id})
RETURN p.at AS at, p.verdict AS verdict, p.json AS json
ORDER BY p.at DESC
LIMIT 1
