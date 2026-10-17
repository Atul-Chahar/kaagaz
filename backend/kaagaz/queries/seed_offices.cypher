// Seed: issuing offices.
UNWIND $rows AS r CREATE (:Office {id: r.id, name: r.name, level: r.level})
