# Using an LLM with Kaagaz (NVIDIA NIM)

Kaagaz works fully without an LLM. With one, the Ask box understands free-text questions: the model picks one tool
from the fixed catalogue and writes one sentence about the result. The sentence is checked against the tool result
(names, documents, numbers, late or on time). If the check fails, the sentence built from the result is shown instead.
The model never writes Cypher and never sees anything outside the tool result.

## Which model, and why

Chosen: **`openai/gpt-oss-20b`** on NVIDIA NIM (`https://integrate.api.nvidia.com/v1`).

How it was chosen: `bench/model_trial.py` runs Kaagaz's own two LLM jobs through the exact code path the app uses,
on 6 questions (explain, prerequisites, plan, "I just got this certificate", recall). A question passes routing only
if the model picks the expected tool with the expected ids. A sentence passes only if `check_sentence` accepts it.
Raw answers and timings are in `bench/results/model-trial-*.json`.

Run on 17 Oct 2026 (`bench/results/model-trial-20261017T161913Z.json`), after giving the model the id list and room
for reasoning tokens:

| Model | Right tool and ids | Sentence passed check | Median routing time | Median sentence time |
|---|---|---|---|---|
| `openai/gpt-oss-20b` | 5 of 6 | 5 of 6 | 3.6 s | 8.1 s |
| `nvidia/nemotron-3-super-120b-a12b` | 4 of 6 | 3 of 6 | 3.7 s | 12.8 s |

Results from the earlier run of 12 models on the same key (`model-trial-20261017T154334Z.json`):
- 5 returned HTTP 404 ("Function not found for account"), so they are listed but cannot be used on this key:
  `nemotron-nano-3-30b-a3b`, `kimi-k2.6`, `mistral-large-2-instruct`, `mistral-nemo-12b-instruct`,
  `llama-3.1-nemotron-70b-instruct`.
- 3 timed out on every call: `glm-5.3-flash`, `deepseek-v4.1-flash`, `gemma-4-31b-it`.
- 2 were too slow or did not call a tool: `nemotron-3.5-lightning-30b-a3b` (route median 144 s),
  `step-5-preview` (8 s, and 2 of 6 with no tool call).

Honest limits:
- 6 questions is a small trial. It is enough to rule models out, not to rank close ones.
- The one routing miss for gpt-oss-20b called `prerequisites` instead of `explain`. The answer was still correct.
- The checker misses some wrong sentences. In one recall answer the model wrote "late at least 21 days" when the
  data said it needs at least 21 working days and is 12 short. Every number in that sentence was a real fact, so the
  checker passed it. The verdict stamp on the Chain screen always comes from the planner, never from the model.
- The free NIM endpoint is shared. Speed depends on load: at 10 PM IST on 17 Oct 2026 even a one-line request to
  gpt-oss-20b timed out after 60 s. When the model call fails, Ask falls back to name search and says so in the trace.

## Setup

1. Get a key at https://build.nvidia.com (it starts with `nvapi-`).
2. In the repo root, copy `.env.example` to `.env` (`.env` is in `.gitignore`; never put a key in `.env.example`):

   ```
   LLM_PROVIDER=openai
   LLM_BASE_URL=https://integrate.api.nvidia.com/v1
   LLM_API_KEY=nvapi-...
   LLM_MODEL=openai/gpt-oss-20b
   # optional, for reasoning models: low | medium | high (empty = server default)
   LLM_REASONING_EFFORT=
   ```

   `chmod 600 .env` keeps other users on the machine from reading it.
3. Start Kaagaz either way. Both read `.env` by themselves:
   - Local: `docker compose up -d falkordb`, then `make dev` (API and built UI on http://localhost:8000).
   - Docker: `docker compose up -d --build` (compose passes the `LLM_*` variables into the app container).
4. Check it is on: open the Ask screen. The answer card shows how the question was routed: by the model, or by name
   search. The trace below it lists the tool, its arguments and every query.

## Daily use

- **Ask**: type a question such as "Does PM YASASVI Top Class need a hostel certificate?" or "I just received my
  caste and income certificate today." The model picks one tool. You see the tool, its arguments, the outcome, the
  sentence (marked as checked, or replaced if the check failed) and the trace.
- **Everything else** (Start, Chain, Why panel, Benchmark, Sources) does not use the model at all.
- **No key, or the model is down**: Ask becomes a name search over the graph. Nothing else changes.

## Switching models

Change `LLM_MODEL` in `.env` and restart the API (or `docker compose up -d` again). Any OpenAI-compatible model that
supports tool calls with `tool_choice: "required"` works. Before switching, try it on the same 6 questions:

```bash
cd backend && uv run python ../bench/model_trial.py openai/gpt-oss-20b some/other-model
```

It prints one line per model and writes `bench/results/model-trial-<time>.json` (no key is written). See which models
your key can use:

```bash
curl -s https://integrate.api.nvidia.com/v1/models -H "Authorization: Bearer $LLM_API_KEY" | python3 -m json.tool
```

A model can be listed and still return 404 for your account; the trial shows that.

## The benchmark

`make bench` runs 29 questions through three systems with the same model (model alone, plain RAG over the same
sources, Kaagaz) and writes `bench/results/<time>.json` with the model name, date, raw answers and the number of
failed calls. It asks 8 questions at the same time (`--workers`), so a full run takes a few minutes on the free tier
(2 min 39 s on 17 Oct 2026). A failed call counts as a wrong answer, never as skipped. The Benchmark page reads the
newest file. Commit the results file so the numbers in the README can be checked.

Latest run (`bench/results/20261017T171028Z.json`): Kaagaz 93% document recall and 92% verdict accuracy, against 9%
and 38% for the model alone and 5% and 46% for plain RAG. Full table and caveats in the README.

## Operating notes

- **Queue and rate limits**: the free NIM tier puts every request in a queue shared by all users and allows about
  40 requests a minute per key. Big models have the longest queues, which is one more reason to use a small one like
  gpt-oss-20b. Waiting longer does not help much; sending calls in parallel does (that is what the benchmark does).
  Kaagaz retries 429 and 5xx twice with a short wait, then falls back to name search. One Ask is two model calls.
- **Timeouts**: set `LLM_TIMEOUT_S` (default 90) to fail faster. Each model call waits up to that long and is tried up to 3 times, so on a stuck endpoint one Ask can take
  minutes before it falls back to name search (the trial uses 60 s). On a busy endpoint, try again later
  or pick a model that answered faster in the trial.
- **Rotating the key**: create a new key on build.nvidia.com, replace `LLM_API_KEY` in `.env`, restart, then revoke
  the old key. If a key was ever pasted into a tracked file or a chat, revoke it.
- **Turning it off**: empty `LLM_PROVIDER` (or `LLM_MODEL`) and restart. `scripts/verify.sh` and the end-to-end tests
  always run with the LLM off, so they never need a key.
- **Privacy**: the model receives the question, the student id, the scheme and document id list and the trimmed
  tool result. NVIDIA says inputs and outputs on the free hosted tier are logged and may be used for training. The
  Example student is synthetic. Do not type real personal details into Ask when a hosted model is on.
