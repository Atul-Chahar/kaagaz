// Agents graph: an agent starts a run (watcher check, caseworker propagation).
MATCH (a:Agent {id: $agent})
CREATE (a)-[:RAN]->(r:Run {id: $run_id, agent: $agent, pack: $pack, started_at: $now, status: 'running',
  trigger: $trigger})
RETURN r.id AS id
