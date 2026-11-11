# Record Access Audit

Helps a clinic's privacy officer find and review inappropriate looks at patients' records. Code reads the record system's access log and flags accesses the clinic's rules call unusual; Claude explains each flagged case in plain words; the privacy officer decides. Every step is in an append-only audit log.

**Status:** brief and spec done ([`docs/product/spec.md`](docs/product/spec.md), 34 acceptance criteria); the architecture is next. See [`AGENTS.md`](AGENTS.md) for the phases.

The fourth of four healthcare projects, after [Lab Report Assistant](https://github.com/Enriquez-Johnmark/lab-report-assistant), [Care Reminders](https://github.com/Enriquez-Johnmark/care-reminders) and [Care Message Assistant](https://github.com/Enriquez-Johnmark/care-message-assistant). Made-up clinic, made-up staff and patients: this repository contains no real patient data and names no real company outside its research notes.

## Licence

All rights reserved ([LICENSE](LICENSE)). The source is published to be read, not reused.
