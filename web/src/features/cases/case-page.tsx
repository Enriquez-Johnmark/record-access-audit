import { zodResolver } from "@hookform/resolvers/zod"
import { CalendarClockIcon, CircleAlertIcon, SearchIcon, SparklesIcon } from "lucide-react"
import { useForm } from "react-hook-form"
import { Link, useParams } from "react-router"
import { z } from "zod"

import type { CaseDetail, Outcome, StoredSummary } from "@/api/types"
import { PageHeader } from "@/components/page-header"
import { QueryError } from "@/components/query-error"
import { SaveError } from "@/components/save-error"
import { Section } from "@/components/section"
import { Status } from "@/components/status"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Field, FieldDescription, FieldError, FieldGroup, FieldLabel } from "@/components/ui/field"
import { NativeSelect, NativeSelectOption } from "@/components/ui/native-select"
import { Skeleton } from "@/components/ui/skeleton"
import { Spinner } from "@/components/ui/spinner"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { Textarea } from "@/components/ui/textarea"
import { formatDate, formatDateTime } from "@/lib/dates"
import { actionLabel, checkLabel, outcomeLabel, ruleLabel } from "@/lib/labels"
import { useCase, useDecide } from "@/features/cases/queries"

/** One case: who looked at whose record and how, why the rules flagged it,
 *  the facts, Claude's summary of them if it passed every check, and the
 *  privacy officer's decision. Every rule is the API's; this page shows its answers. */
export function CasePage() {
  const id = Number(useParams().id)
  const found = useCase(id)
  if (found.isPending) return <Skeleton className="h-96 w-full" />
  if (found.isError) return <QueryError error={found.error} />
  const c = found.data
  const status = outcomeLabel(c.status)
  return (
    <>
      <Link to="/" className="text-sm text-muted-foreground hover:text-foreground">
        ← Cases
      </Link>
      <PageHeader
        title={
          c.patient
            ? `${c.staff.name} opened ${c.patient.name}'s record`
            : `${c.staff.name}'s charts on one day`
        }
        description={`${c.staff.name}: ${c.staff.role}, ${c.staff.department}. Everyone here is made up.`}
      >
        <Status tone={c.status === "open" ? "default" : status.variant}>
          {c.status === "open"
            ? `Open for ${c.age_days === 1 ? "1 day" : `${c.age_days} days`}`
            : status.label}
        </Status>
      </PageHeader>
      {c.reminder ? (
        <Alert>
          <CalendarClockIcon />
          <AlertTitle>Notification reminder: {formatDate(c.reminder.date)}</AlertTitle>
          <AlertDescription>{c.reminder.text}</AlertDescription>
        </Alert>
      ) : null}
      <div className="grid gap-6 lg:grid-cols-[3fr_2fr]">
        <div className="flex min-w-0 flex-col gap-6">
          <Looks c={c} />
          <Summary summary={c.summary} />
          <Decide c={c} />
          <History c={c} />
        </div>
        <aside
          aria-label="Why it was flagged, and the facts"
          className="flex min-w-0 flex-col gap-6"
        >
          <section className="flex flex-col gap-3">
            <h2 className="text-base font-semibold">Why it was flagged</h2>
            <ul className="flex flex-col gap-2">
              {c.rules.map(([code, description]) => (
                <li key={code} className="flex flex-col gap-0.5">
                  <Badge variant="outline">{ruleLabel(code)}</Badge>
                  <span className="text-sm text-muted-foreground">{description}</span>
                </li>
              ))}
            </ul>
          </section>
          <Section
            title="The facts"
            description="Written by code from the log. Claude sees these and nothing else."
          >
            <ol className="flex list-none flex-col gap-2 text-sm">
              {c.facts.map((fact, n) => (
                <li key={n} id={`fact-${n + 1}`} className="flex gap-2">
                  <span className="w-5 shrink-0 text-right text-muted-foreground tabular-nums">
                    {n + 1}
                  </span>
                  <span>{fact}</span>
                </li>
              ))}
            </ol>
          </Section>
        </aside>
      </div>
    </>
  )
}

/** A day of many charts shows its first dozen; a pair's few looks show in full. */
function shown(c: CaseDetail) {
  return c.patient ? 50 : 12
}

function Looks({ c }: { c: CaseDetail }) {
  return (
    <section
      aria-label="What happened"
      className="flex flex-col gap-3 rounded-lg border bg-card p-4"
    >
      <h2 className="font-semibold">
        {c.looks.length === 1 ? "1 chart opened" : `${c.looks.length} charts opened`}
      </h2>
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>When</TableHead>
            <TableHead>Part of the chart</TableHead>
            <TableHead className="text-right">Time spent</TableHead>
            <TableHead>Workstation</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {c.looks.slice(0, shown(c)).map((look) => (
            <TableRow key={look.access}>
              <TableCell className="whitespace-nowrap">{formatDateTime(look.at)}</TableCell>
              <TableCell>{look.section ?? "summary"}</TableCell>
              <TableCell className="text-right tabular-nums">{look.seconds} s</TableCell>
              <TableCell className="text-muted-foreground">{look.workstation}</TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
      {c.looks.length > shown(c) ? (
        <p className="text-sm text-muted-foreground">
          And {c.looks.length - shown(c)} more the same day.
        </p>
      ) : null}
      {c.search_hits.length > 0 ? (
        <Alert>
          <SearchIcon />
          <AlertTitle>
            Also in{" "}
            {c.search_hits.length === 1 ? "1 search list" : `${c.search_hits.length} search lists`}:
            the chart was not opened from them
          </AlertTitle>
          <AlertDescription>
            A search list shows names only. Appearing in one is not opening the chart, and never
            raises a case. First: {formatDateTime(c.search_hits[0]!.at)}.
          </AlertDescription>
        </Alert>
      ) : null}
    </section>
  )
}

function Summary({ summary }: { summary: StoredSummary | null }) {
  if (summary === null)
    return (
      <p className="text-sm text-muted-foreground">
        No summary yet. The numbered facts on this page are everything the rules and Claude have to
        go on.
      </p>
    )
  if (summary.status !== "shown" || summary.summary === null)
    return (
      <Alert variant="destructive">
        <CircleAlertIcon />
        <AlertTitle>No summary: it failed a check</AlertTitle>
        <AlertDescription>
          {summary.status === "unreadable"
            ? "Claude's answer wasn't in the agreed shape, so it isn't shown. The facts are complete without it."
            : `Claude's summary was blocked, so it isn't shown: ${summary.problems
                .map((p) => `${checkLabel(p.check)} ("${p.found}", ${p.where})`)
                .join("; ")}.`}
        </AlertDescription>
      </Alert>
    )
  return (
    <section aria-label="Summary" className="flex flex-col gap-3 rounded-lg border bg-card p-4">
      <div className="flex items-center gap-2">
        <SparklesIcon aria-hidden className="size-4 text-muted-foreground" />
        <h2 className="font-semibold">AI summary of the listed facts, not a finding</h2>
      </div>
      <Sentences sentences={summary.summary.summary} />
      {summary.summary.to_check.length > 0 ? (
        <>
          <h3 className="text-sm font-medium">Innocent explanations you could check</h3>
          <Sentences sentences={summary.summary.to_check} list />
        </>
      ) : null}
      <p className="text-xs text-muted-foreground">
        Written by {summary.model} and passed every check: each sentence cites the facts it rests
        on, every number comes from them, and nothing decides, accuses or names clinical content.
      </p>
    </section>
  )
}

function Sentences({
  sentences,
  list,
}: {
  sentences: { text: string; facts: number[] }[]
  list?: boolean
}) {
  const items = sentences.map((s, n) => (
    <li key={n}>
      {s.text}{" "}
      <span className="text-xs text-muted-foreground">
        {s.facts.map((f) => (
          <a key={f} href={`#fact-${f}`} className="mr-1 underline-offset-2 hover:underline">
            [{f}]
          </a>
        ))}
      </span>
    </li>
  ))
  return list ? (
    <ul className="flex list-disc flex-col gap-1 pl-5">{items}</ul>
  ) : (
    <ul className="flex list-none flex-col gap-1">{items}</ul>
  )
}

const decisionSchema = z.object({
  outcome: z.enum(["appropriate", "follow-up", "possible breach"], { error: "Choose a decision." }),
  reason: z.string().trim().min(10, "Write at least 10 characters: what you found and why."),
})
type DecisionForm = z.infer<typeof decisionSchema>

function Decide({ c }: { c: CaseDetail }) {
  const decide = useDecide(c.id)
  const form = useForm<DecisionForm>({
    resolver: zodResolver(decisionSchema),
    defaultValues: { outcome: undefined as unknown as Outcome, reason: "" },
  })
  return (
    <Section
      title={c.decisions.length === 0 ? "Your decision" : "Change the decision"}
      description="Only you decide. The tool sends no message to the staff member, HR, the patient or anyone else."
    >
      <form
        noValidate
        onSubmit={form.handleSubmit((values) =>
          decide.mutate(values, { onSuccess: () => form.reset() })
        )}
      >
        <FieldGroup>
          <Field data-invalid={form.formState.errors.outcome ? true : undefined}>
            <FieldLabel htmlFor="outcome">Decision</FieldLabel>
            <NativeSelect
              id="outcome"
              aria-invalid={form.formState.errors.outcome ? true : undefined}
              {...form.register("outcome")}
            >
              <NativeSelectOption value="">Choose…</NativeSelectOption>
              {c.outcomes.map((o) => (
                <NativeSelectOption key={o.value} value={o.value}>
                  {o.label}
                </NativeSelectOption>
              ))}
            </NativeSelect>
            <FieldError errors={[form.formState.errors.outcome]} />
          </Field>
          <Field data-invalid={form.formState.errors.reason ? true : undefined}>
            <FieldLabel htmlFor="reason">Reason</FieldLabel>
            <Textarea
              id="reason"
              rows={3}
              aria-invalid={form.formState.errors.reason ? true : undefined}
              {...form.register("reason")}
            />
            <FieldDescription>
              Kept for good in the case's history, with your name and the time.
            </FieldDescription>
            <FieldError errors={[form.formState.errors.reason]} />
          </Field>
          {decide.isError ? <SaveError error={decide.error} /> : null}
          <Button type="submit" disabled={decide.isPending} className="self-start">
            {decide.isPending ? <Spinner data-icon="inline-start" /> : null}
            Record the decision
          </Button>
        </FieldGroup>
      </form>
    </Section>
  )
}

function History({ c }: { c: CaseDetail }) {
  return (
    <Section
      title="History"
      description="Every step on this case. Nothing here can be changed or removed."
    >
      {c.decisions.length > 0 ? (
        <ul className="flex flex-col gap-3">
          {c.decisions.map((d) => (
            <li key={d.id} className="flex flex-col gap-1 rounded-lg border bg-card p-3">
              <Status tone={outcomeLabel(d.outcome).variant}>
                {outcomeLabel(d.outcome).label}
              </Status>
              <p className="text-sm">{d.reason}</p>
              <p className="text-xs text-muted-foreground">
                {d.decided_by}, {formatDateTime(d.decided_at)}
              </p>
            </li>
          ))}
        </ul>
      ) : null}
      <ol className="flex flex-col gap-1 text-sm">
        {c.timeline.map((e) => (
          <li key={e.id} className="flex flex-wrap gap-x-2">
            <span className="text-muted-foreground tabular-nums">{formatDateTime(e.at)}</span>
            <span>{actionLabel(e.action)}</span>
            <span className="text-muted-foreground">by {e.actor}</span>
          </li>
        ))}
      </ol>
    </Section>
  )
}
