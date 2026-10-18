// Agents graph: the watcher records what it saw when it re-fetched one source.
MATCH (r:Run {id: $run_id})
CREATE (r)-[:CHECKED]->(c:SourceCheck)
SET c += $props
RETURN c.source_id AS source_id
