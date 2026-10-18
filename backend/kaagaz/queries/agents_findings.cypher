// Agents graph: findings for a pack (optionally one status), newest first, with the schemes they affect and
// how many students target those schemes (Example copies counted apart: they are synthetic).
MATCH (f:Finding)
WHERE f.pack = $pack AND ($status IS NULL OR f.status = $status)
OPTIONAL MATCH (f)-[:AFFECTS]->(s:SchemeRef)
OPTIONAL MATCH (s)<-[:TARGETS]-(st:StudentRef)
WITH f, collect(DISTINCT s.id) AS schemes, collect(DISTINCT st.id) AS ids
RETURN properties(f) AS finding, schemes,
       size([i IN ids WHERE NOT i STARTS WITH 'example-']) AS students,
       size([i IN ids WHERE i STARTS WITH 'example-']) AS examples
ORDER BY f.created_at DESC
LIMIT $limit
