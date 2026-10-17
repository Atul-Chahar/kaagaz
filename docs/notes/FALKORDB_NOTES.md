# FalkorDB notes (verified 2026-10-17)

Tested against `falkordb/falkordb:latest` (Redis 8.10.2, graph module ver `42201` = v4.22.x) with
`falkordb` Python client 1.8.0 (backend/.venv). Every example here was run, and the output shown is what came back.
Sources: docs.falkordb.com (cypher/known-limitations, algorithms/*, operations/docker, getting-started/configuration,
browser), github.com/FalkorDB/FalkorDB issues #3350, #1916.

Test graph used below: `(a:Document:Act {id:'a'})-[:CITES{w:1}]->(b:Document)-[:AMENDS{w:5}]->(c:Rule)-[:REQUIRES{w:1}]->(d:AnyOf)`,
plus `(a)-[:CITES{w:10}]->(c)`.

## TOP GOTCHAS
1. **`-[:A|B*1..$depth]->` does NOT work.** A parameter as a var-length bound fails with
   `ResponseError: Encountered unhandled type in inlined properties.` (`*..$d` fails the same way). Open bug #3350.
   Workaround: validate the int in Python and format it into the query string (see section 2).
2. **The image ships `FALKORDB_ARGS=... TIMEOUT 1000`.** Read queries are killed after about 1s with `Query timed out`
   unless you pass `timeout=` per query or override `FALKORDB_ARGS`.
3. **Label unions `(n:Document|AnyOf)` / `(n:Document|:AnyOf)` are a syntax error.** Use `WHERE n:Document OR n:AnyOf`.
4. **`algo.SSpaths` with `pathCount:0` returns only ONE path** (the docs say 0 = all). Pass a large `pathCount`.
5. **Unnamed relationships are existence-checked, not counted.** `(s)-[:R]->(t)` with 2 parallel edges gives `count(*)=1`.
   Give it an alias: `-[e:R]->` gives 2 (on this version, naming the alias was enough).
6. **Nulls are never stored.** `CREATE ({note:null})` and `SET n.x = null` drop the key. Arrays cannot hold null.

## 1. Python client
```python
from falkordb import FalkorDB
db = FalkorDB(host="localhost", port=6390, username="kaagaz", password="s3cret")  # both optional
db = FalkorDB.from_url("falkor://kaagaz:s3cret@localhost:6390")   # falkors:// = TLS; redis:// also accepted
g  = db.select_graph("kaagaz:probe:ka")          # lazy: the key is created on first write
r  = g.query("MATCH (n {id:$id})-[e]->(m) RETURN n, e, m LIMIT 1", {"id": "a"}, timeout=5000)  # timeout in ms
r  = g.ro_query("MATCH (n) RETURN count(n)")     # GRAPH.RO_QUERY: rejects writes
db.list_graphs()   # ['kaagaz:probe:ka', 'kaagaz:rules:ka']
g.delete()         # drop the graph. On a missing graph it raises: "Invalid graph operation on empty key"
```
Bad password gives `AuthenticationError invalid username-password pair or user is disabled.`
`ro_query("CREATE (:Z)")` gives `ResponseError graph.RO_QUERY is to be executed only on read-only queries`.

**QueryResult**: `r.header` = `[[1,'n'],[1,'e'],[1,'m']]`, `r.result_set` = list of rows (lists), plus stats
(`r.nodes_created`, `r.relationships_created`, `r.properties_set`, `r.indices_created`, `r.run_time_ms`, ...).
Writes with no RETURN give `result_set == []`.

**Node / Edge / Path objects** (actual output):
```
Node: n.id=0  n.labels=['Document','Act']  n.properties={'id':'a','name':'A'}
Edge: e.id=0  e.relation='CITES'  e.src_node=0  e.dest_node=1  e.properties={'w':1}   # src/dest are internal ids
Path: p.nodes() -> [Node, Node], p.edges() -> [Edge]; also first_node(), last_node(), node_count(), edge_count()
      nodes inside a path keep labels and props: [(['Document','Act'],{'id':'a','name':'A'}), (['Document'],{'id':'b',...})]
```
Maps come back as `OrderedDict`, lists as `list`, and missing/null as `None`. Params accept str/int/float/bool/None/list/dict:
`RETURN $m,$l,$b` with `{"m":{"k":[1,"x"]},"l":[1,2],"b":True}` gives `[[OrderedDict({'k':[1,'x']}), [1,2], True]]`.

**Timeouts**: `UNWIND range(1,30000000) AS x RETURN count(x)` with `timeout=50` gives `ResponseError: Query timed out`.
With no `timeout`, a 40M-row read timed out at about 1.9s because of the image's `TIMEOUT 1000`. With `timeout=60000` it passed (5.1s).
A write `UNWIND range(1,2000000) AS x CREATE (:Tmp {x:x})` with `timeout=10` did NOT time out (1.24s, all rows created).
Docs: `TIMEOUT` (deprecated) = default for reads only. `TIMEOUT_DEFAULT` / `TIMEOUT_MAX` (ms, both 0 = off here) apply to reads and writes.
A per-query timeout cannot exceed `TIMEOUT_MAX`. Check with `db.config_get("TIMEOUT")` (1000) and set with `db.config_set(...)`.

## 2. Cypher support and limitations
**Variable-length + parameter (the important one)**
```
MATCH p=(:Document {id:'a'})-[:CITES|AMENDS*1..$d]->(x) RETURN x.id   {'d':2}
  ERROR: ResponseError Encountered unhandled type in inlined properties.
MATCH p=(:Document {id:'a'})-[:CITES|AMENDS*1..2]->(x) RETURN p, length(p)   -> 3 rows, lengths 1,1,2   (literal OK)
```
Workaround (tested), with the rest kept parameterized:
```python
def reach(start_id: str, depth: int):
    d = int(depth)
    if not 1 <= d <= 6: raise ValueError("depth out of range")
    return g.ro_query(f"MATCH (s {{id:$id}})-[:CITES|AMENDS|REQUIRES*1..{d}]->(x) "
                      "RETURN DISTINCT x.id ORDER BY x.id", {"id": start_id}).result_set
reach("a",1) -> [['b'],['c']]      reach("a",3) -> [['b'],['c'],['d']]
```
An alternative that works but is unbounded and expensive: `-[:A|B*]->(x) WHERE length(p) <= $d` gave `[['c',1],['d',2],['b',1],['c',2]]`.
Either way, keep a literal upper bound in the pattern.

**nodes()/relationships()/reduce()/list comprehension**: all work.
```
MATCH p=(a {id:'a'})-[*1..3]->(x)
RETURN [n IN nodes(p) | n.id], [r IN relationships(p) | type(r)],
       reduce(s=0, r IN relationships(p) | s + r.w) AS cost ORDER BY cost
-> [['a','b'],['CITES'],1], [['a','b','c'],['CITES','AMENDS'],6], [['a','b','c','d'],[...,'REQUIRES'],7],
   [['a','c'],['CITES'],10], [['a','c','d'],['CITES','REQUIRES'],11]
```
**UNWIND + MERGE ... ON CREATE / ON MATCH**: works.
```
UNWIND $rows AS row MERGE (n:Rule {id: row.id})
  ON CREATE SET n.name=row.name, n.created=true ON MATCH SET n.seen=true
RETURN n.id, n.created, n.seen        {'rows':[{'id':'c','name':'C'},{'id':'e','name':'E'}]}
-> [['c', None, True], ['e', True, None]]
```
Note: `MERGE (n {k: $map_param})` (a whole map as inlined props) hits the same "inlined properties" bug (#1916). Use `row.id` fields as above.

**OPTIONAL MATCH**: `MATCH (n {id:'a'}) OPTIONAL MATCH (n)-[:NOPE]->(x) RETURN n.id, x` gives `[['a', None]]`.

**Label unions**: not supported in patterns or WHERE.
```
MATCH (n:Document|AnyOf) ...     -> errMsg: Invalid input '|': expected a label, '{', a parameter or ')'
MATCH (n) WHERE n:Document|AnyOf -> same syntax error
MATCH (n) WHERE n:Document OR n:AnyOf RETURN n.id                    -> [['a'],['b'],['d']]
MATCH (n) WHERE any(l IN labels(n) WHERE l IN $ls) RETURN n.id       -> [['a'],['b'],['d']]  (dynamic labels)
MATCH (n) WHERE n:Document:Act   -> AND of labels works
```
Relationship-type unions `[:A|B]` DO work (shown above).

**Null properties**
```
CREATE (a {id:'a', note:null})  then  RETURN n.note, n.missing, exists(n.note), n.note IS NULL
-> [[None, None, False, True]]       # null is not stored, so it looks the same as missing
SET n.tmp = null  -> properties(n) no longer has 'tmp' (this is how you remove a property)
CREATE (:X {v:[1,null,2]}) -> ERROR Property values can only be of primitive types or arrays of primitive types
MATCH (n) WHERE n.id = $id  with {'id': None} -> OK (matches nothing)
```
**Unreferenced relationship alias** (documented known limitation):
```
CREATE (s:S),(t:T),(s)-[:R]->(t),(s)-[:R]->(t)
MATCH (s:S)-[:R]->(t:T)   RETURN count(*)  -> [[1]]   # only checks that one edge exists
MATCH (s:S)-[e:R]->(t:T)  RETURN count(e)  -> [[2]]
MATCH (s:S)-[e:R]->(t:T)  RETURN count(*)  -> [[2]]
```
The docs' workaround is to reference the edge (`WHERE ID(e) >= 0` or return `e.prop`). Always alias edges when counting or fanning out.

Other documented limitations: LIMIT does not limit eager ops (CREATE/SET/DELETE/MERGE/aggregates run fully first).
Indexes do not serve `<>` filters. No aggregates inside pattern comprehensions.

## 3. Algorithms (CALL ... YIELD)
Available: `algo.AStar, algo.betweenness, algo.BFS, algo.HarmonicCentrality, algo.labelPropagation, algo.maxFlow,
algo.MSF, algo.pageRank, algo.SPpaths, algo.SSpaths, algo.WCC` (from `CALL dbms.procedures()`).

**algo.SPpaths**: weighted shortest path(s) between two nodes. It takes ONE map argument.
```
CALL algo.SPpaths({sourceNode: a, targetNode: t,
   relTypes: ['CITES','AMENDS'],   // optional in practice: omitted = all types
   weightProp: 'w',                // optional: omitted = hop count (pathWeight = #edges)
   costProp: 'w', maxCost: 8,      // optional cost constraint
   maxLen: $len,                   // optional max hops; a $param is accepted here
   relDirection: 'outgoing',       // default; 'incoming' | 'both'
   pathCount: 1})                  // default 1; n = up to n paths; 0 = all equally-shortest
YIELD path, pathWeight, pathCost
```
Tested (a->d, all 3 types):
```
weightProp:'w'                          -> [['a','b','c','d'], 7.0, 3.0]   (pathCost = hop count when no costProp)
relTypes:['CITES','REQUIRES'] (filter)  -> [['a','c','d'], 11.0]
no weightProp                           -> [['a','c','d'], 2.0]
pathCount:5                             -> [['a','c','d'],11.0], [['a','b','c','d'],7.0]   (NOT sorted, ORDER BY yourself)
pathCount:0                             -> [['a','b','c','d'],7.0]   (all ties for the minimum only)
d->a relDirection:'incoming'            -> [['d','c','b','a'], 7.0]
no path (wrong direction)               -> []  (no error)
```
Weights come back as floats.

**algo.SSpaths**: from a single source to every reachable node. Same map keys, minus `targetNode`.
```
MATCH (a {id:'a'}) CALL algo.SSpaths({sourceNode:a, relTypes:['CITES','AMENDS','REQUIRES'], weightProp:'w', pathCount:10})
YIELD path, pathWeight RETURN [n IN nodes(path) | n.id], pathWeight ORDER BY pathWeight
-> [['a','b'],1.0], [['a','b','c'],6.0], [['a','b','c','d'],7.0], [['a','c'],10.0], [['a','c','d'],11.0]
pathCount:0 or 1 -> [['a','b'],1.0] ONLY   # gotcha: pathCount caps the TOTAL paths, and 0 does not mean all
```
Results include several paths to the same target (c appears twice). Dedupe per target if you need one.

**algo.pageRank(label|NULL, relType|NULL) YIELD node, score**
```
CALL algo.pageRank('Document','CITES') YIELD node, score RETURN node.id, score ORDER BY score DESC
-> [['b', 0.2357], ['a', 0.1274]]
CALL algo.pageRank(NULL, NULL) ...  -> all nodes, e.g. ['d',0.2667], ['c',0.2169], ...
```
**algo.BFS(start, maxDepth, relType|NULL) YIELD nodes, edges** (`algo.bfs` works too). Takes one type only.
```
MATCH (a {id:'a'}) CALL algo.BFS(a, 2, 'CITES') YIELD nodes, edges RETURN [n IN nodes | n.id], [e IN edges | type(e)]
-> [[['b','c'], ['CITES','CITES']]]      # start node NOT included; outgoing; each node once
CALL algo.BFS(a, 1, NULL) -> [['b','c']]  ;  maxDepth 0 -> no rows
```

## 4. Multiple graphs in one instance
Each graph is one Redis key of type `graphdata` (`redis-cli TYPE kaagaz:probe:ka` gives `graphdata`).
Names with colons such as `kaagaz:rules:ka` work fine. Tested: graphs are fully isolated (`kaagaz:rules:ka` count=1,
`kaagaz:probe:ka` count=7 in the same instance). `list_graphs()` lists both, and `delete()` removes one only.
Each query runs against one graph (untested assumption: indexes and schema are per graph too). Cypher cannot cross graphs; query each graph separately.
`g.copy("new:name")` clones a graph. Keys share the Redis keyspace, so avoid using the same names for plain Redis keys.

## 5. FalkorDB Browser
`falkordb/falkordb` (not `falkordb/falkordb-server`) runs the Next.js browser on **container port 3000**
(`BROWSER=1` env, set to 0 to disable). The image metadata EXPOSEs only 6379, so you must map it yourself: `-p 3000:3000`.
Confirmed: `curl http://<container-ip>:3000/` returns 200 with `<title>FalkorDB Browser`. Open `http://localhost:3000`
and fill in host/port/user/password. Untested: since the browser runs inside the container, use host `localhost` and port `6379`
(the container-internal values, not the host-mapped 6390). URL forms accepted: falkor://, falkors://, redis://, rediss://.
Note: on this machine, host port 3000 is already taken by `kaagaz-falkordb-1` (3000->3000, 6380->6379).

## 6. Persistence
Data dir: **`/var/lib/falkordb/data`** (env `FALKORDB_DATA_PATH`, passed as `--dir`; `CONFIG GET dir` confirms it).
The image declares no VOLUME. Defaults: RDB snapshots `save 3600 1 300 100 60 10000`, `appendonly no`.
Verified: after `docker restart`, `dump.rdb` was written there and the graph was intact.
Without a volume, data does not survive `docker rm`. Use:
```
docker run -d -p 6379:6379 -p 3000:3000 -v kaagaz_falkor:/var/lib/falkordb/data \
  -e REDIS_ARGS="--appendonly yes --requirepass secret" \
  -e FALKORDB_ARGS="MAX_QUEUED_QUERIES 25 TIMEOUT_DEFAULT 30000 RESULTSET_SIZE 10000" falkordb/falkordb:latest
```
Setting `FALKORDB_ARGS` replaces the image default, which removes the `TIMEOUT 1000`.

## 7. Indexes (range indexes, all tested)
```
CREATE INDEX FOR (n:Document) ON (n.id)
CREATE INDEX FOR (n:Rule) ON (n.id, n.name)          -- multiple properties
CREATE INDEX FOR ()-[r:CITES]-() ON (r.w)            -- relationship property
DROP INDEX FOR (n:Rule) ON (n.name)
g.create_node_range_index("AnyOf", "id")             -- python helper (also *_fulltext_*, *_vector_*, unique constraints)
CALL db.indexes() YIELD label, properties, types, entitytype
-> ['Document',['id'],{'id':['RANGE']},'NODE'], ['CITES',['w'],{'w':['RANGE']},'RELATIONSHIP'], ...
print(g.explain("MATCH (n:Document {id:'a'}) RETURN n"))  -> "Node By Index Scan | (n:Document)"
```
Put the label in the pattern (`(n:Document {id:$id})`) so the index can be used. Untested: an unlabeled `(n {id:$id})` should not hit the index.
