// Student graph: schemes the student targets.
MATCH (s:Student {id: $student_id})-[tg:TARGETS]->(t:Target)
RETURN t.scheme_id AS scheme_id, t.deadline AS deadline, t.deadline_source AS deadline_source,
       t.added_at AS added_at
ORDER BY t.added_at
