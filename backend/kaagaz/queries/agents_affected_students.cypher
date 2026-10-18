// Agents graph: students whose target scheme a finding affects (only ids; their data stays in their own graph).
MATCH (f:Finding {id: $id})-[:AFFECTS]->(s:SchemeRef)<-[:TARGETS]-(st:StudentRef)
RETURN DISTINCT st.id AS student_id, s.id AS scheme_id, s.pack AS pack
