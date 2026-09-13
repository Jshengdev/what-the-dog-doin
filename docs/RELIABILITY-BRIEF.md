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

## Measured so far (2026-09-13, from ledger.jsonl)

| What | Result | Regenerate |
|---|---|---|
| iMessage post + read-back into the housemates group | 2 of 2 confirmed (text guid, photo guid), 0 duplicates | `python -m wtdd.chat send/photo` then `chat.post` rows |
| Hue cloud route reachability | probe ok: 7 lights, 4 in Living room | `python -m wtdd.hue probe` |
| Hue set + read-back, one light | ok, ~0.8 s per set incl. GET read-back | `python -m wtdd.hue set special --bri 50` |
| Hue rate limit, cloud route | 15 of 15 quick sets ok, no 429, median 794 ms | `python -m wtdd.hue burst special --n 15` |
| Hue alternating red/blue signal | ok, read back `signal: alternating` | `python -m wtdd.hue signal special --seconds 5` |
| Tuya WT1 LED strip, local protocol 3.5 (living room) | probe ok at 10.66.10.44; on, dim 30, temp 80, 17-step fade 5 to 100 over 4 s, all read back (dps 20/22/23) | `python -m wtdd.tuya probe`, `dim 30`, `temp 80`, `fade --start 5 --end 100 --seconds 4` |
| Corridor sweep from the map page (dot crosses zones a, b, c) | a on, b on, a off (lag), c on + strip on, b off, c off + strip off: 8 writes, 8 read-backs, 0 failures | press "run the corridor" at http://127.0.0.1:7788/ then `python -m wtdd.tools ledger_tail` |
| Text to lights, whole chain | wake, "turn the lights off", "lights on pls", stop: living room zone (4 lights) off then on, read back, 2.7 s per zone change | `python -m wtdd.chat simulate "what the dog doin" "lights off" "lights on" "stop"` |
