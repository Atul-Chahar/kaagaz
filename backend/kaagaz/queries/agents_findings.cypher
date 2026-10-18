// Agents graph: findings for a pack (optionally one status), newest first, with the schemes they affect and
// how many students target those schemes.
MATCH (f:Finding)
WHERE f.pack = $pack AND ($status IS NULL OR f.status = $status)
OPTIONAL MATCH (f)-[:AFFECTS]->(s:SchemeRef)
OPTIONAL MATCH (s)<-[:TARGETS]-(st:StudentRef)
WITH f, collect(DISTINCT s.id) AS schemes, count(DISTINCT st) AS students
RETURN properties(f) AS finding, schemes, students
ORDER BY f.created_at DESC
LIMIT $limit
