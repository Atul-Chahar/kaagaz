// Student graph: actions the caseworker proposes; none runs until the student approves it.
MATCH (c:CaseReview {id: $case_id})
UNWIND $rows AS r
CREATE (c)-[:PROPOSED]->(p:Proposal)
SET p += r, p.status = 'pending', p.created_at = $now
RETURN count(p) AS n
