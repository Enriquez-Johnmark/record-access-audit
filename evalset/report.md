# Measurement

Made by `record-access-audit measure` from the made-up log (`evalset/labels.json`), the hand-written bad summaries (`evalset/bad-summaries.json`) and Claude's recorded summaries (`evalset/recorded/summaries.json`). Everyone in it is made up. It measures the tool on a log built to test it; it says nothing about catching real snooping.

## Flagging (I1)

- Planted cases flagged with every rule they were planted for: **31 of 31**.
- Innocent look-alikes flagged anyway (false alarms): **3 of 21**, all of them a nurse covering a visit the record doesn't show.
- Charts opened that the clinic's own data accounts for: **3204 of 3262 (98%)**.

| Rule | Cases raised | Of them planted | Precision | Planted cases expected | Found | Recall |
|---|---|---|---|---|---|---|
| `OWN_RECORD` | 3 | 3 | 100% | 3 | 3 | 100% |
| `ROLE_NO_CHARTS` | 3 | 3 | 100% | 3 | 3 | 100% |
| `NO_RELATIONSHIP` | 29 | 26 | 90% | 26 | 26 | 100% |
| `SAME_LAST_NAME` | 5 | 5 | 100% | 5 | 5 | 100% |
| `SAME_ADDRESS` | 4 | 4 | 100% | 4 | 4 | 100% |
| `COWORKER` | 4 | 4 | 100% | 4 | 4 | 100% |
| `VIP` | 4 | 4 | 100% | 4 | 4 | 100% |
| `DECEASED` | 2 | 2 | 100% | 2 | 2 | 100% |
| `AFTER_CARE_ENDED` | 3 | 3 | 100% | 3 | 3 | 100% |
| `OUTSIDE_SHIFT` | 3 | 3 | 100% | 3 | 3 | 100% |
| `HIGH_VOLUME` | 2 | 2 | 100% | 2 | 2 | 100% |

## Bad summaries (I2)

**30 of 30** hand-written bad summaries are blocked, each by exactly the check it was written to trip.

| Check | Bad summaries | Blocked by it |
|---|---|---|
| `accuses` | 6 | 6 |
| `cites-no-fact` | 6 | 6 |
| `clinical` | 6 | 6 |
| `not-in-facts` | 6 | 6 |
| `too-long` | 6 | 6 |

## Claude's summaries (I3)

Claude (claude-sonnet-5-5) wrote a summary of every case from its numbered facts; recorded once with the owner's key and replayed here. **32 of 34 (94%) pass every check.**

On the first recorded run, 29 of 34 passed. Three of the five blocked named the case's own patient in a sentence citing a fact without that ID; the check now lets a summary name its own case's staff member and patient, with a test. The two still blocked are listed below: one counts rules itself ("Two rules raised the case"), which the instructions forbid; one uses "two" for two people, a false alarm the check keeps because it can't tell the two uses apart.

| Case | Status | Problems |
|---|---|---|
| S-012/P-294 | blocked | not-in-facts: two (to check 2) |
| S-027/P-213 | blocked | not-in-facts: Two (summary sentence 4) |
