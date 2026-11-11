import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"

import { api } from "@/api/client"
import type { CaseDetail, DecidedRow, Decision, Outcome, QueueRow, RunResult } from "@/api/types"
import { caseKeys } from "@/app/query-keys"

export function useQueue() {
  return useQuery({
    queryKey: caseKeys.queue(),
    queryFn: () => api<QueueRow[]>("GET", "/api/queue"),
  })
}

export function useDecided() {
  return useQuery({
    queryKey: caseKeys.decided(),
    queryFn: () => api<DecidedRow[]>("GET", "/api/decided"),
  })
}

export function useCase(id: number) {
  return useQuery({
    queryKey: caseKeys.detail(id),
    queryFn: () => api<CaseDetail>("GET", `/api/cases/${id}`),
  })
}

/** E1–E3: the privacy officer's decision; the API checks who and what. */
export function useDecide(id: number) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (body: { outcome: Outcome; reason: string }) =>
      api<Decision>("POST", `/api/cases/${id}/decisions`, body),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: caseKeys.all() }),
  })
}

/** The administrator loads the access log from the FHIR server and runs the rules. */
export function useRun() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: () => api<RunResult>("POST", "/api/run"),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: caseKeys.all() }),
  })
}
