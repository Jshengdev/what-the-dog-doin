# SETUP: environment prep runbook (Saturday night, 2026-09-12)

Build window is tomorrow 9:30 AM to 4:00 PM PT. Tonight is wiring only: no app code. Every step has a command or tap, what success looks like, a read-only proof, a time-box, and the bail-out. Order is by risk: network, Hue, Tuya, dog, iMessage. Proxyman is optional and last.

Verified from this Mac tonight (about 23:50): Mac is `10.66.10.46/24` behind router `10.66.10.1`; the Hue bridge `001788fffe616851` is at `10.66.1.109:443` per `https://discovery.meethue.com/` and unreachable from here (TCP 443 closed, no ARP entry). Default `python3` is 3.14.3 with `python3.13` also installed; Node v25.9.0 (ABI 141); no bun, no openhue, no Proxyman; Xcode CLT present; Messages.app running; `chat.db` readable.

## 1. Network first (time-box 30 min)

Everything local (Hue CLIP v2, tinytuya LAN, the dog's WebRTC) needs the Mac, the bridge, the Tuya bulbs, and the dog on one subnet. Tonight they are split: Mac on `10.66.10.0/24`, bridge on `10.66.1.0/24`.

1. **Confirm the bridge IP in the Hue app.** Hue app > Settings tab (bottom right) > My Hue System > tap the (i) next to the bridge > IP address at the bottom of the info list (https://huetips.com/help/how-to-find-my-bridge-ip-address/). Success: it reads `10.66.1.109`. The app does not show an SSID: the bridge is wired, so the router its Ethernet cable enters owns `10.66.1.0/24`.
2. **Find which SSID lives on `10.66.1.0/24`.** Ask whoever owns the routers, or join each SSID and check:
```sh
ipconfig getifaddr en0            # want 10.66.1.x
netstat -rn | grep '^default '    # want a 10.66.1.x gateway
```
3. **Find which network the Tuya bulbs are on.** Smart Life app > the living room light > pencil icon top right > Device Information > IP (menu labels UNVERIFIED tonight). Tuya Wi-Fi bulbs are normally 2.4 GHz only (UNVERIFIED for this model).
4. **Pick one fix and do it.**
   - Fix A (fast, preferred): put the Mac, the phone, and tomorrow the dog on the bridge's network. If that SSID is weak where the demo runs, move the bridge's Ethernet cable to the `10.66.10.x` router instead; the bridge takes a new DHCP address, so re-run discovery below.
   - Fix B (slow fallback): Hue Remote API over the cloud (section 2c). Costs 45 to 90 min and adds cloud latency; only if Fix A is impossible tonight.
5. **Verify (read-only):**
```sh
curl -s https://discovery.meethue.com/          # [{"id":"001788fffe616851","internalipaddress":"10.66.1.109","port":443}]
ping -c 3 10.66.1.109
nc -z -G 2 10.66.1.109 443 && echo "443 open"
arp -n 10.66.1.109                               # a MAC address, not "no entry"
curl -k -s https://10.66.1.109/api/0/config      # unauthenticated: name, bridgeid, swversion, apiversion
```
Success: all five answer. Fail: still the wrong subnet; do not start section 2.

## 2. Philips Hue (time-box 30 min after network)

Do 2a first because the raw curl is what the agent calls and what the ledger records. The official CLIP v2 docs need a developer login (https://developers.meethue.com/develop/hue-api-v2/getting-started/); request shapes below are from the OpenAPI mirror at https://github.com/openhue/openhue-api (`src/auth/auth.yaml`, `src/light/schemas/LightPut.yaml`, `src/room/schemas/RoomGet.yaml`).

### 2a. CLIP v2 with curl

1. **Press the physical link button on the bridge, then within 30 s create the app key:**
```sh
curl -k -s -X POST https://10.66.1.109/api -d '{"devicetype":"wtdd#mac","generateclientkey":true}'
```
Success: `[{"success":{"username":"<long string>","clientkey":"<32 hex>"}}]`. Save the username as `HUE_APP_KEY` in `.env` (never commit). Fail: `[{"error":{"type":101,"address":"","description":"link button not pressed"}}]` means press the button and re-run. The bridge cert is self-signed, hence `-k`.
2. **List lights, rooms, zones:**
```sh
export HUE_APP_KEY=...
H='hue-application-key: '"$HUE_APP_KEY"
curl -k -s https://10.66.1.109/clip/v2/resource/light -H "$H" | jq '.data[] | {id, name: .metadata.name, on: .on.on, bri: .dimming.brightness}'
curl -k -s https://10.66.1.109/clip/v2/resource/room  -H "$H" | jq '.data[] | {id, name: .metadata.name, grouped: [.services[] | select(.rtype=="grouped_light") | .rid]}'
curl -k -s https://10.66.1.109/clip/v2/resource/zone  -H "$H" | jq '.data[] | .metadata.name'
```
Success: every demo light has a `light` id; every room has one `grouped_light` rid (rooms expose control through `services[]` of rtype `grouped_light`). Write the three demo lights and their ids into `.env`.
3. **Set on, off, brightness (one light, then a room):**
```sh
L=<light id>
curl -k -s -X PUT https://10.66.1.109/clip/v2/resource/light/$L -H "$H" -H 'Content-Type: application/json' -d '{"on":{"on":true},"dimming":{"brightness":50}}'
curl -k -s -X PUT https://10.66.1.109/clip/v2/resource/light/$L -H "$H" -H 'Content-Type: application/json' -d '{"on":{"on":false}}'
G=<grouped_light rid>
curl -k -s -X PUT https://10.66.1.109/clip/v2/resource/grouped_light/$G -H "$H" -H 'Content-Type: application/json' -d '{"on":{"on":true},"dimming":{"brightness":100}}'
```
Success: `{"data":[{"rid":"...","rtype":"light"}],"errors":[]}` and the bulb visibly changes. Brightness is 0 to 100; writing 0 sets the lowest level, not off (https://github.com/openhue/openhue-api/blob/main/src/common/Brightness.yaml).
4. **Read state back (the receipt):**
```sh
curl -k -s -o /dev/null -w 'hue GET %{time_total}s\n' https://10.66.1.109/clip/v2/resource/light/$L -H "$H"
curl -k -s https://10.66.1.109/clip/v2/resource/light/$L -H "$H" | jq '.data[0] | {on: .on.on, brightness: .dimming.brightness}'
```
Success: `{"on": false, "brightness": ...}` matches what you just set. This GET is what the lights agent logs after every write. Latency: record the `%{time_total}` you see tonight and put it in the reliability brief; do not assume a number.
5. **Rate limits.** Hue's guidance: about 10 commands per second to lights with a 100 ms gap, and at most 1 per second to groups (quoted from the login-gated "Hue System Performance" page in https://github.com/stefanvictora/hue-scheduler/blob/main/docs/advanced_command_line_options.md). The agent throttles to one light write per 100 ms and one grouped_light write per second; above that the bridge drops requests silently, which is exactly the failure the read-back must catch.

### 2b. openhue CLI (same bridge, for humans)

```sh
brew install openhue/cli/openhue-cli          # tap + formula, https://www.openhue.io/cli/installation
openhue setup --bridge 10.66.1.109            # prompts for the link button; writes ~/.openhue/config.yaml
openhue get lights --json
openhue get room
openhue set light "<light name>" --on --brightness 50
openhue set light "<light name>" --off
openhue set room "<room name>" --on --brightness 100 --transition-time 5s
openhue get light "<light name>" --json       # the read-back
```
Flags verified in https://github.com/openhue/openhue-cli (`cmd/set/set_light.go`, `cmd/set/set_room.go`, `cmd/setup/setup.go`). If `openhue setup` cannot find the bridge, `openhue discover` uses mDNS; the `--bridge` flag skips discovery.

### 2c. Hue Remote API (cloud OAuth, only if Fix A failed)

Official page needs a login: https://developers.meethue.com/develop/hue-api-v2/cloud2cloud-getting-started/. URLs below are cross-checked against https://github.com/michielpost/Q42.HueApi/blob/master/src/Q42.HueApi/RemoteAuthenticationClient.cs and https://github.com/jash90/hue-desktop (README).
1. Register a "Remote Hue API" app at https://developers.meethue.com/my-apps/ (any callback URL; you copy the code by hand). You get ClientId, ClientSecret, AppId. Approval time UNVERIFIED; budget 15 min.
2. Browser: `https://api.meethue.com/v2/oauth2/authorize?client_id=<ClientId>&response_type=code&state=wtdd&appid=<AppId>&deviceid=mac&devicename=wtdd`. Log in with the Hue account, copy `code` from the redirect URL.
3. Token:
```sh
curl -s -X POST https://api.meethue.com/v2/oauth2/token -u '<ClientId>:<ClientSecret>' -d 'grant_type=authorization_code&code=<code>'
```
4. Remote link button, then an app key (no physical button):
```sh
T=<access_token>
curl -s -X PUT  https://api.meethue.com/route/api/0/config -H "Authorization: Bearer $T" -d '{"linkbutton":true}'
curl -s -X POST https://api.meethue.com/route/api          -H "Authorization: Bearer $T" -d '{"devicetype":"wtdd#remote"}'
```
5. Every CLIP v2 call is then the same as 2a with base `https://api.meethue.com/route/clip/v2/resource/...` and both headers `Authorization: Bearer $T` and `hue-application-key`. The v1 `/oauth2` endpoints are deprecated. Expect slower round trips than local; measure with the same `-w` flag.

## 3. Tuya / Smart Life living room lights (time-box 45 min)

Path per the tinytuya README (https://github.com/jasonacox/tinytuya#setup-wizard---getting-local-keys) and Tuya's guide (https://developer.tuya.com/en/docs/iot/Platform_Configuration_smarthome?id=Kamcgamwoevrx).

1. **Account and project.** Sign in at https://iot.tuya.com. Cloud > Development > Create Cloud Project: Development Method `Smart Home`, Industry `Smart Home`, Data Center `Western America Data Center` (serves the US and Canada: https://developer.tuya.com/en/docs/iot/oem-app-data-center-distributed?id=Kafi0ku9l07qb). In the authorize dialog keep `IoT Core`, `Authorization Token Management`, `Smart Home Basic Service`, `Device Status Notification` and click Authorize (names drift between portal versions). The IoT Core trial expires (README: first subscription lasts one month, renewable by a short form); confirm it shows active on the Service API tab.
2. **Link the app account.** Project > Devices > Link App Account (older UI: "Link Tuya App Account") > Add App Account > choose `Automatic` and `Read Only Status` (commands still work) > OK shows a QR. Smart Life app > Me tab > scan icon top right > scan > Confirm. Success: the living room lights appear under Devices > All Devices. No devices: wrong data center. Check Smart Life > Me > Settings > Account and Security > Region, then edit the project's data center (Eastern America is the next guess). QR expired: regenerate it.
3. **Keys.** Project > Overview: `Access ID/Client ID` and `Access Secret/Client Secret`. Put them in `.env` as `TUYA_KEY`, `TUYA_SECRET`, `TUYA_REGION=us`.
4. **Install and pull local keys (Mac on the same subnet as the bulbs):**
```sh
python3.13 -m venv .venv && source .venv/bin/activate
pip install tinytuya requests
python -m tinytuya wizard        # answers: API ID, Secret, region "us", device id "scan"; say yes to poll
python -m tinytuya scan          # Address, Device ID, Version (3.3, 3.4 or 3.5) for every bulb on the LAN
```
Success: `devices.json` lists each bulb with `id`, `key` (16 chars), `ip`, `version`; `snapshot.json` shows live `dps`. Needs UDP 6666, 6667, 7000 and TCP 6668 open on the LAN. Add `devices.json`, `tuya-raw.json`, `snapshot.json`, `tinytuya.json` to `.gitignore` (they hold keys).
5. **Turn on, off, and read back, local (the demo path):**
```sh
python -m tinytuya get --name "<bulb name>"            # full status JSON, e.g. {"dps": {"20": true, "22": 1000}}
python -m tinytuya off --name "<bulb name>" && python -m tinytuya get --name "<bulb name>"
python -m tinytuya on  --name "<bulb name>" && python -m tinytuya get --name "<bulb name>"
```
And the Python the agent will use:
```python
import tinytuya, json
d = tinytuya.BulbDevice("<id>", "<ip>", "<local key>")
d.set_version(3.3)              # exactly what `scan` printed for this bulb
d.set_socketPersistent(True)
before = d.status()             # {'dps': {...}}; an 'Error' key means it did not happen
d.turn_on(); d.set_brightness_percentage(50)
after = d.status()
print(json.dumps({"before": before, "after": after}))
```
6. **Cloud (fallback when the bulbs stay on another subnet):**
```python
import tinytuya
c = tinytuya.Cloud(apiRegion="us", apiKey="<Access ID>", apiSecret="<Access Secret>", apiDeviceID="<any device id>")
print(c.getdevices())                         # ids, names, local keys
print(c.getstatus("<id>"))                    # [{'code': 'switch_led', 'value': True}, {'code': 'bright_value_v2', ...}]
print(c.sendcommand("<id>", {"commands": [{"code": "switch_led", "value": False}]}))
print(c.getstatus("<id>"))                    # the receipt
```
Use the `code` names that `getstatus` returns, not guesses. The trial plan limits cloud call volume (README caution); cloud is for the receipt read, not a tight loop.
7. **Gotchas.** `1106 permission deny` from the wizard or cloud: project data center does not match the app region or the calling IP; the fix in https://github.com/jasonacox/tinytuya/issues/96 was Western America plus region `us`. `28841101 No permissions. This API is not subscribed.` and `28841105 ... project is not authorized to call this API`: subscribe IoT Core and click Go to Authorize on the Service API tab (https://github.com/tuya/tuya-homebridge/issues/114). Version: pass the exact `3.3`, `3.4` or `3.5` from `scan`; 3.5 needs `pycryptodome` (the default; `pyaes` cannot do GCM). `Error 905 Device Unreachable`: wrong IP or subnet. `Error 914 Check device key or version`: the local key changed because the bulb was re-paired, or the version is wrong; re-run the wizard. Bulb DPS map: newer bulbs use DPS `20` (switch), `21` (mode), `22` (brightness 10 to 1000); older ones DPS `1` and `3` (25 to 255). `BulbDevice` detects the type; read `status()` once to see which DPS this bulb reports.

## 4. Other lights via Proxyman (optional, hard cap 45 min, only after 2 and 3 are green)

Generic method (https://docs.proxyman.com/debug-devices/ios-device):
1. `brew install --cask proxyman` (cask name UNVERIFIED; download from https://proxyman.com if it fails). Open it; note the port (default 9090) and the Mac's IP.
2. iPhone: Settings > Wi-Fi > the house SSID > Configure Proxy > Manual > Server = Mac IP, Port = 9090. Close every VPN on both devices.
3. iPhone Safari: open `http://proxy.man/ssl` > Allow > Settings > Profile Downloaded > Install. Then Settings > General > About > Certificate Trust Settings > enable full trust for Proxyman CA.
4. In Proxyman, right-click the light app's domain > Enable SSL Proxying. Toggle the light in its app; find the request; right-click > Copy as cURL; replay from the Mac; watch the bulb; then GET whatever the app polls for state and keep that as the read-back.
5. Delete the profile from the iPhone when done.

What breaks: certificate pinning (if bodies never decrypt, stop: https://proxyman.com/posts/2019-11-15-Can-we-bypass-ssl-pinning), signed requests (Tuya-style HMAC over client id, timestamp and nonce; a replay with a stale timestamp fails), and cloud-only devices with no LAN endpoint. If the app turns out to be a Tuya white-label, skip all this and pair the bulb into Smart Life instead. This is on the CUT list in `SCOPE-LOCK.md`; the 45 minutes is the whole budget.

## 5. Unitree dog (time-box 60 min; the riskiest connector)

Driver: `unitree_webrtc_connect` 2.2.0 (https://github.com/legion1581/unitree_webrtc_connect). Go2 firmware 1.1.15+ needs a per-device AES-128 key for the LAN handshake.

1. **Wi-Fi (STA) via the Unitree Go app.** Bind the dog, then choose the Wi-Fi connection mode and pick the house SSID from section 1 (the same one as the bridge). Manual wording: "Bind the robot: you can choose AP router mode and Wi-Fi connection mode"; to change later: Home page > Settings > Robot Settings > Switch Connection (Go2 User Manual, https://static.generation-robots.com/media/Go2-User-Manual.pdf). Where the app shows the firmware version and IP: UNVERIFIED tonight; the driver's typed errors tell you the firmware class anyway (step 5). STA mode is required so the Mac keeps internet for iMessage.
2. **Find its IP** (Mac on the same subnet):
```sh
python -c 'from unitree_webrtc_connect import discover_ip_sn; print(discover_ip_sn(timeout=3, device_type="Go2"))'
arp -a | grep -v incomplete      # fallback: look for the new device on the LAN
```
Success: `{'B42D2000XXXXXXXX': '10.66.x.y'}`. Fail: `{}` means a different subnet, multicast blocked, or the dog is still in AP mode.
3. **Install (macOS notes).** `pyaudio` 0.2.14 has no Python 3.14 wheel and no macOS arm64 wheel on PyPI, so it builds from source against Homebrew portaudio; every other dependency has 3.13 wheels (checked tonight). Use the 3.13 venv from section 3. The examples are not in the wheel, so clone the repo.
```sh
brew install portaudio
source .venv/bin/activate && pip install unitree_webrtc_connect
git clone https://github.com/legion1581/unitree_webrtc_connect.git vendor/unitree_webrtc_connect
```
4. **Fetch the AES key** (the Unitree account the dog is bound to):
```sh
unitree-fetch-aes-key --email <email> --password '<password>' --device-type Go2
export UNITREE_ROBOT_IP=<ip from step 2>
export UNITREE_AES_128_KEY=<32 hex chars>
```
Put both in `.env`; never log the key. Firmware below 1.1.15 needs no key (the driver handles the static key itself).
5. **Read-only verification: sport mode state.** Quit the Unitree Go app on the phone first (one WebRTC client at a time; a second one gets `RobotBusyError`).
```sh
python vendor/unitree_webrtc_connect/examples/go2/data_channel/sportmodestate/sportmodestate.py
```
Success: a refreshing screen with `Mode`, `Position`, `Velocity`, `IMU - RPY`, updating live. Typed errors: `AesKeyRequiredError` means firmware is 1.1.15+ and the key was not picked up (pass `aes_128_key=os.environ["UNITREE_AES_128_KEY"]` to the constructor), `AesKeyRejectedError` means wrong key, `LocalSignalingPortError` means neither 9991 nor 8081 answered at that IP (wrong IP or subnet).
6. **Camera:**
```sh
python vendor/unitree_webrtc_connect/examples/go2/video/camera_stream/display_video_channel.py
```
Success: an OpenCV window showing the front camera. This is the frame source for the vision step.
7. **First write: Hello.** `examples/go2/data_channel/sportmode/sportmode.py` reads the motion switcher (api 1001), switches to `normal` if needed (api 1002, the dog stands up), sends `Hello`, then walks forward and back at 0.5 m/s for 3 s each and switches to AI mode. Copy it and delete everything after the Hello block before running. Before running: battery above 30% in the app (our rule, not Unitree's), at least 2 m of clear floor around the dog (manual), the phone in someone's hand ready to stop it.
8. **If discovery or connect fails:** confirm subnet (`ipconfig getifaddr en0` vs the dog's IP), power-cycle the dog, re-check STA mode in the app, and as a last resort join the dog's hotspot `GO2-XXXXXX` and use `WebRTCConnectionMethod.LocalAP` to prove the driver. The Mac loses internet in that mode, so it is a smoke test, not the demo topology.

## 6. iMessage (time-box 30 min)

SDK: https://github.com/photon-hq/imessage-kit (v3.0.0, Node >= 20). This Mac: Node v25.9.0, Messages.app running, `chat.db` readable, group chat ids in the macOS 26 `any;+;<hex>` form.

1. **Install.** better-sqlite3 13.0.3 ships `prebuilds/darwin-arm64.node` inside its npm tarball (Node >= 22), so no native build:
```sh
cd ~/code/what-the-dog-doin && npm init -y >/dev/null && npm install @photon-ai/imessage-kit better-sqlite3
# or: brew install bun && bun add @photon-ai/imessage-kit     (bun needs no extra deps)
```
2. **Full Disk Access.** Already granted to this terminal; re-prove it in the terminal you will use tomorrow (FDA is per app):
```sh
sqlite3 -readonly ~/Library/Messages/chat.db "select count(*) from chat;"   # a number (327 tonight), not "unable to open"
pgrep -x Messages >/dev/null && echo "Messages running"                    # and signed in to the Apple ID
```
If it fails: System Settings > Privacy & Security > Full Disk Access > add the terminal app, restart it.
3. **Create the test group.** In Messages.app start a new group with Johnny plus one housemate, name it `wtdd test`. Rule: every send tonight and during the build goes to `wtdd test`. Nothing goes to `THE CASTLE` until the recorded demo, and then only behind the gate. (`CASTLE Notifications ` also exists as a group, with a trailing space in its name; do not confuse the two.)
4. **Find chat ids:**
```ts
import { IMessageSDK } from '@photon-ai/imessage-kit'
const sdk = new IMessageSDK()
for (const c of await sdk.listChats({ kind: 'group', search: 'wtdd', limit: 5 })) console.log(c.chatId, c.name)
for (const c of await sdk.listChats({ kind: 'group', search: 'CASTLE', limit: 5 })) console.log(c.chatId, c.name)
await sdk.close()
```
Success: `any;+;<hex>  wtdd test`. Put it in `.env` as `IMESSAGE_TEST_CHAT_ID`; the CASTLE id goes in as `IMESSAGE_DEMO_CHAT_ID` and is only read by the gate. Never hand-write a group id.
5. **Watch, send, confirm** (one script; then text `what the dog doin` from the housemate's phone):
```ts
const text = `wtdd ping ${Date.now()}`
await sdk.startWatching({
  onGroupMessage: (m) => console.log('[wtdd:in]', m.chatId, m.participant, m.text, m.id),
  onFromMeMessage: (m) => { if (m.text === text) console.log('[wtdd:landed]', m.id, 'delivered', m.isDelivered) },
  onError: (e) => console.error('[wtdd:watch]', e),
})
await sdk.send({ to: process.env.IMESSAGE_TEST_CHAT_ID!, text })
```
Success: `[wtdd:in]` fires for the housemate's message with a `participant`; `[wtdd:landed]` prints a row id within a few seconds. `send()` resolves when `osascript` exits, so the `onFromMeMessage` row is the receipt the ledger stores (message id plus `isDelivered`).
6. **Zero-dependency fallback** (poll plus AppleScript; Apple stores dates as nanoseconds since 2001-01-01):
```sh
sqlite3 -readonly ~/Library/Messages/chat.db "select m.ROWID, datetime(m.date/1000000000 + 978307200, 'unixepoch', 'localtime') ts, m.is_from_me, h.id sender, m.text from message m join chat_message_join j on j.message_id = m.ROWID join chat c on c.ROWID = j.chat_id left join handle h on h.ROWID = m.handle_id where c.display_name = 'wtdd test' order by m.date desc limit 5;"
osascript -e 'tell application "Messages"
  set targetChat to chat id "any;+;<hex from step 4>"
  send "wtdd osascript test" to targetChat
end tell'
```
The query was run tonight against `THE CASTLE` and returned rows dated 2026-09-12 23:02. `text` can be NULL when the body only lives in `attributedBody`; the SDK decodes that, the raw query does not. The AppleScript form is the one the SDK itself generates (`chat id` targets an existing group).

## 7. Tonight's checklist

| Connector | Done when | Verified by | Owner |
|---|---|---|---|
| Network | Mac IP is `10.66.1.x` (or the bridge moved to `10.66.10.x`) | `curl -k -s https://10.66.1.109/api/0/config` returns JSON | Johnny |
| Hue | App key in `.env`; three demo light ids known; one PUT then GET matched | section 2a step 4 GET | Johnny |
| Tuya | `devices.json` has the living room bulbs; local off then on read back | `python -m tinytuya get --name ...` | Johnny |
| Dog | STA mode; IP and AES key in `.env`; state stream and camera seen; one Hello | `sportmodestate.py` prints `Position` | Johnny |
| iMessage | `wtdd test` group id in `.env`; one message in and one out both logged | `[wtdd:landed]` line | Johnny |
| Proxyman | skipped unless Hue and Tuya are both green | n/a | Johnny |

Morning-of, 15 minutes at 9:15:
1. `ipconfig getifaddr en0` still `10.66.1.x`; `curl -k -s https://10.66.1.109/api/0/config`.
2. Hue: GET one light with the key; `openhue set light "<name>" --off` then `--on`; GET again.
3. Tuya: `python -m tinytuya get --name "<bulb>"`; bulbs keep their IP only if DHCP did (re-run `scan` on `905`).
4. Dog: charged, on the house Wi-Fi, phone app closed; `discover_ip_sn`; `sportmodestate.py` for 10 s.
5. iMessage: `pgrep -x Messages`; one `wtdd ping` into `wtdd test`; `[wtdd:landed]` seen.
6. `.env` loaded, `ledger.jsonl` empty, `THE CASTLE` id still gated off.
