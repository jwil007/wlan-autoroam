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

// Basic Markdown renderer
function renderMarkdown(text) {
  if (!text) return '';
  
  // Basic Markdown parsing
  return text
    // Convert headers (##)
    .replace(/^### (.*$)/gim, '<h3>$1</h3>')
    .replace(/^## (.*$)/gim, '<h2>$1</h2>')
    .replace(/^# (.*$)/gim, '<h1>$1</h1>')
    // Convert lists
    .replace(/^\s*[\-\*]\s+(.*)$/gm, '<li>$1</li>')
    .replace(/(<li>.*<\/li>\n?)+/g, '<ul>$&</ul>')
    // Convert bold (**text**)
    .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
    // Convert italics (*text*)
    .replace(/\*(.*?)\*/g, '<em>$1</em>')
    // Convert line breaks
    .replace(/\n/g, '<br>');
}

// Toggle AI Analysis Panel
function toggleAIPanel(show) {
  const panel = $('.ai-analysis-panel');
  if (show === undefined) {
    show = panel.style.display === 'none';
  }
  panel.style.display = show ? 'flex' : 'none';
  
  // Focus input when showing
  if (show) {
    $('.chat-input').focus();
  }
}

/*** ==========================================================
     AI INTEGRATION
========================================================== */

/*** ==========================================================
     AI INTEGRATION
========================================================== */
// Setup AI Panel and Chat Functionality
function setupAI() {
  // Initialize chat panel elements
  const aiPanel = $('.ai-analysis-panel');
  const closeBtn = $('.btn-close-ai');
  const analyzeBtn = $('#btnAnalyzeAI');
  const chatInput = $('.chat-input');
  const sendBtn = $('.chat-send');
  const messagesContainer = $('.chat-messages');
  let currentConversation = [];
  let aiAnalysisInProgress = false;

  // Panel state handlers
  const panel = document.querySelector('.ai-analysis-panel');
  const collapseBtn = document.querySelector('.btn-collapse-ai');
  
  collapseBtn.addEventListener('click', () => {
    panel.classList.toggle('collapsed');
    collapseBtn.textContent = panel.classList.contains('collapsed') ? '⌄' : '⌃';
    collapseBtn.title = panel.classList.contains('collapsed') ? 'Expand' : 'Collapse';
  });

  // Show/hide panel handlers
  analyzeBtn.addEventListener('click', async () => {
    if (!data) {
      alert('No data available to analyze');
      return;
    }

    try {
      // Reset conversation and show panel with loading state
      currentConversation = [];
      panel.classList.remove('collapsed');
      collapseBtn.textContent = '⌃';
      toggleAIPanel(true);
      aiAnalysisInProgress = true;
      panel.classList.add('loading');
      
      // Clear existing chat messages and input
      const chatMessages = document.querySelector('.chat-messages');
      if (chatMessages) chatMessages.innerHTML = '';
      if (chatInput) chatInput.value = '';

      const res = await fetch('/api/analyze_with_ai', {
        method: 'POST',
        headers: { 
          'Content-Type': 'application/json',
          'X-API-Key': document.querySelector('meta[name="api-key"]').content
        },
        body: JSON.stringify({
          deep: false,
          run_dir: data.run_dir
        })
      });

      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const result = await res.json();

      // Add initial analysis message
      const analysisMsg = document.createElement('div');
      analysisMsg.className = 'message assistant';
      analysisMsg.innerHTML = renderMarkdown(result.ai.shallow);
      messagesContainer.appendChild(analysisMsg);

      // Save to conversation history
      currentConversation.push({ role: 'assistant', content: result.ai.shallow });

      // Update UI state
      panel.classList.remove('loading');
      chatInput.value = '';
      chatInput.focus();

    } catch (err) {
      console.error('AI analysis failed:', err);
      const errorMsg = document.createElement('div');
      errorMsg.className = 'message error';
      errorMsg.textContent = 'Failed to get AI analysis. Please try again.';
      messagesContainer.appendChild(errorMsg);
    } finally {
      aiAnalysisInProgress = false;
    }
  });

  closeBtn.addEventListener('click', () => toggleAIPanel(false));

  // Handle message sending
  function sendMessage(text) {
    if (!text.trim()) return;
    
    // Add user message
    const userMsg = document.createElement('div');
    userMsg.className = 'message user';
    userMsg.textContent = text;
    messagesContainer.appendChild(userMsg);
    
    // Save to conversation
    currentConversation.push({ role: 'user', content: text });

    // Show typing indicator
    const typingIndicator = document.createElement('div');
    typingIndicator.className = 'message assistant typing';
    messagesContainer.appendChild(typingIndicator);

    // Auto scroll
    messagesContainer.scrollTop = messagesContainer.scrollHeight;

    // Clear input
    chatInput.value = '';
    
    // Send to backend
    fetch('/api/chat_followup', {
      method: 'POST',
      headers: { 
        'Content-Type': 'application/json',
        'X-API-Key': document.querySelector('meta[name="api-key"]').content
      },
      body: JSON.stringify({
        question: text,
        run_dir: data.run_dir
      })
    })
    .then(res => res.json())
    .then(response => {
      // Remove typing indicator
      messagesContainer.removeChild(typingIndicator);
      
      // Add AI response
      const aiMsg = document.createElement('div');
      aiMsg.className = 'message assistant';
      aiMsg.innerHTML = renderMarkdown(response.answer);
      messagesContainer.appendChild(aiMsg);
      
      // Save to conversation
      currentConversation.push({ role: 'assistant', content: response.message });
      
      // Auto scroll
      messagesContainer.scrollTop = messagesContainer.scrollHeight;
    })
    .catch(err => {
      // Remove typing indicator
      messagesContainer.removeChild(typingIndicator);
      
      // Show error message
      const errorMsg = document.createElement('div');
      errorMsg.className = 'message error';
      errorMsg.textContent = 'Error: Could not get AI response. Please try again.';
      messagesContainer.appendChild(errorMsg);
    });
  }

  // Handle chat submission
  sendBtn.addEventListener('click', () => sendMessage(chatInput.value));
  chatInput.addEventListener('keydown', e => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage(chatInput.value);
    }
  });
}

// AI Settings Modal handler
function setupAISettings() {
  const modal = $("#aiSettingsModal");
  const btn = $("#btnAISettings");
  const saveBtn = $("#saveAISettings");
  const cancelBtn = $("#cancelAISettings");
  const testBtn = $("#aiTestBtn");
  const modelSelect = $("#aiModel");
  const customModelInput = $("#aiModelCustom");
  const customModelLabel = $("#aiModelCustomLabel");
  const apiKeyInput = $("#aiApiKey");
  const endpointInput = $("#aiEndpoint");
  const tempInput = $("#aiTemp");
  const maxTokensInput = $("#aiMaxTokens");
  const testResult = $("#aiTestResult");

  // Show/hide custom model input based on dropdown
  modelSelect.addEventListener('change', () => {
    const showCustom = modelSelect.value === 'custom';
    customModelInput.style.display = showCustom ? 'block' : 'none';
    customModelLabel.style.display = showCustom ? 'block' : 'none';
  });

  // Load saved settings when opening modal
  btn.addEventListener('click', async () => {
    try {
      const res = await fetch('/api/ai_settings');
      const settings = await res.json();
      
      // Populate fields
      apiKeyInput.value = settings.api_key || '';
      endpointInput.value = settings.endpoint || '';
      tempInput.value = settings.temperature || '0.2';
      maxTokensInput.value = settings.max_tokens || '512';
      
      // Handle model selection
      const savedModel = settings.model;
      if (savedModel) {
        const option = Array.from(modelSelect.options).find(opt => opt.value === savedModel);
        if (option) {
          modelSelect.value = savedModel;
        } else {
          modelSelect.value = 'custom';
          customModelInput.value = savedModel;
        }
        modelSelect.dispatchEvent(new Event('change'));
      }
    } catch (e) {
      console.error('Failed to load AI settings:', e);
    }
    modal.style.display = 'flex';
  });

  // Test connection
  testBtn.addEventListener('click', async () => {
    testBtn.disabled = true;
    testResult.textContent = 'Testing...';
    testResult.className = 'ai-test-result';

    try {
      const settings = {
        api_key: apiKeyInput.value,
        endpoint: endpointInput.value,
        model: modelSelect.value === 'custom' ? customModelInput.value : modelSelect.value,
        temperature: parseFloat(tempInput.value || '0.2'),
        max_tokens: parseInt(maxTokensInput.value || '512', 10)
      };

      const res = await fetch('/api/ai_test', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(settings)
      });
      const result = await res.json();
      
      if (result.ok) {
        testResult.textContent = '✓ Connection successful';
        testResult.className = 'ai-test-result success';
      } else {
        testResult.textContent = `❌ ${result.error}`;
        testResult.className = 'ai-test-result error';
        console.error('Test details:', result.details);
      }
    } catch (e) {
      testResult.textContent = '❌ Connection failed';
      testResult.className = 'ai-test-result error';
      console.error(e);
    }
    testBtn.disabled = false;
  });

  // Save settings
  saveBtn.addEventListener('click', async () => {
    const settings = {
      api_key: apiKeyInput.value,
      endpoint: endpointInput.value,
      model: modelSelect.value === 'custom' ? customModelInput.value : modelSelect.value,
      temperature: parseFloat(tempInput.value || '0.2'),
      max_tokens: parseInt(maxTokensInput.value || '512', 10)
    };

    try {
      await fetch('/api/ai_settings', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(settings)
      });
      modal.style.display = 'none';
    } catch (e) {
      console.error('Failed to save AI settings:', e);
      alert('Failed to save settings. Please try again.');
    }
  });

  // Close modal
  cancelBtn.addEventListener('click', () => {
    modal.style.display = 'none';
  });
  
  // Close on outside click
  window.addEventListener('click', e => {
    if (e.target === modal) {
      modal.style.display = 'none';
    }
  });
}

// AI Analysis Modal & Logic
async function showAIAnalysis() {
  const overlay = $("#overlay");
  const spinnerText = $("#spinnerText");
  
  if (!data) {
    alert('No data available to analyze');
    return;
  }

  try {
    overlay.style.display = 'flex';
    spinnerText.textContent = 'Running AI analysis...';

    // Get current run directory from data state
    const currentRunDir = data.run_dir;
    
    const res = await fetch('/api/analyze_with_ai', {
      method: 'POST',
      headers: { 
        'Content-Type': 'application/json',
        'X-API-Key': document.querySelector('meta[name="api-key"]').content
      },
      body: JSON.stringify({
        deep: false,
        run_dir: currentRunDir // Pass the current run's directory to analyze
      })
    });
    
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const result = await res.json();

    // Create and show modal
    const modal = document.createElement('div');
    modal.className = 'modal';
    modal.innerHTML = `
      <div class="modal-content ai-modal">
        <h3>AI Analysis</h3>
        <div class="chat-container">
          <div class="chat-messages" id="chatMessages">
            <div class="message assistant">
              ${renderMarkdown(result.ai.shallow)}
            </div>
          </div>
          <div class="chat-input-container">
            <textarea id="chatInput" placeholder="Ask a follow-up question..." rows="2"></textarea>
            <button id="sendChat">Send</button>
          </div>
        </div>
        <div class="modal-actions">
          <button onclick="this.closest('.modal').remove()">Close</button>
        </div>
      </div>
    `;
    
    // Set up chat handlers
    const chatInput = modal.querySelector("#chatInput");
    const sendButton = modal.querySelector("#sendChat");
    const messagesContainer = modal.querySelector("#chatMessages");
    
    async function sendChatMessage() {
      const question = chatInput.value.trim();
      if (!question) return;
      
      // Add user message to chat
      const userDiv = document.createElement('div');
      userDiv.className = 'message user';
      userDiv.textContent = question;
      messagesContainer.appendChild(userDiv);
      
      // Clear input
      chatInput.value = '';
      
      try {
        // Show typing indicator
        const loadingDiv = document.createElement('div');
        loadingDiv.className = 'message assistant typing';
        loadingDiv.textContent = 'Thinking...';
        messagesContainer.appendChild(loadingDiv);
        
        // Send to backend
        const res = await fetch('/api/chat_followup', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'X-API-Key': document.querySelector('meta[name="api-key"]').content
          },
          body: JSON.stringify({
            question,
            run_dir: data.run_dir
          })
        });
        
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const response = await res.json();
        
        // Remove typing indicator
        loadingDiv.remove();
        
        // Add assistant response
        const assistantDiv = document.createElement('div');
        assistantDiv.className = 'message assistant';
        assistantDiv.innerHTML = renderMarkdown(response.answer);
        messagesContainer.appendChild(assistantDiv);
        
        // Scroll to bottom
        messagesContainer.scrollTop = messagesContainer.scrollHeight;
      } catch (e) {
        console.error('Chat failed:', e);
        alert('Failed to send message. Please try again.');
      }
    }
    
    // Send on Enter (but Shift+Enter for new line)
    chatInput.addEventListener('keydown', e => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        sendChatMessage();
      }
    });
    
    sendButton.addEventListener('click', sendChatMessage);

    document.body.appendChild(modal);
    modal.style.display = 'flex';

    // Close on outside click
    modal.addEventListener('click', e => {
      if (e.target === modal) modal.remove();
    });

  } catch (e) {
    console.error('AI analysis failed:', e);
    if (!await checkAIConfigured()) {
      alert('Please configure your AI settings first (API key and endpoint) before running analysis.');
      $("#btnAISettings").click();
    } else {
      alert('Analysis failed. Check the browser console for details and verify your API key is valid.');
    }
  } finally {
    overlay.style.display = 'none';
  }
}

// Helper to check if AI is configured
async function checkAIConfigured() {
  try {
    const res = await fetch('/api/ai_settings', {
      headers: {
        'X-API-Key': document.querySelector('meta[name="api-key"]').content
      }
    });
    const settings = await res.json();
    return !!(settings.api_key && settings.endpoint);
  } catch (e) {
    console.error('Failed to check AI settings:', e);
    return false;
  }
}
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

// Initialize everything
document.addEventListener('DOMContentLoaded', () => {
  setupAISettings();
  setupAI();  // Initialize AI panel and chat functionality
  
  // We don't need this anymore since we're using the panel
  // $("#btnAnalyzeAI").addEventListener('click', showAIAnalysis);
});

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

// === Simple sortable table ===
function makeTableSortable(tableId) {
  const table = document.getElementById(tableId);
  if (!table) return;

  const headers = table.querySelectorAll("th");
  headers.forEach((th, index) => {
    th.style.cursor = "pointer";
    th.addEventListener("click", () => sortTableByColumn(table, index));
  });
}

function sortTableByColumn(table, columnIndex) {
  const tbody = table.tBodies[0];
  const rows = Array.from(tbody.querySelectorAll("tr"));
  const header = table.tHead.rows[0].cells[columnIndex];

  // Toggle sort direction
  const currentDir = header.dataset.sortDir === "asc" ? "desc" : "asc";
  header.dataset.sortDir = currentDir;

  // Sort rows
  const sortedRows = rows.sort((a, b) => {
    const aText = a.cells[columnIndex].innerText.trim();
    const bText = b.cells[columnIndex].innerText.trim();

    // Try numeric comparison first
    const aNum = parseFloat(aText.replace(/[^\d.-]/g, ""));
    const bNum = parseFloat(bText.replace(/[^\d.-]/g, ""));
    const bothNumeric = !isNaN(aNum) && !isNaN(bNum);

    if (bothNumeric) {
      return currentDir === "asc" ? aNum - bNum : bNum - aNum;
    } else {
      return currentDir === "asc"
        ? aText.localeCompare(bText)
        : bText.localeCompare(aText);
    }
  });

  // Rebuild tbody
  tbody.innerHTML = "";
  sortedRows.forEach(row => tbody.appendChild(row));

  // Optional: visually mark sorted column
  table.querySelectorAll("th").forEach(th => th.classList.remove("sorted"));
  header.classList.add("sorted");
}

// Activate sorting for your AP table
makeTableSortable("apTable");

/*** ==========================================================
     CHART (SVG stacked bars)
========================================================== */
function renderChart() {
  const svg = $("#chart");
  svg.innerHTML = "";

  const padL = 110, padR = 20, padT = 18, padB = 32;

  // Build items FIRST so we know how tall the SVG needs to be
  const roams = (data.roams || []);
  const items = roams.map((r, i) => {
    const segs = PHASES.map(p => {
      const ph = r.phases?.[p.key];
      const dur = ph?.duration_ms ?? 0;
      return {
        k: p.key, label: p.label, dur: +dur, color: p.color, status: ph?.status, type: ph?.type,
        target: r.target_bssid, rssi: findRssi(r.target_bssid)
      };
    });
    const total = segs.reduce((s, x) => s + (x.dur || 0), 0);
    return { index: r.roam_index, total, segs, status: r.overall_status, target: r.target_bssid, freq: r.final_freq };
  });

// --- Dynamic SVG height and scroll handling ---
const baseVisibleRows = 20;   // show up to 20 roams without scrolling
const rowPitch = 28;          // estimated vertical spacing per roam row
const baseHeight = 400;       // matches .chartWrap max-height (px)

// Calculate how tall the SVG should be
let desiredHeight = baseHeight;
if (items.length > baseVisibleRows) {
  desiredHeight = padT + padB + items.length * rowPitch;
}

// Apply height: fixed (<=20 rows) or scrollable (>20)
svg.style.height = `${desiredHeight}px`;


  // Now measure after height is set
  const W = svg.clientWidth;
  const H = svg.clientHeight;
  const plotW = W - padL - padR, plotH = H - padT - padB;

  const maxX = Math.max(1, ...items.map(d => d.total));

  // grid + labels
  for (let i = 0; i <= 4; i++) {
    const x = padL + (i / 4) * plotW;
    const gl = document.createElementNS(svg.namespaceURI, "line");
    gl.setAttribute("x1", x); gl.setAttribute("x2", x);
    gl.setAttribute("y1", padT); gl.setAttribute("y2", padT + plotH);
    gl.setAttribute("stroke", "#213045"); gl.setAttribute("stroke-width", "1");
    svg.appendChild(gl);
    const lbl = document.createElementNS(svg.namespaceURI, "text");
    lbl.setAttribute("x", x); lbl.setAttribute("y", H - 10);
    lbl.setAttribute("text-anchor", "middle");
    lbl.setAttribute("fill", "#e8f1ff");
    lbl.textContent = `${Math.round((i / 4) * maxX)} ms`;
    svg.appendChild(lbl);
  }

  // bars + chips
  const rowH = plotH / Math.max(1, items.length);
  const barH = Math.max(14, rowH - 12);
  items.forEach((d, rowIdx) => {
    const y = padT + rowIdx * rowH + (rowH - barH) / 2;
    const statusColor = (d.status === "success" ? cssVar('--ok') : cssVar('--bad')) || "#25e07b";
    const chipGroup = document.createElementNS(svg.namespaceURI, "g");
    const rect = document.createElementNS(svg.namespaceURI, "rect");
    rect.setAttribute("x", 14);
    rect.setAttribute("y", y + (barH - 20) / 2);
    rect.setAttribute("width", 78);
    rect.setAttribute("height", 20);
    rect.setAttribute("rx", 10);
    rect.setAttribute("fill", statusColor);
    rect.setAttribute("opacity", "0.9");
    chipGroup.appendChild(rect);
    const t = document.createElementNS(svg.namespaceURI, "text");
    t.setAttribute("x", 53);
    t.setAttribute("y", y + barH / 2 + 1);
    t.setAttribute("text-anchor", "middle");
    t.setAttribute("class", "rowChip chipTextLight");
    t.textContent = `Roam #${d.index}`;
    chipGroup.appendChild(t);
    svg.appendChild(chipGroup);

    let cursor = 0;
    d.segs.forEach(seg => {
      if (!visible.has(seg.k) || !seg.dur) return;
      const w = (seg.dur / maxX) * plotW;
      const r = document.createElementNS(svg.namespaceURI, "rect");
      r.setAttribute("x", padL + cursor);
      r.setAttribute("y", y);
      r.setAttribute("width", Math.max(0, w));
      r.setAttribute("height", barH);
      r.setAttribute("rx", 4);
      r.setAttribute("fill", seg.color);
      r.setAttribute("opacity", seg.status === "success" ? "1" : "0.9");
      r.addEventListener("mousemove", ev => {
        showTip(ev.clientX, ev.clientY, `
          <h4>Roam #${d.index} · ${seg.status || "—"}</h4>
          <p><strong>AP</strong> ${d.target || "—"} · <strong>${seg.type || seg.k}</strong></p>
          <p>RSSI: ${seg.rssi ?? "—"} · Phase: <strong>${seg.label}</strong> = ${fmtMs(seg.dur)}</p>
          <small>Total: ${fmtMs(d.total)}</small>`);
      });
      r.addEventListener("mouseleave", hideTip);
      svg.appendChild(r);
      cursor += w;
    });
  });

  const leg = $("#legend"); leg.innerHTML = "";
  for (const p of PHASES) {
    const chip = document.createElement("div");
    chip.className = "chip" + (visible.has(p.key) ? "" : " dim");
    chip.innerHTML = `<span class="dot" style="background:${p.color}"></span>${p.label}`;
    chip.onclick = () => { visible.has(p.key) ? visible.delete(p.key) : visible.add(p.key); renderChart(); };
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
        ${errs.length ? `
          <details class="logDetails">
            <summary><span class="pill logPill">Informative logs (${errs.length})</span></summary>
            <pre class="logContent">${errs.join("")}</pre>
          </details>
        ` : ""}
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

function expandAllRoams() {
  document.querySelectorAll("#roams .accBody").forEach(b => b.classList.add("open"));
}

function collapseAllRoams() {
  document.querySelectorAll("#roams .accBody").forEach(b => b.classList.remove("open"));
}

document.addEventListener("DOMContentLoaded", () => {
  $("#btnExpandAll")?.addEventListener("click", expandAllRoams);
  $("#btnCollapseAll")?.addEventListener("click", collapseAllRoams);
});

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

//Top bar logout button
document.addEventListener("DOMContentLoaded", () => {
  const logoutBtn = document.getElementById("btnLogout");
  if (logoutBtn) {
    logoutBtn.addEventListener("click", () => {
      window.location.href = "/logout";
    });
  }
});


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
  // Update global data state
  data = summary;
  // Update UI
  renderHeader();
  renderMetrics();
  renderTable();
  renderChart();
  renderRoams();
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