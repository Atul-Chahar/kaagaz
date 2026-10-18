// Agents graph: how many students target each scheme, so the watcher checks their sources first.
MATCH (st:StudentRef)-[:TARGETS]->(s:SchemeRef {pack: $pack})
RETURN s.id AS scheme_id, count(DISTINCT st) AS students
