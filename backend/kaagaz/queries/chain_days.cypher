// All-of chains only: every REQUIRES path from the scheme through documents the student does not hold,
// with the remaining legal processing days summed along the path by reduce().
// A path that passes through a held document is dropped (a held document needs nothing more).
// A document the student has applied for counts only its days still left ($progress_ids / $progress_left, same
// order), and paths below it are dropped (its prerequisites are done).
// Paths through an AnyOf are not all-of chains and are left to the planner (it takes the fastest option).
// A conditional edge counts only if the student said it applies to them (its target id is in $applies).
MATCH p = (s:Scheme {id: $scheme_id})-[hops:REQUIRES*1..8]->(leaf:Document)
WHERE length(p) <= $depth
  AND none(x IN tail(nodes(p)) WHERE x.id IN $held OR NOT x:Document)
  AND none(i IN range(1, length(p) - 1) WHERE nodes(p)[i].id IN $progress_ids)
  AND all(i IN range(0, length(p) - 1) WHERE relationships(p)[i].condition IS NULL OR nodes(p)[i + 1].id IN $applies)
RETURN [x IN nodes(p) | x.id] AS path,
       reduce(total = 0, x IN tail(nodes(p)) | total + CASE WHEN x.id IN $progress_ids AND x.days IS NOT NULL
         THEN [i IN range(0, size($progress_ids) - 1) WHERE $progress_ids[i] = x.id | $progress_left[i]][0]
         ELSE coalesce(x.days, 0) END) AS days,
       any(x IN tail(nodes(p)) WHERE x.days IS NULL) AS has_unknown,
       [x IN tail(nodes(p)) WHERE x.days IS NULL | x.id] AS unknown_ids
ORDER BY days DESC, size(path) DESC
LIMIT $limit
