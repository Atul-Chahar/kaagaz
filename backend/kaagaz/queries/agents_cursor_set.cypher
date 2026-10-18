// Agents graph: move an agent's cursor (what it has already handled).
MATCH (a:Agent {id: $id})
SET a.cursor = $cursor
RETURN a.cursor AS cursor
