# SCOPE-LOCK: the one agent

Johnny fills this. Claude sharpens it. Nothing gets built until §1 through §4 are filled and §7 is signed.

**Status: OPEN** (2026-09-12)

## 1. The job (one sentence)

Who is it for, what triggers it, and what is true afterwards that was not true before.

>

## 2. The apps (at least three)

| # | App | Role in the job | Read / Write | Auth we have today | Risk (auth, rate limit, odd API) |
|---|---|---|---|---|---|
| A | | | | | |
| B | | | | | |
| C | | | | | |

## 3. The steps (numbered, one app each)

1.
2.
3.

## 4. Crystal I/O

- **Trigger** (the exact input):
- **Result** (the exact visible output):
- **Receipt** (what the ledger shows for one successful run):

## 5. Sharpening questions (answer before building)

- What would have to be true for this to work?
- What is the test that would falsify it?
- What is the smallest version that would prove the bet?
- Why these three apps and not any other three?
- What is unique about doing this on our stack?

## 6. CUT list (explicitly not building)

-

## 7. Stack lock

- Runtime / language:
- Agent loop (model, tool calling):
- App connectors (SDKs, MCP, raw API):
- Where the ledger lives:
- Where evals live and the one command that runs them:

Signed: ________ (date)

## Feasibility check (2026-09-12, verified from this Mac)

Facts found before the lock. Not decisions.

| App | What was verified | Status | Risk / what has to be true |
|---|---|---|---|
| iMessage | `~/Library/Messages/chat.db` is readable from this process (327 chats; Full Disk Access already granted). Most active named group chat: "THE CASTLE" (last message 2026-09-12 20:51). Free `@photon-ai/imessage-kit` reads chat.db via WAL watching, sends to a group `chatId` via AppleScript, and `onGroupMessage` carries sender identity. The `doubles` repo already wraps the paid Photon kit (`src/spectrum/imessage.ts`, needs `IMESSAGE_SERVER_URL` + `IMESSAGE_API_KEY`). | GREEN | Messages.app must be running and signed in on the demo Mac. Sends are fire-and-forget; confirm via the from-me watcher. Tapbacks and threaded replies need the paid kit. Real housemates are on the other end: every write must be idempotent and gated. |
| Philips Hue | A bridge (id `001788fffe616851`) is registered under this public IP at `10.66.1.109`. This Mac is on `10.66.10.0/24`. TCP 443 and 80 to the bridge fail; no ARP entry. | YELLOW | The Mac and the bridge must be on the same subnet (join the router the bridge is wired to, or move the bridge). Then one link-button press to pair. Local CLIP v2 API or `openhue` CLI (`brew install openhue/cli/openhue-cli`). Fallback is the Hue Remote API (cloud OAuth, developer account, slower to set up). |
| Tuya (Smart Life app) | No prior code in any repo. Path: Tuya IoT Platform project, link the Smart Life app by QR, `python -m tinytuya wizard` to pull device ids and local keys, then local LAN control or `tinytuya.Cloud`. | YELLOW | Developer account approval and the app-link step are the friction. Which physical devices are on the app decides what the agent can actually do (plug, bulb, heater, fan). Same-LAN needed for local control. |
| Unitree robot dog | No prior code in any repo. `unitree_webrtc_connect` (PyPI) drives Go2 Air/Pro/Edu and G1 over Wi-Fi with the same WebRTC protocol as the Unitree app, no jailbreak. Same LAN or AP mode. | UNKNOWN | Is there a physical dog available on 2026-09-13, which model, and on which network? Without a dog in the room, "what the dog doin" has no dog. |

Sources: https://github.com/photon-hq/imessage-kit · https://github.com/legion1581/unitree_webrtc_connect · https://github.com/jasonacox/tinytuya · https://www.openhue.io/cli · https://discovery.meethue.com/

## Decision log

- 2026-09-12: repo created. Idea not yet articulated.
- 2026-09-12 (Johnny, verbatim): "a basic idea i have is just something to connect an agent to imessage group chats about housemates, then it connects to phillips hue if possible and this tuya app on my phone and then finally a unitree robo dog and want to call the project what hte dog doin. and its just an agent that acts as the intermediate for your smart home"
- 2026-09-12 (Johnny, verbatim): "i have a phsyical unitree dog i signedi nto phillip and tuya does tha wok?> the devices tuya is just hte living room lights. THe overall concept here is real world housemate enviornemtn. when you live iwth housemates and want the dog to go find out what you doin. something liek that"
  - Resolved: physical Unitree dog exists (model not yet stated). Tuya devices = the living room lights only. Signed into the Hue app and the Tuya app on the phone.
