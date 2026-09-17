/**
 * Lightweight Mock Backend
 *
 * Purpose:
 *  Replaces backend service for local integration testing.
 *
 * Endpoints:
 *  POST /api/internal/positions  — receive position from Python service
 *  GET  /positions               — return all stored positions as JSON
 *  GET  /                        — map UI (Leaflet + OpenStreetMap)
 *  GET  /health                  — health check
 *
 * Run: node mock_backend/server.js
 */

"use strict";

const fs   = require("fs");
const http = require("http");
const path = require("path");

// ---------------------------------------------------------------------------
// .env loader
// ---------------------------------------------------------------------------

function loadEnv() {
  const file = path.resolve(__dirname, "..", ".env");
  try {
    fs.readFileSync(file, "utf8").split("\n").forEach(line => {
      const clean = line.trim();
      if (!clean || clean.startsWith("#") || !clean.includes("=")) return;
      const [k, ...v] = clean.split("=");
      if (!(k.trim() in process.env)) process.env[k.trim()] = v.join("=").trim();
    });
  } catch {}
}

loadEnv();

const PORT    = Number(process.env.BACKEND_PORT || 4200);
const API_KEY = process.env.BACKEND_API_KEY;

// ---------------------------------------------------------------------------
// In-memory store — one entry per tag_id (last known position)
// ---------------------------------------------------------------------------

const positions = new Map([
  ["default-tag-001", {
    tag_id:     "default-tag-001",
    lat:        14.792644500732422,
    lng:        -17.361555099487305,
    accuracy:   10,
    confidence: 2,
    timestamp:  new Date().toISOString(),
  }],
]);

// ---------------------------------------------------------------------------
// Utilities
// ---------------------------------------------------------------------------

function send(res, status, contentType, body) {
  res.writeHead(status, { "Content-Type": contentType });
  res.end(body);
}

function json(res, status, data) {
  send(res, status, "application/json", JSON.stringify(data));
}

function readBody(req) {
  return new Promise((resolve, reject) => {
    let data = "";
    req.on("data", chunk => (data += chunk));
    req.on("end",  () => resolve(data));
    req.on("error", reject);
  });
}

function log(level, message, meta) {
  const ts   = new Date().toISOString().slice(0, 23).replace("T", " ");
  const line = meta ? `${message} | ${JSON.stringify(meta)}` : message;
  console.log(`${ts} [${level.padEnd(4)}] ${line}`);
}

// ---------------------------------------------------------------------------
// Map HTML (Leaflet + OpenStreetMap)
// ---------------------------------------------------------------------------

function buildMapHtml() {
  return /* html */ `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Live Tag Map</title>
  <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
  <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
  <style>
    * { margin: 0; padding: 0; box-sizing: border-box; }

    body {
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      background: #f8fafc;
      color: #000000;
      display: flex;
      flex-direction: column;
      height: 100vh;
    }

    header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 12px 20px;
      background: #ffffff;
      border-bottom: 1px solid #e2e8f0;
      flex-shrink: 0;
      box-shadow: 0 1px 3px rgba(0,0,0,0.06);
    }

    header h1 { font-size: 16px; font-weight: 600; letter-spacing: 0.3px; }
    header h1 span { color: #1615B5; }

    #status {
      font-size: 12px;
      padding: 4px 10px;
      border-radius: 20px;
      background: #f1f5f9;
      border: 1px solid #cbd5e1;
      color: #64748b;
    }

    #status.live { border-color: #16a34a; color: #16a34a; background: #f0fdf4; }

    #map { flex: 1; }

    #panel {
      width: 100%;
      max-height: 200px;
      overflow-y: auto;
      background: #ffffff;
      border-top: 1px solid #e2e8f0;
      flex-shrink: 0;
    }

    table {
      width: 100%;
      border-collapse: collapse;
      font-size: 12px;
    }

    thead th {
      position: sticky;
      top: 0;
      background: #f8fafc;
      padding: 8px 12px;
      text-align: left;
      font-weight: 600;
      color: #64748b;
      border-bottom: 1px solid #e2e8f0;
      text-transform: uppercase;
      letter-spacing: 0.5px;
      font-size: 11px;
    }

    tbody tr { border-bottom: 1px solid #f1f5f9; }
    tbody tr:hover { background: #f8fafc; }
    tbody td { padding: 7px 12px; color: #334155; }
    tbody td.tag  { color: #1615B5; font-family: monospace; }
    tbody td.ts   { color: #94a3b8; }

    .btn-locate {
      padding: 3px 10px;
      font-size: 11px;
      font-weight: 500;
      border: 1px solid #1615B5;
      border-radius: 6px;
      color: #1615B5;
      background: transparent;
      cursor: pointer;
      transition: background 0.15s, color 0.15s;
    }
    .btn-locate:hover { background: #3e3ef6; color: #fff; }

    .empty {
      padding: 20px;
      text-align: center;
      color: #94a3b8;
      font-size: 12px;
    }
  </style>
</head>
<body>

<header>
  <h1>Live Tag Map</h1>
  <span id="status">Connecting...</span>
</header>

<div id="map"></div>

<div id="panel">
  <table>
    <thead>
      <tr>
        <th>Tag ID</th>
        <th>Latitude</th>
        <th>Longitude</th>
        <th>Accuracy (m)</th>
        <th>Confidence</th>
        <th>Last seen</th>
        <th></th>
      </tr>
    </thead>
    <tbody id="table-body">
      <tr><td colspan="6" class="empty">Waiting for positions...</td></tr>
    </tbody>
  </table>
</div>

<script>
  const map = L.map("map").setView([14.7167, -17.4677], 13);

  L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
    attribution: "&copy; OpenStreetMap contributors",
    maxZoom: 19,
  }).addTo(map);

  const markers = {};

  function tagColor(tagId) {
    let hash = 0;
    for (const c of tagId) hash = (hash * 31 + c.charCodeAt(0)) >>> 0;
    const hue = hash % 360;
    return \`hsl(\${hue}, 80%, 55%)\`;
  }

  function makeIcon(tagId) {
    const color = tagColor(tagId);
    const html = \`<div style="
      width: 40px;
      height: 40px;
      border-radius: 50%;
      background: \${color};
      border: 3px solid #fff;
      box-shadow: 0 2px 8px rgba(0,0,0,0.4);
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 18px;
      line-height: 1;
    ">🧳</div>\`;
    return L.divIcon({
      html,
      iconSize:    [40, 40],
      iconAnchor:  [20, 20],
      popupAnchor: [0, -24],
      className:   "",
    });
  }

  function formatDate(iso) {
    if (!iso) return "—";
    const d = new Date(iso);
    return d.toLocaleDateString("fr-FR", { day: "2-digit", month: "short", year: "numeric" })
      + " " + d.toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit", second: "2-digit" });
  }

  function locateTag(tagId) {
    const m = markers[tagId];
    if (!m) return;
    map.flyTo(m.getLatLng(), 16, { duration: 1 });
    m.openPopup();
  }

  function updateMap(data) {
    const tbody = document.getElementById("table-body");

    if (data.length === 0) {
      tbody.innerHTML = '<tr><td colspan="7" class="empty">Waiting for positions...</td></tr>';
      return;
    }

    data.forEach(p => {
      const latlng = [p.lat, p.lng];
      const popup  = \`<b>Tag</b>: \${p.tag_id}<br>
                      <b>Lat</b>: \${p.lat}<br>
                      <b>Lng</b>: \${p.lng}<br>
                      <b>Accuracy</b>: \${p.accuracy ?? "—"} m<br>
                      <b>Confidence</b>: \${p.confidence ?? "—"}<br>
                      <b>Last seen</b>: \${formatDate(p.timestamp)}\`;

      if (markers[p.tag_id]) {
        markers[p.tag_id].setLatLng(latlng).setPopupContent(popup);
      } else {
        markers[p.tag_id] = L.marker(latlng, { icon: makeIcon(p.tag_id) })
          .addTo(map)
          .bindPopup(popup);
      }
    });

    const latlngs = data.map(p => [p.lat, p.lng]);
    if (latlngs.length === 1) {
      map.setView(latlngs[0], 15);
    } else {
      map.fitBounds(latlngs, { padding: [40, 40] });
    }

    tbody.innerHTML = data
      .sort((a, b) => new Date(b.timestamp) - new Date(a.timestamp))
      .map(p => \`<tr>
        <td class="tag">\${p.tag_id}</td>
        <td>\${p.lat.toFixed(6)}</td>
        <td>\${p.lng.toFixed(6)}</td>
        <td>\${p.accuracy ?? "—"}</td>
        <td>\${p.confidence ?? "—"}</td>
        <td class="ts">\${formatDate(p.timestamp)}</td>
        <td><button class="btn-locate" onclick="locateTag('\${p.tag_id}')">Localiser</button></td>
      </tr>\`).join("");
  }

  async function refresh() {
    try {
      const res  = await fetch("/positions");
      const data = await res.json();
      updateMap(data);
      document.getElementById("status").textContent = \`\${data.length} tag(s) live\`;
      document.getElementById("status").className = "live";
    } catch {
      document.getElementById("status").textContent = "Disconnected";
      document.getElementById("status").className = "";
    }
  }

  refresh();
  setInterval(refresh, 5000);
</script>
</body>
</html>`;
}

// ---------------------------------------------------------------------------
// Route handlers
// ---------------------------------------------------------------------------

async function handleIncomingPosition(req, res) {
  const key = req.headers["x-api-key"];
  if (key !== API_KEY) {
    log("WARN", "Unauthorized request — invalid X-API-Key");
    return json(res, 401, { error: "Unauthorized" });
  }

  let body;
  try {
    body = JSON.parse(await readBody(req));
  } catch {
    log("WARN", "Invalid JSON body");
    return json(res, 400, { error: "Invalid JSON" });
  }

  const { tag_id, lat, lng, accuracy, confidence, timestamp } = body;
  if (!tag_id || lat == null || lng == null) {
    log("WARN", "Missing required fields", body);
    return json(res, 422, { error: "Missing required fields: tag_id, lat, lng" });
  }

  positions.set(tag_id, { tag_id, lat, lng, accuracy, confidence, timestamp });
  log("INFO", "Position stored", { tag_id, lat, lng });
  return json(res, 200, { ok: true });
}

function handleGetPositions(_, res) {
  json(res, 200, Array.from(positions.values()));
}

function handleMap(_, res) {
  send(res, 200, "text/html; charset=utf-8", buildMapHtml());
}

function handleHealth(_, res) {
  json(res, 200, { status: "ok" });
}

// ---------------------------------------------------------------------------
// Server
// ---------------------------------------------------------------------------

const server = http.createServer((req, res) => {
  const { method, url } = req;

  if (method === "GET"  && url === "/")                         return handleMap(req, res);
  if (method === "GET"  && url === "/health")                   return handleHealth(req, res);
  if (method === "GET"  && url === "/positions")                return handleGetPositions(req, res);
  if (method === "POST" && url === "/api/internal/positions")   return handleIncomingPosition(req, res);

  return json(res, 404, { error: "Not found" });
});

server.listen(PORT, () => {
  log("INFO", `Mock backend running on :${PORT}`);
  log("INFO", `Map available at http://localhost:${PORT}`);
});
