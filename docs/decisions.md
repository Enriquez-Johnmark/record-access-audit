# Decisions

Approved by the owner, newest last.

## 2026-11-10 (recorded in Lab Report Assistant's `docs/decisions.md`)

- **A healthcare series:** four portfolio projects, each in its own repository, built one at a time, each finished before the next: lab reports, care follow-up reminders, a care-team message assistant and a record-access audit (this one).
- **Language:** Python, with React pages.

## 2026-11-11: standing approval

- **Standing approval:** the owner approved in advance every recommendation put to them ("approved if it's your recommendation, yes to all"; recorded first in Care Reminders' `docs/decisions.md`). Decisions below marked "(standing approval)" were taken under it.
- **Repository:** created by the owner; work starts now that Care Message Assistant is finished (standing approval).
- **Research documents** may name real companies as cited sources, as in the other healthcare projects (standing approval).
- **Research:** done (`docs/research/README.md`).
- **Brief, Round 1** (all twelve as recommended in `docs/research/README.md`, Open decisions; standing approval; `docs/product/brief.md`):
  1. Scope: the access log of one made-up clinic (about 30 staff, 300 patients, 2–4 weeks); flag, explain and record decisions only; no automatic discipline, no message to the staff member or HR, no automatic patient or regulator notice.
  2. Explain first, then flag: code sets aside accesses the clinic's own data explains, then flags what remains when a rule fires; a model never decides what is flagged or its order.
  3. Eleven rules, each with a reason code, description, configurable threshold and version; a name match raises a case only with "no care relationship".
  4. Versioned rules: every flag records its rule version; a change never rewrites past flags.
  5. The model sees only numbered facts with pseudonymous IDs, role, department, times, actions, rule reasons and care-relationship facts; no names, addresses, birth dates or clinical content.
  6. Blocking checks on every explanation: fact citations, numbers and IDs from the cited facts, no deciding or accusing words, no clinical words, a length limit; a failure shows the facts alone.
  7. Decisions by the privacy officer only: appropriate, needs follow-up with the staff member, or possible breach (risk assessment needed), each with a written reason; history is append-only.
  8. Case age shown, open cases never hidden or auto-dismissed; a 60-day reminder on a possible breach, labelled as not legal advice.
  9. A patient access report of roles, departments and times, no staff names, marked as beyond what HIPAA now requires.
  10. FHIR R4 `AuditEvent` (IHE BALP shape) and related resources from our own generator on a pinned local HAPI server, read-only to the tool; the tool's append-only log is the record of review.
  11. Measurement on a labelled made-up log with planted cases and innocent look-alikes: recall and precision per rule, share explained away, explanation pass rate; no claim of catching real snooping.
  12. Claude Sonnet through `OWNER_ANTHROPIC_API_KEY`; the README says real use needs a BAA and makes no compliance claim.
- **Spec** (as recommended; standing approval; `docs/product/spec.md`): Example Valley Clinic with a privacy officer, an administrator and patients; 30 made-up staff, 300 patients and a 14-day labelled log (at least 30 planted cases and 20 innocent look-alikes) from a seeded generator; accesses accounted for by care team, encounter, appointment or the role's ordinary work; eleven weighted rules, two of them (own record, a role that never reads charts) on every opened chart and the rest only on accesses not accounted for; a search-list hit never raises a case; queue ordered by weight then age in code; Claude's summaries from numbered facts with pseudonymous IDs, blocked by five checks; three decisions with a written reason, append-only; a 60-day reminder labelled not legal advice; a patient access report by role and department; 34 acceptance criteria (A1–J1).
- **Architecture** (as recommended; standing approval; `docs/architecture.md`): one Python package (FastAPI, psycopg 3, pydantic, httpx, the Anthropic SDK) with the React app in `web/`; the rules as pure functions in `core/`; accesses stored in Postgres when read; flags unique on (access, rule, rule-set version); a read-only FHIR client and a separate loader for this computer only; recorded model answers; a facts type with no field for names or clinical content; append-only log and decisions enforced by a trigger; emailed-link logins; build order M1–M6.
- **Build:** approved (standing approval); M1 starts.
