// Why a scheme needs a document: the requirement paths from scheme to document with each hop's source.
MATCH p = (s:Scheme {id: $scheme_id})-[hops:REQUIRES|OPTION*1..16]->(d {id: $doc_id})
WITH p, length(p) AS hops_count
RETURN [x IN nodes(p) | {id: x.id, name: x.name, label: labels(x)[0]}] AS nodes,
       [r IN relationships(p) | properties(r)] AS rules,
       [r IN relationships(p) | type(r)] AS types,
       hops_count
ORDER BY hops_count
LIMIT 5
