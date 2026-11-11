import { DatabaseIcon } from "lucide-react"

import { PageHeader } from "@/components/page-header"
import { SaveError } from "@/components/save-error"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import { Spinner } from "@/components/ui/spinner"
import { useRun } from "@/features/cases/queries"

/** The administrator reads the record system's access log from the clinic's
 *  FHIR server; the rules run on what is new, and each new case is summarised. */
export function RunPage() {
  const run = useRun()
  const result = run.data
  const summaries = result ? Object.entries(result.summaries) : []
  return (
    <>
      <PageHeader
        title="Access log"
        description="Read the newest entries from the record system's FHIR server and run the clinic's rules on them. Entries already read are skipped."
      >
        <Button onClick={() => run.mutate()} disabled={run.isPending}>
          {run.isPending ? (
            <Spinner data-icon="inline-start" />
          ) : (
            <DatabaseIcon data-icon="inline-start" />
          )}
          Read the log and run the rules
        </Button>
      </PageHeader>
      {run.isError ? <SaveError error={run.error} /> : null}
      {result ? (
        <Alert>
          <AlertTitle>
            {result.new_accesses === 0
              ? "Nothing new in the log"
              : `${result.new_accesses} new entries read; ${result.new_cases} new cases flagged`}
          </AlertTitle>
          <AlertDescription>
            {result.new_flags} new flags.{" "}
            {summaries.length > 0
              ? `Summaries: ${summaries.map(([status, n]) => `${n} ${status}`).join(", ")}.`
              : "No summaries were written."}{" "}
            {result.refused.length > 0
              ? `${result.refused.length} entries couldn't be read and were left out: ${result.refused.join("; ")}.`
              : null}
          </AlertDescription>
        </Alert>
      ) : null}
    </>
  )
}
