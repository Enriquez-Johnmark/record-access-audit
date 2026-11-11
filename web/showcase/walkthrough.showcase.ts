import { join } from "node:path"

import { expect, test, type Page } from "@playwright/test"

import { logIn } from "../e2e/support.ts"
import { addOverlay, ADMIN, OFFICER, OUT, PATIENT, pointAt, press, record, say } from "./support.ts"

const size = { width: 1280, height: 720 }

/** A screenshot for people to look at, into docs/showcase/. */
async function shot(page: Page, name: string) {
  await page.evaluate(() => window.showCaption?.(""))
  await page.waitForTimeout(400)
  await page.screenshot({ path: join(OUT, `${name}.png`) })
}

/** Opens the case whose row mentions `text`, from the open cases. */
async function open(page: Page, text: string) {
  await page.goto("/")
  await press(page, page.getByRole("row").filter({ hasText: text }).first().getByRole("link"))
  await page.getByRole("heading", { name: "The facts" }).waitFor()
}

/** About two minutes, with captions: reading the log, the queue, a case and
 *  its checked summary, a decision, the rules, the log and a patient's report;
 *  saved as docs/showcase/walkthrough.mp4, with screenshots on the way. */
test("walkthrough", async ({ browser }, testInfo) => {
  const context = await browser.newContext({ viewport: size, deviceScaleFactor: 2 })
  const page = await context.newPage()
  await logIn(page, ADMIN)
  await addOverlay(page)
  const stop = await record(page, testInfo.outputPath("frames"))

  await page.goto("/")
  await say(page, "Record Access Audit, at a made-up clinic with made-up staff and patients.")
  await say(
    page,
    "The record system logs every look at a patient's chart. The log is on the clinic's FHIR server, the healthcare data standard."
  )
  await press(page, page.getByRole("button", { name: "Read the log and run the rules" }))
  await expect(page.getByText(/new cases flagged/)).toBeVisible({ timeout: 90_000 })
  await say(
    page,
    "Code first sets aside every look the clinic's own data explains: care teams, visits, appointments, a role's own work."
  )
  await say(page, "Eleven rules flag what is left. A model never decides what is flagged.", 4000)
  await shot(page, "desktop-1-log-read")

  await say(page, "The privacy officer logs in with an emailed link.", 3000)
  await context.clearCookies()
  await logIn(page, OFFICER)
  await page.getByRole("heading", { name: "Cases" }).waitFor()
  await say(
    page,
    "Open cases, heaviest first by the clinic's rule weights, then the oldest. None is ever hidden or closed by itself."
  )
  await shot(page, "desktop-2-queue")

  await open(page, "Aaron Quintero")
  await pointAt(page, page.getByRole("heading", { name: "The facts" }))
  await say(
    page,
    "A nurse opened the chart of someone at her home address, with no care relationship. Code writes the case's numbered facts."
  )
  await say(
    page,
    "Claude sees those facts and nothing else: no names, no addresses, no clinical content."
  )
  await pointAt(
    page,
    page.getByRole("heading", { name: "AI summary of the listed facts, not a finding" })
  )
  await say(
    page,
    "Its summary cites the facts each sentence rests on. Code checks every number and ID, and blocks any word that decides or accuses."
  )
  await shot(page, "desktop-3-case")

  await open(page, "Liam Prescombe")
  await page.getByText("No summary: it failed a check").waitFor()
  await say(
    page,
    "Here Claude counted something itself, so the summary isn't shown. The facts are."
  )
  await shot(page, "desktop-4-blocked-summary")

  await open(page, "Aaron Quintero")
  await page.getByLabel("Decision").selectOption("possible breach")
  await page
    .getByLabel("Reason")
    .fill("Same home address and no care relationship; a risk assessment is needed.")
  await press(page, page.getByRole("button", { name: "Record the decision" }))
  await page.getByText(/Notification reminder/).waitFor()
  await page.evaluate(() => window.scrollTo({ top: 0 }))
  await pointAt(page, page.getByText(/Notification reminder/))
  await say(
    page,
    "Only the privacy officer decides, always with a reason, kept for good. A possible breach shows a 60-day reminder, not legal advice."
  )
  await shot(page, "desktop-5-decided")

  await page.goto("/rules")
  await page.getByRole("heading", { name: "Rules" }).waitFor()
  await say(
    page,
    "The rules are the clinic's, with weights and thresholds. Each change is a new version and never rewrites a past flag."
  )
  await shot(page, "desktop-6-rules")

  await page.goto("/activity")
  await expect(page.getByRole("row").nth(5)).toBeVisible()
  await say(page, "Every step is in an append-only log the database refuses to change.")
  await shot(page, "desktop-7-activity")

  await say(page, "And the patient can see who looked.", 3000)
  await context.clearCookies()
  await logIn(page, PATIENT)
  await page.getByRole("heading", { name: "Who looked at your record" }).waitFor()
  await say(page, "Each time their chart was opened, by role and department, never by name.")
  await shot(page, "desktop-8-patient-report")
  await say(
    page,
    "Code flags, the model explains checked facts, a person decides. Made up from end to end.",
    4500
  )

  await stop(join(OUT, "walkthrough.mp4"))
  await context.close()
})

/** A case and the patient's report on a phone. */
test("phone", async ({ browser }) => {
  const context = await browser.newContext({
    viewport: { width: 390, height: 844 },
    deviceScaleFactor: 3,
  })
  const page = await context.newPage()
  await logIn(page, OFFICER)
  await open(page, "Bella Demirtas")
  await page.screenshot({ path: join(OUT, "phone-1-case.png"), fullPage: true })
  await context.clearCookies()
  await logIn(page, PATIENT)
  await page.getByRole("heading", { name: "Who looked at your record" }).waitFor()
  await page.screenshot({ path: join(OUT, "phone-2-report.png"), fullPage: true })
  await context.close()
})
