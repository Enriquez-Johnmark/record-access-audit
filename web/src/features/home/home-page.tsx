import { useMe } from "@/app/queries"
import { Skeleton } from "@/components/ui/skeleton"
import { QueuePage } from "@/features/cases/queue-page"
import { RunPage } from "@/features/home/run-page"

/** The privacy officer starts at the cases; the administrator at the access log. */
export function HomePage() {
  const me = useMe()
  if (!me.data) return <Skeleton className="h-64 w-full" />
  return me.data.who === "user" && me.data.role === "administrator" ? <RunPage /> : <QueuePage />
}
