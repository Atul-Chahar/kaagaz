// Seed: OPTION edges (an AnyOf group can be met by this document), each with its source.
UNWIND $rows AS r
MATCH (a:AnyOf {id: r.src}), (b:Document {id: r.dst})
CREATE (a)-[:OPTION {source_url: r.source_url, source_title: r.source_title, retrieved_at: r.retrieved_at,
  excerpt: r.excerpt, confidence: r.confidence, note: r.note}]->(b)
