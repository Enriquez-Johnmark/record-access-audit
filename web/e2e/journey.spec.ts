import { expect, test } from "@playwright/test"

import { logIn } from "./support.ts"

const OFFICER = "privacy@clinic.example.test"
const ADMIN = "admin@clinic.example.test"

// One journey, in order: the administrator reads the access log, the
// privacy officer works the heaviest case, decides it and changes a rule.
test.describe.configure({ mode: "serial" })

test("the administrator reads the access log and the rules flag the made-up cases", async ({
  page,
}) => {
  await logIn(page, ADMIN)
  await page.getByRole("button", { name: "Read the log and run the rules" }).click()
  await expect(
    page.getByText(/new entries read; 34 new cases flagged|Nothing new in the log/)
  ).toBeVisible({
    timeout: 60_000,
  })
  await page.getByRole("link", { name: "Activity" }).click()
  await expect(page.getByRole("cell", { name: "Rules run" }).first()).toBeVisible()
})

test("the privacy officer opens the heaviest case and must give a reason to decide it", async ({
  page,
}) => {
  await logIn(page, OFFICER)
  await expect(page.getByRole("tab", { name: /Open \(\d+\)/ })).toBeVisible()
  await page.locator("tbody tr a").first().click()
  await expect(page.getByRole("heading", { name: "The facts" })).toBeVisible()
  await expect(page.getByText(/^Rule [A-Z_]+ raised this case/).first()).toBeVisible()

  await page.getByLabel("Decision").selectOption("follow-up")
  await page.getByLabel("Reason").fill("short")
  await page.getByRole("button", { name: "Record the decision" }).click()
  await expect(page.getByText("Write at least 10 characters")).toBeVisible()

  await page
    .getByLabel("Reason")
    .fill("Same home address and no care relationship; asking the nurse.")
  await page.getByRole("button", { name: "Record the decision" }).click()
  await expect(
    page.getByText("Same home address and no care relationship; asking the nurse.")
  ).toBeVisible()
  await expect(page.getByText("Needs follow-up").first()).toBeVisible()

  await page.getByRole("link", { name: "← Cases" }).click()
  await page.getByRole("tab", { name: /Decided/ }).click()
  await expect(page.getByRole("cell", { name: /Needs follow-up/ })).toBeVisible()
})

test("the privacy officer saves a rule change as a new version", async ({ page }) => {
  await logIn(page, OFFICER)
  await page.getByRole("link", { name: "Rules" }).click()
  await page.getByLabel(/Many charts in a day: more than/).fill("45")
  await page.getByRole("button", { name: "Save as a new version" }).click()
  await expect(page.getByText(/Saved as version \d+/)).toBeVisible()
})

test("a patient sees who looked at their record by role and department, never by name", async ({
  page,
}) => {
  // A made-up patient living at a nurse's address, whose chart the nurse opened three times.
  await logIn(page, "aaron.quintero.p289@example.test")
  await expect(page.getByRole("heading", { name: "Who looked at your record" })).toBeVisible()
  const rows = page.locator("tbody tr")
  await expect(rows).toHaveCount(3)
  await expect(rows.first()).toContainText("nurse")
  await expect(rows.first()).toContainText("Family Medicine")
  await expect(page.locator("table")).not.toContainText("Rosa")
  await expect(page.getByText(/beyond what HIPAA now requires/)).toBeVisible()
})
