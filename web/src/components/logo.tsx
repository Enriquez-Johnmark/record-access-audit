import { cn } from "@/lib/utils"

/** The app's name beside a mark: a record page under a magnifying glass. */
export function Logo({ className }: { className?: string }) {
  return (
    <span className={cn("flex items-center gap-2 font-semibold", className)}>
      <svg viewBox="0 0 32 32" aria-hidden="true" className="size-6">
        <rect width="32" height="32" rx="8" className="fill-primary" />
        <path
          d="M9 7.5h9l4 4v6M9 7.5v17h8M12 13h6M12 17h4"
          fill="none"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
          className="stroke-primary-foreground"
        />
        <circle
          cx="21.5"
          cy="21.5"
          r="3.5"
          fill="none"
          strokeWidth="2"
          className="stroke-primary-foreground"
        />
        <path
          d="m24 24 2.5 2.5"
          strokeWidth="2"
          strokeLinecap="round"
          className="stroke-primary-foreground"
        />
      </svg>
      Record Access Audit
    </span>
  )
}
