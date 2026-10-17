// One document with its issuing office, processing time source, and what it directly requires.
MATCH (d:Document {id: $doc_id})
OPTIONAL MATCH (o:Office)-[iss:ISSUES]->(d)
OPTIONAL MATCH (d)-[req:REQUIRES]->(c)
RETURN properties(d) AS doc, o.id AS office_id, o.name AS office_name, properties(iss) AS issues,
       collect(CASE WHEN c IS NULL THEN NULL ELSE {id: c.id, name: c.name, label: labels(c)[0]} END) AS requires
