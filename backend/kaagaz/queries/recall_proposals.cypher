// Student graph: proposed actions, newest first, with the review that proposed them.
MATCH (:Student {id: $student_id})-[:REVIEWED]->(c:CaseReview)-[:PROPOSED]->(p:Proposal)
RETURN properties(p) AS proposal, c.id AS case_id
ORDER BY p.created_at DESC, p.id
LIMIT $limit
