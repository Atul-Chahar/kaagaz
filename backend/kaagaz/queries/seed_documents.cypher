// Seed: documents. days may be null (no official time found); null properties are simply not stored.
UNWIND $rows AS r
CREATE (:Document {id: r.id, name: r.name, days: r.days, days_unit: r.days_unit, validity: r.validity, office: r.office, note: r.note,
  days_source_url: r.days_source_url, days_source_title: r.days_source_title,
  days_retrieved_at: r.days_retrieved_at, days_excerpt: r.days_excerpt, days_confidence: r.days_confidence, days_stale_since: r.days_stale_since,
  service_days: r.service_days, service_days_source_url: r.service_days_source_url,
  service_days_source_title: r.service_days_source_title, service_days_retrieved_at: r.service_days_retrieved_at,
  service_days_excerpt: r.service_days_excerpt})
