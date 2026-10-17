// Every document in the pack with its office, for the "tick what you hold" list.
MATCH (d:Document)
OPTIONAL MATCH (o:Office)-[iss:ISSUES]->(d)
OPTIONAL MATCH (s:Scheme)-[req:REQUIRES]->(d)
WITH d, o, count(req) AS direct_schemes
RETURN d.id AS id, d.name AS name, d.days AS days, d.days_unit AS days_unit, o.name AS office_name, direct_schemes
ORDER BY direct_schemes DESC, name
