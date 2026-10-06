// plane-monitor — Neon Function: device heartbeat ingest + health dashboard.
//
// Routes (one function, routed by method + path):
//   POST /beat?key=...   device posts a JSON snapshot each wake -> INSERT row
//   GET  /data           JSON: latest beat + aggregates + recent history
//   GET  /               self-contained HTML dashboard (polls /data every 30s)
//
// DATABASE_URL is injected by Neon at runtime. DEVICE_KEY guards /beat; it is
// read from the function env, falling back to the baked constant below (the one
// generated at deploy time) so the endpoint is never left open.
import { Pool } from "pg";

const DEVICE_KEY = process.env.DEVICE_KEY || "2e4c0877f66e2faab3b55aa07e6dbbe5";
const ONLINE_MIN = 12; // "online" if a beat arrived within this many minutes

const pool = new Pool({ connectionString: process.env.DATABASE_URL, max: 3 });
// node-postgres emits idle-client failures as 'error'; with no listener Node
// would treat it as an uncaughtException and kill the isolate. Swallow the
// expected idle drops (the pooler reclaims the connection).
pool.on("error", (err) => console.error("[pool]", err.message));

const json = (obj, status = 200) =>
  new Response(JSON.stringify(obj), {
    status,
    headers: { "content-type": "application/json" },
  });

export default {
  async fetch(request) {
    const url = new URL(request.url);
    const path = url.pathname;

    try {
      // ---- ingest ----------------------------------------------------------
      if (request.method === "POST" && path === "/beat") {
        const key =
          url.searchParams.get("key") || request.headers.get("x-device-key");
        if (key !== DEVICE_KEY)
          return new Response("forbidden", { status: 403 });

        let b;
        try {
          b = await request.json();
        } catch {
          return new Response("bad json", { status: 400 });
        }

        await pool.query(
          `INSERT INTO heartbeat
             (device_id, fw, boot_count, uptime_ms, batt_pct, wifi_rssi,
              http_code, num_states, credits, free_heap, plane_valid,
              callsign, dist_km, alt_ft, airline, model)
           VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16)`,
          [
            b.id ?? "unknown",
            b.fw ?? null,
            b.boot ?? null,
            b.up ?? null,
            b.batt ?? null,
            b.rssi ?? null,
            b.http ?? null,
            b.states ?? null,
            b.credits ?? null,
            b.heap ?? null,
            typeof b.valid === "boolean" ? b.valid : null,
            b.cs ?? null,
            b.dist ?? null,
            b.alt ?? null,
            b.al ?? null,
            b.md ?? null,
          ],
        );
        return new Response(null, { status: 204 });
      }

      // ---- data ------------------------------------------------------------
      if (request.method === "GET" && path === "/data") {
        const latest =
          (await pool.query(
            "SELECT * FROM heartbeat ORDER BY received_at DESC LIMIT 1",
          )).rows[0] || null;

        const agg = (
          await pool.query(`
            SELECT count(*)::int AS total,
                   count(*) FILTER (WHERE http_code = 200)::int AS ok,
                   count(*) FILTER (WHERE received_at > now() - interval '24 hours')::int AS total24,
                   count(*) FILTER (WHERE http_code = 200 AND received_at > now() - interval '24 hours')::int AS ok24
            FROM heartbeat`)
        ).rows[0];

        const recent = (
          await pool.query(`
            SELECT received_at, batt_pct, wifi_rssi, http_code, num_states,
                   credits, plane_valid, callsign, airline, model, dist_km,
                   alt_ft, boot_count
            FROM heartbeat ORDER BY received_at DESC LIMIT 30`)
        ).rows;

        let online = false;
        let secs_since = null;
        if (latest) {
          secs_since = Math.floor(
            (Date.now() - new Date(latest.received_at).getTime()) / 1000,
          );
          online = secs_since < ONLINE_MIN * 60;
        }

        return json({
          online,
          secs_since,
          online_threshold_min: ONLINE_MIN,
          latest,
          agg,
          recent,
        });
      }

      // ---- dashboard -------------------------------------------------------
      if (request.method === "GET" && (path === "/" || path === "")) {
        return new Response(HTML, {
          status: 200,
          headers: { "content-type": "text/html; charset=utf-8" },
        });
      }

      return new Response("not found", { status: 404 });
    } catch (e) {
      return json({ error: String((e && e.message) || e) }, 500);
    }
  },
};

const HTML = `<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Plane device monitor</title>
<style>
  :root { color-scheme: dark; }
  * { box-sizing: border-box; }
  body { margin:0; font:15px/1.5 system-ui,-apple-system,Segoe UI,Roboto,sans-serif;
         background:#0e1116; color:#e6edf3; padding:24px; }
  h1 { font-size:18px; margin:0 0 2px; }
  .sub { color:#8b949e; font-size:13px; margin-bottom:20px; }
  .badge { display:inline-flex; align-items:center; gap:10px; padding:10px 18px;
           border-radius:999px; font-weight:700; font-size:18px; margin-bottom:18px; }
  .badge .dot { width:12px; height:12px; border-radius:50%; }
  .online  { background:#0f2e1a; color:#3fb950; } .online .dot{ background:#3fb950; box-shadow:0 0 10px #3fb950; }
  .offline { background:#3a1416; color:#f85149; } .offline .dot{ background:#f85149; }
  .unknown { background:#21262d; color:#8b949e; } .unknown .dot{ background:#8b949e; }
  .grid { display:grid; grid-template-columns:repeat(auto-fit,minmax(170px,1fr)); gap:14px; margin-bottom:22px; }
  .card { background:#161b22; border:1px solid #30363d; border-radius:12px; padding:14px 16px; }
  .card .label { color:#8b949e; font-size:12px; text-transform:uppercase; letter-spacing:.04em; }
  .card .val { font-size:26px; font-weight:700; margin-top:4px; }
  .card .val small { font-size:14px; color:#8b949e; font-weight:400; }
  table { width:100%; border-collapse:collapse; font-size:13px; }
  th,td { text-align:left; padding:7px 10px; border-bottom:1px solid #21262d; white-space:nowrap; }
  th { color:#8b949e; font-weight:600; position:sticky; top:0; background:#0e1116; }
  .wrap { overflow:auto; border:1px solid #30363d; border-radius:12px; }
  .ok { color:#3fb950; } .bad { color:#f85149; }
  .muted { color:#8b949e; }
  .foot { color:#8b949e; font-size:12px; margin-top:16px; }
</style>
</head>
<body>
  <h1>✈️ Closest-Plane device monitor</h1>
  <div class="sub">Heartbeat health for the e-paper dashboard. Auto-refreshes every 30s.</div>
  <div id="badge" class="badge unknown"><span class="dot"></span><span id="badgeText">Loading…</span></div>
  <div class="grid" id="cards"></div>
  <div class="wrap"><table id="tbl">
    <thead><tr>
      <th>Time</th><th>Batt</th><th>WiFi</th><th>OpenSky</th><th>States</th>
      <th>Credits</th><th>Plane</th><th>Dist</th><th>Alt</th><th>Boot</th>
    </tr></thead><tbody></tbody>
  </table></div>
  <div class="foot" id="foot"></div>

<script>
const fmtAgo = s => s==null ? "—"
  : s<60 ? s+"s ago"
  : s<3600 ? Math.floor(s/60)+"m "+(s%60)+"s ago"
  : Math.floor(s/3600)+"h "+Math.floor((s%60))+"m ago";
const fmtTime = t => t ? new Date(t).toLocaleString() : "—";

async function load() {
  let d;
  try { d = await (await fetch("data", {cache:"no-store"})).json(); }
  catch (e) { document.getElementById("badgeText").textContent = "dashboard fetch failed"; return; }

  const badge = document.getElementById("badge");
  const bt = document.getElementById("badgeText");
  if (!d.latest) { badge.className="badge unknown"; bt.textContent="No heartbeats yet"; }
  else if (d.online) { badge.className="badge online"; bt.textContent="ONLINE · last seen "+fmtAgo(d.secs_since); }
  else { badge.className="badge offline"; bt.textContent="OFFLINE · last seen "+fmtAgo(d.secs_since); }

  const L = d.latest || {};
  const rate = d.agg && d.agg.total ? Math.round(100*d.agg.ok/d.agg.total) : null;
  const rate24 = d.agg && d.agg.total24 ? Math.round(100*d.agg.ok24/d.agg.total24) : null;
  const planeTxt = L.plane_valid
    ? (L.callsign||"?") + (L.airline ? " · "+L.airline : "")
    : "none";
  const cards = [
    ["Battery", L.batt_pct!=null ? L.batt_pct+"<small>%</small>" : "—"],
    ["WiFi signal", L.wifi_rssi!=null ? L.wifi_rssi+"<small> dBm</small>" : "—"],
    ["OpenSky now", L.http_code!=null ? (L.http_code===200?'<span class="ok">200 OK</span>':'<span class="bad">'+L.http_code+'</span>') : "—"],
    ["Success (24h)", rate24!=null ? rate24+"<small>%</small>" : "—"],
    ["Successful calls", d.agg ? d.agg.ok+'<small> / '+d.agg.total+'</small>' : "—"],
    ["OpenSky credits", L.credits!=null && L.credits>=0 ? L.credits : "—"],
    ["Last plane", '<span style="font-size:18px">'+planeTxt+'</span>'],
    ["Boot count", L.boot_count!=null ? L.boot_count : "—"],
  ];
  document.getElementById("cards").innerHTML = cards.map(c =>
    '<div class="card"><div class="label">'+c[0]+'</div><div class="val">'+c[1]+'</div></div>').join("");

  const tb = document.querySelector("#tbl tbody");
  tb.innerHTML = (d.recent||[]).map(r => {
    const code = r.http_code===200 ? '<span class="ok">200</span>'
      : r.http_code!=null ? '<span class="bad">'+r.http_code+'</span>' : '<span class="muted">—</span>';
    const plane = r.plane_valid ? (r.callsign||"?") : '<span class="muted">none</span>';
    return "<tr><td>"+fmtTime(r.received_at)+"</td><td>"+(r.batt_pct??"—")+"%</td><td>"+(r.wifi_rssi??"—")+
      "</td><td>"+code+"</td><td>"+(r.num_states??"—")+"</td><td>"+(r.credits??"—")+"</td><td>"+plane+
      "</td><td>"+(r.dist_km!=null?r.dist_km.toFixed(1)+" km":"—")+"</td><td>"+(r.alt_ft!=null?r.alt_ft+" ft":"—")+
      "</td><td>"+(r.boot_count??"—")+"</td></tr>";
  }).join("") || '<tr><td colspan="10" class="muted">No data</td></tr>';

  document.getElementById("foot").textContent =
    "Device: "+(L.device_id||"—")+(L.fw?" · fw "+L.fw:"")+" · refreshed "+new Date().toLocaleTimeString();
}
load();
setInterval(load, 30000);
</script>
</body>
</html>`;
