// Every document and "any one of" group a scheme needs, at every depth up to $depth.
// Depth counts REQUIRES hops only (an OPTION hop inside an AnyOf does not use up a step).
// FalkorDB does not accept a parameter as the variable-length bound, so the literal 16 (= 2 x max depth 8)
// is the hard ceiling and $depth (validated 1..8 by the tool layer) filters the paths.
MATCH p = (s:Scheme {id: $scheme_id})-[hops:REQUIRES|OPTION*1..16]->(n)
WITH p, n, size([r IN relationships(p) WHERE type(r) = 'REQUIRES']) AS depth
WHERE depth <= $depth
WITH p, n, depth, relationships(p) AS rs
OPTIONAL MATCH (o:Office)-[iss:ISSUES]->(n)
RETURN n.id AS id, labels(n)[0] AS label, n.name AS name, n.days AS days, depth,
       [x IN nodes(p) | x.id] AS path,
       [r IN rs | type(r)] AS hop_types,
       properties(rs[size(rs) - 1]) AS hop,
       size([(n)-[more:REQUIRES]->(m) | m.id]) AS out_requires,
       properties(n) AS props,
       o.id AS office_id, o.name AS office_name, properties(iss) AS issues
ORDER BY depth, id
