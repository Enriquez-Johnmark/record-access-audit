# Record Access Audit

Helps a clinic's privacy officer find and review inappropriate looks at patients' records. Code reads the record system's access log, sets aside every look the clinic's own data explains, and flags what is left when one of the clinic's rules fires. Claude explains each flagged case in plain words from numbered facts, code checks the explanation, and the privacy officer decides, with a written reason. Every step is in an append-only audit log.

**Status:** built to M5 (data and FHIR; flagging; summaries; decisions and pages; the patient report and measurement), with all 34 acceptance criteria proven ([the evidence page](docs/evidence/m5.html)); the showcase (M6) is next. See [`AGENTS.md`](AGENTS.md) for the phases and [`docs/architecture.md`](docs/architecture.md) for the build order.

The fourth of four healthcare projects, after [Lab Report Assistant](https://github.com/Enriquez-Johnmark/lab-report-assistant), [Care Reminders](https://github.com/Enriquez-Johnmark/care-reminders) and [Care Message Assistant](https://github.com/Enriquez-Johnmark/care-message-assistant). Made-up clinic, made-up staff and patients: this repository contains no real patient data and names no real company outside its research notes.

## Why

Staff look at records they have no reason to see: co-workers', relatives', neighbours', celebrities'. A large health system logs millions of accesses a week, privacy teams are one to three people, and OCR settlements keep citing the same failure: not regularly reviewing system activity. The opposite failure matters as much: staff have said they were fired when a famous patient's name only appeared in a search list on their screen. Simple rules raise many false alarms, and the clinic's own care data explains much of what they flag. (Sources: [`docs/research/README.md`](docs/research/README.md).) So this project is about the parts that keep the review fair and checkable, each enforced in code and tested.

## What it does

- **The access log, from FHIR (`a1`, `h2`, `h3`):** a seeded generator writes a made-up clinic (30 staff, 300 patients, their care teams, visits and appointments) and 14 days of accesses as FHIR R4 `AuditEvent`s shaped like IHE BALP `PatientRead` (a chart opened) and `PatientQuery` (a search list), loaded into a local HAPI FHIR server. A strict reader refuses what it can't read, with the reason; the tool's FHIR client only ever reads.
- **Explain first, in code (`b1`):** a look is set aside when the clinic's data gives a reason: the staff member is on the patient's care team, took part in a visit that day or the day before or after, has an appointment with them that day, or it is the front desk's or billing's ordinary work.
- **Eleven rules flag what is left (`b2`–`b5`):** own record, a role that never reads charts, no care relationship, same last name, same home address, a co-worker's record, VIP, a patient who had died, care that ended long before, outside the shift, and many charts in a day. Each has a weight; the queue is ordered by weight, then age, in code. **A search-list hit never raises a case** and is shown apart from an opened chart. Rules are versioned: a change never rewrites a past flag (`b6`).
- **Numbered facts, and nothing else, for the model (`a2`, `c1`):** pseudonymous IDs (S-009, P-286), roles, departments, shifts, times, actions, the rules that fired, and what the clinic's data does and doesn't show. Never a name, address, date of birth or clinical content.
- **Five checks on every summary (`d1`–`d6`):** each sentence cites the facts it rests on; every number, time and ID comes from them; nothing decides or accuses ("snooped", "unauthorized", "no legitimate reason"…); nothing clinical; at most 120 words. A blocked summary isn't shown; the case shows its facts and why. Without a model, every case is still flagged and shown with its facts (`c3`); a summary never changes what is flagged or the order (`c4`).
- **The privacy officer decides (`e1`–`e4`):** appropriate, needs follow-up with the staff member, or possible breach (risk assessment needed), always with a written reason. A later decision adds to the history. A possible breach shows a 60-day reminder, labelled as not legal advice. The tool sends no message to anyone.
- **The activity log (`g1`–`g3`):** every step, with who and when, in a log the database refuses to change. Each case has its timeline; opening a case is itself logged.
- **Logins by emailed link (`h1`):** a link works once and for 15 minutes, used only by its page's button so a mail scanner can't use it up; every staff route checks the role.
- **The patient access report (`a4`):** a patient logs in and sees each time their chart was opened, by the staff member's role and department, never their name. This goes beyond what HIPAA now requires (a 2011 proposal for such a report was withdrawn).

## How it measures up

On the made-up log with 31 planted cases and 21 innocent look-alikes ([`evalset/report.md`](evalset/report.md)):

| Measure | Result |
|---|---|
| Planted cases flagged with every rule they were planted for | 31 of 31 |
| Innocent look-alikes flagged anyway | 3 of 21, each a nurse covering a visit the record doesn't show |
| Charts opened that the clinic's own data accounts for | 98% |
| Hand-written bad summaries blocked by the check they were written to trip | 30 of 30 |
| Claude's summaries passing every check | 32 of 34 (94%) |

The log was built to test the tool, so 31 of 31 says the rules do what they were written to do, not that they would catch real snooping. Claude's summaries first passed 29 of 34; three false alarms (a summary naming its own case's patient) were fixed with a test. The two still blocked are listed in the report.

## Try it

```bash
docker compose --profile fhir up -d          # Postgres, Mailpit (http://localhost:8025) and HAPI FHIR (port 8090)
cp .env.example .env
uv sync && pnpm --dir web install && pnpm --dir web build
uv run record-access-audit migrate
uv run record-access-audit add-user --email privacy@clinic.example.test --name "Alex Example" --role "privacy officer"
uv run record-access-audit add-user --email admin@clinic.example.test --name "Example Administrator" --role administrator
uv run record-access-audit load-made-up      # only a FHIR server on this computer is accepted
uv run record-access-audit serve --recorded  # http://127.0.0.1:8000, summarising from the recordings: no key, no cost
```

Log in as the administrator and press "Read the log and run the rules". Then log in as the privacy officer to work the cases: login emails arrive in Mailpit. To see a patient's report, log in with a made-up patient's address, such as `aaron.quintero.p289@example.test`. `uv run pytest` runs the tests (Postgres and HAPI FHIR must be running); `uv run record-access-audit measure` rebuilds the report from the recordings.

Any real use would need a model provider that signs a business associate agreement. The README makes no compliance claim; it says what the code enforces and how it is tested.

## Licence

All rights reserved ([LICENSE](LICENSE)). The source is published to be read, not reused.
