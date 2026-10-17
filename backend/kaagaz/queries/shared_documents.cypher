// Other schemes whose requirement trees (any depth) reuse documents this student still needs.
MATCH p = (o:Scheme)-[hops:REQUIRES|OPTION*1..16]->(d:Document)
WHERE o.id <> $scheme_id AND d.id IN $needed
WITH o, collect(DISTINCT d.id) AS shared
RETURN o.id AS scheme_id, o.name AS name, o.window_end AS window_end, o.window_year AS window_year,
       o.window_is_last_published AS last_published, shared, size(shared) AS shared_count
ORDER BY shared_count DESC, scheme_id
