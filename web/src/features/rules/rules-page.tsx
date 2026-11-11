import {
  type UseMutationResult,
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query"
import { useState } from "react"

import { api } from "@/api/client"
import type { RuleSettings, RulesPage as Rules } from "@/api/types"
import { useMe } from "@/app/queries"
import { ruleKeys } from "@/app/query-keys"
import { PageHeader } from "@/components/page-header"
import { QueryError } from "@/components/query-error"
import { SaveError } from "@/components/save-error"
import { Section } from "@/components/section"
import { Alert, AlertTitle } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import { Checkbox } from "@/components/ui/checkbox"
import { Field, FieldGroup, FieldLabel } from "@/components/ui/field"
import { Input } from "@/components/ui/input"
import { Skeleton } from "@/components/ui/skeleton"
import { Spinner } from "@/components/ui/spinner"
import { formatDateTime } from "@/lib/dates"
import { ruleLabel } from "@/lib/labels"

const thresholds: { key: keyof RuleSettings; label: string; unit: string }[] = [
  {
    key: "encounter_days",
    label: "A visit accounts for looks this many days either side",
    unit: "days",
  },
  {
    key: "front_desk_days",
    label: "Front desk: a booking accounts for looks within",
    unit: "days",
  },
  { key: "billing_days", label: "Billing: a visit accounts for looks for", unit: "days" },
  { key: "after_care_days", label: "Care counts as long ended after", unit: "days" },
  { key: "shift_grace_minutes", label: "A look counts as outside a shift after", unit: "minutes" },
  { key: "high_volume_charts", label: "Many charts in a day: more than", unit: "patients" },
]

/** B6: the clinic's rules, versioned. Only the privacy officer changes them;
 *  each change is saved as a new version and never rewrites a past flag. */
export function RulesPage() {
  const me = useMe()
  const queryClient = useQueryClient()
  const rules = useQuery({
    queryKey: ruleKeys.current(),
    queryFn: () => api<Rules>("GET", "/api/rules"),
  })
  // Kept here, not in the form: the form starts afresh for each new version.
  const save = useMutation({
    mutationFn: (settings: RuleSettings) =>
      api<{ version: number }>("POST", "/api/rules", settings),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ruleKeys.current() }),
  })
  if (rules.isPending || !me.data) return <Skeleton className="h-96 w-full" />
  if (rules.isError) return <QueryError error={rules.error} />
  return (
    <RulesForm
      key={rules.data.version}
      page={rules.data}
      canEdit={me.data.role === "privacy officer"}
      save={save}
    />
  )
}

type Save = UseMutationResult<{ version: number }, Error, RuleSettings>

function RulesForm({ page, canEdit, save }: { page: Rules; canEdit: boolean; save: Save }) {
  const [settings, setSettings] = useState<RuleSettings>(page.settings)
  const number = (value: string) => (value === "" ? 0 : Number(value))
  return (
    <>
      <PageHeader
        title="Rules"
        description={`Version ${page.version}. Code applies these to every look in the log; a model never decides what is flagged.`}
      />
      {save.isSuccess ? (
        <Alert>
          <AlertTitle>
            Saved as version {save.data.version}. Cases already flagged keep the version that
            flagged them.
          </AlertTitle>
        </Alert>
      ) : null}
      <form
        onSubmit={(event) => {
          event.preventDefault()
          save.mutate(settings)
        }}
        className="flex flex-col gap-6"
      >
        <Section
          title="Weights"
          description="The queue puts the case whose rules weigh most first."
        >
          <FieldGroup className="grid gap-4 sm:grid-cols-2">
            {page.rules.map((rule) => (
              <Field key={rule.code}>
                <FieldLabel htmlFor={`w-${rule.code}`}>{ruleLabel(rule.code)}</FieldLabel>
                <Input
                  id={`w-${rule.code}`}
                  type="number"
                  inputMode="numeric"
                  min={1}
                  max={20}
                  disabled={!canEdit}
                  value={settings.weights[rule.code] ?? ""}
                  onChange={(e) =>
                    setSettings({
                      ...settings,
                      weights: { ...settings.weights, [rule.code]: number(e.target.value) },
                    })
                  }
                />
                <p className="text-xs text-muted-foreground">{rule.description}</p>
              </Field>
            ))}
          </FieldGroup>
        </Section>
        <Section title="Thresholds">
          <FieldGroup className="grid gap-4 sm:grid-cols-2">
            {thresholds.map((t) => (
              <Field key={t.key}>
                <FieldLabel htmlFor={t.key}>
                  {t.label} ({t.unit})
                </FieldLabel>
                <Input
                  id={t.key}
                  type="number"
                  inputMode="numeric"
                  min={0}
                  disabled={!canEdit}
                  value={settings[t.key] as number}
                  onChange={(e) => setSettings({ ...settings, [t.key]: number(e.target.value) })}
                />
              </Field>
            ))}
          </FieldGroup>
        </Section>
        <Section
          title="Roles that never read charts"
          description="Any chart these roles open is flagged, whatever the care data says."
        >
          <div className="flex flex-wrap gap-x-6 gap-y-3">
            {page.roles.map((role) => {
              const checked = settings.roles_no_charts.includes(role.value)
              return (
                <label key={role.value} className="flex items-center gap-2 text-sm">
                  <Checkbox
                    checked={checked}
                    disabled={!canEdit}
                    onCheckedChange={(on) =>
                      setSettings({
                        ...settings,
                        roles_no_charts: on
                          ? [...settings.roles_no_charts, role.value]
                          : settings.roles_no_charts.filter((r) => r !== role.value),
                      })
                    }
                  />
                  {role.label}
                </label>
              )
            })}
          </div>
        </Section>
        {save.isError ? <SaveError error={save.error} /> : null}
        {canEdit ? (
          <Button type="submit" disabled={save.isPending} className="self-start">
            {save.isPending ? <Spinner data-icon="inline-start" /> : null}
            Save as a new version
          </Button>
        ) : (
          <p className="text-sm text-muted-foreground">
            Only the privacy officer changes the rules.
          </p>
        )}
      </form>
      <Section title="Versions">
        <ul className="flex flex-col gap-1 text-sm">
          {page.versions.map((v) => (
            <li key={v.version}>
              Version {v.version}, {formatDateTime(v.created_at)}, by {v.created_by}
            </li>
          ))}
        </ul>
      </Section>
    </>
  )
}
