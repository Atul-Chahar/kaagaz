// Student graph: the student approves or rejects one pending proposal.
MATCH (:Student {id: $student_id})-[:REVIEWED]->(:CaseReview)-[:PROPOSED]->(p:Proposal {id: $id})
WHERE p.status = 'pending'
SET p.status = $status, p.decided_at = $now
RETURN properties(p) AS proposal
