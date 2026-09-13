# System and reliability brief: what-the-dog-doin

Submission document. Filled during the build as facts land. Every number here is read from a ledger or an eval output and regenerates with the command written next to it.

## What it does

One paragraph: the job, the trigger, the result.

## System

Trigger, then step 1 (app A), step 2 (app B), step 3 (app C), then the result. Diagram or numbered list, with the model and the agent loop named.

## Apps connected

| App | Operation | Read / Write | How auth works | Live or DEMO_CACHE |
|---|---|---|---|---|
| | | | | |

## How we know it works

### Receipts

Where the ledger lives, what one record looks like, and the command that regenerates it.

### Evals

| Scenario | What it checks | Status | Command |
|---|---|---|---|
| | | | |

### Trials (pass / fail / unsafe)

Each scenario run at least three times. Graded from before-and-after state read back from the apps and devices, never from the agent's own report.

| Scenario | Trials | Pass | Fail | Unsafe | Command |
|---|---|---|---|---|---|
| | | | | | |

### Prohibited actions (asserted after every run)

| Never | Asserted how | Violations |
|---|---|---|
| | | |

### Numbers

| Metric | Value | Source command |
|---|---|---|
| | | |

## Failure modes

| Failure | Detected how | Handled how | Eval, or known ceiling |
|---|---|---|---|
| | | | |

## Known ceilings and DEMO_CACHE inventory

Output of `grep -rn "DEMO_CACHE:" .` with one line each on what is cached and how to run it live.

## Idempotence

What re-running the agent does and does not do to real accounts.
