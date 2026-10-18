// Agents graph: every agent with its run count, last run and cursor.
MATCH (a:Agent)
OPTIONAL MATCH (a)-[:RAN]->(r:Run)
WITH a, count(r) AS runs, max(r.started_at) AS last_run
OPTIONAL MATCH (a)-[d:DECIDED]->(:Finding)
RETURN a.id AS id, a.name AS name, a.role AS role, a.cursor AS cursor, runs, last_run, count(d) AS decisions
ORDER BY id
