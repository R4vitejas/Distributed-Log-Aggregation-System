import socket
import time
import random
from flask import Flask, jsonify, render_template_string, request
from cryptography.fernet import Fernet
import threading

# ================= CONFIG =================
SERVER_IP = "0.0.0.0"
PORT = 9999

key = b'7QluHyBCTCsVy9G-qMHrV9paH2fw-BnawNacDG5pUIg='
cipher = Fernet(key)

MAX_BUFFER = 100
SPILL_THRESHOLD = 70

# ================= STATE =================
log_buffer = []
log_id_counter = 0

history = []
total_logs = 0
error_count = 0
lost_packets = 0
spilled_packets = 0
latency_samples = []
client_counts = {"CLIENT1": 0, "CLIENT2": 0}

count = 0
start = time.time()
lock = threading.Lock()

# ================= SOCKET =================
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.bind((SERVER_IP, PORT))

# ================= FLASK =================
app = Flask(__name__)

# ================= HTML =================
HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>LogStream Monitor</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;600;700&family=DM+Sans:wght@400;500;600&display=swap" rel="stylesheet">
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
<style>
  :root {
    --bg:        #0b0d12;
    --surface:   #11141c;
    --surface2:  #181c27;
    --border:    #1e2435;
    --accent:    #5b8af0;
    --c1:        #5ba4f5;
    --c2:        #b07ef8;
    --err:       #f26d6d;
    --warn:      #f5b942;
    --ok:        #52d9a0;
    --muted:     #3a4560;
    --text:      #d0d9ee;
    --textdim:   #68789e;
    --mono:      'JetBrains Mono', monospace;
    --ui:        'DM Sans', sans-serif;
  }
  *, *::before, *::after { box-sizing:border-box; margin:0; padding:0; }
  html, body {
    height:100%; background:var(--bg); color:var(--text);
    font-family:var(--ui); font-size:16px; overflow:hidden;
  }

  .shell { display:grid; height:100vh; grid-template-rows:50px 1fr; }

  /* ── Topbar ── */
  .topbar {
    display:flex; align-items:center; gap:20px; padding:0 20px;
    border-bottom:1px solid var(--border); background:var(--surface);
  }
  .logo {
    font-family:var(--mono); font-size:17px; font-weight:700;
    letter-spacing:.12em; color:var(--accent); text-transform:uppercase;
  }
  .sep { flex:1; }
  .badge {
    display:inline-flex; align-items:center; gap:6px;
    font-family:var(--mono); font-size:13px; color:var(--textdim);
  }
  .dot {
    width:8px; height:8px; border-radius:50%;
    background:var(--ok); box-shadow:0 0 7px var(--ok);
    animation:pulse 2s infinite;
  }
  @keyframes pulse { 0%,100%{opacity:1} 50%{opacity:.3} }
  .threshold-wrap {
    display:flex; align-items:center; gap:7px;
    font-family:var(--mono); font-size:13px; color:var(--textdim);
  }
  .threshold-wrap input {
    width:50px; background:var(--bg); border:1px solid var(--border);
    border-radius:4px; color:var(--accent); font-family:var(--mono);
    font-size:13px; padding:3px 6px; text-align:center; outline:none;
  }
  .threshold-wrap input:focus { border-color:var(--accent); }

  /* ── Main grid ── */
  .main {
    display:grid;
    grid-template-columns:255px 1fr 1fr;
    grid-template-rows:1fr 1fr;
    gap:9px; padding:9px; overflow:hidden;
  }
  .sidebar {
    grid-row:1/3; display:flex; flex-direction:column;
    gap:9px; overflow:hidden; min-height:0;
  }

  /* ── Panel ── */
  .panel {
    background:var(--surface); border:1px solid var(--border);
    border-radius:8px; padding:13px;
    display:flex; flex-direction:column; gap:9px;
    overflow:hidden; min-height:0;
  }
  .panel-title {
    font-family:var(--mono); font-size:12px; font-weight:700;
    letter-spacing:.16em; text-transform:uppercase; color:var(--textdim);
    border-bottom:1px solid var(--border); padding-bottom:8px; flex-shrink:0;
  }

  /* ── Stats ── */
  .stat-grid { display:grid; grid-template-columns:1fr 1fr; gap:7px; }
  .stat {
    background:var(--surface2); border:1px solid var(--border);
    border-radius:6px; padding:9px 11px;
  }
  .stat-label { font-size:11px; color:var(--textdim); font-family:var(--mono); letter-spacing:.08em; }
  .stat-value { font-family:var(--mono); font-size:28px; font-weight:700; line-height:1.1; margin-top:2px; }
  .va { color:var(--accent); }
  .vo { color:var(--ok); }
  .ve { color:var(--err); }
  .vw { color:var(--warn); }

  /* ── Semicircle dial ── */
  .dial-wrap { display:flex; flex-direction:column; align-items:center; gap:3px; }
  .dial-svg  { width:100%; max-width:190px; }
  .dial-ends {
    display:flex; justify-content:space-between; width:100%; max-width:190px;
    font-family:var(--mono); font-size:11px; color:var(--muted); padding:0 6px;
  }
  .dial-sub { font-family:var(--mono); font-size:12px; color:var(--textdim); }

  /* ── Clients ── */
  .client-row {
    display:flex; align-items:center; gap:9px;
    font-family:var(--mono); font-size:14px;
  }
  .client-dot { width:9px; height:9px; border-radius:50%; flex-shrink:0; }
  .bar-bg { flex:1; height:6px; background:var(--bg); border-radius:3px; overflow:hidden; }
  .bar-fill { height:100%; border-radius:3px; transition:width .5s; }
  .client-n { color:var(--textdim); min-width:38px; text-align:right; }

  /* ── Spill ── */
  .spill-box {
    background:var(--surface2); border:1px solid var(--border);
    border-radius:6px; padding:9px 11px;
    font-family:var(--mono); font-size:12px; color:var(--textdim);
  }
  .spill-n { font-size:26px; font-weight:700; display:block; margin-top:2px; }
  .spill-note { font-size:11px; color:var(--muted); margin-top:4px; line-height:1.4; }

  /* ── Chart wrap ── */
  .chart-wrap { flex:1; min-height:0; position:relative; }

  /* ── Log stream ── */
  .log-panel { grid-column:2/4; }
  .log-stream {
    flex:1; min-height:0; overflow-y:auto;
    font-family:var(--mono); font-size:14px;
    display:flex; flex-direction:column; gap:1px;
  }
  .log-stream::-webkit-scrollbar { width:4px; }
  .log-stream::-webkit-scrollbar-thumb { background:var(--border); border-radius:2px; }

  .log-entry {
    display:grid;
    grid-template-columns:82px 90px 52px 1fr 44px;
    gap:8px; padding:5px 9px;
    border-radius:4px; align-items:center;
    border-left:3px solid transparent;
    animation:fadeIn .2s ease;
  }
  @keyframes fadeIn { from{opacity:0;transform:translateY(-3px)} to{opacity:1} }
  .log-entry:hover { background:rgba(255,255,255,.03); }

  /* Per-client colour: left border + very faint tinted bg */
  .lc1 { border-left-color:var(--c1); background:rgba(91,164,245,.055); }
  .lc2 { border-left-color:var(--c2); background:rgba(176,126,248,.055); }
  /* Error/warn override */
  .is-err  { background:rgba(242,109,109,.12) !important; border-left-color:var(--err) !important; }
  .is-warn { background:rgba(245,185,66,.08)  !important; border-left-color:var(--warn) !important; }

  .le-client { font-weight:700; font-size:13px; }
  .lc1-txt   { color:var(--c1); }
  .lc2-txt   { color:var(--c2); }
  .le-ts     { color:var(--muted); font-size:12px; }
  .le-method { color:var(--textdim); font-size:13px; }
  .le-path   { color:var(--text); overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
  .s-ok   { color:var(--ok);   font-weight:700; }
  .s-warn { color:var(--warn); font-weight:700; }
  .s-err  { color:var(--err);  font-weight:700; }
</style>
</head>
<body>
<div class="shell">

  <div class="topbar">
    <span class="logo">&#9632; LogStream</span>
    <div class="badge"><span class="dot"></span> LIVE</div>
    <span class="badge">UDP :9999 &rarr; HTTP :5000</span>
    <div class="sep"></div>
    <div class="threshold-wrap">
      SPILL THRESHOLD
      <input id="th" type="number" value="70" min="1" max="100" onchange="setThreshold()">%
    </div>
  </div>

  <div class="main">

    <div class="sidebar">

      <!-- Stats -->
      <div class="panel">
        <div class="panel-title">Overview</div>
        <div class="stat-grid">
          <div class="stat"><div class="stat-label">TOTAL PKTS</div><div class="stat-value va" id="s-total">0</div></div>
          <div class="stat"><div class="stat-label">RATE /s</div><div class="stat-value vo" id="s-rate">0</div></div>
          <div class="stat"><div class="stat-label">ERRORS</div><div class="stat-value ve" id="s-errors">0</div></div>
          <div class="stat"><div class="stat-label">LOST PKTS</div><div class="stat-value vw" id="s-loss">0</div></div>
        </div>
      </div>

      <!-- Congestion dial -->
      <div class="panel">
        <div class="panel-title">Buffer Congestion</div>
        <div class="dial-wrap">
          <!--
            Semicircle: centre (100,105), radius 80.
            Left tip: (20,105), Right tip: (180,105).
            Arc length = pi * 80 = ~251.33
            stroke-dasharray = 251.33 (full arc)
            stroke-dashoffset = 251.33 means 0% filled, 0 means 100% filled.
            Needle: rotates around (100,105). -90deg = leftmost (0%), +90deg = rightmost (100%).
          -->
          <svg class="dial-svg" viewBox="0 0 200 115" xmlns="http://www.w3.org/2000/svg">
            <!-- track (background arc) -->
            <path d="M 20 105 A 80 80 0 0 1 180 105"
              fill="none" stroke="#1e2435" stroke-width="16" stroke-linecap="round"/>
            <!-- coloured fill arc -->
            <path id="dial-fill"
              d="M 20 105 A 80 80 0 0 1 180 105"
              fill="none" stroke="#52d9a0" stroke-width="16" stroke-linecap="round"
              stroke-dasharray="251.33" stroke-dashoffset="251.33"
              style="transition:stroke-dashoffset .55s ease, stroke .4s ease"/>
            <!-- tick marks at 25 / 50 / 75 % -->
            <line x1="100" y1="27" x2="100" y2="35" stroke="#2a3048" stroke-width="2"/>
            <line x1="43"  y1="63" x2="50"  y2="69" stroke="#2a3048" stroke-width="2"
              transform="rotate(-45 100 105)"/>
            <line x1="157" y1="63" x2="150" y2="69" stroke="#2a3048" stroke-width="2"
              transform="rotate(45 100 105)"/>
            <!-- needle -->
            <line id="dial-needle" x1="100" y1="105" x2="100" y2="34"
              stroke="#c9d1e0" stroke-width="2.5" stroke-linecap="round"
              style="transform-origin:100px 105px; transform:rotate(-90deg);
                     transition:transform .55s ease, stroke .4s ease"/>
            <circle cx="100" cy="105" r="5" fill="#c9d1e0"/>
            <!-- centre percentage text -->
            <text id="dial-pct" x="100" y="90"
              text-anchor="middle" font-family="JetBrains Mono,monospace"
              font-size="24" font-weight="700" fill="#d0d9ee">0%</text>
          </svg>
          <div class="dial-ends"><span>0%</span><span>50%</span><span>100%</span></div>
          <div class="dial-sub" id="dial-buf">0 / 100 packets in buffer</div>
        </div>
      </div>

      <!-- Clients -->
      <div class="panel">
        <div class="panel-title">Clients</div>
        <div style="display:flex;flex-direction:column;gap:11px">
          <div class="client-row">
            <div class="client-dot" style="background:var(--c1)"></div>
            <span style="color:var(--c1);min-width:66px">CLIENT1</span>
            <div class="bar-bg"><div class="bar-fill" id="bar-c1" style="width:0%;background:var(--c1)"></div></div>
            <span class="client-n" id="cnt-c1">0</span>
          </div>
          <div class="client-row">
            <div class="client-dot" style="background:var(--c2)"></div>
            <span style="color:var(--c2);min-width:66px">CLIENT2</span>
            <div class="bar-bg"><div class="bar-fill" id="bar-c2" style="width:0%;background:var(--c2)"></div></div>
            <span class="client-n" id="cnt-c2">0</span>
          </div>
        </div>
      </div>

      <!-- Backpressure -->
      <div class="panel" style="flex:1">
        <div class="panel-title">Backpressure</div>
        <div class="spill-box">
          <span>SPILLED TO DISK</span>
          <span class="spill-n vw" id="s-spill">0</span>
          <div class="spill-note">Written to spill_logs.txt when buffer exceeds threshold</div>
        </div>
        <div class="spill-box" style="margin-top:2px">
          <span>BUFFER USED</span>
          <span class="spill-n va" id="s-bufsize">0 / 100</span>
          <div class="spill-note">In-memory ring buffer, FIFO, time-ordered</div>
        </div>
      </div>

    </div>

    <!-- Throughput -->
    <div class="panel">
      <div class="panel-title">Throughput — packets / sec</div>
      <div class="chart-wrap"><canvas id="chart-throughput"></canvas></div>
    </div>

    <!-- Latency -->
    <div class="panel">
      <div class="panel-title">Simulated Network Latency — ms</div>
      <div class="chart-wrap"><canvas id="chart-latency"></canvas></div>
    </div>

    <!-- Log stream -->
    <div class="panel log-panel">
      <div class="panel-title">
        Decrypted Log Stream — time-ordered
        <span style="float:right;font-size:12px;color:var(--muted);font-weight:400;letter-spacing:0">
          <span style="color:var(--c1)">&#9612;</span> CLIENT1 &nbsp;
          <span style="color:var(--c2)">&#9612;</span> CLIENT2 &nbsp;
          <span style="color:var(--err)">&#9612;</span> 5xx &nbsp;
          <span style="color:var(--warn)">&#9612;</span> 4xx
        </span>
      </div>
      <!-- header row -->
      <div style="display:grid;grid-template-columns:82px 90px 52px 1fr 44px;gap:8px;
                  padding:0 9px 4px;font-family:var(--mono);font-size:11px;color:var(--muted);
                  border-bottom:1px solid var(--border);flex-shrink:0">
        <span>CLIENT</span><span>TIME</span><span>METHOD</span><span>PATH</span><span>STATUS</span>
      </div>
      <div class="log-stream" id="log-stream"></div>
    </div>

  </div>
</div>

<script>
let tChart, lChart;
let lastSeenId = -1;  // monotonic: only render entries with id > this

const ARC_LEN = Math.PI * 80;  // semicircle circumference for r=80

const chartDefaults = {
  responsive:true, maintainAspectRatio:false,
  animation:{duration:250},
  plugins:{legend:{display:false}},
  scales:{
    x:{
      ticks:{color:'#3a4560',font:{family:'JetBrains Mono',size:11},maxTicksLimit:8},
      grid:{color:'#181c27'}, border:{color:'#1e2435'}
    },
    y:{
      ticks:{color:'#3a4560',font:{family:'JetBrains Mono',size:11},maxTicksLimit:5},
      grid:{color:'#181c27'}, border:{color:'#1e2435'}
    }
  }
};

function initCharts() {
  tChart = new Chart(document.getElementById('chart-throughput'), {
    type:'line',
    data:{
      labels:[],
      datasets:[{
        data:[], borderColor:'#5b8af0',
        backgroundColor:'rgba(91,138,240,.10)',
        borderWidth:2.5, pointRadius:0, tension:0.4, fill:true
      }]
    },
    options:{...chartDefaults}
  });

  lChart = new Chart(document.getElementById('chart-latency'), {
    type:'bar',
    data:{
      labels:[],
      datasets:[{
        data:[],
        backgroundColor: ctx => {
          const v = ctx.raw;
          if (v > 150) return 'rgba(242,109,109,.78)';
          if (v > 80)  return 'rgba(245,185,66,.78)';
          return 'rgba(82,217,160,.68)';
        },
        borderRadius:3, borderSkipped:false
      }]
    },
    options:{
      ...chartDefaults,
      scales:{...chartDefaults.scales,
        y:{...chartDefaults.scales.y, suggestedMin:0, suggestedMax:220}}
    }
  });
}

function updateDial(pct) {
  const fill   = document.getElementById('dial-fill');
  const needle = document.getElementById('dial-needle');
  const txt    = document.getElementById('dial-pct');
  const col    = pct > 85 ? '#f26d6d' : pct > 60 ? '#f5b942' : '#52d9a0';

  // dashoffset: full arc (251.33) = 0%, 0 = 100%
  fill.style.strokeDashoffset = ARC_LEN * (1 - pct / 100);
  fill.style.stroke = col;
  txt.textContent   = pct + '%';
  txt.setAttribute('fill', col);

  // needle: -90deg = 0% (left), +90deg = 100% (right)
  needle.style.transform = `rotate(${-90 + pct * 1.8}deg)`;
  needle.style.stroke     = col;
}

function statusCls(code) {
  if (code >= 500) return 's-err';
  if (code >= 400) return 's-warn';
  return 's-ok';
}
function rowCls(client, code) {
  if (code >= 500) return 'is-err';
  if (code >= 400) return 'is-warn';
  return client === 'CLIENT1' ? 'lc1' : 'lc2';
}

function renderLogs(entries) {
  const container = document.getElementById('log-stream');
  // entries already filtered server-side to id > lastSeenId, but double-check
  const fresh = entries.filter(e => e.id > lastSeenId);
  if (!fresh.length) return;

  fresh.forEach(e => {
    const code = parseInt(e.status);
    const t    = new Date(parseFloat(e.ts) * 1000);
    const ms   = String(t.getMilliseconds()).padStart(3,'0');
    const ts   = t.toLocaleTimeString('en-GB',{hour12:false}) + '.' + ms;
    const txtCls = e.client === 'CLIENT1' ? 'lc1-txt' : 'lc2-txt';

    const div = document.createElement('div');
    div.className = 'log-entry ' + rowCls(e.client, code);
    div.innerHTML =
      `<span class="le-client ${txtCls}">${e.client}</span>` +
      `<span class="le-ts">${ts}</span>` +
      `<span class="le-method">${e.method}</span>` +
      `<span class="le-path">${e.path}</span>` +
      `<span class="${statusCls(code)}">${e.status}</span>`;
    container.appendChild(div);

    if (e.id > lastSeenId) lastSeenId = e.id;
  });

  // keep DOM tidy
  while (container.children.length > 120) container.removeChild(container.firstChild);
  container.scrollTop = container.scrollHeight;
}

async function setThreshold() {
  await fetch('/set_threshold?value=' + document.getElementById('th').value);
}

async function tick() {
  try {
    const res = await fetch('/data?since=' + lastSeenId);
    const d   = await res.json();

    document.getElementById('s-total').textContent   = d.total;
    document.getElementById('s-rate').textContent    = d.rate;
    document.getElementById('s-errors').textContent  = d.errors;
    document.getElementById('s-loss').textContent    = d.loss;
    document.getElementById('s-spill').textContent   = d.spilled;
    document.getElementById('s-bufsize').textContent = d.bufsize + ' / 100';
    document.getElementById('dial-buf').textContent  = d.bufsize + ' / 100 packets in buffer';

    updateDial(d.congestion);

    const tot = (d.c1 + d.c2) || 1;
    document.getElementById('bar-c1').style.width = (d.c1/tot*100) + '%';
    document.getElementById('bar-c2').style.width = (d.c2/tot*100) + '%';
    document.getElementById('cnt-c1').textContent  = d.c1;
    document.getElementById('cnt-c2').textContent  = d.c2;

    tChart.data.labels            = d.history.map((_,i) => (i-d.history.length+1)+'s');
    tChart.data.datasets[0].data  = d.history;
    tChart.update('none');

    lChart.data.labels            = d.latency.map((_,i) => '#'+(i+1));
    lChart.data.datasets[0].data  = d.latency;
    lChart.update('none');

    renderLogs(d.logs);
  } catch(e) { /* skip */ }
}

initCharts();
updateDial(0);
setInterval(tick, 1000);
tick();
</script>
</body>
</html>"""

# ─── Routes ───────────────────────────────────────────────

@app.route("/")
def home():
    return render_template_string(HTML)

@app.route("/set_threshold")
def set_threshold():
    global SPILL_THRESHOLD
    try:
        SPILL_THRESHOLD = max(1, min(100, int(request.args.get("value", 70))))
    except ValueError:
        pass
    return "OK"

@app.route("/data")
def data():
    since = int(request.args.get("since", -1))
    with lock:
        new_logs = [e for e in log_buffer if e["id"] > since]
        data = {
            "logs":      new_logs,
            "total":     total_logs,
            "errors":    error_count,
            "history":   list(history),
            "rate":      history[-1] if history else 0,
            "congestion":int((len(log_buffer) / MAX_BUFFER) * 100),
            "latency":   list(latency_samples),
            "loss":      lost_packets,
            "spilled":   spilled_packets,
            "bufsize":   len(log_buffer),
            "c1":        client_counts["CLIENT1"],
            "c2":        client_counts["CLIENT2"],
        }
    return jsonify(data)

# ─── UDP Server ───────────────────────────────────────────

def udp_server():
    global total_logs, error_count, count, start
    global lost_packets, spilled_packets, log_id_counter

    while True:
        try:
            raw_data, addr = sock.recvfrom(4096)

            # count EVERY packet received
            with lock:
                total_logs += 1

            # simulate packet loss
            if random.random() < 0.05:
                with lock:
                    lost_packets += 1
                continue

            # decrypt
            try:
                msg = cipher.decrypt(raw_data).decode()
                print("DECRYPTED:", msg)
            except Exception as e:
                print("DECRYPT FAILED:", e)
                continue

            # simulate latency
            latency = random.randint(10, 200)
            time.sleep(latency / 1000)

            # parse message
            parts = msg.split("|")
            try:
                client_id   = parts[0]
                timestamp   = float(parts[1])
                method      = parts[3]
                path        = parts[4]
                status_str  = parts[5]
                size        = parts[6] if len(parts) > 6 else "?"
                status_code = int(status_str)
            except Exception:
                client_id   = "UNKNOWN"
                timestamp   = time.time()
                method      = "GET"
                path        = "/"
                status_str  = "200"
                size        = "?"
                status_code = 200

            # compute congestion
            with lock:
                current_buf_len = len(log_buffer)
            congestion = int((current_buf_len / MAX_BUFFER) * 100)

            entry = {
                "id":     log_id_counter,
                "client": client_id,
                "ts":     timestamp,
                "method": method,
                "path":   path,
                "status": status_str,
                "size":   size,
            }

            # ALWAYS push to buffer
            with lock:
                log_id_counter += 1
                log_buffer.append(entry)

                if len(log_buffer) > MAX_BUFFER:
                    log_buffer.pop(0)

                latency_samples.append(latency)
                if len(latency_samples) > 40:
                    latency_samples.pop(0)

                count += 1

                if client_id in client_counts:
                    client_counts[client_id] += 1

                if status_code >= 500:
                    error_count += 1

            # ALSO spill if congested
            if congestion > SPILL_THRESHOLD:
                with open("spill_logs.txt", "a") as f:
                    f.write(msg + "\n")
                with lock:
                    spilled_packets += 1

            # throughput tracking
            with lock:
                if time.time() - start >= 1:
                    smooth = int(history[-1] * 0.7 + count * 0.3) if history else count
                    history.append(smooth)
                    if len(history) > 60:
                        history.pop(0)
                    count = 0
                    start = time.time()

        except Exception:
            pass
        
if __name__ == "__main__":
    threading.Thread(target=udp_server, daemon=True).start()
    app.run(host="0.0.0.0", port=5000, debug=False, threaded=True)






