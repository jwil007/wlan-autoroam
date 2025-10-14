/*** ==========================================================
     GLOBAL STATE & CONSTANTS
========================================================== */
let data = null;

// Phase palette (reads CSS variables to preserve theme)
const PHASES = [
  { key: "Authentication", label: "Authentication", color: getComputedStyle(document.documentElement).getPropertyValue('--ph-auth').trim() || "#7ccaff" },
  { key: "Association",    label: "Association",    color: getComputedStyle(document.documentElement).getPropertyValue('--ph-assoc').trim() || "#68efc3" },
  { key: "EAP",            label: "EAP",            color: getComputedStyle(document.documentElement).getPropertyValue('--ph-eap').trim()  || "#ffc76a" },
  { key: "4-Way",          label: "4-Way",          color: getComputedStyle(document.documentElement).getPropertyValue('--ph-4way').trim() || "#caa6ff" }
];
let visible = new Set(PHASES.map(p => p.key));

/*** ==========================================================
     HELPERS
========================================================== */
const $ = s => document.querySelector(s);
const fmtMs = n => n == null ? "—" : `${(+n).toFixed(2)} ms`;
const bandStr = f => {
  if (f == null) return "—";
  let band = (f < 3000 ? "2.4 GHz" : (f < 6000 ? "5 GHz" : (f < 7000 ? "6 GHz" : "")));
  return `${f} (${band})`;
};
const rssiClass = r => (r >= -65 ? "green" : (r >= -72 ? "yellow" : "red"));
const successRate = roams => {
  if (!roams?.length) return [0, 0];
  const ok = roams.filter(r => r.overall_status === "success").length;
  return [ok, roams.length];
};
const median = arr => {
  if (!arr.length) return 0;
  const a = [...arr].sort((x, y) => x - y);
  const m = Math.floor(a.length / 2);
  return a.length % 2 ? a[m] : (a[m - 1] + a[m]) / 2;
};
const cssVar = n => getComputedStyle(document.documentElement).getPropertyValue(n).trim();

/*** ==========================================================
     MAIN RENDER PIPELINE
========================================================== */
function loadData(d) {
  data = d;
  renderHeader();
  renderMetrics();
  renderTable();
  renderChart();
  renderRoams();
}

/*** ==========================================================
     HEADER / SUMMARY METRICS
========================================================== */
function renderHeader() {
  $("#hSsid").textContent = data.ssid ?? "—";
  $("#hSec").textContent  = data.security_type ?? "—";
  $("#hExec").textContent = data.execution_duration_s != null ? `${data.execution_duration_s.toFixed(2)} s` : "—";
  if (data.timestamp) {
    const ts = new Date(data.timestamp);
    const formatted = ts.toLocaleString(undefined, {
      year: "numeric",
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
    });
    $("#hTime").textContent = formatted;
  } else {
    $("#hTime").textContent = "—";
  }

  $("#mSecType").textContent = data.security_type ?? "—";
  const notesContainer = document.getElementById("notesPill");
  if (notesContainer) {
    const notes = data.notes;
    if (notes && notes.trim()) {
      notesContainer.textContent = notes;
    } else {
      notesContainer.textContent = "—";
    }
  }
}

function renderMetrics() {
  const [ok, total] = successRate(data.roams || []);
  $("#mRoams").textContent   = total;
  $("#mSuccess").textContent = total ? `${Math.round((ok / total) * 100)}%` : "—";
  const totals = (data.roams || []).map(r => +r.roam_duration_ms || 0);
  $("#mAvg").textContent    = totals.length ? `${(totals.reduce((a,b)=>a+b,0)/totals.length).toFixed(2)} ms` : "—";
  $("#mMedian").textContent = totals.length ? `${median(totals).toFixed(2)} ms` : "—";
  if (totals.length) {
    const fast = Math.min(...totals).toFixed(2);
    const slow = Math.max(...totals).toFixed(2);
    $("#mFS").textContent = `${fast} ms / ${slow} ms`;
  } else $("#mFS").textContent = "—";
}

/*** ==========================================================
     CANDIDATES TABLE
========================================================== */
function renderTable() {
  const tb = $("#apTable tbody");
  tb.innerHTML = "";
  const rows = (data.candidates || []).slice().sort((a,b)=>(b.rssi ?? -999) - (a.rssi ?? -999));
  for (const c of rows) {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td>${c.bssid ?? "—"}</td>
      <td>${bandStr(c.freq)}</td>
      <td class="rssi ${rssiClass(+c.rssi)}">${c.rssi}</td>
      <td>${c.qbss_util_prct ?? "—"}</td>
      <td>${c.qbss_sta_count ?? "—"}</td>
      <td>${(c.auth_suites||[]).map(s=>`<span class="pill"><span class="dot" style="background:${cssVar('--ph-auth')||'#7ccaff'}"></span>${s}</span>`).join(" ") || "—"}</td>
      <td><span class="pill"><span class="dot" style="background:${c.mfp_flag?.includes("required")? "#ff9e66":"#8bd8ff"}"></span>${c.mfp_flag ?? "—"}</span></td>
      <td class="muted">${c.supported_rates ?? "—"}</td>`;
    tb.appendChild(tr);
  }
}

/*** ==========================================================
     CHART (SVG stacked bars)
========================================================== */
function renderChart() {
  const svg = $("#chart");
  svg.innerHTML = "";

  const padL=110, padR=20, padT=18, padB=32;
  const W = svg.clientWidth, H = svg.clientHeight;
  const plotW = W - padL - padR, plotH = H - padT - padB;

  const roams = (data.roams || []);
  const items = roams.map((r,i)=>{
    const segs = PHASES.map(p=>{
      const ph = r.phases?.[p.key];
      const dur = ph?.duration_ms ?? 0;
      return {
        k:p.key,label:p.label,dur:+dur,color:p.color,status:ph?.status,type:ph?.type,
        target:r.target_bssid, rssi: findRssi(r.target_bssid)
      };
    });
    const total = segs.reduce((s,x)=>s+(x.dur||0),0);
    return {index:r.roam_index,total,segs,status:r.overall_status,target:r.target_bssid,freq:r.final_freq};
  });

  const maxX = Math.max(1, ...items.map(d=>d.total));

  // grid + labels
  for (let i=0;i<=4;i++){
    const x = padL + (i/4)*plotW;
    const gl = document.createElementNS(svg.namespaceURI,"line");
    gl.setAttribute("x1",x);gl.setAttribute("x2",x);
    gl.setAttribute("y1",padT);gl.setAttribute("y2",padT+plotH);
    gl.setAttribute("stroke","#213045");gl.setAttribute("stroke-width","1");
    svg.appendChild(gl);
    const lbl = document.createElementNS(svg.namespaceURI,"text");
    lbl.setAttribute("x",x); lbl.setAttribute("y",H-10);
    lbl.setAttribute("text-anchor","middle");
    lbl.setAttribute("fill","#e8f1ff");
    lbl.textContent = `${Math.round((i/4)*maxX)} ms`;
    svg.appendChild(lbl);
  }

  // bars + chips
  const rowH = plotH / Math.max(1, items.length);
  const barH = Math.max(14, rowH - 12);
  items.forEach((d,rowIdx)=>{
    const y = padT + rowIdx*rowH + (rowH-barH)/2;
    const statusColor = (d.status==="success"? cssVar('--ok'): cssVar('--bad')) || "#25e07b";
    const chipGroup = document.createElementNS(svg.namespaceURI,"g");
    const rect = document.createElementNS(svg.namespaceURI,"rect");
    rect.setAttribute("x",14);
    rect.setAttribute("y",y+(barH-20)/2);
    rect.setAttribute("width",78);
    rect.setAttribute("height",20);
    rect.setAttribute("rx",10);
    rect.setAttribute("fill",statusColor);
    rect.setAttribute("opacity","0.9");
    chipGroup.appendChild(rect);
    const t = document.createElementNS(svg.namespaceURI,"text");
    t.setAttribute("x",53);
    t.setAttribute("y",y+barH/2+1);
    t.setAttribute("text-anchor","middle");
    t.setAttribute("class","rowChip chipTextLight");
    t.textContent = `Roam #${d.index}`;
    chipGroup.appendChild(t);
    svg.appendChild(chipGroup);

    let cursor=0;
    d.segs.forEach(seg=>{
      if(!visible.has(seg.k)||!seg.dur)return;
      const w=(seg.dur/maxX)*plotW;
      const r=document.createElementNS(svg.namespaceURI,"rect");
      r.setAttribute("x",padL+cursor);
      r.setAttribute("y",y);
      r.setAttribute("width",Math.max(0,w));
      r.setAttribute("height",barH);
      r.setAttribute("rx",4);
      r.setAttribute("fill",seg.color);
      r.setAttribute("opacity",seg.status==="success"?"1":"0.9");
      r.addEventListener("mousemove",ev=>{
        showTip(ev.clientX,ev.clientY,`
          <h4>Roam #${d.index} · ${seg.status||"—"}</h4>
          <p><strong>AP</strong> ${d.target||"—"} · <strong>${seg.type||seg.k}</strong></p>
          <p>RSSI: ${seg.rssi??"—"} · Phase: <strong>${seg.label}</strong> = ${fmtMs(seg.dur)}</p>
          <small>Total: ${fmtMs(d.total)}</small>`);
      });
      r.addEventListener("mouseleave",hideTip);
      svg.appendChild(r);
      cursor+=w;
    });
  });

  const leg=$("#legend"); leg.innerHTML="";
  for(const p of PHASES){
    const chip=document.createElement("div");
    chip.className="chip"+(visible.has(p.key)?"":" dim");
    chip.innerHTML=`<span class="dot" style="background:${p.color}"></span>${p.label}`;
    chip.onclick=()=>{visible.has(p.key)?visible.delete(p.key):visible.add(p.key);renderChart();};
    leg.appendChild(chip);
  }
}

function showTip(x,y,html){
  const t=$("#tooltip"); t.innerHTML=html; t.style.display="block";
  const pad=24,vw=window.innerWidth,vh=window.innerHeight;
  const rect=t.getBoundingClientRect();
  let tx=x+16, ty=y+16;
  if(tx+rect.width+pad>vw)tx=vw-rect.width-pad;
  if(ty+rect.height+pad>vh)ty=vh-rect.height-pad;
  t.style.left=tx+"px"; t.style.top=ty+"px";
}
function hideTip(){ $("#tooltip").style.display="none"; }
function findRssi(bssid){
  const c=(data.candidates||[]).find(x=>x.bssid===bssid);
  return c?.rssi ?? null;
}

/*** ==========================================================
     ROAM DETAILS (accordion)
========================================================== */
function renderRoams(){
  const wrap=$("#roams"); wrap.innerHTML="";
  for(const r of (data.roams||[])){
    const acc=document.createElement("div"); acc.className="accordion";
    const head=document.createElement("div"); head.className="accHead";
    head.innerHTML=`
      <div class="pill" style="background:${r.overall_status==='success'?'rgba(37,224,123,.12)':'rgba(255,108,121,.12)'};border-color:#2a394b;">
        <span class="dot" style="background:${r.overall_status==='success'?cssVar('--ok'):cssVar('--bad')}"></span>
        Roam #${r.roam_index}
      </div>
      <div>
        <span class="muted">AP</span> ${r.target_bssid||r.final_bssid||"—"} 
        <span class="muted">·</span> 
        <span class="muted">${
          r.start_time
            ? new Date(r.start_time).toLocaleTimeString([], {
                hour: "2-digit",
                minute: "2-digit",
                second: "2-digit",
                fractionalSecondDigits: 3
              })
            : "—"
        }
        </span>
        <span class="muted">·</span> Total <strong>${fmtMs(r.roam_duration_ms)}</strong>
      </div>

      <div class="statusGroup">
        ${r.overall_status==="failure"&&r.failure_log?`<button class="btnDownloadRoam" data-filename="${r.failure_log}">Download log file</button>`:""}
        <div class="status ${r.overall_status==="success"?"ok":"bad"}">${r.overall_status}</div>
      </div>`;
    const body=document.createElement("div"); body.className="accBody";

    if(r.details&&Object.keys(r.details).length){
      const detailsDiv=document.createElement("div");
      detailsDiv.className="roamDetailsInline";
      detailsDiv.innerHTML=`
        <div style="margin-bottom:10px;display:flex;flex-wrap:wrap;gap:10px;align-items:center;">
          ${Object.entries(r.details).map(([k,v])=>`<span class="muted">${k}:</span> <span class="kbd">${v}</span>`).join("<span class='muted'>·</span> ")}
        </div>`;
      body.appendChild(detailsDiv);
    }

    const phases=["Authentication","Association","EAP","4-Way"];
    phases.forEach(k=>{
      const ph=r.phases?.[k]; if(!ph)return;
      const errs=(ph.errors||[]);
      const card=document.createElement("div"); card.className="phaseCard";
      card.innerHTML=`
      <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap">
        <div style="display:flex;gap:10px;align-items:center;flex-wrap:wrap">
          <strong>${ph.name}</strong>
          <span class="${ph.status==="success"?"ok":(ph.status==="N/A"||ph.status==="unknown"?"muted":"bad")}">${ph.status}</span>
          <span class="muted">Type:</span> <span>${ph.type||"—"}</span>
          <span class="muted">· Duration:</span> <span>${fmtMs(ph.duration_ms)}</span>
        </div>
        <span class="kbd" style="white-space:nowrap;margin-left:auto;">
          ${
            ph.start
              ? new Date(ph.start).toLocaleTimeString([], {
                  hour: "2-digit",
                  minute: "2-digit",
                  second: "2-digit",
                  fractionalSecondDigits: 3
                })
              : "—"
          }
        </span>
      </div>
        ${Object.keys(ph.details||{}).length?`<div class="muted" style="margin-top:6px">${Object.entries(ph.details).map(([k,v])=>`${k}: <span class="kbd">${v}</span>`).join(" · ")}</div>`:""}
        ${errs.length?`<details style="margin-top:8px"><summary>Errors (${errs.length})</summary><pre style="white-space:pre-wrap;max-height:240px;overflow:auto;margin:6px 0 0 0;color:#d9eaff">${errs.join("")}</pre></details>`:""}
      `;
      body.appendChild(card);
    });

    head.onclick=()=>body.classList.toggle("open");
    acc.append(head,body);
    wrap.appendChild(acc);
    console.log("Attaching handlers to download buttons...");
    wrap.querySelectorAll('.btnDownloadRoam').forEach(btn => {
      btn.onclick = async e => {   // ← replaces addEventListener()
        e.stopPropagation();
        const filename = btn.dataset.filename;
        if (!filename) { alert("No log file found for this roam."); return; }
        try {
          const selectedDir = document.getElementById("loadDropdown")?.value || "";
          const url = selectedDir
            ? `/api/download_log?dir=${encodeURIComponent(selectedDir)}&filename=${encodeURIComponent(filename)}`
            : `/api/download_log?filename=${encodeURIComponent(filename)}`;

          const res = await fetch(`${url}&_=${Date.now()}`);
          if (!res.ok) { alert("No log file found for this roam."); return; }

          const blob = await res.blob();
          const blobUrl = window.URL.createObjectURL(blob);
          const a = document.createElement('a');
          a.href = blobUrl;
          a.download = filename;
          document.body.appendChild(a);
          a.click();
          a.remove();
          window.URL.revokeObjectURL(blobUrl);
        } catch (err) {
          console.error("Failed to download roam log:", err);
          alert("Failed to download log.");
        }
      };
    });

  }
}

/*** ==========================================================
     OVERLAY CONTROLS
========================================================== */
function showOverlay(msg="Running roam..."){
  document.getElementById('overlay').style.display='flex';
  document.getElementById('spinnerText').textContent=msg;
  document.getElementById('logOutput').textContent="";
}
function hideOverlay(){
  document.getElementById('overlay').style.display='none';
}

/*** ==========================================================
     EVENT HANDLERS + API INTEGRATION
========================================================== */
const runBtn=document.getElementById('btnRunNow');
const statusLabel=document.getElementById('runStatus');
const downloadBtn=document.getElementById('btnDownloadLog');


let roamInProgress=false;
runBtn.addEventListener('click',async()=>{
  if(roamInProgress)return;
  roamInProgress=true;
  runBtn.disabled=true;
  statusLabel.textContent="";
  showOverlay();
  loadDropdown.selectedIndex = 0; // reset dropdown to "Load Results..."


  const iface = document.getElementById('iface').value.trim() || "wlan0";
  const rssi = parseInt(document.getElementById('rssi').value.trim() || "-75", 10);

  const payload = { iface, rssi};
  
try {
    const startRes = await fetch('/api/start_roam', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    const startData = await startRes.json();
    console.log("▶ Roam started with args:", payload, startData);

    const logsPromise = pollLogs();
    await pollForSummary();

    if (logPollController) {
      logPollController.abort();
      logPollController = null;
    }

    await logsPromise;

  } catch (err) {
    console.error("❌ Error starting roam:", err);
    statusLabel.textContent = "Error starting roam.";
  } finally {
    runBtn.disabled = false;
    roamInProgress = false;
    hideOverlay();
  }
});

/*** ==========================================================
     LOG POLLING
========================================================== */
let logPollController = null;
let logPollingActive = false;
let lastLogLength = 0;

async function pollLogs() {
  if (logPollingActive) {
    console.warn("⛔ pollLogs already running — skipping duplicate start");
    return;
  }
  logPollingActive = true;

  const logBox = document.getElementById('logOutput');
  logBox.textContent = "";
  lastLogLength = 0;

  if (logPollController) logPollController.abort();
  logPollController = new AbortController();
  const signal = logPollController.signal;

  console.log("📡 Starting log polling");

  try {
    while (true) {
      if (signal.aborted) {
        console.log("⚙️ Abort signal received — breaking loop");
        break;
      }

      const res = await fetch(`/api/logs?nocache=${Date.now()}`, { signal });
      if (res.ok) {
        const { log } = await res.json();
        if (log.length > lastLogLength) {
          const newPart = log.slice(lastLogLength);
          logBox.textContent += newPart;
          logBox.scrollTop = logBox.scrollHeight;
          lastLogLength = log.length;
        }
      }

      const overlayVisible = document.getElementById('overlay').style.display === 'flex';
      if (!overlayVisible) {
        console.log("✅ Overlay hidden — stopping log polling");
        break;
      }

      await new Promise(r => setTimeout(r, 1000));
    }
  } catch (err) {
    if (err.name === "AbortError") {
      console.log("🛑 Log polling aborted (fetch aborted)");
    } else {
      console.error("Log polling error:", err);
    }
  } finally {
    logPollingActive = false;
    console.log("🛑 Log polling stopped (finally)");
  }
}

/*** ==========================================================
     SUMMARY POLLING
========================================================== */
async function pollForSummary() {
  const maxWait = 120; // seconds
  const pollInterval = 3; // seconds

  let baselineMtime = 0;
  try {
    const res = await fetch('/api/latest_cycle_summary');
    if (res.ok) {
      const payload = await res.json();
      baselineMtime = payload.mtime || 0;
      console.log("Baseline mtime before roam:", baselineMtime);
    }
  } catch {
    console.warn("No existing summary baseline found, starting fresh.");
  }

  for (let i = 0; i < maxWait / pollInterval; i++) {
    // 🔹 1️⃣ Check for early process exit (flag file)
    const doneCheck = await fetch(`/server/roam_done.flag?nocache=${Date.now()}`);
    if (doneCheck.ok) {
      console.log("⚠️ Detected roam process finished early — stopping poll");
      statusLabel.textContent = "Roam process exited early.";
      hideOverlay();
      return;
    }

    // 🔹 2️⃣ Normal summary polling
    const res = await fetch(`/api/latest_cycle_summary?nocache=${Date.now()}`);
    if (res.ok) {
      const payload = await res.json();
      const { mtime, data } = payload;

      if (mtime > baselineMtime) {
        window.lastSummaryMtime = mtime;
        console.log("Got NEW cycle summary:", data);
        renderCycleSummary(data);
        return;
      }
    }

    console.log("Waiting for new roam data...");
    await new Promise(r => setTimeout(r, pollInterval * 1000));
  }

  statusLabel.textContent = "Timed out waiting for roam.";
}

/*** ==========================================================
     RENDER NEW SUMMARY
========================================================== */
function renderCycleSummary(summary) {
  console.log("Rendering new roam data:", summary);
  window.data = summary;
  loadData(summary);
}

/*** ==========================================================
     DOWNLOAD DEBUG LOG BUTTON
========================================================== */
downloadLogBtn.addEventListener("click", async () => {
  try {
    const selectedDir = loadDropdown.value; // empty if viewing current run
    const url = selectedDir
      ? `/api/download_log?dir=${encodeURIComponent(selectedDir)}&filename=roam_debug.log`
      : `/api/download_log?filename=roam_debug.log`;

    const res = await fetch(url);
    if (!res.ok) {
      alert("No debug log found for the selected run.");
      return;
    }
    const blob = await res.blob();
    const blobUrl = window.URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = blobUrl;
    a.download = "roam_debug.log";
    document.body.appendChild(a);
    a.click();
    a.remove();
    window.URL.revokeObjectURL(blobUrl);
  } catch (err) {
    console.error("Failed to download debug log:", err);
    alert("Failed to download debug log.");
  }
});

/*** ==========================================================
     Save results logic
========================================================== */
const saveBtn = document.getElementById("saveBtn");
const saveModal = document.getElementById("saveModal");
const confirmSave = document.getElementById("confirmSave");
const cancelSave = document.getElementById("cancelSave");
const notesInput = document.getElementById("notesInput");

saveBtn.onclick = () => {
  saveModal.style.display = "flex";
};

cancelSave.onclick = () => {
  saveModal.style.display = "none";
  notesInput.value = "";
};

confirmSave.onclick = async () => {
  const notes = notesInput.value.trim();
  saveModal.style.display = "none";

  try {
    const latest = await fetch("/api/latest_cycle_summary");
    const latestData = await latest.json();
    const runDir = latestData.run_dir;

    const res = await fetch("/api/save_results", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ run_dir: runDir, notes }),
    });
    const data = await res.json();
    alert("Results saved successfully!");
    refreshLoadDropdown();
  } catch (err) {
    console.error("Failed to save results:", err);
    alert("Error saving results");
  }
};

/*** ==========================================================
     Load results logic
========================================================== */
const loadDropdown = document.getElementById("loadDropdown");

async function refreshLoadDropdown() {
  try {
    const res = await fetch("/api/list_saved_runs");
    const runs = await res.json();
    loadDropdown.innerHTML = '<option value="">Load Results...</option>';
    runs.forEach(run => {
      const opt = document.createElement("option");
      opt.value = run.dir;
      opt.textContent = `${run.ssid} (${new Date(run.timestamp).toLocaleString()})`;
      loadDropdown.appendChild(opt);
    });
  } catch (err) {
    console.error("Failed to refresh saved runs:", err);
  }
}

loadDropdown.onchange = async () => {
  const dir = loadDropdown.value;
  if (!dir) return;

  try {
    const res = await fetch(`/api/load_results?dir=${encodeURIComponent(dir)}`);
    const data = await res.json();
    renderCycleSummary(data);; // existing render logic for cycle_summary.json
  } catch (err) {
    console.error("Failed to load saved results:", err);
  }
};
// Populate dropdown on startup
refreshLoadDropdown();