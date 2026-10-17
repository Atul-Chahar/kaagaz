// Student graph: the most recent saved plans.
MATCH (s:Student {id: $student_id})-[snap:PLANNED]->(p:PlanSnapshot)
RETURN p.at AS at, p.scheme_id AS scheme_id, p.verdict AS verdict, p.critical_days AS critical_days,
       p.exact AS exact
ORDER BY p.at DESC
LIMIT $limit
