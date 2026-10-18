// Agents graph (kaagaz:agents, shared by every agent): register an agent once.
MERGE (a:Agent {id: $id})
ON CREATE SET a.name = $name, a.role = $role, a.created_at = $now
RETURN a.id AS id, a.name AS name, a.cursor AS cursor
