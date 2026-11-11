// Every server-data key in one place, so a change in one feature can
// refresh what another shows.

export const caseKeys = {
  all: () => ["cases"] as const,
  queue: () => [...caseKeys.all(), "queue"] as const,
  decided: () => [...caseKeys.all(), "decided"] as const,
  detail: (id: number) => [...caseKeys.all(), "detail", id] as const,
}

export const activityKeys = {
  list: (actor: string, action: string) => ["activity", actor, action] as const,
}

export const ruleKeys = {
  current: () => ["rules"] as const,
}
