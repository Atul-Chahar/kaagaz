// Node and edge counts by label and type, for the About page and health check.
MATCH (n)
RETURN 'node' AS kind, labels(n)[0] AS name, count(n) AS n
UNION ALL
MATCH ()-[e]->()
RETURN 'edge' AS kind, type(e) AS name, count(e) AS n
