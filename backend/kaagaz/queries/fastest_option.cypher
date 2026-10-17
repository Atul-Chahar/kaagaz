// For one "any one of" group: each option's remaining time, as the longest chain of not-held REQUIRES
// prerequisites below it (an option is ready only when ALL its own prerequisites are done).
// A shortest-path procedure (algo.SPpaths) would pick the SHORTEST chain under an option, which is wrong for
// all-of prerequisites, so this is a weighted path query that takes the maximum per option.
// The planner runs this for every open group as a cross-check of its own choice (plan -> option_checks).
MATCH (a:AnyOf {id: $anyof_id})-[opt:OPTION]->(o:Document)
WHERE NOT o.id IN $held
OPTIONAL MATCH p = (o)-[hops:REQUIRES*1..8]->(x:Document)
WHERE none(y IN nodes(p) WHERE y.id IN $held OR NOT y:Document)
  AND all(i IN range(0, length(p) - 1) WHERE relationships(p)[i].condition IS NULL OR nodes(p)[i + 1].id IN $applies)
WITH o, opt, p,
     CASE WHEN p IS NULL THEN 0 ELSE reduce(t = 0, y IN tail(nodes(p)) | t + coalesce(y.days, 0)) END AS below,
     CASE WHEN p IS NULL THEN false ELSE any(y IN tail(nodes(p)) WHERE y.days IS NULL) END AS below_unknown
WITH o, opt, max(below) AS below, max(CASE WHEN below_unknown THEN 1 ELSE 0 END) AS below_unknown
RETURN o.id AS doc_id, o.name AS name, o.days AS days,
       coalesce(o.days, 0) + below AS total_days,
       (o.days IS NULL OR below_unknown = 1) AS has_unknown,
       properties(opt) AS rule
ORDER BY total_days, has_unknown, doc_id
