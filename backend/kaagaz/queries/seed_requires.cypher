// Seed: REQUIRES edges (scheme or document needs a document or an AnyOf group), each with its source.
UNWIND $rows AS r
MATCH (a {id: r.src}), (b {id: r.dst})
CREATE (a)-[:REQUIRES {source_url: r.source_url, source_title: r.source_title, retrieved_at: r.retrieved_at,
  excerpt: r.excerpt, confidence: r.confidence, stale_since: r.stale_since, changed_from: r.changed_from, note: r.note, condition: r.condition}]->(b)
