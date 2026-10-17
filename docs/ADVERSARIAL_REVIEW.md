# Adversarial review (17 Oct 2026)

A subagent with a fresh context reviewed the whole repo against KAAGAZ_SPEC.md, looking only for problems with
correctness, honesty or the hackathon requirements. Every finding and what was done:

| # | Finding | Severity | Done |
|---|---|---|---|
| 1 | The static file route served any file on disk (`/../../README.md`, `/etc/hostname`) | high | Fixed: paths are resolved and must stay inside `frontend/dist`; regression test with four traversal forms |
| 2 | The LLM sentence checker accepted any number found anywhere in the result (the plan carries every calendar date), and missed short document names | high | Fixed: numbers must come from fact fields (days, margins, counts, the deadline's own date); short names and "... certificate/card" phrases must be in the result; a sentence must not turn "on time" into "short" or back. Tests on a real plan payload |
| 3 | Rules marked "only if" were treated as always required | medium | Fixed: conditional rules count only when the student says "This applies to me" (saved in their graph); conditions true for everyone a pack models are pack assumptions; Cypher (`chain_days`, `fastest_option`) and planner both honour it; tests |
| 4 | CSSS listed as open though its 2026-27 window is for renewals only, while the modelled rules are for fresh applicants | medium | Fixed: window marked renewals-only; a fresh plan shows "no fresh-application window" and the UI labels it everywhere |
| 5 | The demo's depth-2 change rests on "proof of residence", a category with no options | medium | Fixed honestly: renamed "Address proof (the source does not list which documents count)" (same for ID proof); the demo script and UI say the source gives no list and no time; "Start today" says "apply for or gather" |
| 6 | `fastest_option.cypher` was only run in a test | medium | Fixed: every plan runs it for each open "any one of" group as a cross-check; shown under "How this was computed"; integration test requires agreement |
| 7 | Some excerpts did not prove their claim (ration card days, Aadhaar proof lists, SSP account) and GST 7 days is a best case | low-medium | Fixed: replaced with sentences that state the fact (all re-checked by the audit); SSP account edge carries a note on how the page shows the order; GST note states the Aadhaar-authentication assumption and the 30-day case |
| 8 | Depth 1 shows a green verdict while steps are hidden; "Other options" hides the missing 2027 holiday list | low | Fixed: the verdict sentence says steps are hidden; options past the holiday list say spare days may be fewer |
| 9 | Ask tie-break picked "caste and income" for "income certificate"; unknown-name message said no query ran; explain said "days" not "working days" | low | Fixed and tested |
| 10 | Critical path could run through a held document | low | Fixed in the planner, with a test. Alphabetical choice among options with no times is now stated as a limitation |
| 11 | README said 51 sources (60), one secondary source (two), `<this repo>` placeholder, tracking parameter in a UIDAI URL, bad student id gave a 500, shared Example graph, no licence | low | Fixed: README corrected; UIDAI source re-saved from the clean URL; 422 for bad ids; each visitor gets a private Example copy; MIT licence added |

While checking the fixes, the screenshots found two more issues, also fixed: the default Start page used the company
pack's wording (now the API flags the default pack, with an e2e check), and a stamp could read "AT LEAST 0 DAYS"
(now "TIME UNKNOWN").
