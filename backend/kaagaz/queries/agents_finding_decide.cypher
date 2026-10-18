// Agents graph: the reviewer (a person) approves or rejects an open finding. The decision is an edge, so the
// graph keeps who decided what and when.
MATCH (f:Finding {id: $id})
WHERE f.status = 'open'
MATCH (a:Agent {id: 'reviewer'})
SET f.status = $status, f.decided_at = $now, f.decided_note = $note
CREATE (a)-[:DECIDED {at: $now, status: $status}]->(f)
RETURN properties(f) AS finding
