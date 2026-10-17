# Phase 1: data feasibility

Date: 17 Oct 2026. Decision: **PASS. Build Kaagaz on the Indian scholarship pack** (no switch to the company pack).

## What was collected

11 schemes with a published 2026-27 application window (none needed the "last published window" fallback):

| Scheme | Portal | Window ends |
|---|---|---|
| PM-USP Central Sector Scheme of Scholarship (CSSS, renewals) | NSP | 31 Oct 2026 |
| PM YASASVI Top Class Education in College (OBC/EBC/DNT) | NSP | 31 Oct 2026 |
| Central Sector Scholarship of Top Class Education for SC Students | NSP | 31 Oct 2026 |
| AICTE Pragati for Girl Students (degree) | NSP | 31 Oct 2026 |
| PostMatric for OBC Students (BCWD) | SSP Karnataka | 31 Oct 2026 |
| Vidyasiri food and accommodation (BCWD) | SSP Karnataka | 31 Oct 2026 |
| BCWD fee concession | SSP Karnataka | 31 Oct 2026 |
| Fee Reimbursement for Minorities | SSP Karnataka | 30 Nov 2026 |
| Vidyasiri for Minorities | SSP Karnataka | 30 Nov 2026 |
| Postmatric Scholarship for ST Students | SSP Karnataka | 31 Dec 2026 |
| SC Post Matric Scholarship | SSP Karnataka | 31 Jan 2027 |

The pack has 41 documents, 10 "any one of" groups, 13 offices and 143 requirement rules. Every rule quotes a sentence
(25 words or fewer) from a saved source; `scripts/audit_data.py` checks each quote against the saved text.

## Legal processing times found (Karnataka Sakala compendium, 05-05-2026, working days)

- Birth certificate (Karnataka, urban local body registrar; event already registered): 7 working days
- Caste certificate (Karnataka; Category-A, SC/ST, OBC-Central): 21 working days
- Caste and income certificate (Karnataka; Form F, backward classes other than Category-1): 21 working days
- Income certificate (Karnataka): 21 working days
- Ration card (Karnataka; new / BPL): 7 working days
- Residence certificate (Karnataka): 14 working days

No official time limit was found for: Aadhaar (UIDAI states only a "normally up to 180 days" service level, kept as
information, not summed), bank account opening, Aadhaar seeding, PAN, NSP One Time Registration, SSP registration,
college papers. These stay `null`; any verdict that depends on them is shown as a lower bound.

The Karnataka 2026 holiday list (DPAR notification, 17.11.2025) and the rule that Sundays and second and fourth
Saturdays are holidays are also sourced, so working days left can be counted. The 2027 list is not out yet.

## Deepest chain (6 REQUIRES levels, 10 nodes)

SSP scheme > Aadhaar-seeded bank account > bank account > PAN or Form 60 > PAN card > Aadhaar > one proof of identity >
Karnataka caste certificate > one of ration card or voter card > ration card.

A shorter one that every SSP scheme shares: scheme > caste and income certificate (21 working days) > proof of residence.
An NSP one: scheme > One Time Registration > Aadhaar face authentication > Aadhaar.

## Longest critical path against a real deadline

Today (17 Oct 2026) there are **9 working days** left before 31 Oct 2026 (Sundays, the 4th Saturday and the
Mahanavami and Vijayadasami holidays removed). A student who does not yet hold the Karnataka caste and income
certificate needs **21 working days** for it alone. That makes five real schemes closing 31 Oct 2026 at least
**12 working days short**: PostMatric for OBC, Vidyasiri (BCWD), BCWD fee concession, Pragati and Top Class SC
(the last two through the income certificate).

Both pass conditions hold: chains are 3 or more levels deep, and the critical path is longer than the time left.

## Honest limits of the data

- Many leaf documents (proof of residence, proof of identity, college papers) have no official time limit, so most
  full-depth verdicts are lower bounds ("at least 21 working days").
- The detailed Karnataka list of accepted proofs for Nadakacheri certificates exists only as scanned Kannada images,
  so the requirement lists come from Tumakuru district NIC pages (official, but district-level).
- One source is secondary: an SSP e-attestation FAQ hosted by Mangalore University (the SSP PDFs need a browser session).
- The 74 MB Sakala compendium and the holiday list PDF are over 5 MB, so only their hash and extracted text are in git.
- Eligibility (caste, income limits, marks) is not modelled; Kaagaz plans documents and time only.

## Sources cited by the pack

| id | title | url | retrieved | kind |
|---|---|---|---|---|
| `aicte-aadhaar-seeding-steps` | Steps to activate the inactive Aadhaar by the beneficiary students of SSSJKL (AICTE) | https://aicte.gov.in/sites/default/files/STEPS%20TO%20ACTIVATE%20THE%20INACTIVE%20AADHAAR%20BY%20THE%20BENEFICIARY%20STUDENTS%20OF%20SSSJKL.pdf | 2026-10-17 | official |
| `ajsk-faqs` | AJSK FAQs | https://nadakacheri.karnataka.gov.in/AJSK/Assets/Documents/AJSKFAQs.pdf | 2026-10-17 | official |
| `bcwd-ka-postmatric-2026-27` | 2026-27 Post Matric Scholarship - Backward Classes Welfare Department | https://bcwd.karnataka.gov.in/163/2026-27-post-matric-scholarship/en | 2026-10-17 | official |
| `dpar-ka-holidays-2026` | Government of Karnataka Notification No. DPAR 16 HHL 2025 dated 17.11.2025: General Holidays and Restricted Holidays for 2026 (file name HOLIDAYSLIST2024.pdf) | https://ceg.karnataka.gov.in/frontend/opt1/pdfs/HOLIDAYSLIST2024.pdf | 2026-10-17 | official |
| `itd-instant-epan-help` | Instant e-PAN - Income Tax e-Filing portal help | https://www.incometax.gov.in/iec/foportal/help/all-topics/e-filing-services/instant-e-pan | 2026-10-17 | official |
| `nsp-aicte-pragati-degree-faq` | AICTE Pragati Scholarship Scheme for Girl Students (Technical Degree) - FAQ | https://scholarships.gov.in/public/schemeGuidelines/AICTE/AICTE_2010_F.pdf | 2026-10-17 | official |
| `nsp-aicte-pragati-degree-guidelines` | AICTE Pragati Scholarship Scheme for Girl Students (Technical Degree) - Guidelines | https://scholarships.gov.in/public/schemeGuidelines/AICTE/AICTE_2010_G.pdf | 2026-10-17 | official |
| `nsp-all-scholarships` | Schemes on NSP - All Scholarships | https://scholarships.gov.in/All-Scholarships | 2026-10-17 | official |
| `nsp-csss-faq` | FAQ - Central Sector Scheme of Scholarships (Department of Higher Education) | https://scholarships.gov.in/public/schemeGuidelines/FAQ_DOHE_CSSS.pdf | 2026-10-17 | official |
| `nsp-csss-guidelines` | Central Sector Scheme of Scholarships for College and University Students - Guidelines (updated 07.02.2024) | https://scholarships.gov.in/public/schemeGuidelines/CSSS_GUIDLINES_07022024_updated.pdf | 2026-10-17 | official |
| `nsp-home` | National Scholarship Portal home | https://scholarships.gov.in/ | 2026-10-17 | official |
| `nsp-otr-faq` | NSP One Time Registration (OTR) FAQ v1.4 | https://scholarships.gov.in/public/FAQ/OTR%20FAQ%20v1.4.pdf | 2026-10-17 | official |
| `nsp-topclass-sc-faq` | Top Class Education Scheme for SC Students - FAQ | https://scholarships.gov.in/public/schemeGuidelines/Top_Class_Education_Scheme_2018_FAQ.pdf | 2026-10-17 | official |
| `nsp-yasasvi-topclass-college-guidelines` | PM YASASVI Top Class Education in College for OBC, EBC and DNT Students - Guidelines | https://scholarships.gov.in/public/schemeGuidelines/ApprovedmodifieddraftofTopClassCollege.pdf | 2026-10-17 | official |
| `rbi-kyc-md` | RBI Master Direction - Know Your Customer (KYC) Direction, 2016 (updated) | https://www.rbi.org.in/Scripts/BS_ViewMasDirections.aspx?id=11566 | 2026-10-17 | official |
| `sakala-compendium-en` | Sakala Service Compendium (English), 05-05-2026 | https://sakala.kar.nic.in/Service%20Compendium/05-05-2026%20sakala_service_compendium_English%20(Final).pdf | 2026-10-17 | official |
| `ssp-e-attestation-faq-v3` | FAQ for Post Matric E-Attestation Application v3 (SSP Karnataka) | https://www.mangaloreuniversity.ac.in/sites/default/files/2019/FAQ-for-Post-Matric-E-Attestation-Application_v3.pdf | 2026-10-17 | secondary |
| `ssp-ka-archives` | Archives - State Scholarship Portal Karnataka | https://ssp.karnataka.gov.in/Archives | 2026-10-17 | official |
| `ssp-ka-home` | State Scholarship Portal Karnataka | https://ssp.karnataka.gov.in/ | 2026-10-17 | official |
| `tumkur-caste-cert` | Caste Certificate | District Tumakuru | https://tumkur.nic.in/en/service/caste-certificate/ | 2026-10-17 | official |
| `tumkur-income-cert` | Apply For Income Certificate | District Tumakuru | https://tumkur.nic.in/en/service/apply-for-income-certificate/ | 2026-10-17 | official |
| `tumkur-residence-cert` | Residence Certificate | District Tumakuru | https://tumkur.nic.in/en/service/residence-certificate/ | 2026-10-17 | official |
| `uidai-faq-enrolling-children-wb` | UIDAI FAQs: Enrolling Children (uidai.gov.in, Wayback Machine snapshot 2026-01-09) | https://web.archive.org/web/20260109213046id_/https://uidai.gov.in/en/contact-support/have-any-question/299-english-uk/faqs/enrolment-update/enrolling-children.html?utm_source=chatgpt.com | 2026-10-17 | official |
| `uidai-supporting-docs-goa` | List of Supporting Documents for Aadhaar Enrolment and Update (UIDAI), hosted by DPSE Goa | https://www.dpse.goa.gov.in/list-of-Supporting-Document-for-Aadhaar-Enrolment-and-Update.pdf | 2026-10-17 | official |