// The shapes the API sends, as src/record_access_audit/api/app.py builds them.

export type Role = "privacy officer" | "administrator"

export type Me =
  { who: "user"; name: string; email: string; role: Role } | { who: "patient"; name: string }

export interface AccessReport {
  patient: string
  note: string
  looks: { at: string; role: string; department: string }[]
}

export interface Person {
  id: string
  name: string
}

export interface StaffMember extends Person {
  role: string
  department: string
}

export interface QueueRow {
  id: number
  staff: StaffMember
  patient: Person | null
  day: string | null
  rules: string[]
  score: number
  age_days: number
  first_look: string
}

export interface DecidedRow {
  id: number
  staff: StaffMember
  patient: Person | null
  day: string | null
  outcome: Outcome
  outcome_label: string
  decided_at: string
  decided_by: string
}

export type Outcome = "appropriate" | "follow-up" | "possible breach"

export interface Look {
  access: string
  at: string
  kind: "chart opened" | "search list"
  section: string | null
  seconds: number
  workstation: string
}

export interface Sentence {
  text: string
  facts: number[]
}

export interface StoredSummary {
  id: number
  model: string
  status: "shown" | "blocked" | "unreadable"
  summary: { summary: Sentence[]; to_check: Sentence[] } | null
  problems: { check: string; found: string; where: string; why: string }[]
  written_at: string
}

export interface Decision {
  id: number
  outcome: Outcome
  reason: string
  decided_by: string
  decided_at: string
}

export interface Entry {
  id: number
  at: string
  actor: string
  action: string
  subject_type: string
  subject_id: string
  details: Record<string, unknown>
}

export interface CaseDetail {
  id: number
  status: "open" | Outcome
  flagged_at: string
  age_days: number
  staff: StaffMember
  patient: Person | null
  day: string | null
  rules: [string, string][]
  looks: Look[]
  search_hits: Look[]
  facts: string[]
  summary: StoredSummary | null
  decisions: Decision[]
  reminder: { date: string; text: string } | null
  timeline: Entry[]
  outcomes: { value: Outcome; label: string }[]
}

export interface RuleSettings {
  weights: Record<string, number>
  roles_no_charts: string[]
  encounter_days: number
  front_desk_days: number
  billing_days: number
  after_care_days: number
  shift_grace_minutes: number
  high_volume_charts: number
}

export interface RulesPage {
  version: number
  settings: RuleSettings
  rules: { code: string; description: string }[]
  roles: { value: string; label: string }[]
  versions: { version: number; created_at: string; created_by: string }[]
}

export interface RunResult {
  new_accesses: number
  refused: string[]
  new_flags: number
  new_cases: number
  summaries: Record<string, number>
}
