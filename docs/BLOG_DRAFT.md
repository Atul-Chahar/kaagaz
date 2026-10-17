# DRAFT, for Atul to edit before posting

# I built a tool that tells students they are already too late

Every year I watch the same thing happen. A student finds a scholarship, checks that they are eligible, and starts the
application a week before it closes. Then the portal asks for a caste and income certificate. The taluk office has 21
working days by law to issue it. The deadline is in 9. Nobody told them, because every scheme finder stops at
"you are eligible".

That gap is what I built Kaagaz for, for Graph Hacks by WeMakeDevs and FalkorDB.

## The idea

A scholarship is not a checklist. It is a chain. The scholarship needs a certificate, the certificate needs a proof
of residence, the bank account needs an identity document, and so on. Each step is a different office with a
different legal time limit. If you draw it, it is a graph. So I put it in a graph.

Kaagaz takes the scholarship you picked and the documents you already have, walks every chain in FalkorDB, adds up
the legal working days on the longest one, and puts a rubber stamp on the screen: "on time, 9 days spare", or
"12 days short".

## Why a graph database

The hard question is "what do I need, including the things I need to get those things?". In Cypher that is one
variable-length pattern, `-[:REQUIRES|OPTION*1..16]->`, with the depth as a filter. I added a stepper in the UI that
shows depth 1, then 2, then 3. At depth 1 the Example student looks fine. At depth 2 a step with no legal time limit
appears and the green stamp turns into a blue "at least 21 days". That moment is the whole product.

Each student also gets their own graph. A query runs on one graph, so one student's documents can never show up in
another student's query. I liked that the isolation comes from the database, not from a WHERE clause I could forget.

A few things I learned about FalkorDB on the way: you cannot pass the upper bound of a variable-length pattern as a
parameter, label unions like `(n:A|B)` are not supported, and the default query timeout is one second. All easy to
work around once you know.

## Being honest with the data

This was the part I cared about most. Every rule in the graph stores the URL, the title, the date I saved it, and the
exact sentence (25 words or fewer) that proves it. A script fails the build if any sentence is not in the saved page.

Many steps have no official time limit. Kaagaz does not guess them. It says "at least 21 days" instead of a confident
number. The Karnataka Sakala limits turned out to be working days, so I had to add the official 2026 holiday list and
the second-and-fourth-Saturday rule before any verdict made sense.

The benchmark is honest too. A separate pass wrote 29 questions from the sources alone. The planner agreed on 12 of 13
deadline questions but only 3 of 9 "what first" questions, mostly because when no step has a legal time limit there is
no right order. I left those numbers as they are. With an NVIDIA NIM key and the small `gpt-oss-20b` model, the
"LLM alone vs RAG vs Kaagaz" run gave document recall of 9%, 5% and 93%, and verdict accuracy of 38%, 46% and 92%.
Kaagaz still listed too many documents when the model asked for a scheme's general rules instead of the student's
plan. That number is in the table too.

## What is next

A second rule pack (starting a company, or a student visa) to show the engine does not know anything about India; a
way for students to say their category so conditional rules can be switched off; and a live deployment.

## AI disclosure

I built Kaagaz with Claude Code (Anthropic). I designed the idea, reviewed the code and verified the results.
