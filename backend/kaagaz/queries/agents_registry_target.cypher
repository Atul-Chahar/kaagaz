// Agents graph: the shared registry of which student targets which scheme, so a rule change can find the
// students it affects. Only ids are shared; holdings and plans stay in each student's own graph.
MERGE (st:StudentRef {id: $student_id})
MERGE (s:SchemeRef {key: $pack + ':' + $scheme_id})
ON CREATE SET s.pack = $pack, s.id = $scheme_id
MERGE (st)-[t:TARGETS]->(s)
SET t.at = $now
RETURN st.id AS id
