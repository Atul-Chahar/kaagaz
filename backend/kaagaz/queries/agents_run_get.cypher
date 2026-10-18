// Agents graph: one run with every source check and the findings it raised or saw again.
MATCH (r:Run {id: $run_id})
OPTIONAL MATCH (r)-[:CHECKED]->(c:SourceCheck)
WITH r, collect(properties(c)) AS checks
OPTIONAL MATCH (r)-[:FOUND]->(f:Finding)
RETURN properties(r) AS run, checks, collect(f.id) AS findings
