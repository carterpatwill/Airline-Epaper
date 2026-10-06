# Plane device monitor — remote health dashboard

A heartbeat-based health check for the "Closest Plane Overhead" e-paper device.
The device deep-sleeps between 1–5 min wakes, so it can't host anything. Instead,
on each wake (while WiFi is still up) it POSTs a tiny JSON snapshot to a public
**Neon Function**, which stores it in Postgres and serves a dashboard you can
open from anywhere to check in.

```
device (each wake) --HTTPS POST /beat--> Neon Function --> Postgres (heartbeat)
your browser       --HTTPS GET  /    --> Neon Function --> dashboard HTML
                   --HTTPS GET  /data--> Neon Function --> JSON (latest + stats)
```

Decisions already made: **cloud free tier (Neon)**, **dashboard-only** (no push
alerts). Full approved plan: `~/.claude/plans/serialized-orbiting-snowflake.md`.

---

## STATUS — where we left off (2026-10-05)

### ✅ Done
1. **Neon project created** (free tier):
   - Project ID: `raspy-breeze-46225705`  (name: `plane-monitor`)
   - Region: `aws-us-east-1` (a region where Neon Functions are supported)
   - Default branch ID: `br-little-pine-b8ziwwqm`  (name: `main`)
2. **`heartbeat` table + index created** on the default branch. Schema is in
   `schema.sql` (this folder) — already applied, kept for reference.
3. **Function code written & bundled**:
   - Source (version-controlled, reviewable): `monitor/src/index.js`
   - Bundled with esbuild → zip built & syntax-checked in the scratchpad.
4. **Device key generated**: `2e4c0877f66e2faab3b55aa07e6dbbe5`
   - This is baked into `src/index.js` as the `DEVICE_KEY` fallback constant AND
     must be used by the firmware. Guards `POST /beat` (`?key=...`).

### ⬜ Remaining (pick up here)

#### Step 1 — Deploy the Neon Function
The function wasn't deployed yet. Two ways:

**Option A — rebuild + deploy the zip** (from this folder):
```bash
cd monitor
npm install pg esbuild          # if node_modules isn't present
mkdir -p dist
./node_modules/.bin/esbuild src/index.js --bundle --platform=node \
  --target=node24 --format=esm \
  --banner:js="import{createRequire as ___cr}from'module';import{fileURLToPath as ___f}from'url';import{dirname as ___d}from'path';const require=___cr(import.meta.url);const __filename=___f(import.meta.url);const __dirname=___d(__filename);" \
  --outfile=dist/index.mjs
zip -j function.zip dist/index.mjs
```
Then deploy the zip. The entry file **must** be named `index.mjs` (the runtime
looks for that). Deploy via one of:
   - **Neon MCP** `deploy_function` with `branch_id=br-little-pine-b8ziwwqm`,
     `slug=planemonitor`, `runtime=nodejs24`, and `zip`=base64 of `function.zip`.
     (Base64 is ~56 KB — awkward to pass through the model inline. The CLI below
     is easier.)
   - **Neon CLI** (cleaner — deploys the file directly, no base64):
     ```bash
     neon functions deploy planemonitor --src dist/index.mjs \
       --project-id raspy-breeze-46225705 --branch br-little-pine-b8ziwwqm \
       --env DEVICE_KEY=2e4c0877f66e2faab3b55aa07e6dbbe5
     ```
     (CLI must be logged in: `neon auth`. The `--env` is optional since the key
     is baked in as a fallback, but passing it is cleaner.)

Note: slug must match `^[a-z0-9]{1,20}$` — use `planemonitor` (no hyphen).

#### Step 2 — Grab the function URL
```bash
neon functions get planemonitor --project-id raspy-breeze-46225705 \
  --branch br-little-pine-b8ziwwqm       # look at invocation_url
```
Form: `https://br-little-pine-b8ziwwqm-planemonitor.compute.<cell>.us-east-1.aws.neon.tech`

#### Step 3 — Smoke-test the backend (before touching the device)
```bash
FN="https://<invocation_url>"
# wrong key -> 403
curl -s -o /dev/null -w "%{http_code}\n" -X POST "$FN/beat?key=nope" -d '{}'
# good beat -> 204
curl -s -o /dev/null -w "%{http_code}\n" -X POST "$FN/beat?key=2e4c0877f66e2faab3b55aa07e6dbbe5" \
  -H 'content-type: application/json' \
  -d '{"id":"planewatch-1","fw":"1.0","boot":1,"batt":87,"rssi":-61,"http":200,"states":142,"credits":3987,"valid":true,"cs":"TEST123","al":"Southwest","dist":3.4,"alt":9500,"md":"Boeing 737-800"}'
curl -s "$FN/data" | head -c 600      # test beat should appear, online:true
open "$FN/"                            # dashboard in browser
# cleanup the synthetic row later:  DELETE FROM heartbeat WHERE callsign='TEST123';
```

#### Step 4 — Firmware heartbeat (not started)
Add the device side. See the approved plan for detail; summary:
- **`firmware/src/core/config.h`** (+ `config.example.h` with placeholders) — add:
  ```c
  #define TELEMETRY_ENABLED   1
  #define DEVICE_ID           "planewatch-1"
  #define DEVICE_KEY          "2e4c0877f66e2faab3b55aa07e6dbbe5"   // matches function
  #define TELEMETRY_BEAT_URL  "https://<invocation_url>/beat"       // from Step 2
  ```
  (config.h is gitignored — real key/URL stay private. example.h gets dummies.)
- **`firmware/src/net/net.h` / `net.cpp`** — add `void sendHeartbeat();`.
  Mirror the existing POST-over-TLS pattern in `getOpenSkyToken()`
  (net.cpp ~line 125): `WiFiClientSecure` + `setInsecure()` + `HTTPClient`
  `begin/addHeader("Content-Type","application/json")/POST(body)/end`, 8s timeout.
  No-op unless `TELEMETRY_ENABLED` and `WiFi.status()==WL_CONNECTED`. Build the
  JSON body with `snprintf` (no ArduinoJson needed) from the globals that are
  already populated each cycle: `g_bootCount`, `millis()`, `g_battPct`,
  `g_wifiRssi`, `g_httpCode`, `g_numStates`, `g_credits`, `ESP.getFreeHeap()`,
  and from `g_plane` (include `state.h`): `valid`, `callsign`, `distKm`, `altFt`,
  `airline`, `model`. POST to `TELEMETRY_BEAT_URL "?key=" DEVICE_KEY`.
  JSON field names must match the function: `id,fw,boot,up,batt,rssi,http,states,
  credits,heap,valid,cs,dist,alt,al,md`.
- **Boot counter** — add `RTC_DATA_ATTR uint32_t g_bootCount;` in `net.cpp`
  (extern in `net.h`), next to the existing RTC token vars (net.cpp ~line 21).
  Increment once per wake in `setup()`.
- **`firmware/src/main.cpp`** —
  - `setup()`: `g_bootCount++;` before `runCycle()`.
  - Call `sendHeartbeat()` at the END of `runCycle()`'s success path (after
    `drawCurrentScreen()`, ~line 104) **and** in the **no-plane branch** before
    its `return` (~line 75), so an OpenSky outage still reports
    "device online, OpenSky failing" (the most useful signal while it's away).
    The no-WiFi branch can't send; its silence is itself the offline signal.

#### Step 5 — Build, flash, verify
```bash
cd firmware && pio run            # clean build
pio run -t upload                 # or the esp32-flash skill
```
After the next wake, refresh the dashboard → a real beat appears with live
battery, RSSI, OpenSky status, and the last plane. To test offline detection,
power the device off; the badge flips to OFFLINE within ~12 min.

---

## Files in this folder
- `src/index.js` — the Neon Function (ingest + /data + dashboard HTML). **Edit
  here**, then rebuild/redeploy (Step 1).
- `schema.sql` — the `heartbeat` table DDL (already applied; reference only).
- `DEVICE_KEY.txt` — the generated shared secret (gitignore this if committing).

## Reference IDs (copy/paste)
| Thing | Value |
|---|---|
| Neon project ID | `raspy-breeze-46225705` |
| Default branch ID | `br-little-pine-b8ziwwqm` |
| Function slug (planned) | `planemonitor` |
| Device key | `2e4c0877f66e2faab3b55aa07e6dbbe5` |
| Device ID | `planewatch-1` |
| Region | `aws-us-east-1` |

## Notes / gotchas
- Neon `run_sql` runs ONE statement per call — split multi-statement DDL.
- Function zip entry file must be `index.mjs` or `index.js`; deps must be bundled
  (esbuild), hence the `--banner` that restores `require/__filename/__dirname`
  for `pg`.
- The firmware already uses `client.setInsecure()` for TLS, which is fine against
  Neon's valid cert — `sendHeartbeat()` can do the same.
- Cost is trivial: ~288 beats/day at 5-min cadence, a few hundred bytes each;
  Neon free tier + scale-to-zero. No impact on the OpenSky credit budget.
