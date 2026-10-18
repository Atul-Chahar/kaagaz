# Submission form answers (copy and paste)

## Project title

Kaagaz

## Description (What problem does your project solve, and who is it for?)

A scholarship planner that tells a student whether they are already too late, by walking the chain of certificates each document needs in FalkorDB and adding up the time the law gives each office to issue them.

It is for students in India applying for government scholarships, starting with 11 Karnataka and central schemes. A portal lists what to upload. It doesn't say that the caste and income certificate it asks for can take 21 working days, or that the certificate needs an address proof first. On 18 Oct 2026, Post Matric for OBC Students closed in 9 working days. A student without that certificate was already 12 days short, and nothing on the portal told them.

Kaagaz shows the chain one depth at a time and stamps a verdict against the real deadline: ON TIME, AT LEAST 21 DAYS or 12 DAYS SHORT. It lists what to apply for today and which other schemes reuse the same certificate. Every rule carries the exact sentence from its government source, and the build fails if that sentence isn't in the saved page. When the law gives no time for a step, Kaagaz leaves it unknown and the verdict becomes "at least". Each student has their own memory graph, so the documents they already hold are remembered between visits.

Three agents work through one shared FalkorDB graph. A caseworker reviews a student's case step by step (recall, plan, explain, alternatives), decides, and proposes tasks with due dates or a plan B; nothing happens until the student approves. A watcher re-fetches the government pages and checks that every rule's exact sentence is still there; on its first real run it checked 175 rules on 22 pages and flagged 8 sentences that had disappeared from one portal page. A person approves or rejects each finding, and on approval the caseworker re-plans every student it affects and leaves them an alert. Applications count down: once a student applies for a certificate, its remaining time is the legal limit minus the working days since.

On a 29-question benchmark with the same model (gpt-oss-20b), Kaagaz found 93% of the required documents. The model alone found 9% and plain RAG 5%.

If you open it after 18 Oct 2026, most of these windows will have closed. A bar under the menu offers "See it as on 18 Oct 2026". It moves only the start date and stays on screen while it is on.

## Track

Tick both:
- Agents That Act on Connected Data
- Agent Memory and Coordination

## Repository

https://github.com/Atul-Chahar/kaagaz

## Demo video

https://drive.google.com/file/d/1O2tQ376d4i9ojpo3L3ipvYGz6F57Pmp9/view?usp=sharing

(The form asks for a YouTube link, public or unlisted. If it rejects a Drive link, upload the same file to YouTube as unlisted and use that link here and in the README.)

## Live demo or deployment

Leave empty. The README has a one-command local setup (`docker compose up -d --build`) that starts FalkorDB, FalkorDB Browser and the app. GitHub Actions runs every test against a real FalkorDB on each push: https://github.com/Atul-Chahar/kaagaz/actions/workflows/ci.yml

## How did you use FalkorDB in your project?

The rules live in a FalkorDB graph: 11 scholarships, 41 documents, 13 issuing offices and 10 "any one of these" groups, joined by 143 REQUIRES and OPTION edges. These are the problems it solved:

1. Finding steps nobody lists. One variable-length pattern, -[:REQUIRES|OPTION*1..16]->, returns every document a scholarship needs with its full path and the source of each hop. The "Show hidden steps" control in the UI is this query, filtered by depth.

2. Adding up the waiting time. chain_days.cypher sums the legal days along each chain with reduce(). It drops chains that pass through a document the student already holds, and counts a conditional rule only if the student said it applies to them. The Python planner computes the same critical path, every plan shows whether the two agree, and the integration tests compare them on more than 100 cases.

3. Keeping students apart. Each student is a separate graph, kaagaz:student:<id>, holding their documents, targets and saved plans. A query runs on one graph, so one student's data can't reach another student's query, and no WHERE clause has to remember to filter. Tests check the isolation and that memory survives an API restart.

4. Proof next to every answer. Each edge stores its source URL, saved date, exact sentence and whether the source is official. The Why panel shows that proof next to the Cypher that produced it, with a link to run the same query in FalkorDB Browser.

5. Ranking documents. algo.pageRank over REQUIRES edges finds the documents most of the pack depends on.

6. A safe agent. All 71 queries are parameterised .cypher files behind a fixed tool catalogue, also served over MCP. The model picks a tool and never writes Cypher, names are resolved in the graph before any other query runs, and every query shows up in the UI trace.

7. Agents that coordinate through a graph. A shared graph, kaagaz:agents, holds every watcher run, source check, finding, human decision and caseworker notification as nodes and edges. When a person approves a finding, the caseworker finds the affected students with one pattern, (f:Finding)-[:AFFECTS]->(:SchemeRef)<-[:TARGETS]-(:StudentRef), re-plans each one in their own graph, and records the notification. A cursor on its Agent node means each approval is handled once. MERGE and FOREACH keep the watcher's writes idempotent across runs.

8. Memory that changes over time. A student's graph holds applications with dates, the caseworker's earlier reviews, proposals, tasks and alerts. The countdown for an application in progress is computed in Cypher too, so the planner and the database must agree on it; the integration tests check over 300 cases.

What we had to work around: a parameter can't be the upper bound of a variable-length pattern, so the bound is a fixed 16 and $depth filters the paths. Label unions like (n:Document|AnyOf) aren't supported, so queries use WHERE n:Document OR n:AnyOf. We raised the default 1-second query timeout per query. algo.SPpaths returns the shortest chain under an option, but an option is ready only when all of its own prerequisites are done, so fastest_option.cypher takes the longest chain per option and then picks the smallest.

## Blog link

(your published post URL; the post is in docs/BLOG_DRAFT.md)

## What did you like about FalkorDB?

Many graphs in one instance made per-student memory simple and safe: one graph per student, and a query only sees the graph it runs on. A full plan runs 15 queries. 13 of them take under 2 ms and the two deep traversals about 30 ms, so the whole plan is recomputed on every click with no cache. FalkorDB Browser ships in the same Docker image, so every answer in the app links to its own query and a judge can run it. reduce() over paths let us compute the critical path inside the database and check it against our planner. algo.pageRank was there when we needed a second view of which documents matter most.

## What improvements would you like to see in FalkorDB?

1. Accept a parameter as the upper bound of a variable-length pattern (*1..$depth). Today we use a fixed bound and filter afterwards, which does extra work.
2. Support label unions in patterns, such as (n:Document|AnyOf).
3. Say in the error message when a query hits the default 1-second timeout, and document the default next to the Docker image instructions.
4. A way to run one read query across a list of graphs, for example a teacher looking at several students, while keeping isolation as the default.
5. More examples of graph algorithms (pageRank, shortest paths) with weighted edges in the docs.
