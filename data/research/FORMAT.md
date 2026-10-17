# Research fragment format

Each research area writes one YAML file here: `data/research/<area>.yaml`.
Every fact cites a saved source. Fetch every source ONLY with:

    backend/.venv/bin/python scripts/fetch_source.py URL --title "Exact page/PDF title" --id short-kebab-id

(add `--insecure` only if TLS verification fails; never bypass robots.txt). Then verify every excerpt:

    backend/.venv/bin/python scripts/check_excerpt.py short-kebab-id "exact words copied from the text file"

An excerpt must be copied verbatim from data/sources/text/<id>.txt (case and whitespace may differ), 25 words or fewer,
and must on its own prove the fact. If no source proves a fact, leave it out (or set days: null). NEVER guess.

```yaml
offices:
  - id: taluk-office-ka            # kebab-case, stable
    name: Taluk office (Nadakacheri), Revenue Department, Karnataka
    level: taluk                   # national | state | district | taluk | institution | bank
documents:
  - id: income-certificate-ka
    name: Income certificate (Karnataka)
    office: taluk-office-ka
    office_cite: {source_id: ..., excerpt: "...", confidence: official}   # proves who issues it
    days: 21                       # legal max processing days from an official RTPS/Sakala/issuer page; null if not found
    days_cite: {source_id: ..., excerpt: "...", confidence: official}     # omit if days is null
    validity: null                 # optional free text, only if a source states it
    requires:                      # what you must submit to GET this document
      - doc: ration-card-ka
        cite: {source_id: ..., excerpt: "...", confidence: official}
      - any_of: {id: proof-of-address-ka, label: "One proof of address"}
        cite: {...}
        options:
          - doc: aadhaar
            cite: {...}
          - doc: voter-id
            cite: {...}
schemes:
  - id: nsp-post-matric-minority
    name: Post Matric Scholarship for Minorities
    authority: Ministry of Minority Affairs, Government of India
    portal: NSP                    # NSP | SSP
    window: {start: 2026-07-01, end: 2026-10-31, year: "2026-27", is_last_published: false,
             cite: {source_id: ..., excerpt: "...", confidence: official}}
    requires:
      - doc: income-certificate-ka
        cite: {...}
```

confidence: `official` for .gov.in / .nic.in / state portals / government notifications and PDFs;
`secondary` only when no official source exists (college notices, news). Prefer official always.
Dates ISO. Window dates only if a source states them; if only a past year's window exists, give that year and set
is_last_published: true.

Canonical IDs (reuse these if the same thing; add new ones if needed):
documents: aadhaar, bank-account, bank-account-aadhaar-seeded, nsp-otr, income-certificate-ka, caste-certificate-ka,
caste-income-certificate-ka, residence-certificate-ka, ration-card-ka, study-certificate, fee-receipt, marks-card-previous,
sslc-marks-card, admission-proof, disability-certificate, pan-card, minority-declaration, hostel-certificate, birth-certificate
offices: uidai-enrolment-centre, bank-branch, college-institution, taluk-office-ka, food-civil-supplies-ka, nsp-portal,
ssp-portal-ka, income-tax-dept, municipal-registrar
