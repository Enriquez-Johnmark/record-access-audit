# Spec: Record Access Audit

The single source for spec decisions. The brief is `brief.md`. Status: **complete** (decided 2026-11-11 under the owner's standing approval; `docs/decisions.md`), with 34 acceptance criteria.

## Words

- An **access** is one entry in the record system's access log: a staff member **opened a patient's chart** (a read), or a patient **appeared in a search list** on a staff member's screen (a query). Each is one FHIR `AuditEvent`.
- An access is **accounted for** when the clinic's own data gives the staff member a reason to be in that chart: a **care relationship** (below) or their role's ordinary work.
- A **rule** is one of the clinic's eleven checks on accesses, with a **reason code**, a plain description, a threshold where it needs one, and a **weight**. The rules together are the **rule set**; each change makes a new **rule-set version**.
- A **flag** is one rule firing on one access, under one rule-set version.
- A **case** gathers the flags for one staff member and one patient (or, for high volume, one staff member and one day). It is **open** until the privacy officer **decides** it.
- The **facts** of a case are numbered statements built by code from the log and the clinic's data. The model sees only these.
- A **summary** is Claude's plain-words account of a case's facts. A **check** is a rule in code a summary must pass before a person sees it.

## The made-up clinic

- **Example Valley Clinic**, a made-up US outpatient clinic with an urgent-care wing.
- The tool's users: a **privacy officer** (Alex Example, who works the cases and edits the rules), an **administrator** (loads the log and sees the audit log) and the **patients** (who see their own access report).
- 30 made-up **staff** appear in the log: physicians, nurses, front desk, billing, a lab technician, IT and two security guards, in five departments, each with a shift.
- Every page, file and summary says the clinic, staff and patients are made up.

## Made-up data

- A fixed generator (a seed, so the same every time) writes:
  - 30 staff as `Practitioner` and `PractitionerRole` (role, department);
  - 300 patients as `Patient`, some marked VIP, a few deceased, some of them staff members or staff members' relatives;
  - their `Encounter`s, `Appointment`s and `CareTeam`s;
  - 14 days of accesses as `AuditEvent`s shaped like IHE BALP `PatientRead` (chart opened) and `PatientQuery` (search list), about 4,000 in all.
- Clinic facts with no clean FHIR home stay in one saved file: staff shifts, staff home addresses, which patient record belongs to a staff member, and the VIP list.
- Every FHIR resource is marked as test data (`HTEST`) and tagged with the clinic.
- The log is **labelled** (`evalset/labels.json`): every planted case, by kind (co-worker, relative at the same address, same last name, VIP, own record, a role that never reads charts, deceased patient, a look long after care ended, a burst of charts in a day, a look outside the staff member's shift), and every **innocent look-alike** (a relative treated with a care relationship, a VIP seen by their care team, a VIP in a search list only, a covering nurse with no recorded relationship, a shared last name with an appointment, and others). At least 30 planted cases and 20 look-alikes.
- The data is loaded into a pinned local HAPI FHIR server by a command that accepts only a server on this computer.

## Accounting for accesses

An access is accounted for when, at its time:

- the staff member is on the patient's **care team**; or
- the staff member took part in an **encounter** with the patient that day or the day before or after; or
- the staff member is on an **appointment** with the patient that day; or
- **front desk** staff: the patient has an appointment within 14 days before or after; or
- **billing** staff: the patient had an encounter in the 90 days before.

## The rules

| Code | Fires when | Applies to | Weight |
|---|---|---|---|
| `OWN_RECORD` | a staff member opens their own record | every chart opened | 3 |
| `ROLE_NO_CHARTS` | the staff member's role never reads charts (security, IT) | every chart opened | 3 |
| `NO_RELATIONSHIP` | no care relationship or role's work accounts for it | charts opened, not accounted for | 1 |
| `SAME_LAST_NAME` | the patient shares the staff member's last name | not accounted for | 2 |
| `SAME_ADDRESS` | the patient lives at the staff member's home address | not accounted for | 3 |
| `COWORKER` | the patient is a staff member | not accounted for | 2 |
| `VIP` | the patient is on the VIP list | not accounted for | 2 |
| `DECEASED` | the patient died before the access | not accounted for | 2 |
| `AFTER_CARE_ENDED` | the staff member's last care relationship with the patient ended over 30 days before | not accounted for | 1 |
| `OUTSIDE_SHIFT` | the chart was opened over an hour outside the staff member's shift | not accounted for | 1 |
| `HIGH_VOLUME` | the staff member opened more than 60 charts that day, accounted for or not | every chart opened; one case per staff member and day | 2 |

- Thresholds (30 days, an hour, 60 charts, 14 and 90 days) and weights are settings in the rule set.
- When a staff member opens **their own record**, only `OWN_RECORD` applies (and the chart counts toward `HIGH_VOLUME`); the name, address and co-worker rules would match trivially. `COWORKER` means another staff member's record.
- A **search-list hit never raises a case.** In a case it is shown as "appeared in a search list; chart not opened", never as an opened chart.
- The **queue** is ordered by code: the sum of a case's rule weights, highest first, then the oldest flag first. A model never changes what is flagged or the order.
- **Running** the rules over the log is idempotent: the same log and rule-set version raise no new flags. A new version flags under its own number and never rewrites a past flag. A flag on a pair whose case is already decided opens a new case.
- Only the privacy officer edits the rule set.

## Summaries

- For each case, code builds the **facts**, numbered: pseudonymous IDs (`S-014` for a staff member, `P-203` for a patient), the staff member's role, department and shift, each access (time, chart opened or search list, how long, which sections by category: summary, results, notes, medicines, billing), each rule that fired with its description, and the care-relationship facts found and not found ("no care team, encounter or appointment for this pair in the 90 days before").
- The facts never include a name, address, date of birth, diagnosis, note, result, medicine or other clinical content. The page shows real names to the privacy officer; the model never sees them.
- **Claude Sonnet** writes the summary by default, through the owner's key, as strict JSON:
  - `summary`: up to five sentences, each with the fact numbers it relies on;
  - `to_check`: up to three possible innocent explanations the privacy officer could check, each with its facts.
- Its answers are recorded, so tests, CI and the demo need no key. Without a model, cases are flagged and shown with their facts alone.
- The page labels a summary "AI summary of the listed facts, not a finding".

## Checks on every summary

A summary is **blocked**, with each problem and what was found shown, if:

1. a sentence **cites no fact**, or cites a fact the case doesn't have;
2. a **number, time or ID** in a sentence is not in the facts it cites;
3. it **decides or accuses**: "violated", "violation", "snooped", "snooping", "breach", "unauthorized", "inappropriate", "improper", "illegal", "guilty", "misconduct", "fired", "disciplined" and the like;
4. it uses a **clinical word** (a diagnosis, a medicine, a test result);
5. it is **too long**: over 120 words in all.

A blocked summary is not shown; the case shows its facts and "No summary: it failed a check".

## Decisions

- Only the **privacy officer** decides a case: **appropriate**, **needs follow-up with the staff member**, or **possible breach: risk assessment needed**, with a written reason of at least 10 characters.
- A later decision on the same case is added to its history; nothing replaces or deletes an earlier one.
- The queue shows each open case's **age** in days from its first flag. Open cases are never hidden or closed automatically.
- A **possible breach** case shows a reminder date 60 days after the decision: "Reminder only, not legal advice: HIPAA allows at most 60 days from discovery to notify".
- The tool sends no message to anyone about a case.

## The patient access report

- A patient logs in with an emailed link and sees, for their own record only, each time a chart was opened: the date and time, the staff member's **role and department**, never their name. Search-list hits are not listed.
- The page says the report goes beyond what HIPAA now requires (the 2011 access-report proposal was withdrawn).

## The activity log

- Every step is in an **append-only** log the database refuses to change: log loaded, rules run, rule set changed, case flagged, summary written, summary blocked, case viewed, decision recorded, login.
- Each case has its timeline; the administrator and the privacy officer see the whole log, filtered by person and step.

## How it is measured

| Set | What it holds | Target |
|---|---|---|
| Labelled log | the made-up log with its planted cases and look-alikes | every planted case flagged; look-alikes accounted for are not flagged; precision per rule reported |
| Bad summaries | 30 hand-written summaries, each with one planted fault | every one blocked by the check it was written to trip |
| Claude's summaries | Claude's summary of every case in the demo, recorded | at least 90% pass; every failure listed |
| The log | the demo log | the share of chart opens accounted for, reported |

It never claims to catch real snooping.

## The evidence pack

- A page, built on every push, linking each acceptance criterion to the tests that prove it. CI fails if a finished milestone's criterion has none passing.

## Tooling

- **Python** 3.12 with uv, FastAPI, pydantic for every input and every model answer, psycopg 3 with numbered SQL migrations, httpx for FHIR, and the official Anthropic SDK; ruff (direct clock calls banned), pyright strict and pytest.
- **React**, TypeScript and shadcn for the privacy officer's pages and the patient report, in the clinical look of the other healthcare projects.
- **Postgres 17**, **HAPI FHIR** v8.4.0-1 and **Mailpit** in Docker, locally and in CI; **Playwright**; **GitHub Actions**.

## Acceptance criteria

Each criterion has tests whose names start with its ID, e.g. `test_b3_a_search_list_hit_never_raises_a_case`; the evidence pack links them.

### A. Data and privacy

- **A1** The made-up data is the same every time: 30 staff, 300 patients and the 14-day log, valid FHIR R4, each resource marked as test data, with every planted case and look-alike labelled.
- **A2** A request to the model carries no name, address, date of birth or clinical content: only numbered facts with pseudonymous IDs.
- **A3** CI fails if the repository names a real company outside research documents, or holds FHIR not marked as test data.
- **A4** A patient sees only their own access report, with roles and departments and never a staff name.

### B. Flagging

- **B1** An access accounted for by a care team, an encounter, an appointment or the role's work raises no flag from the rules that apply only to unaccounted accesses.
- **B2** Each rule fires on its planted cases and not on accesses outside its terms; every flag records its reason code and rule-set version.
- **B3** A search-list hit never raises a case, and is shown as a search-list hit, never as an opened chart.
- **B4** Running the rules again raises no new flags; a new rule-set version never rewrites a past flag; a flag after a decision opens a new case.
- **B5** The queue is ordered by rule weight, then age, with no model involved; an open case is never hidden or closed automatically.
- **B6** Only the privacy officer changes the rule set; each change makes a new version with its thresholds and weights.

### C. Summaries

- **C1** The model sees only the case's numbered facts; each summary records the model and the facts it was given.
- **C2** The model's answers are parsed into strict types; an answer that doesn't parse leaves the case with its facts and no summary.
- **C3** With no model, every case is still flagged, ordered and shown with its facts.
- **C4** A summary never changes which cases are flagged or their order.

### D. Checks

- **D1** A summary sentence citing no fact, or a fact the case doesn't have, is blocked.
- **D2** A number, time or ID not in the cited facts is blocked.
- **D3** Deciding or accusing words are blocked.
- **D4** Clinical words are blocked.
- **D5** A summary over 120 words is blocked.
- **D6** Every blocked summary shows which check failed and what it found, and the case shows its facts instead.

### E. Decisions

- **E1** Only the privacy officer can decide a case.
- **E2** A decision is one of the three outcomes with a written reason of at least 10 characters.
- **E3** A later decision adds to the case's history and never replaces an earlier one.
- **E4** Each open case shows its age; a possible-breach case shows its 60-day reminder, labelled as not legal advice.

### G. The activity log

- **G1** Every step is logged with who and when.
- **G2** The log is append-only: the database refuses to change or delete an entry.
- **G3** Each case has its timeline, and the whole log can be filtered by person and step.

### H. Logins and data

- **H1** Staff and patients log in with an emailed link; every staff API needs the right role and every patient API a patient login.
- **H2** The log and the clinic's records are read from the FHIR server through a strict reader; a resource it can't read is refused with the reason, and the others are taken in.
- **H3** The tool never writes to the FHIR server; only the loading command does, and it accepts only a server on this computer.

### I. Measurement

- **I1** Every planted case in the labelled log is flagged; the report gives recall and precision per rule and the share of chart opens accounted for.
- **I2** All 30 bad summaries are blocked, each by the check it was written to trip.
- **I3** At least 90% of Claude's recorded summaries pass, and the report lists every one that didn't.

### J. Evidence

- **J1** The evidence pack links each acceptance criterion to its passing tests; CI fails if a finished milestone's criterion has none.
