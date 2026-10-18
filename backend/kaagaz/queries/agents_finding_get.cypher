// Agents graph: one finding.
MATCH (f:Finding {id: $id})
OPTIONAL MATCH (f)-[:AFFECTS]->(s:SchemeRef)
RETURN properties(f) AS finding, collect(s.id) AS schemes
