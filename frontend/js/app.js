(function () {
  const els = {
    wsDot: document.getElementById("wsDot"),
    wsLabel: document.getElementById("wsLabel"),
    doorState: document.getElementById("doorState"),
    elapsed: document.getElementById("elapsed"),
    deviceId: document.getElementById("deviceId"),
    lastSeen: document.getElementById("lastSeen"),
    alarm: document.getElementById("alarm"),
    log: document.getElementById("log"),
    msgCount: document.getElementById("msgCount"),
  };

  let msgCount = 0;
  let latest = null;
  let receivedAt = 0;
  let ws = null;
  let pollTimer = null;

  function setConn(ok, label) {
    els.wsDot.className = "dot " + (ok ? "dot-on" : "dot-off");
    els.wsLabel.textContent = label;
  }

  function fmtElapsed(s) {
    s = Math.max(0, Math.floor(s));
    if (s < 60) return s + " s";
    const m = Math.floor(s / 60);
    return m + "m " + (s % 60) + "s";
  }

  function render(data) {
    latest = data;
    receivedAt = Date.now();
    if (!data || data.connected === false && !data.door_state) {
      if (!data.door_state) {
        els.doorState.textContent = "NO DATA";
        return;
      }
    }
    const state = data.door_state || "—";
    els.doorState.textContent = state;
    els.doorState.className = "big " + (state === "OPEN" ? "state-open" : state === "CLOSED" ? "state-closed" : "");
    els.deviceId.textContent = data.device_id || "unknown";
    const alarm = data.alarm_active;
    els.alarm.textContent = alarm === true ? "ACTIVE" : alarm === false ? "OFF" : "—";
    els.alarm.className = "big " + (alarm ? "alarm-on" : "alarm-off");
    if (data._received_at) {
      const d = new Date(data._received_at * 1000);
      els.lastSeen.textContent = "last message: " + d.toLocaleTimeString();
    }
  }

  function tick() {
    if (!latest || !latest.door_state) return;
    let open = latest.door_state === "OPEN";
    let base = latest.door_open_seconds || 0;
    const recvMs = latest._received_at ? latest._received_at * 1000 : 0;
    if (open && recvMs) {
      base += Math.max(0, (Date.now() - recvMs) / 1000);
    }
    els.elapsed.textContent = fmtElapsed(open ? base : 0);
    const stale = Date.now() - receivedAt > 5000;
    if (stale) {
      setConn(false, "stale — no data 5s");
      els.lastSeen.textContent = "STALE (client clock) — server last: " +
        (latest._received_at ? new Date(latest._received_at * 1000).toLocaleTimeString() : "—");
    }
  }

  function addLog(source, payload) {
    msgCount++;
    els.msgCount.textContent = msgCount + " messages";
    const line = document.createElement("div");
    line.className = "line";
    const time = new Date().toLocaleTimeString();
    line.innerHTML = '<span class="t">' + time + '</span><span class="src">[' + source + ']</span>' +
      escapeHtml(JSON.stringify(payload));
    els.log.appendChild(line);
    while (els.log.children.length > 60) els.log.removeChild(els.log.firstChild);
    els.log.scrollTop = els.log.scrollHeight;
  }

  function escapeHtml(s) {
    return s.replace(/[&<>]/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;" }[c];
    });
  }

  function handleWsMessage(text) {
    let msg;
    try { msg = JSON.parse(text); } catch { return; }
    addLog("ws", msg);
    if (msg.type === "state" && msg.data) render(msg.data);
    if (msg.type === "event" && msg.data && msg.data.raw && !latest) {
      render(Object.assign({ _received_at: Date.now() / 1000 }, msg.data.raw));
    }
  }

  function connectWs() {
    const proto = location.protocol === "https:" ? "wss:" : "ws:";
    ws = new WebSocket(proto + "//" + location.host + "/ws/live");
    ws.onopen = () => setConn(true, "live (websocket)");
    ws.onmessage = (e) => handleWsMessage(e.data);
    ws.onclose = () => {
      setConn(false, "ws down — http fallback");
      startPolling();
      setTimeout(connectWs, 2000);
    };
    ws.onerror = () => ws.close();
  }

  async function fetchStatus() {
    try {
      const r = await fetch("/api/device/status", { cache: "no-store" });
      if (!r.ok) throw new Error("HTTP " + r.status);
      const data = await r.json();
      render(data);
      if (ws && ws.readyState === WebSocket.OPEN) return;
      setConn(true, "live (http fallback)");
    } catch (err) {
      setConn(false, "server unreachable");
    }
  }

  function startPolling() {
    if (pollTimer) return;
    pollTimer = setInterval(fetchStatus, 2000);
    fetchStatus();
  }

  connectWs();
  startPolling();
  setInterval(tick, 500);
  fetchStatus();
})();
