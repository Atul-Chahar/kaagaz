# Design review

Each round: Playwright saves every screen at 1440 px and 390 px, light and dark (`e2e/screenshots.spec.ts`), I open
the images and write what is wrong, fix it, and shoot again.

## Round 1 (17 Oct 2026, 32 screenshots)

**Chain, 1440 light (depth 1).** The concept reads in one glance: verdict sentence on the left, green stamp on the right,
the paper slip on a dated working-day axis, deadline as a dashed line. Problems:
- The red tape runs straight through the slip's text, so "Caste and income certificate" is struck through. Looks like a
  deletion, which is the wrong message. Fix: run the tape along the lower edge of each slip.
- The deadline label is clipped at the right edge of the frame ("Deadline 30 Nov 202"). Fix: more room after the span.
- Document names from the sources are long ("Caste and income certificate (Karnataka; Form F, backward classes other
  than Category-1)"). They wrap the "why" chips into a tall box. Fix: a short display name (drop the trailing
  qualifier in brackets); the Why panel still shows the full official name.
- The stamp's ink texture eats too much of the letters in light mode. Fix: lighter noise.
- "Other options" was still loading when the screenshot was taken (timing in the test, not the product). Fix: the
  screenshot waits for it.

**Chain, 1440 dark (late, OBC scheme).** The red stamp "12 DAYS SHORT" and the hatched overrun past 31 Oct work well.
Problem: thin blue lines down both sides of the page. That is the focus ring on `<main>`, which gets focus on route
change for screen readers. Fix: no visible ring on `main`.

**Chain, 390 light (depth 2).** Verdict and stamp stay above the timeline, the timeline scrolls in its own frame.
Problem: the red tape draws a "Z" from the end of the first slip back to the start of the next one, across the label
text. Fix: a curved tie between slips at the lower edge.

**Why panel, 1440 light.** Captured mid fade-in, so it looks transparent and the stamp shows through. The product is
fine once settled; the screenshot now waits 600 ms. Content order (legal time, office, status, toggle, path chips,
each step with quote and source, Cypher, Browser link) is right.

**Start, 1440 light.** Clear three-step layout, the red "CLOSES 31 OCT 2026" tags work. Problem: the scheme list had
a fixed height with its own scroll, which cut an item in half ("Department of Social Justice" half visible). Fix: no
inner scroll; 11 schemes fit.

**About the graph, 1440 light.** The diagram sits in half a column, so its labels are tiny. Fix: full width diagram,
rules and load-bearing tables side by side below it. Also the blue focus lines (same `main` fix).

**Ask, 390 dark.** Found a real routing bug through the screenshot: "Does PM YASASVI Top Class need a hostel
certificate?" picked the sibling affidavit, because "top" and "class" matched both the scheme and that document.
Fix in `agent.py`: words used by the chosen scheme's name no longer count for the document. Regression test added.

**Benchmark, Sources (all sizes).** Honest empty state reads plainly. Sources table scrolls sideways on phones inside
its own frame. No change needed.

## Round 2 (17 Oct 2026, re-shot after the round 1 fixes)

**Chain, 1440 light (depth 2).** Fixed: tape no longer strikes text, short names, no focus lines, other options loaded.
New problems found:
- The axis showed two overlapping sets of dates ("26 Oct" on top of "3 Nov"). I checked the live page with a script:
  18 evenly spaced ticks and one timeline, so the overlap came from the full-page screenshot catching a re-layout.
  Screenshots now use `animations: 'disabled'`; the re-shot image is clean.
- The deadline label was still clipped when the deadline sits near the right edge of the frame. Fix: the label flips
  to the left of the dashed line there.
- The tape's curve between two slips still crossed "21 working days". Fix: the tape runs just under each slip.
- "Other options" listed "AT LEAST 21 DAYS" schemes between "SHORT" ones. Fix: rank can make it, might make it
  (lower bound only), can't tell, short, closed. Also fixed "1 more documents wait" grammar.
- Moving to short names broke the slips' accessible names (axe `label-content-name-mismatch`: the visible text must
  start the name). Fix: the label now starts with the short name and days, and adds the full official name at the end.

**Chain, 390 dark (depth 2).** Found that the page was 422 px wide: the Start-today column grew to fit the long,
unbreakable "Source: nadakacheri.karnataka.gov.in" link. Fix: grid children may shrink and long links wrap. A new
e2e test now checks that no screen is wider than 390 px.

**About the graph, 1440 dark.** The full-width diagram is readable now, with the rules and load-bearing tables side by
side. The load-bearing table shows 11 of 11 for the top documents; that is true (Aadhaar sits in every chain) and is
shown as is.

**Benchmark, 1440 light.** Honest empty states for both sections, no numbers. Matches section 6 of the spec.

**Why panel, 390 dark.** Path chips, quotes with source, retrieval date and an "Official" tag per step, readable in
night mode. Good.
