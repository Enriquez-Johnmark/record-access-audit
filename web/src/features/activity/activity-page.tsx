import { useQuery } from "@tanstack/react-query"
import { useSearchParams } from "react-router"

import { api } from "@/api/client"
import type { Entry } from "@/api/types"
import { activityKeys } from "@/app/query-keys"
import { PageHeader } from "@/components/page-header"
import { QueryError } from "@/components/query-error"
import { Input } from "@/components/ui/input"
import { NativeSelect, NativeSelectOption } from "@/components/ui/native-select"
import { Skeleton } from "@/components/ui/skeleton"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { formatDateTime } from "@/lib/dates"
import { actionChoices, actionLabel } from "@/lib/labels"

/** G3: the activity log, newest first; the filters live in the address so
 *  a filtered view can be shared. The database refuses to change an entry. */
export function ActivityPage() {
  const [params, setParams] = useSearchParams()
  const actor = params.get("actor") ?? ""
  const action = params.get("action") ?? ""
  const activity = useQuery({
    queryKey: activityKeys.list(actor, action),
    queryFn: () =>
      api<Entry[]>("GET", `/api/activity?${new URLSearchParams({ actor, action }).toString()}`),
  })
  const setFilter = (name: string, value: string) =>
    setParams((old) => {
      const next = new URLSearchParams(old)
      if (value) next.set(name, value)
      else next.delete(name)
      return next
    })

  return (
    <>
      <PageHeader
        title="Activity"
        description="Every log read, flag, summary, decision, rule change and login: who did it and when. Nothing here can be changed."
      />
      <div className="flex flex-wrap gap-3">
        <div className="flex flex-col gap-1.5">
          <label htmlFor="actor" className="text-sm font-medium">
            Person
          </label>
          <Input
            id="actor"
            type="email"
            spellCheck={false}
            placeholder="privacy@clinic.example.test…"
            defaultValue={actor}
            onBlur={(event) => setFilter("actor", event.target.value.trim())}
            onKeyDown={(event) => {
              if (event.key === "Enter") setFilter("actor", event.currentTarget.value.trim())
            }}
          />
        </div>
        <div className="flex flex-col gap-1.5">
          <label htmlFor="action" className="text-sm font-medium">
            Step
          </label>
          <NativeSelect
            id="action"
            value={action}
            onChange={(event) => setFilter("action", event.target.value)}
          >
            <NativeSelectOption value="">Every step</NativeSelectOption>
            {actionChoices.map(([code, label]) => (
              <NativeSelectOption key={code} value={code}>
                {label}
              </NativeSelectOption>
            ))}
          </NativeSelect>
        </div>
      </div>
      {activity.isPending ? (
        <Skeleton className="h-64 w-full" />
      ) : activity.isError ? (
        <QueryError error={activity.error} />
      ) : activity.data.length === 0 ? (
        <p className="text-sm text-muted-foreground">
          {actor || action ? "Nothing matches these filters." : "Nothing has happened yet."}
        </p>
      ) : (
        <div className="overflow-hidden rounded-lg border bg-card">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>When</TableHead>
                <TableHead>Step</TableHead>
                <TableHead>Who</TableHead>
                <TableHead>Details</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {activity.data.map((entry) => (
                <TableRow key={entry.id}>
                  <TableCell className="text-muted-foreground tabular-nums">
                    {formatDateTime(entry.at)}
                  </TableCell>
                  <TableCell>{actionLabel(entry.action)}</TableCell>
                  <TableCell>{entry.actor}</TableCell>
                  <TableCell className="whitespace-normal">
                    <span className="text-muted-foreground">{summary(entry)}</span>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}
    </>
  )
}

/** One line about an entry, from its details. */
function summary(entry: Entry) {
  const details = entry.details
  const text = (key: string) => (typeof details[key] === "string" ? details[key] : "")
  const count = (key: string) => (typeof details[key] === "number" ? details[key] : 0)
  const subject = entry.subject_type === "case" ? `Case ${entry.subject_id}` : ""
  switch (entry.action) {
    case "decision.recorded":
      return `${subject}: ${text("outcome")}. ${text("reason")}`
    case "rules.run":
      return `Version ${entry.subject_id}: ${count("flags")} new flags in ${count("cases")} new cases`
    case "log.loaded":
      return `${count("new_accesses")} new entries`
    case "rule_set.changed":
      return `Version ${entry.subject_id}`
    case "summary.blocked":
      return `${subject}: blocked by a check`
    default:
      return subject
  }
}
