import { useQuery } from "@tanstack/react-query"

import { api } from "@/api/client"
import type { Me } from "@/api/types"

export const meKeys = {
  me: () => ["me"] as const,
}

/** Who is logged in; fails with a 401 ApiError when nobody is. */
export function useMe() {
  return useQuery({
    queryKey: meKeys.me(),
    queryFn: () => api<Me>("GET", "/api/me"),
    staleTime: 5 * 60 * 1000,
  })
}
