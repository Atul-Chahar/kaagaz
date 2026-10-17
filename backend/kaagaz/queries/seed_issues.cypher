// Seed: ISSUES edges (office issues document), with the legal days and the source for the office.
UNWIND $rows AS r
MATCH (o:Office {id: r.office}), (d:Document {id: r.doc})
CREATE (o)-[:ISSUES {days: r.days, days_source_url: r.days_source_url, source_url: r.source_url,
  source_title: r.source_title, retrieved_at: r.retrieved_at, excerpt: r.excerpt, confidence: r.confidence}]->(d)
