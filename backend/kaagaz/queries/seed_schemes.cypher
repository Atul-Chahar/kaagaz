// Seed: schemes with their application window and the source that proves it.
UNWIND $rows AS r
CREATE (:Scheme {id: r.id, name: r.name, authority: r.authority, portal: r.portal, note: r.note,
  window_start: r.window_start, window_end: r.window_end, window_year: r.window_year,
  window_is_last_published: r.window_is_last_published, window_note: r.window_note,
  window_renewals_only: r.window_renewals_only,
  source_url: r.window_source_url, window_source_url: r.window_source_url,
  window_source_title: r.window_source_title, window_retrieved_at: r.window_retrieved_at,
  window_excerpt: r.window_excerpt, window_confidence: r.window_confidence})
