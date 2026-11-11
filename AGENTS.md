# AGENTS.md

**Record Access Audit** helps a clinic's privacy officer find and review inappropriate looks at patients' records: code reads the record system's access log and flags accesses the clinic's rules call unusual, Claude explains each flagged case in plain words from those facts alone, the privacy officer decides, and every step is in an append-only audit log. It works for any clinic; the demo uses a **made-up clinic with made-up staff and patients**, and the repository names no real company. Working name; it may be renamed.

It is the fourth of four healthcare projects, each in its own repository: [Lab Report Assistant](https://github.com/Enriquez-Johnmark/lab-report-assistant), [Care Reminders](https://github.com/Enriquez-Johnmark/care-reminders), [Care Message Assistant](https://github.com/Enriquez-Johnmark/care-message-assistant) and the record-access audit (this one).

## Phases

Each gate needs the owner's explicit "yes"; an approval for one phase never carries into the next.

| Phase | Status |
| --- | --- |
| 1. Research | done (2026-11-11, `docs/research/README.md`) |
| 2. Brief | done, approved 2026-11-11 under the standing approval (`docs/product/brief.md`) |
| 3. Spec & acceptance criteria | done, approved 2026-11-11 under the standing approval (`docs/product/spec.md`, 34 criteria) |
| 4. Architecture | done, approved 2026-11-11 under the standing approval (`docs/architecture.md`) |
| 5. Build | **in progress**, approved 2026-11-11: M1–M5 done, all 34 criteria proven (`docs/evidence/m5.html`); M6 (showcase) next |

Code follows the build order in `docs/architecture.md`, one milestone at a time; each ends with a code review and an evidence page.

## Owner decisions

Every decision needing the owner's judgement goes through the `grilling` skill: numbered rounds of questions, each with a recommended answer, worded so "yes" accepts it. Look facts up yourself, using sub-agents for research; put only decisions to the owner. Record every approved decision, dated, in `docs/decisions.md`.

## Evidence

Research claims carry a source (URL, publisher, date) and a confidence (H/M/L). Label vendor claims as vendor claims. When evidence is missing, write "not found"; a gap stays a gap. Keep facts, hypotheses, recommendations and owner-approved decisions visibly distinct.

## Rules

- **No real company, person or patient.** No real company's name, branding or content, and no real staff or patient data, anywhere in the repository, except that research documents may name real companies as cited sources.
- **Code flags; the model explains; a person decides.** Which accesses are flagged is decided by the clinic's rules in code, never by a model. No case is closed and no one is named as having done wrong without the privacy officer's decision.
- **Model output is untrusted.** Parsed into strict types and checked by rules before a person sees it.
- **API key only.** The Claude API through the owner's key (`OWNER_ANTHROPIC_API_KEY`), never a Claude subscription; no data to free model tiers that train on inputs.
- **No compliance claims.** The README never says "HIPAA compliant" or "certified".
- **Language:** Python, with React pages (decided 2026-11-10).
- **Report test results only from commands actually run.**
- **Tests:** test first (one criterion's test, see it fail, then make it pass); every acceptance criterion has a test whose name starts with its ID, e.g. `test_b3_a_search_list_hit_never_raises_a_case`.
- **Time:** read only through the injected `Clock` (`clock.py`); ruff bans direct system-clock calls elsewhere.
- **The model never sees who anyone is.** Requests carry only numbered facts with pseudonymous IDs; no name, address, date of birth or clinical content.
- **React:** read the `vercel-react-best-practices`, `vercel-composition-patterns`, `shadcn`, `frontend-design`, `web-design-guidelines` and `ui-taste` skills before writing or reviewing the React app.
- **Small commits** on `main`, each one change; messages imperative; no AI attribution trailers such as "Co-Authored-By" (owner's choice). Commits are signed with the owner's SSH key, so GitHub shows them as verified.

## Working here

- **Before every commit:** `uv run ruff format --check .`, `uv run ruff check .`, `uv run pyright` and `uv run pytest` pass, and for changes under `web/`, `pnpm --dir web lint`, `typecheck`, `test` and `build` too.

- **Cloud sessions:** `scripts/cloud-session-start.sh` runs at session start (via `.claude/settings.json`) and sets up commit signing.
