// The API sends codes; these are the words people see. An unknown code is
// shown as it is rather than hidden.

const rules: Record<string, string> = {
  OWN_RECORD: "Own record",
  ROLE_NO_CHARTS: "Role never reads charts",
  NO_RELATIONSHIP: "No care relationship",
  SAME_LAST_NAME: "Same last name",
  SAME_ADDRESS: "Same home address",
  COWORKER: "A co-worker's record",
  VIP: "VIP",
  DECEASED: "Patient had died",
  AFTER_CARE_ENDED: "Long after care ended",
  OUTSIDE_SHIFT: "Outside shift",
  HIGH_VOLUME: "Many charts in a day",
}

export function ruleLabel(code: string) {
  return rules[code] ?? code
}

const outcomes: Record<
  string,
  { label: string; variant: "secondary" | "warning" | "destructive" }
> = {
  open: { label: "Open", variant: "secondary" },
  appropriate: { label: "Appropriate", variant: "secondary" },
  "follow-up": { label: "Needs follow-up", variant: "warning" },
  "possible breach": { label: "Possible breach", variant: "destructive" },
}

export function outcomeLabel(outcome: string) {
  return outcomes[outcome] ?? { label: outcome, variant: "secondary" as const }
}

const checks: Record<string, string> = {
  "cites-no-fact": "Cites no fact",
  "not-in-facts": "Not in the facts",
  accuses: "Decides or accuses",
  clinical: "Clinical words",
  "too-long": "Too long",
}

export function checkLabel(check: string) {
  return checks[check] ?? check
}

const actions: Record<string, string> = {
  "log.loaded": "Access log loaded",
  "rules.run": "Rules run",
  "case.flagged": "Case flagged",
  "summary.written": "Summary written",
  "summary.blocked": "Summary blocked",
  "summary.unreadable": "Summary unreadable",
  "summary.failed": "Summary failed",
  "case.viewed": "Case opened",
  "decision.recorded": "Decision recorded",
  "report.viewed": "Patient viewed their report",
  "rule_set.created": "Rules installed",
  "rule_set.changed": "Rules changed",
  login: "Logged in",
}

export function actionLabel(action: string) {
  return actions[action] ?? action
}

/** The steps the activity page can filter by. */
export const actionChoices = Object.entries(actions)

/** "the case of S-009 and P-286" in words people use. */
export function caseTitle(row: {
  staff: { name: string }
  patient: { name: string } | null
  day: string | null
}) {
  return row.patient ? `${row.staff.name} → ${row.patient.name}` : `${row.staff.name}, one day`
}
