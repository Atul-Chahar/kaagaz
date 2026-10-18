---
title: I built a scholarship planner that tells students they're already too late
published: false
tags: showdev, opensource, ai, database
cover_image: https://raw.githubusercontent.com/Atul-Chahar/kaagaz/main/docs/screenshots/chain-late-1440-light.png
---

On 18 October 2026, a student in Karnataka applying for the Post Matric scholarship for OBC students had 9 working days left. The portal asks for a caste and income certificate. Under Karnataka's Sakala rules, the office has up to 21 working days to issue one.

A student without that certificate was 12 days short before they started, and nothing on the portal said so.

Scholarship portals tell you what to upload. Scheme finders tell you what you're eligible for. None of them tell you that the certificate on the upload list needs an address proof first, or how long each office is allowed to take. Students find out when the window closes.

I built [Kaagaz](https://github.com/Atul-Chahar/kaagaz) for Graph Hacks (WeMakeDevs x FalkorDB) to answer one question: given the documents you have today, can you still make this deadline? Kaagaz means "paper" in Hindi and Urdu.

![The chain screen: 12 working days short of a 31 Oct 2026 deadline](https://raw.githubusercontent.com/Atul-Chahar/kaagaz/main/docs/screenshots/chain-late-1440-light.png)

## What it does

You pick a scholarship and tick the documents you already hold. Kaagaz walks every chain of requirements below that scholarship, adds up the legal processing time on the longest one, and puts a rubber stamp on the screen: `ON TIME · 9 DAYS SPARE`, `AT LEAST 21 DAYS`, or `12 DAYS SHORT`.

Under the stamp is a list called "Start today": the documents you can apply for right now, sorted by how much each one shortens the wait. Next to it is a list of other scholarships with later deadlines that reuse the certificate you're about to apply for anyway.

Click any step and a panel opens with the exact sentence from the government page that says this step is needed, the link, the date I saved it, and the Cypher query that produced the answer.

## A scholarship is a chain, so I put it in a graph

A scholarship looks like a checklist until you look at what each item needs. The scholarship needs a caste and income certificate. The certificate needs an address proof and an ID proof. Some documents can be met by "any one of" three others, and each of those has its own prerequisites. Every step is a different office with a different time limit.

Drawn on paper, that's a graph, so the rules live in FalkorDB: 11 scholarships, 41 documents, 13 issuing offices and 10 "any one of" groups, joined by 143 requirement edges. Each scholarship and document is a node, and `REQUIRES`, `OPTION` and `ISSUES` are edges.

"What do I need, including what I need to get those things?" becomes one variable-length pattern:

```cypher
MATCH p = (s:Scheme {id: $scheme_id})-[hops:REQUIRES|OPTION*1..16]->(n)
WITH p, n, size([r IN relationships(p) WHERE type(r) = 'REQUIRES']) AS depth
WHERE depth <= $depth
RETURN n.id, n.name, n.days, depth, [x IN nodes(p) | x.id] AS path
```

The UI has a stepper labelled "Show hidden steps" that runs this query at depth 1, then 2, then 3. With the Example student (a made-up profile, labelled as one everywhere), depth 1 looks fine: the chain takes 21 working days, there are 30 before the 30 November deadline, green stamp, 9 days spare. Press "One step deeper" and an address proof appears under the certificate. The law gives no time limit for it, so the green stamp turns blue: `AT LEAST 21 DAYS`. Kaagaz can no longer promise you're on time, and it says so.

The legal days along each chain are added up inside the database with `reduce()`:

```cypher
MATCH p = (s:Scheme {id: $scheme_id})-[hops:REQUIRES*1..8]->(leaf:Document)
WHERE length(p) <= $depth
  AND none(x IN tail(nodes(p)) WHERE x.id IN $held OR NOT x:Document)
RETURN [x IN nodes(p) | x.id] AS path,
       reduce(total = 0, x IN tail(nodes(p)) | total + coalesce(x.days, 0)) AS days
ORDER BY days DESC
```

My Python planner computes the same critical path a different way (`finish(doc) = days(doc) + max(finish(prerequisite))`). Every plan runs both, and the screen shows whether they agree. The integration tests compare them on more than 100 cases.

Each student also gets their own graph, `kaagaz:student:<id>`, with the documents they hold, the scholarship they're targeting and their past plans. A FalkorDB query runs on one graph, so one student's data can't show up in another student's query. I like that the isolation comes from the database, so there's no `WHERE student_id = ...` for me to forget somewhere.

A full plan runs 15 queries. On my laptop 13 of them take under 2 ms and the two deep traversals about 30 ms, so I recompute the whole plan on every click and skip caching entirely.

## It won't guess

This is the rule I care about most. A wrong "you're on time" is worse than no answer, because the student stops worrying.

So every rule in the graph stores where it came from: the URL, the page title, the date I saved it, whether the source is official, and the exact sentence (25 words or fewer) that proves it. I saved 60 government pages and PDFs with their SHA-256 hashes. A script, `audit_data.py`, fails the build if any stored sentence isn't found in the saved text, or if any saved file's hash has changed.

Many steps have no official time limit. Opening a bank account, getting an address proof, seeding Aadhaar to your bank: no law says how long these take. Kaagaz stores those times as `null` and never fills in a "typical" number. A verdict that depends on an unknown step becomes a lower bound ("at least 21 days") or "time unknown".

The Sakala limits turned out to be working days, which meant I needed Karnataka's official 2026 holiday list and the rule that second and fourth Saturdays are off before any count made sense. For deadlines in January 2027 the 2027 list isn't published yet, and the screen says the count may be slightly high.

## The rules go stale, so an agent checks them

Saving the sources fixes the rules to the day I saved them. Government pages change: deadlines get extended, portals get redesigned. So Kaagaz has a watcher agent. It fetches every saved page again (robots.txt respected, one request per second per site) and checks that each rule's exact sentence is still on the live page. When a sentence is gone, it finds the closest sentence on the new page with the digits masked, so "Last date to apply: 31.10.2026" and "Last date to apply: 15.11.2026" match, and it reports the new date.

The watcher never changes a rule. Each finding waits on an Agents screen, where a person sees the saved sentence next to what the page says now and approves or rejects it. An approval saves the new copy of the page as a new source version, writes the change to a file that the same audit checks, and rebuilds the rules graph. Then a third agent, the caseworker, follows a registry in the graph to every student who targets an affected scheme, re-plans each one and leaves them an alert.

All three share one FalkorDB graph, `kaagaz:agents`. Runs, source checks, findings and decisions are nodes, and finding the students a change affects is one pattern:

```cypher
MATCH (f:Finding {id: $id})-[:AFFECTS]->(s:SchemeRef)<-[:TARGETS]-(st:StudentRef)
RETURN DISTINCT st.id AS student_id, s.id AS scheme_id
```

Its first real run, on 18 October, checked the 22 pages behind 175 rules. 18 had exactly the same text. Every deadline sentence was still there. One page, the State Scholarship Portal's home page, had lost the application steps that 48 rules quote. They may have moved into a section the page loads with a script, which a text check can't tell apart from a real change. So the findings are open, waiting for me to look.

The same caseworker also works on one student at a time. "Review my case" runs recall, plan, explain and, only when the answer isn't a clear yes, alternatives. Then it decides with a written policy and proposes tasks with due dates or a plan B. Nothing happens until the student presses Approve. Once a student applies for a certificate, the plan counts it down: the legal limit minus the working days since they applied. The Cypher cross-check applies the same countdown, so the planner and the database still have to agree.

## Letting a model near it, carefully

There's an optional Ask box where a language model can answer free-text questions. The model gets seven tools (`resolve`, `prerequisites`, `plan`, `explain`, `alternatives`, `remember_holding`, `recall`) and picks one. It never writes Cypher. Names are looked up in the graph before any other query runs, so "income certificate" either matches a real node or comes back as "unknown name".

The model then writes one sentence about the result, and a checker reads that sentence before it's shown. Every scheme or document it names and every number it states must be in the tool result. If not, the user sees a sentence built from the data instead.

I tried 12 models on NVIDIA NIM's free tier. Five returned HTTP 404 for my account, three timed out on every call, and two were too slow or didn't call a tool. Of the two left, `openai/gpt-oss-20b` picked the right tool with the right ids on 5 of 6 test questions, so that's the default.

Then I ran a 29-question benchmark, with questions and answers written from the saved sources alone, without looking at the graph:

| System | Documents found | Deadline verdict right | First step right |
|---|---|---|---|
| Model alone | 9% | 5 of 13 | 1 of 9 |
| Plain RAG over the same sources | 5% | 6 of 13 | 2 of 9 |
| Kaagaz | 93% | 12 of 13 | 3 of 9 |

Two caveats, both in the README too. The ground truth and the graph come from the same sources, so this measures whether Kaagaz reads them the same way the question writer did. And Kaagaz still listed too many documents in some answers, because the model called `prerequisites` (every document any applicant might need) instead of `plan` (this student's documents). The "first step" score is low because when no step in a chain has a legal time, there is no right order to apply in.

## What went wrong

Most of what I learned came from bugs. Before calling it done, I had a separate review pass go through the whole repo with fresh eyes, looking only for correctness and honesty problems. It found 11. Screenshots caught a few more, and preparing this submission caught the last one.

**The sentence checker could be fooled by the data it checked against.** It accepted any number found anywhere in the tool result. But a plan carries every date on the timeline, so almost any number the model made up was in there somewhere. Now numbers must come from the fact fields (days, margins, counts, the deadline's own date), and a sentence can't turn "on time" into "short" or back. It still isn't perfect. In one trial answer the model wrote "late at least 21 days" when the data said "needs at least 21 working days, 12 short". Every number in it was real, so the checker passed it. That's why the stamp on the main screen always comes from the planner, never from the model.

**Rules that apply to some students were counted for everyone.** A hostel certificate is needed "only if residing in a private or college-run hostel". The first version put it in every student's chain. Now conditional rules stay out until the student presses "This applies to me", and that choice is saved in their graph. Both the Cypher and the planner honour it.

**"Address proof" isn't a document.** The certificate rule says ID and address proof are mandatory but never lists which documents count. I had been calling it "proof of residence" as if it were one thing. It's now named "Address proof (the source does not list which documents count)", and the screen says Kaagaz can't give a time for it.

**A stamp read "AT LEAST 0 DAYS".** That happens when every remaining step has an unknown time. It now says "TIME UNKNOWN".

**The static file route could serve any file on the server.** `/../../README.md` worked. Paths are now resolved and must stay inside the built frontend, with a test for four ways of writing a traversal.

**One change showed up 48 times.** The watcher's first real run raised 48 findings. There were really 8: the portal's sentences back the same requirement for six schemes, and the watcher made one finding per rule. It now raises one finding per sentence, listing every rule that cites it. When most of a page's sentences vanish at once, it also says so, because that usually means the page moved, not that the law changed.

**The demo would have shown closed windows to the judges.** I found this one while preparing the submission. Seven of the 11 scholarships close on 31 October 2026, and judging happens after that. Anyone opening the app in November would see a wall of "window closed". I added a bar that offers "See it as on 18 Oct 2026". It moves only the start date. The rules and deadlines stay real, the bar stays on screen, and plans viewed that way aren't saved to the student's memory.

FalkorDB had a few surprises too. You can't pass the upper bound of a variable-length pattern as a parameter (`*1..$depth`), so I use a fixed bound and filter by depth. Label unions like `(n:Document|AnyOf)` aren't supported. The default query timeout is one second. And `algo.SPpaths` looked perfect for "which option is fastest" until I remembered that an option is ready only when all of its own prerequisites are done. That's the longest chain under each option, not the shortest, so I wrote that query myself.

## What it doesn't do

- It doesn't check eligibility. Category, income limits and marks aren't modelled. You pick the scholarship.
- Most full-depth verdicts are lower bounds, because many steps have no legal time limit.
- Legal limits are maximums. A real office can be faster or slower; Kaagaz plans against the limit.
- It covers 11 Karnataka and central scholarships, plus a second rule pack for starting a company in Karnataka that runs on the same engine with no code changes. Other states need their own rule packs built from their own sources.
- There's no live deployment. It runs locally with one Docker command.
- The watcher compares text, so a page that builds its content with JavaScript can look changed when it isn't. A person decides every finding for that reason.
- The caseworker's decisions are a fixed policy. It doesn't learn from what happened to earlier students.
- The benchmark is small: 29 questions, one model, and ground truth from the same sources as the graph.

## If you're building something like this

Store the proof on the edge. When every requirement carries its source sentence, the UI can show why, the audit can check it, and you can't quietly add a rule you can't back up.

Make "unknown" a real value. A `null` time and an "at least" verdict sometimes tell the student less than they hoped, but every number left on the screen has a source behind it.

Compute the important number twice, and compare the two on every request instead of only in a test. My `fastest_option.cypher` cross-check started out running only in a test; the review moved it into every plan.

Check what the model says against the data, and assume your checker will miss something. Put the decision on the screen from code, and let the model add a sentence.

## Try it

```bash
git clone https://github.com/Atul-Chahar/kaagaz.git && cd kaagaz && docker compose up -d --build
```

Open http://localhost:8000 and press **Load the Example student**. FalkorDB Browser is at http://localhost:3000 if you want to run the queries yourself. No API key is needed; with one, the Ask box takes free-text questions. The [demo video](https://drive.google.com/file/d/1O2tQ376d4i9ojpo3L3ipvYGz6F57Pmp9/view?usp=sharing) walks through it in a few minutes.

## How I built it

I found the problem and worked out the solution, decided how FalkorDB is used in it, set up the CI/CD, and set the rules the project follows: every rule needs a government source and its exact sentence, an unknown time is never guessed, the model never writes Cypher, and nothing is faked. The code was written by AI, with Claude Code (Anthropic). I guided it through the fixes and the ideas that went into the project. The rules I gave it and the log of every decision are in the repo, in `CLAUDE.md` and `docs/process/`.
