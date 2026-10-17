// PageRank over REQUIRES edges on the whole pack: documents that many requirements point to (directly or
// through other documents) score highest. Shown next to the distinct-scheme count on the About page.
CALL algo.pageRank('Document', 'REQUIRES') YIELD node, score
RETURN node.id AS doc_id, node.name AS name, score
ORDER BY score DESC, doc_id
LIMIT $limit
