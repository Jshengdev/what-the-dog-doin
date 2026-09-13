# GOAL: lights (Philips Hue)

**Goal.** From this Mac, programmatically pair with the Hue bridge, list every light on it (Johnny says there are four around the house), read each light's state back (on, brightness, color if any, reachable), set state (on, off, brightness, color), and run the native `alternating` red and blue signal. Every call writes a ledger row via `wtdd.ledger.step`.

**Loop.** Build `wtdd/hue/__main__.py` so `python -m wtdd.hue <cmd>` works, run `probe`, read the ledger, fix, repeat until every done criterion below has a passing command in the transcript.

**Commands.** `probe` (discovery + reachability + key check, never throws before printing what is blocked) · `pair` (link-button flow, writes HUE_APP_KEY into .env) · `lights` (table: id, name, room, on, bri, reachable) · `read <id|name>` · `set <id|name> --on/--off [--bri 0-100] [--xy x,y]` · `signal <id|name> --seconds N` (alternating red/blue) · `zone <name> --on/--off` (a zone = list of light ids from `wtdd/hue/zones.json`).

**Done when.** `probe` reports the bridge reachable and the key valid; `lights` prints all lights with live state; `set` then `read` shows the change in state_after; `signal` runs on a color bulb; every one of these has a ledger row with latency.

**Facts.** Bridge id `001788fffe616851` at `10.66.1.109` (meethue discovery); this Mac is on `10.66.10.0/24` and cannot reach it as of 00:40. Local CLIP v2 over HTTPS with `hue-application-key` header (self-signed cert: verify=False is acceptable on the LAN, log it once). Rate guidance: about 10 light commands per second, 1 grouped_light per second. See `docs/SETUP.md` §1 to §2 for the exact curls.

**Johnny must do (prompt him, do not wait silently).** 1) Put this Mac on the bridge's subnet (or move the bridge's Ethernet to this router). 2) Press the physical link button when `pair` says so. 3) Say which four lights are which rooms so `zones.json` gets real names.

**Never.** No fallbacks, no cached light state pretending to be live, no writes to lights that were not named in the command, no git commit.
