from fastapi import APIRouter
from fastapi.responses import HTMLResponse

router = APIRouter()

@router.get("/demo")
def demo():
    return HTMLResponse("""<!doctype html><meta charset="utf-8">
<title>SCALP • Demo</title>
<style>
body{background:#0f141b;color:#d7e1ec;font-family:system-ui,Segoe UI,Roboto,Arial,sans-serif}
table{width:100%;border-collapse:collapse;margin-top:10px}
th,td{padding:6px 8px;border-bottom:1px solid #223} th{color:#9ab;text-align:left}
.tag{padding:2px 6px;border:1px solid #2a394a;border-radius:6px;background:#1b2430}
.muted{color:#789}
</style>
<h3>SCALP • Demo</h3>
<div><a href="/viz/hello">/viz/hello</a> · <a href="/api/signals">/api/signals</a>
<button id="r">⟳ Refresh</button></div>
<table id="t"><thead><tr><th>ts</th><th>sym</th><th>tf</th><th>side</th><th>entry</th></tr></thead><tbody></tbody></table>
<script>
const fmt=(x)=>{try{const d=new Date(parseInt(x,10)*1000);return d.toISOString().replace('T',' ').replace('.000Z','')}catch(e){return x}};
async function load(){
  const r=await fetch('/api/signals?include_hold=true&limit=100');
  const js=await r.json(); const rows=js.items||[];
  const tb=document.querySelector('#t tbody'); tb.innerHTML='';
  for(const it of rows){
    const tr=document.createElement('tr');
    tr.innerHTML=`<td class="muted">${fmt(it.ts)}</td>
                  <td><span class="tag">${it.sym}</span></td>
                  <td class="muted">${it.tf}</td>
                  <td>${it.side}</td>
                  <td class="muted">${it.entry||it.details||''}</td>`;
    tb.appendChild(tr);
  }
}
document.querySelector('#r').onclick=load;
load(); setInterval(load,5000);
try{
  const es=new EventSource('/viz/stream');
  es.addEventListener('signal',ev=>{
    const it=JSON.parse(ev.data);
    const tb=document.querySelector('#t tbody');
    const tr=document.createElement('tr');
    tr.innerHTML=`<td class="muted">${fmt(it.ts)}</td>
                  <td><span class="tag">${it.sym}</span></td>
                  <td class="muted">${it.tf}</td>
                  <td>${it.side}</td>
                  <td class="muted">${it.entry||it.details||''}</td>`;
    tb.prepend(tr);
  });
}catch(e){}
</script>
""")
