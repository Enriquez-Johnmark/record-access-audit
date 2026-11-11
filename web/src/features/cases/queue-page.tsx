import { InboxIcon } from "lucide-react"
import { Link } from "react-router"

import type { DecidedRow, QueueRow } from "@/api/types"
import { PageHeader } from "@/components/page-header"
import { QueryError } from "@/components/query-error"
import { Status } from "@/components/status"
import { Badge } from "@/components/ui/badge"
import { Empty, EmptyDescription, EmptyHeader, EmptyMedia, EmptyTitle } from "@/components/ui/empty"
import { Skeleton } from "@/components/ui/skeleton"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { formatDate, formatDateTime } from "@/lib/dates"
import { outcomeLabel, ruleLabel } from "@/lib/labels"
import { useDecided, useQueue } from "@/features/cases/queries"

/** B5: every open case, in the order the clinic's rules weigh it (heaviest
 *  first, then the oldest); none is hidden or closed however old it is. */
export function QueuePage() {
  const queue = useQueue()
  const decided = useDecided()
  return (
    <>
      <PageHeader
        title="Cases"
        description="Looks at patients' records the clinic's rules call unusual. Code flags them; you decide."
      />
      <Tabs defaultValue="open">
        <TabsList>
          <TabsTrigger value="open">Open{queue.data ? ` (${queue.data.length})` : ""}</TabsTrigger>
          <TabsTrigger value="decided">
            Decided{decided.data ? ` (${decided.data.length})` : ""}
          </TabsTrigger>
        </TabsList>
        <TabsContent value="open" className="pt-4">
          {queue.isPending ? (
            <Skeleton className="h-64 w-full" />
          ) : queue.isError ? (
            <QueryError error={queue.error} />
          ) : queue.data.length === 0 ? (
            <Empty>
              <EmptyHeader>
                <EmptyMedia variant="icon">
                  <InboxIcon />
                </EmptyMedia>
                <EmptyTitle>No open cases</EmptyTitle>
                <EmptyDescription>
                  When the administrator reads the access log, any look the rules flag appears here.
                </EmptyDescription>
              </EmptyHeader>
            </Empty>
          ) : (
            <OpenCases rows={queue.data} />
          )}
        </TabsContent>
        <TabsContent value="decided" className="pt-4">
          {decided.isPending ? (
            <Skeleton className="h-64 w-full" />
          ) : decided.isError ? (
            <QueryError error={decided.error} />
          ) : decided.data.length === 0 ? (
            <p className="text-sm text-muted-foreground">No case has been decided yet.</p>
          ) : (
            <DecidedCases rows={decided.data} />
          )}
        </TabsContent>
      </Tabs>
    </>
  )
}

function Who({ row }: { row: QueueRow | DecidedRow }) {
  return (
    <Link to={`/cases/${row.id}`} className="flex flex-col gap-0.5 hover:underline">
      <span className="font-medium">{row.staff.name}</span>
      <span className="text-xs text-muted-foreground">
        {row.staff.role}, {row.staff.department}
      </span>
    </Link>
  )
}

function Whose({ row }: { row: QueueRow | DecidedRow }) {
  return row.patient ? (
    <span>{row.patient.name}</span>
  ) : (
    <span className="text-muted-foreground">
      Many charts on {row.day ? formatDate(row.day) : "one day"}
    </span>
  )
}

function OpenCases({ rows }: { rows: QueueRow[] }) {
  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Staff member</TableHead>
          <TableHead>Whose record</TableHead>
          <TableHead>Why it was flagged</TableHead>
          <TableHead className="text-right">Weight</TableHead>
          <TableHead>First look</TableHead>
          <TableHead className="text-right">Open for</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {rows.map((row) => (
          <TableRow key={row.id}>
            <TableCell>
              <Who row={row} />
            </TableCell>
            <TableCell>
              <Whose row={row} />
            </TableCell>
            <TableCell>
              <div className="flex flex-wrap gap-1">
                {row.rules.map((code) => (
                  <Badge key={code} variant="outline">
                    {ruleLabel(code)}
                  </Badge>
                ))}
              </div>
            </TableCell>
            <TableCell className="text-right tabular-nums">{row.score}</TableCell>
            <TableCell className="whitespace-nowrap">{formatDateTime(row.first_look)}</TableCell>
            <TableCell className="text-right whitespace-nowrap tabular-nums">
              {row.age_days === 1 ? "1 day" : `${row.age_days} days`}
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  )
}

function DecidedCases({ rows }: { rows: DecidedRow[] }) {
  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Staff member</TableHead>
          <TableHead>Whose record</TableHead>
          <TableHead>Decision</TableHead>
          <TableHead>Decided</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {rows.map((row) => {
          const outcome = outcomeLabel(row.outcome)
          return (
            <TableRow key={row.id}>
              <TableCell>
                <Who row={row} />
              </TableCell>
              <TableCell>
                <Whose row={row} />
              </TableCell>
              <TableCell>
                <Status tone={outcome.variant}>{outcome.label}</Status>
              </TableCell>
              <TableCell className="whitespace-nowrap">{formatDateTime(row.decided_at)}</TableCell>
            </TableRow>
          )
        })}
      </TableBody>
    </Table>
  )
}
