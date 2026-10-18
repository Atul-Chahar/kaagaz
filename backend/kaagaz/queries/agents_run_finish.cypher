// Agents graph: close a run with its status and a JSON summary.
MATCH (r:Run {id: $run_id})
SET r.finished_at = $now, r.status = $status, r.summary = $summary
RETURN properties(r) AS run
