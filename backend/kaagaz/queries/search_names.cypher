// Name search used by the Ask box when no LLM key is set: schemes and documents whose name contains a word.
MATCH (n)
WHERE (n:Scheme OR n:Document) AND any(w IN $words WHERE toLower(n.name) CONTAINS w OR toLower(n.id) CONTAINS w)
RETURN n.id AS id, labels(n)[0] AS label, n.name AS name,
       size([w IN $words WHERE toLower(n.name) CONTAINS w OR toLower(n.id) CONTAINS w]) AS hits
ORDER BY hits DESC, label DESC, id
LIMIT $limit
