# Showcase

Screenshots and a captioned walkthrough (1 min 37 s) of Record Access Audit at a made-up clinic, Example Valley Clinic. The administrator reads 14 days of access log from the clinic's FHIR server (HAPI FHIR, running on this computer), and the clinic's rules flag 34 cases. The privacy officer opens a nurse's look at the chart of someone living at her home address, with Claude's checked summary of the case's numbered facts; opens a case whose summary was blocked by a check; and decides the first case as a possible breach, which shows a 60-day reminder. Then come the rules page, the activity log, and the patient's own access report.

The summaries are Claude Sonnet's, made with the owner's API key on 2026-11-11 and replayed from `evalset/recorded/` (the same summaries `evalset/report.md` measures). Everything is made up: the clinic, the staff, the patients, their care and the `example.test` addresses. Login emails arrive in Mailpit, a test inbox on this computer; nothing is sent anywhere. Times are shown in the clinic's time zone.

| File | Shows |
|---|---|
| `walkthrough.mp4` | The whole loop, from reading the log to the patient's report |
| `desktop-1-log-read.png` | The administrator reads the access log; the rules flag 34 cases |
| `desktop-2-queue.png` | The privacy officer's open cases, heaviest first, then the oldest |
| `desktop-3-case.png` | A case: the charts opened, why it was flagged, the numbered facts, and Claude's summary citing them |
| `desktop-4-blocked-summary.png` | A case whose summary failed a check: it isn't shown, the facts are |
| `desktop-5-decided.png` | A decision of possible breach, with its 60-day reminder labelled as not legal advice |
| `desktop-6-rules.png` | The clinic's rules: weights, thresholds and roles that never read charts, versioned |
| `desktop-7-activity.png` | The append-only activity log |
| `desktop-8-patient-report.png` | A patient's access report: when, by role and department, never by name |
| `phone-1-case.png`, `phone-2-report.png` | A case and the patient's report on a phone |

## Making them again

```bash
docker compose --profile fhir up -d
uv sync && pnpm --dir web install && pnpm --dir web build
scripts/showcase.sh
```

The script starts a fresh database and a server on port 8020 that summarises from the recordings (`serve --recorded`), so it needs no API key and costs nothing. It loads the made-up clinic into HAPI FHIR on this computer; nothing is sent to a public FHIR server. The video needs ffmpeg.
