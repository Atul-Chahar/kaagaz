// Seed: id indexes (one statement per line, run one by one).
CREATE INDEX FOR (n:Scheme) ON (n.id);
CREATE INDEX FOR (n:Document) ON (n.id);
CREATE INDEX FOR (n:AnyOf) ON (n.id);
CREATE INDEX FOR (n:Office) ON (n.id)
