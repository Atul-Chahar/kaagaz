// All-of chains only: every REQUIRES path from the scheme through documents the student does not hold,
// with the remaining legal processing days summed along the path by reduce().
// A path that passes through a held document is dropped (a held document needs nothing more).
// Paths through an AnyOf are not all-of chains and are left to the planner (it takes the fastest option).
MATCH p = (s:Scheme {id: $scheme_id})-[hops:REQUIRES*1..8]->(leaf:Document)
WHERE length(p) <= $depth
  AND none(x IN tail(nodes(p)) WHERE x.id IN $held OR NOT x:Document)
RETURN [x IN nodes(p) | x.id] AS path,
       reduce(total = 0, x IN tail(nodes(p)) | total + coalesce(x.days, 0)) AS days,
       any(x IN tail(nodes(p)) WHERE x.days IS NULL) AS has_unknown,
       [x IN tail(nodes(p)) WHERE x.days IS NULL | x.id] AS unknown_ids
ORDER BY days DESC, size(path) DESC
LIMIT $limit
