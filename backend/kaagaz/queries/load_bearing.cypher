// The document that sits in the prerequisite trees of the most schemes in $scheme_ids
// (count of distinct schemes per document), skipping documents already held.
MATCH p = (s:Scheme)-[hops:REQUIRES|OPTION*1..16]->(d:Document)
WHERE s.id IN $scheme_ids AND NOT d.id IN $held
WITH d, collect(DISTINCT s.id) AS schemes
RETURN d.id AS doc_id, d.name AS name, d.days AS days, size(schemes) AS scheme_count, schemes
ORDER BY scheme_count DESC, doc_id
LIMIT $limit
