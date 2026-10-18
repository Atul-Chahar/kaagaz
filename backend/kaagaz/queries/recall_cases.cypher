// Student graph: the caseworker's earlier reviews, newest first (its memory of this case).
MATCH (:Student {id: $student_id})-[:REVIEWED]->(c:CaseReview)
RETURN properties(c) AS review
ORDER BY c.at DESC
LIMIT $limit
