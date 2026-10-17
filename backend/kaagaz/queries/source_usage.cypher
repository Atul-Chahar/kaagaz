// How many rules in the graph cite each source URL (edges, processing times, windows).
MATCH ()-[r]->()
WHERE r.source_url IS NOT NULL
WITH r.source_url AS url, count(r) AS n
RETURN url, n
UNION ALL
MATCH (d:Document) WHERE d.days_source_url IS NOT NULL
RETURN d.days_source_url AS url, count(d) AS n
UNION ALL
MATCH (s:Scheme) WHERE s.window_source_url IS NOT NULL
RETURN s.window_source_url AS url, count(s) AS n
