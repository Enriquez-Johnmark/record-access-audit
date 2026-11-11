import { createBrowserRouter } from "react-router"

import { AppShell } from "@/app/app-shell"
import { NotFoundPage } from "@/app/not-found-page"
import { PageLoading } from "@/app/page-loading"

/** Each page is loaded when first visited, so the first screen stays small.
 *  A login link opens a page whose button uses it, so a mail scanner can't. */
export const router = createBrowserRouter([
  {
    path: "/login",
    HydrateFallback: PageLoading,
    lazy: async () => ({ Component: (await import("@/features/login/login-page")).LoginPage }),
  },
  {
    path: "/login/:token",
    HydrateFallback: PageLoading,
    lazy: async () => ({
      Component: (await import("@/features/login/login-link-page")).LoginLinkPage,
    }),
  },
  {
    Component: AppShell,
    HydrateFallback: PageLoading,
    children: [
      {
        index: true,
        lazy: async () => ({ Component: (await import("@/features/home/home-page")).HomePage }),
      },
      {
        path: "cases/:id",
        lazy: async () => ({ Component: (await import("@/features/cases/case-page")).CasePage }),
      },
      {
        path: "rules",
        lazy: async () => ({ Component: (await import("@/features/rules/rules-page")).RulesPage }),
      },
      {
        path: "activity",
        lazy: async () => ({
          Component: (await import("@/features/activity/activity-page")).ActivityPage,
        }),
      },
      { path: "*", Component: NotFoundPage },
    ],
  },
])
