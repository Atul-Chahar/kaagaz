// Seed: "any one of these documents" groups.
UNWIND $rows AS r CREATE (:AnyOf {id: r.id, label: r.label, name: r.label})
