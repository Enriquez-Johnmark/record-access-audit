import { describe, expect, it } from "vitest"

import { actionLabel, checkLabel, outcomeLabel, ruleLabel } from "@/lib/labels"

describe("labels", () => {
  it("names each code in plain words", () => {
    expect(ruleLabel("NO_RELATIONSHIP")).toBe("No care relationship")
    expect(outcomeLabel("possible breach").label).toBe("Possible breach")
    expect(checkLabel("accuses")).toBe("Decides or accuses")
    expect(actionLabel("decision.recorded")).toBe("Decision recorded")
  })

  it("shows an unknown code as it is rather than hiding it", () => {
    expect(ruleLabel("SOMETHING_NEW")).toBe("SOMETHING_NEW")
    expect(outcomeLabel("odd")).toEqual({ label: "odd", variant: "secondary" })
  })
})
