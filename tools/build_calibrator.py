#!/usr/bin/env python3
"""
Generate a self-contained map-calibration page (map_calibrate.html) for locating
SanFranGrey.png in real-world coordinates.

It renders the EXACT 800x480 crop the device shows (same cover_resize as
build_map.py), embedded as a data URI so the file works by double-click with no
server. You click points on the map, tag each with a known lat/lon (the airports
from Airports.md are pre-loaded in a dropdown), and it solves the pixel<->lat/lon
transform via least squares, reports the per-point error in miles, and prints the
firmware constants (image corner bounds) ready to paste.

Run from the repo root:
    python3 tools/build_calibrator.py
Then open map_calibrate.html in any browser.
"""
import base64, io, json, os, re
from PIL import Image
from build_map import cover_resize, W, H   # same crop as the device bitmap

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC  = os.path.join(ROOT, "assets", "map", "SanFranGrey.png")
AIRPORTS_MD = os.path.join(ROOT, "Airports.md")
OUT  = os.path.join(ROOT, "map_calibrate.html")


def load_airports():
    pts = []
    if not os.path.exists(AIRPORTS_MD):
        return pts
    pat = re.compile(r"^\s*(.+?)\s*=\s*(-?\d+\.\d+)\s*,\s*(-?\d+\.\d+)")
    with open(AIRPORTS_MD) as f:
        for line in f:
            m = pat.match(line)
            if m:
                pts.append({"name": m.group(1).strip(),
                            "lat": float(m.group(2)), "lon": float(m.group(3))})
    return pts


def map_data_uri():
    g = Image.open(SRC).convert("L")
    g = cover_resize(g, W, H)
    buf = io.BytesIO()
    g.save(buf, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


HTML = r"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"><title>Map calibration</title>
<style>
  body { margin:0; font-family:-apple-system,Arial,sans-serif; background:#222;
         color:#eee; display:flex; gap:16px; padding:16px; }
  h1 { font-size:18px; margin:0 0 8px; }
  #mapwrap { position:relative; width:800px; flex:none; border:2px solid #555;
             background:#fff; }
  #mapwrap img { display:block; width:800px; height:480px; cursor:crosshair;
                 image-rendering:pixelated; }
  .marker { position:absolute; width:14px; height:14px; margin:-7px 0 0 -7px;
            border:2px solid #e33; border-radius:50%; background:rgba(255,60,60,.35);
            pointer-events:none; font-size:10px; color:#e33; }
  .marker b { position:absolute; left:16px; top:-3px; white-space:nowrap;
              background:#000a; padding:0 3px; border-radius:3px; }
  .pred { position:absolute; width:0; height:0; margin:-8px 0 0 -8px;
          pointer-events:none; color:#28f; font-size:16px; font-weight:800; }
  #side { width:520px; }
  table { border-collapse:collapse; width:100%; font-size:13px; }
  th,td { border:1px solid #444; padding:3px 5px; text-align:left; }
  select,input { background:#333; color:#eee; border:1px solid #555; font-size:12px;
                 padding:2px; }
  input.lat,input.lon { width:92px; }
  button { background:#2a6; color:#fff; border:0; padding:7px 12px; border-radius:5px;
           cursor:pointer; font-size:13px; }
  button.sec { background:#555; }
  .del { background:#a33; padding:1px 7px; }
  pre { background:#111; padding:10px; border-radius:6px; white-space:pre-wrap;
        font-size:12px; max-height:220px; overflow:auto; }
  .hint { color:#aaa; font-size:12px; }
  #readout { font-size:13px; color:#8cf; height:18px; }
  .err-ok { color:#6d6; } .err-bad { color:#f88; }
</style></head><body>

<div>
  <h1>Map calibration &mdash; SanFranGrey.png (800&times;480)</h1>
  <div id="mapwrap"><img id="map" src="__IMG__" draggable="false"></div>
  <div id="readout">&nbsp;</div>
  <p class="hint">Click the map where a known point is, then pick its airport (or
  Custom + type lat/lon). Add 2&ndash;4 well-spread points, then Compute.</p>
</div>

<div id="side">
  <h1>Points</h1>
  <table id="tbl"><thead><tr><th>#</th><th>x,y</th><th>Location</th>
    <th>lat</th><th>lon</th><th>err</th><th></th></tr></thead><tbody></tbody></table>
  <p>
    <button onclick="compute()">Compute mapping</button>
    <button class="sec" onclick="clearAll()">Clear</button>
  </p>
  <h1>Result</h1>
  <pre id="out">Add points and click Compute.</pre>
  <button class="sec" onclick="copyOut()">Copy result</button>
</div>

<script>
const AIRPORTS = __AIRPORTS__;
const img = document.getElementById('map');
const wrap = document.getElementById('mapwrap');
let pts = [];          // {x,y,sel,lat,lon}
let fit = null;        // {mx,bx,my,by}

function imgXY(e){
  const r = img.getBoundingClientRect();
  return { x:(e.clientX-r.left)*(800/r.width), y:(e.clientY-r.top)*(480/r.height) };
}
img.addEventListener('click', e=>{
  const p = imgXY(e);
  const a = AIRPORTS[0] || null;
  pts.push({ x:Math.round(p.x), y:Math.round(p.y),
             sel: a?0:-1, lat: a?a.lat:'', lon: a?a.lon:'' });
  render();
});
img.addEventListener('mousemove', e=>{
  if(!fit) return;
  const p = imgXY(e);
  const lon = fit.mx*p.x+fit.bx, lat = fit.my*p.y+fit.by;
  document.getElementById('readout').textContent =
    `cursor  ${lat.toFixed(5)}, ${lon.toFixed(5)}`;
});

function haversineMi(la1,lo1,la2,lo2){
  const R=3958.8, d=x=>x*Math.PI/180;
  const a=Math.sin(d(la2-la1)/2)**2 +
          Math.cos(d(la1))*Math.cos(d(la2))*Math.sin(d(lo2-lo1)/2)**2;
  return 2*R*Math.asin(Math.sqrt(a));
}
function linfit(xs,vs){
  const n=xs.length; let sx=0,sv=0,sxx=0,sxv=0;
  for(let i=0;i<n;i++){ sx+=xs[i]; sv+=vs[i]; sxx+=xs[i]*xs[i]; sxv+=xs[i]*vs[i]; }
  const den=n*sxx-sx*sx;
  if(Math.abs(den)<1e-9) return null;
  const m=(n*sxv-sx*sv)/den, b=(sv-m*sx)/n; return {m,b};
}

function render(){
  // markers
  wrap.querySelectorAll('.marker,.pred').forEach(n=>n.remove());
  pts.forEach((p,i)=>{
    const m=document.createElement('div'); m.className='marker';
    m.style.left=(p.x/800*100)+'%'; m.style.top=(p.y/480*100)+'%';
    m.innerHTML='<b>'+(i+1)+'</b>'; wrap.appendChild(m);
  });
  // table
  const tb=document.querySelector('#tbl tbody'); tb.innerHTML='';
  pts.forEach((p,i)=>{
    const tr=document.createElement('tr');
    let opts='<option value="-1">Custom…</option>';
    AIRPORTS.forEach((a,j)=>opts+=`<option value="${j}" ${p.sel==j?'selected':''}>${a.name}</option>`);
    const custom = p.sel==-1;
    tr.innerHTML=
      `<td>${i+1}</td><td>${p.x},${p.y}</td>`+
      `<td><select onchange="setSel(${i},this.value)">${opts}</select></td>`+
      `<td><input class="lat" value="${p.lat}" ${custom?'':'disabled'} oninput="setV(${i},'lat',this.value)"></td>`+
      `<td><input class="lon" value="${p.lon}" ${custom?'':'disabled'} oninput="setV(${i},'lon',this.value)"></td>`+
      `<td class="${p.errClass||''}">${p.err!=null?p.err.toFixed(2)+' mi':''}</td>`+
      `<td><button class="del" onclick="delPt(${i})">×</button></td>`;
    tb.appendChild(tr);
  });
}
function setSel(i,v){ v=+v; pts[i].sel=v;
  if(v>=0){ pts[i].lat=AIRPORTS[v].lat; pts[i].lon=AIRPORTS[v].lon; } render(); }
function setV(i,k,v){ pts[i][k]=v; }
function delPt(i){ pts.splice(i,1); render(); }
function clearAll(){ pts=[]; fit=null; document.getElementById('out').textContent='Add points and click Compute.'; render(); }

function compute(){
  const good = pts.filter(p=>p.lat!==''&&p.lon!==''&&!isNaN(+p.lat)&&!isNaN(+p.lon));
  if(good.length<2){ out('Need at least 2 points with lat/lon.'); return; }
  const fx=linfit(good.map(p=>p.x), good.map(p=>+p.lon));  // lon = mx*x+bx
  const fy=linfit(good.map(p=>p.y), good.map(p=>+p.lat));  // lat = my*y+by
  if(!fx){ out('Points do not vary enough in X (need different columns).'); return; }
  if(!fy){ out('Points do not vary enough in Y (need different rows).'); return; }
  fit={mx:fx.m,bx:fx.b,my:fy.m,by:fy.b};

  // residuals
  let rms=0;
  pts.forEach(p=>{
    if(p.lat===''||p.lon===''){ p.err=null; p.errClass=''; return; }
    const plon=fit.mx*p.x+fit.bx, plat=fit.my*p.y+fit.by;
    p.err=haversineMi(+p.lat,+p.lon,plat,plon);
    p.errClass = p.err<0.6?'err-ok':'err-bad';
  });
  const errs=pts.filter(p=>p.err!=null).map(p=>p.err);
  rms=Math.sqrt(errs.reduce((s,e)=>s+e*e,0)/errs.length);

  // corner bounds (x=0..800, y=0..480)
  const lonL=fit.bx, lonR=fit.mx*800+fit.bx;
  const latT=fit.by, latB=fit.my*480+fit.by;
  const widthMi=haversineMi((latT+latB)/2,lonL,(latT+latB)/2,lonR);
  const heightMi=haversineMi(latT,(lonL+lonR)/2,latB,(lonL+lonR)/2);

  const snip =
`// --- Map calibration for SanFranGrey.png (800x480) ---
// RMS fit error: ${rms.toFixed(2)} mi over ${errs.length} points.
// Span: ${widthMi.toFixed(1)} mi wide x ${heightMi.toFixed(1)} mi tall.
static const double MAP_LAT_TOP   = ${latT.toFixed(6)};  // pixel y = 0
static const double MAP_LAT_BOT   = ${latB.toFixed(6)};  // pixel y = 480
static const double MAP_LON_LEFT  = ${lonL.toFixed(6)};  // pixel x = 0
static const double MAP_LON_RIGHT = ${lonR.toFixed(6)};  // pixel x = 800

// lat/lon -> map pixel:
//   px = (lon - MAP_LON_LEFT) / (MAP_LON_RIGHT - MAP_LON_LEFT) * 800.0;
//   py = (lat - MAP_LAT_TOP)  / (MAP_LAT_BOT  - MAP_LAT_TOP ) * 480.0;`;
  out(snip);
  render();
}
function out(s){ document.getElementById('out').textContent=s; }
function copyOut(){ navigator.clipboard.writeText(document.getElementById('out').textContent); }
render();
</script>
</body></html>
"""


def main():
    html = (HTML
            .replace("__IMG__", map_data_uri())
            .replace("__AIRPORTS__", json.dumps(load_airports())))
    with open(OUT, "w") as f:
        f.write(html)
    n = len(load_airports())
    print(f"wrote {OUT}  ({n} airports preloaded)")
    print("Open it in a browser, click points, tag lat/lon, Compute.")


if __name__ == "__main__":
    main()
