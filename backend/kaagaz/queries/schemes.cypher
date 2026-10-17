// Every scheme in the pack with its application window, for the Start screen.
MATCH (s:Scheme)
OPTIONAL MATCH (s)-[req:REQUIRES]->(c)
WITH s, count(req) AS direct_requirements
RETURN properties(s) AS scheme, direct_requirements, s.window_end AS window_end, s.name AS name
ORDER BY window_end, name
