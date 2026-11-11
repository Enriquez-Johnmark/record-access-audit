# Architecture

Status: **decided 2026-11-11** under the owner's standing approval (`docs/decisions.md`). The spec is [product/spec.md](product/spec.md). The patterns come from the other healthcare projects ([Lab Report Assistant](https://github.com/Enriquez-Johnmark/lab-report-assistant), [Care Reminders](https://github.com/Enriquez-Johnmark/care-reminders), [Care Message Assistant](https://github.com/Enriquez-Johnmark/care-message-assistant)) and the Python tooling of [Help Assistant](https://github.com/Enriquez-Johnmark/help-assistant).

## Shape

One Python package, `record_access_audit`, under `src/`, with the React app in `web/`:

| Module | Holds | Criteria |
|---|---|---|
| `core/` | The rules, with no input or output: accounting for accesses, the eleven rules, case building, the queue order, the facts, the summary checks | B1–B5, C4, D1–D6 |
| `fhir/` | The strict FHIR R4 reader and the client for the clinic's FHIR server (reads only; the loader is separate) | H2, H3 |
| `made_up/` | The seeded generator of staff, patients, care and the labelled log; the made-up check | A1, A3 |
| `model/` | The model client: live (Claude) and recorded (for tests and the demo); the request builder | A2, C1, C2 |
| `store/` | Postgres: the connection pool, numbered SQL migrations and the repositories | G1, G2 |
| `audit_run.py` | Loading the log from FHIR and running the rules: flags and cases | B2, B4 |
| `summaries.py` | Writing and checking each case's summary | C1–C3 |
| `decisions.py` | The privacy officer's decisions, the rule-set versions | B6, E1–E4 |
| `api/` | The JSON API (FastAPI) for the privacy officer's pages and the patient report, and emailed-link logins | A4, H1 |
| `measure.py`, `evidence.py` | The measurement report and the evidence pack | I1–I3, J1 |
| `cli.py` | The commands: `migrate`, `add-staff`, `load-made-up`, `run`, `summarise`, `serve`, `measure`, `evidence` | |
| `web/` | The React app: the queue, a case, the rules, the activity log, the patient report | |
| `demo/`, `evalset/` | The generator's saved output, the labels, the bad summaries, the recorded answers | A1 |

The rules live in `core/` as pure functions over typed values (pydantic models and frozen dataclasses), called by every way in (the API, the commands, the measurement), so none can skip a rule. Anything from the FHIR server and every model answer is untrusted: parsed with pydantic, never put into SQL text or HTML.

## One clinic

The demo has one made-up clinic, so tables carry no clinic column. The boundaries that matter are the roles (only the privacy officer decides or edits the rules) and the patient (A4): every patient query filters on the logged-in patient's own record.

## From the log to the queue

1. **Read:** `fhir/` fetches the clinic's resources (tagged with the clinic) page by page and parses them into typed values: `Staff`, `Patient`, `CareRecord` (care teams, encounters, appointments) and `Access`. A resource that doesn't parse is refused with its reason, and the rest are taken in (H2). The clinic's own facts (shifts, staff addresses, which patient record is a staff member's, the VIP list) come from the saved clinic file.
2. **Account for:** `core.accounting` gives each chart opened its reasons (care team, encounter, appointment, role's work) or none.
3. **Flag:** `core.rules` runs the current rule-set version over every access and returns flags (access, reason code, version). Search-list hits are never passed to a rule that raises a case (B3).
4. **Case:** `core.cases` groups flags by staff member and patient (and high volume by staff member and day). Flags are stored with a unique key on (access, rule code, rule-set version), so a second run inserts nothing (B4). A flag whose pair has only decided cases opens a new case.
5. **Order:** the queue is a SQL query ordered by the sum of the case's rule weights, then its first flag's time. No model value is read by it (B5, C4).

Accesses are stored in Postgres when read, so the rules, the facts and the patient report never call the FHIR server mid-request. The tool's FHIR client has no method that writes; `load-made-up` uses a separate loader that refuses any server not on this computer (H3).

## The model

Behind a protocol with two versions, as in the other projects:

- **Live:** the official Anthropic SDK with `OWNER_ANTHROPIC_API_KEY` (never `ANTHROPIC_API_KEY`), `claude-sonnet-5-5`, structured output parsed into a pydantic `Summary`.
- **Recorded:** replays saved answers keyed by the SHA-256 of the exact request, so tests, CI and the demo need no key and cost nothing; a request nobody recorded fails rather than reaching a model.

The request is built from a `CaseFacts` value whose fields are pseudonymous IDs, roles, departments, times, actions, section categories, reason codes and care-relationship statements; it has no field that could hold a name, address, birth date or clinical content, so A2 holds by construction, and a test also searches every request for the made-up people's names and addresses. Each summary row stores the model, the request hash and the facts.

## Checks

`core.checks.check(summary, facts)` returns a list of problems, each naming its check and what it found (D6). A summary with any problem is stored as blocked and never shown; the page shows the facts with "No summary: it failed a check".

## Decisions

A `decisions` table: case, outcome (one of three), reason (at least 10 characters, checked in code and by a database constraint), who, when. No update or delete is ever issued, and the append-only trigger also covers it (E3). A case's status is its latest decision. The rule set lives in a `rule_set_versions` table: each change inserts a new version with all thresholds and weights; flags reference their version.

## Logins

Emailed links through Mailpit's send API in development: a single-use token, hashed in the database, valid for 15 minutes, giving a session cookie (HttpOnly, SameSite=Lax). Staff (privacy officer, administrator) and patients have separate sessions; every staff route checks the role, every patient route the patient. A same-origin check guards every POST.

## The activity log

An `audit_events` table with a trigger that refuses `UPDATE`, `DELETE` and `TRUNCATE` (G2). Every step writes to it in the same transaction as the change it records.

## Time

Read only through an injected `Clock`; ruff bans `datetime.now`, `datetime.utcnow`, `date.today` and `time.time` outside `clock.py`.

## Checks before every commit

`uv run ruff format --check .`, `uv run ruff check .`, `uv run pyright` and `uv run pytest` (against Postgres and a HAPI FHIR server), and for `web/` its own lint, typecheck, tests and build. CI also runs the browser tests and builds the evidence pack.

## Build order

| Milestone | What | Criteria | Status |
|---|---|---|---|
| M1 | Data and FHIR: the generator and labels, HAPI FHIR, the strict reader, read-only client, the made-up check, the evidence pack, CI | A1, A3, H2, H3, J1 | done (2026-11-11) |
| M2 | Flagging: accounting, the eleven rules, cases, the queue order, rule-set versions; recall and precision on the labelled log | B1–B5, I1 | done (2026-11-11) |
| M3 | Summaries: the facts, the model client, recorded answers, the checks, the 30 bad summaries | A2, C1–C4, D1–D6, I2 | planned |
| M4 | Logins, decisions, the rules page and the activity log, with the privacy officer's pages | B6, E1–E4, G1–G3, H1 | planned |
| M5 | The patient access report and measurement: Claude's recorded summaries, the report | A4, I3 | planned |
| M6 | Showcase: README, screenshots, walkthrough video, portfolio page | none | planned |

Each milestone ends with a code review and an evidence page.
