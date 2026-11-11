# Brief: Record Access Audit

Status: **approved** (2026-11-11, Round 1, under the owner's standing approval of every recommendation; `docs/decisions.md`). The spec (`spec.md`) is decided from it. "Record Access Audit" is a working name.

## In one sentence

A tool for a clinic's privacy officer: code reads the record system's access log, sets aside every access the clinic's own data explains, and flags what is left when one of the clinic's rules fires; Claude explains each flagged case in plain words from numbered facts; code checks the explanation; the privacy officer decides, with a written reason. Every step is in an append-only audit log.

## Why it exists

A portfolio project for AI roles in health software, and the last of four healthcare projects, after [Lab Report Assistant](https://github.com/Enriquez-Johnmark/lab-report-assistant), [Care Reminders](https://github.com/Enriquez-Johnmark/care-reminders) and [Care Message Assistant](https://github.com/Enriquez-Johnmark/care-message-assistant). It shows what matters when AI helps judge people's conduct: code decides what is flagged, the model only explains facts it was given and can't accuse anyone, and a person decides, on the record.

## The problem

Staff look at records they have no reason to see: co-workers', relatives', neighbours', celebrities' (`docs/research/README.md` §1).

- The logs are far too big to read: a large academic centre records 4.5–7.5 million accesses a week, and privacy teams are one to three people. Reviewing one event by hand takes about 10 minutes.
- OCR settlements keep citing the same failure: not regularly reviewing system activity. Examples run from $240,000 (23 security guards viewing 419 patients' records, 2023) to $5.5 million.
- The opposite failure is real too: staff at one hospital said they were fired when a famous patient's name only appeared in a search list on their screen.
- Simple rules raise many false alarms (in one study a first-name control rule flagged more accesses than the last-name rule), and the clinic's own data (appointments, visits, care teams) explains a large share of flagged accesses (§3).

The useful product is not "AI catches snoopers". It is: the clinic's rules, open and versioned, flag cases in code; the evidence is shown precisely enough to tell a search-list hit from an opened chart; the model writes a checked explanation of the facts; and the privacy officer's decision and reason are kept for good.

## Who uses it

- **The privacy officer** works the queue of flagged cases, reads the facts and Claude's explanation, records a decision with a reason, and edits the clinic's rules.
- **A clinic administrator** loads the access log and sees the audit log.
- **A patient** sees which roles and departments in the clinic looked at their record, and when (no staff names).

(In the portfolio, all of them are shown in a demo of a made-up US clinic.)

## What it does (first version)

1. **Reads the access log** of one made-up clinic (about 30 staff, 300 patients, 2–4 weeks) as FHIR R4 `AuditEvent`s shaped like IHE BALP `PatientRead` and `PatientQuery`, with `Practitioner`, `PractitionerRole`, `Patient`, `Encounter`, `Appointment` and `CareTeam`, from a pinned local HAPI FHIR server. HAPI is read-only to the tool.
2. **Explains first, in code:** an access is set aside when the clinic's own data gives a reason (the staff member is on the patient's care team, or had an encounter or appointment with the patient that day, or wrote an order or note).
3. **Flags what is left** when one of eleven rules fires: same last name, same home address, co-worker as patient, VIP patient, own record, high daily volume, no care relationship, outside shift, deceased patient, long after discharge, and a role that should not read charts. Each rule has a reason code, a plain description and a configurable threshold. A name match raises a case only together with "no care relationship". A model never decides what is flagged or its order.
4. **Versions the rules:** the privacy officer edits them as versioned settings; every flag records the version that raised it, and a change never rewrites past flags.
5. **Explains each case** with Claude, from numbered facts built by code: pseudonymous staff and patient IDs, role, department, access times and actions (search list or chart opened, how long, section categories), the rule reasons, and the care-relationship facts found and not found. Never a name, address, date of birth, diagnosis, note, result or medicine.
6. **Checks every explanation in code:** each sentence cites fact numbers; every number, time and ID in it appears in the cited facts; no deciding or accusing words ("violated", "snooped", "breach", "unauthorized", "inappropriate", "guilty", "fired" and the like); no clinical words; a length limit. A failed check shows the facts with "no explanation".
7. **Lets the privacy officer decide:** a case closes only by their decision, **appropriate**, **needs follow-up with the staff member** or **possible breach: risk assessment needed**, each with a required written reason. A later decision adds to the history and never replaces it.
8. **Keeps cases in view:** the queue shows each open case's age; open cases are never hidden or dismissed automatically; a "possible breach" case shows a 60-day reminder date, labelled as a reminder, not legal advice.
9. **Shows a patient access report** of roles, departments and times (no staff names), as a demonstration of the withdrawn HITECH access report, marked as beyond what HIPAA now requires.
10. **Logs every step** in an append-only audit log the database refuses to change.
11. **Measures itself** on a labelled made-up log with planted cases of each kind and innocent look-alikes: recall and precision per rule, the share of accesses explained away, and the explanation check pass rate. It never claims to catch real snooping.
12. **Produces an evidence pack** linking each acceptance criterion to the test that proves it.

## What it must never do

- Let a model decide which accesses are flagged, their order, or a case's outcome.
- Close a case, or name anyone as having done wrong, without the privacy officer's decision and written reason.
- Message the staff member, HR, the patient or a regulator by itself.
- Show a search-list hit as if the chart had been opened.
- Send the model a name, address, date of birth or any clinical content.
- Use real staff or patient data, or a real company's name or branding.
- Claim to be "HIPAA compliant" or certified. The README says that any real use needs a model provider that signs a business associate agreement.

## How success is shown

- **Every planted case flagged** on the labelled log, with the innocent look-alikes counted as false alarms and reported per rule.
- **The share of accesses explained away** by the clinic's own data, reported.
- **The explanation checks, measured** on explanations with planted faults (an accusing word, a number not in the facts, a sentence citing no fact): every one blocked; and Claude's recorded explanations put through the same checks, with the pass rate and cost reported.
- **Safety tests that always pass:** no case closes without a decision and reason, the model never sees a name or clinical content, and the log can't be changed.
- **The evidence pack**, published with each commit; a README with screenshots and a walkthrough video, and a page on the owner's portfolio.

## Technology (proposed)

**Python** (decided 2026-11-10) with FastAPI, pydantic and Postgres 17; **React** pages in the clinical look of the other healthcare projects; **Claude** through the owner's API key (`OWNER_ANTHROPIC_API_KEY`), Sonnet by default, with recorded answers so tests and CI need no key; FHIR R4 from a pinned local **HAPI FHIR** server, filled by our own generator (no public data set has access logs); pytest and Playwright; GitHub Actions. The details are decided in the spec and the architecture.

## Not in the first version

Machine-learning detection, automatic messages to staff, HR, patients or regulators, a breach risk-assessment workflow, real record-system connectors (Epic, syslog/ATNA), several clinics, and an employee self-audit page.
