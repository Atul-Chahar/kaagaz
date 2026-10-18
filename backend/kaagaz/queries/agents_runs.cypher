// Agents graph: recent runs, newest first (optionally for one agent).
MATCH (a:Agent)-[:RAN]->(r:Run)
WHERE $agent IS NULL OR a.id = $agent
RETURN a.id AS agent, properties(r) AS run
ORDER BY r.started_at DESC
LIMIT $limit
