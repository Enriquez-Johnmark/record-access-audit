import { Alert, AlertTitle } from "@/components/ui/alert"

/** Why the API refused an action, in its own words. */
export function SaveError({ error }: { error: Error }) {
  return (
    <Alert variant="destructive">
      <AlertTitle>{error.message}</AlertTitle>
    </Alert>
  )
}
