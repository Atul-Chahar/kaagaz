// Agents graph: the caseworker records that it re-planned a student because of a finding.
MATCH (a:Agent {id: 'caseworker'}), (f:Finding {id: $finding_id})
CREATE (a)-[:NOTIFIED {at: $now, student_id: $student_id, before: $before, after: $after}]->(f)
RETURN f.id AS id
