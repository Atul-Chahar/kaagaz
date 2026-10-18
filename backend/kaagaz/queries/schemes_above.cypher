// Rules graph: every scheme whose requirement tree (any depth) contains this node, or the scheme itself.
MATCH (s:Scheme)
WHERE s.id = $id
RETURN s.id AS scheme_id
UNION
MATCH (s:Scheme)-[hops:REQUIRES|OPTION*1..16]->(n {id: $id})
RETURN DISTINCT s.id AS scheme_id
