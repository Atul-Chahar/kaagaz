# Submission form answers (copy and paste)

## Project title

Kaagaz: are you already too late for your scholarship?

## Description (What problem does your project solve, and who is it for?)

Every scheme finder tells a student what they are eligible for. Kaagaz tells them whether they are already too late, and which certificate to apply for today.

It is for students in India applying for government scholarships, starting with 11 Karnataka and central schemes. A scholarship needs documents, and those documents need other documents first, each from a different office with its own legal processing time. A caste and income certificate in Karnataka, for example, takes up to 21 working days by law. Nobody adds this chain up, so students find out after the window has closed.

Kaagaz keeps the rules in a FalkorDB graph, with a government source for every rule. For a student's chosen scholarship it walks the requirement graph at every depth to find hidden prerequisites, adds up the legal working days on the longest chain using the official Karnataka holiday calendar, and stamps a verdict against the real deadline: "ON TIME, 9 DAYS SPARE", "AT LEAST 21 DAYS", or "12 DAYS SHORT". It then lists what to apply for today and other schemes that reuse the same documents. Unknown processing times are never guessed; the verdict becomes "at least" instead.

Each student has their own memory graph, so documents they already hold persist and the plan updates. An optional LLM can only pick one of seven fixed tools; it never writes queries, and its sentence is checked against the graph. On a 29-question benchmark with the same model (gpt-oss-20b), Kaagaz found 93% of required documents, against 9% for the model alone and 5% for plain RAG, and got the deadline verdict right 12 of 13 times.

The same engine runs a second rule pack (starting a company in Karnataka) with no code changes.

If you open it after 18 Oct 2026, most 2026-27 windows will have closed. A bar under the menu offers "See it as on 18 Oct 2026", the submission day: only the start date moves, the rules and deadlines stay real, and the screen says so.

## Track

Tick both:
- Agents That Act on Connected Data
- Agent Memory and Coordination (each student has a persistent memory graph of their own; the rules allow entering more than one track)

## Repository

https://github.com/Atul-Chahar/kaagaz

## Demo video

https://drive.google.com/file/d/1O2tQ376d4i9ojpo3L3ipvYGz6F57Pmp9/view?usp=sharing

(The form asks for a YouTube link, public or unlisted. If it rejects a Drive link, upload the same file to YouTube as unlisted and use that link here and in the README.)

## Live demo or deployment

Leave empty. The README has a one-command local setup (`docker compose up -d --build`) that starts FalkorDB, FalkorDB Browser and the app. Every push is also checked by GitHub Actions against a real FalkorDB: https://github.com/Atul-Chahar/kaagaz/actions/workflows/ci.yml

## How did you use FalkorDB in your project?

FalkorDB is the product. Without it there is no answer to give.

1. Requirement graph. Scholarships, documents, issuing offices and "any one of" groups are nodes; REQUIRES, OPTION and ISSUES are edges (76 nodes, 158 edges in the scholarship pack). Every edge carries its source URL, the exact excerpt, the saved date and whether the source is official.
2. Hidden prerequisites by depth. A variable-length traversal from the scholarship returns every document with its full path and the source of each hop. The "Show hidden steps" control in the UI is this query at depth 1, 2, 3 and so on.
3. Critical path in Cypher. chain_days.cypher computes the longest chain of legal processing days with reduce() over paths. It must agree with the Python planner on every plan, and an integration test checks them against each other on more than 100 cases.
4. Other options and load-bearing documents. shared_documents.cypher finds schemes that reuse the documents a student still needs; load_bearing.cypher counts how many schemes depend on each document, and algo.pageRank gives a second view.
5. Per-student memory with multigraph isolation. Each student is a separate graph (kaagaz:student:<id>) holding their documents, targets and saved plans. One query runs on one graph, so one student's data can never leak into another's query. Tests prove isolation and that memory survives an API restart.
6. Safe agent access. All 35 queries are parameterised .cypher files behind a fixed catalogue of seven tools (also exposed over MCP). The LLM never writes Cypher, names are resolved in the graph before any other query, and every query is shown in the UI with an "Open in FalkorDB Browser" link.

Problems we solved along the way: a parameter cannot be the upper bound of a variable-length pattern, so queries use a fixed *1..16 and filter on path length; label unions are not supported, so queries use WHERE n:A OR n:B; and the image's default 1-second query timeout is set explicitly.

## Blog link

(your published blog URL; the draft is in docs/BLOG_DRAFT.md)

## What did you like about FalkorDB?

Multiple graphs in one instance made per-user memory easy and safe: one graph per student, and a query can only see the graph it runs on. Simple queries on our graph return in about a millisecond, so the whole plan is recomputed on every click without any caching. The Browser ships in the same Docker image, which made it easy to show judges the exact query behind each answer. Cypher with reduce() over paths let us compute the critical path in the database and check it against our own planner. algo.pageRank was there when we needed it.

## What improvements would you like to see in FalkorDB?

1. Allow a query parameter as the upper bound of a variable-length pattern (for example *1..$depth). Today we use a fixed bound and filter, which wastes work.
2. Support label unions in patterns, (n:Document|AnyOf), as in openCypher. We had to write WHERE n:Document OR n:AnyOf.
3. A clearer error when the default 1-second query timeout is hit, and the default documented next to the Docker image instructions.
4. A way to run one read query across a list of graphs (for example, a teacher view over several students' graphs) while keeping isolation by default.
5. More examples of graph algorithms (pageRank, shortest paths) with weighted edges in the docs.
