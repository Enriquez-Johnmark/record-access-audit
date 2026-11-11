import { useQuery } from "@tanstack/react-query"
import { Navigate } from "react-router"

import { api, ApiError } from "@/api/client"
import type { AccessReport } from "@/api/types"
import { Account } from "@/app/app-shell"
import { useMe } from "@/app/queries"
import { reportKeys } from "@/app/query-keys"
import { Logo } from "@/components/logo"
import { QueryError } from "@/components/query-error"
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

/** A4: a patient's own access report: each time their chart was opened, by
 *  the staff member's role and department, never their name. */
export function ReportPage() {
  const me = useMe()
  const report = useQuery({
    queryKey: reportKeys.mine(),
    queryFn: () => api<AccessReport>("GET", "/api/report"),
    enabled: me.data?.who === "patient",
    // Each fetch is logged as the report being viewed, so not again on every return to the window.
    refetchOnWindowFocus: false,
    staleTime: 5 * 60 * 1000,
  })
  if (me.error instanceof ApiError && me.error.isNotLoggedIn)
    return <Navigate to="/login" replace />
  if (me.data?.who === "user") return <Navigate to="/" replace />
  return (
    <div className="flex min-h-svh flex-col">
      <header className="border-b bg-card">
        <div className="mx-auto flex w-full max-w-3xl flex-wrap items-center justify-between gap-4 px-4 py-3 md:px-8">
          <Logo />
          <Account who={me.data?.name} />
        </div>
      </header>
      <main className="mx-auto flex w-full max-w-3xl flex-1 flex-col gap-6 px-4 py-6 md:px-8">
        <div className="flex flex-col gap-1">
          <h1 className="text-2xl font-semibold tracking-tight">Who looked at your record</h1>
          <p className="text-sm text-muted-foreground">
            Each time someone at the clinic opened your chart, by their role and department.
          </p>
        </div>
        {report.isPending ? (
          <Skeleton className="h-48 w-full" />
        ) : report.isError ? (
          <QueryError error={report.error} />
        ) : (
          <>
            {report.data.looks.length === 0 ? (
              <p className="text-sm text-muted-foreground">
                No one at the clinic has opened your chart.
              </p>
            ) : (
              <div className="overflow-hidden rounded-lg border bg-card">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>When</TableHead>
                      <TableHead>Role</TableHead>
                      <TableHead>Department</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {report.data.looks.map((look, n) => (
                      <TableRow key={`${look.at}-${n}`}>
                        <TableCell className="whitespace-nowrap tabular-nums">
                          {formatDateTime(look.at)}
                        </TableCell>
                        <TableCell>{look.role}</TableCell>
                        <TableCell>{look.department}</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
            )}
            <p className="text-sm text-muted-foreground">{report.data.note}</p>
          </>
        )}
      </main>
    </div>
  )
}
