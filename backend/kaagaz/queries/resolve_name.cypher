// Exact, then case-insensitive, lookup of a scheme or document by id or name. Runs before any other tool.
MATCH (n)
WHERE (n:Scheme OR n:Document)
  AND (n.id = $q OR toLower(n.id) = toLower($q) OR toLower(n.name) = toLower($q))
RETURN n.id AS id, labels(n)[0] AS label, n.name AS name,
       CASE WHEN n.id = $q OR n.name = $q THEN 'exact' ELSE 'case_insensitive' END AS match
ORDER BY match, id
