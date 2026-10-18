// Agents graph: the watcher records a finding (idempotent by id) and links it to the schemes it affects.
// A finding seen again in a later run is linked to that run too; its status (open, approved, rejected) is kept.
MATCH (r:Run {id: $run_id})
MERGE (f:Finding {id: $id})
ON CREATE SET f += $props, f.status = 'open', f.created_at = $now, f.seen_count = 0
SET f.last_seen = $now, f.seen_count = f.seen_count + 1
MERGE (r)-[:FOUND]->(f)
FOREACH (sid IN $scheme_ids |
  MERGE (s:SchemeRef {key: $pack + ':' + sid})
  ON CREATE SET s.pack = $pack, s.id = sid
  MERGE (f)-[:AFFECTS]->(s))
RETURN f.id AS id, f.status AS status
