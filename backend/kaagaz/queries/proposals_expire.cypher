// Student graph: pending proposals from earlier reviews are replaced by a new review.
MATCH (:Student {id: $student_id})-[:REVIEWED]->(c:CaseReview)-[:PROPOSED]->(p:Proposal)
WHERE p.status = 'pending' AND c.id <> $case_id
SET p.status = 'replaced', p.decided_at = $now
RETURN count(p) AS n
