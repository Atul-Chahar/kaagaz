// Agents graph: approved findings the caseworker has not handled yet (decided after its cursor).
MATCH (f:Finding)
WHERE f.status = 'approved' AND f.decided_at > $cursor
RETURN properties(f) AS finding
ORDER BY f.decided_at
