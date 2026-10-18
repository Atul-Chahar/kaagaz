// Rules graph: every rule with its proof sentence, for the watcher to re-check against the live page.
// rule_key names the rule: REQUIRES:<from>><to>, OPTION:<from>><to>, office:<doc>, days:<doc>, window:<scheme>.
MATCH (a)-[r:REQUIRES|OPTION]->(b)
WHERE r.source_url IS NOT NULL
RETURN r.source_url AS url, type(r) + ':' + a.id + '>' + b.id AS rule_key, type(r) AS kind, a.id AS from_id,
       b.id AS to_id, r.excerpt AS excerpt, r.retrieved_at AS retrieved_at, null AS value
UNION ALL
MATCH (o:Office)-[r:ISSUES]->(d:Document)
WHERE r.source_url IS NOT NULL
RETURN r.source_url AS url, 'office:' + d.id AS rule_key, 'ISSUES' AS kind, o.id AS from_id, d.id AS to_id,
       r.excerpt AS excerpt, r.retrieved_at AS retrieved_at, null AS value
UNION ALL
MATCH (d:Document)
WHERE d.days_source_url IS NOT NULL
RETURN d.days_source_url AS url, 'days:' + d.id AS rule_key, 'days' AS kind, d.id AS from_id, d.id AS to_id,
       d.days_excerpt AS excerpt, d.days_retrieved_at AS retrieved_at, toString(d.days) AS value
UNION ALL
MATCH (s:Scheme)
WHERE s.window_source_url IS NOT NULL
RETURN s.window_source_url AS url, 'window:' + s.id AS rule_key, 'window' AS kind, s.id AS from_id, s.id AS to_id,
       s.window_excerpt AS excerpt, s.window_retrieved_at AS retrieved_at, s.window_end AS value
