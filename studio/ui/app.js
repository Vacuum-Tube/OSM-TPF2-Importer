/* global L, pywebview */
const OPT_KEYS = [
  ["build_streets", "Streets"],
  ["build_tracks", "Tracks"],
  ["build_subwaytracks", "Subway / light rail"],
  ["build_tramtracks", "Tram as tracks"],
  ["build_bridges", "Bridges"],
  ["build_tunnels", "Tunnels"],
  ["build_signals", "Signals"],
  ["build_autobahn", "Motorways"],
  ["build_streets_street_types", "Street types"],
  ["build_streets_footway_types", "Footways"],
  ["build_streets_water", "Water streets"],
  ["build_streets_airport", "Airport roads"],
  ["build_buildings_residential", "Houses"],
  ["build_buildings_commercial", "Shops / offices"],
  ["build_buildings_industrial", "Industry buildings"],
  ["skip_nodes_outofbounds", "Skip out of bounds"],
  ["crash_type_not_found", "Abort if vanilla type missing"],
];

const api = () => window.pywebview.api;

let map, rect, box, sizeKey = "huge", targetGame = "tpf2";
let currentJobId = "";
const logEl = () => document.getElementById("log");

function log(msg) {
  const el = logEl();
  const line = typeof msg === "string" ? msg : JSON.stringify(msg, null, 2);
  el.textContent += (el.textContent ? "\n" : "") + line;
  el.scrollTop = el.scrollHeight;
}

function boundsLatLng(b) {
  return [[b.minlat, b.minlon], [b.maxlat, b.maxlon]];
}

function hasPlace() {
  return !!(box && Number.isFinite(box.center_lat) && Number.isFinite(box.center_lon));
}

function needPlace() {
  if (hasPlace()) return true;
  log("Search a place or Shift-click the map first — there is no default city.");
  return false;
}

function fmtMb(bytes) {
  if (bytes == null) return "—";
  if (bytes < 1e6) return Math.round(bytes / 1e3) + " KB";
  return (bytes / 1e6).toFixed(1) + " MB";
}

function hideHits() {
  const el = document.getElementById("searchHits");
  if (el) {
    el.hidden = true;
    el.innerHTML = "";
  }
}

function showHits(hits) {
  const host = document.getElementById("searchHits");
  if (!host) return;
  host.innerHTML = "";
  hits.forEach((hit) => {
    const b = document.createElement("button");
    b.type = "button";
    b.className = "hit";
    b.appendChild(document.createTextNode(hit.label || "Place"));
    const detail = document.createElement("small");
    detail.textContent = `${hit.type || ""} ${hit.lat.toFixed(4)}, ${hit.lon.toFixed(4)}`;
    b.appendChild(detail);
    b.onclick = async () => {
      hideHits();
      document.getElementById("searchQ").value = hit.label || "";
      log(hit.label);
      await refreshBox(hit.lat, hit.lon, document.getElementById("sizeKey").value, true);
    };
    host.appendChild(b);
  });
  host.hidden = !hits.length;
}

async function applyBoxResult(r, fit) {
  if (!r || !r.ok || !r.box) return r;
  if (r.size_key) {
    sizeKey = r.size_key;
    const sel = document.getElementById("sizeKey");
    if (sel && sel.value !== sizeKey) sel.value = sizeKey;
  }
  drawBox(r.box, fit !== false);
  renderFacts(r);
  return r;
}

function renderWork(st) {
  const facts = document.getElementById("workFacts");
  const warn = document.getElementById("osmWarn");
  const preview = document.getElementById("installPreview");
  if (!st) return;
  if (facts) {
    const osm = st.osm || {};
    const work = st.work_lua || {};
    const live = st.live_lua || {};
    const bldg = st.buildings || {};
    const ov = st.overlap == null ? "—" : Math.round(st.overlap * 100) + "%";
    const crop = st.cropped || {};
    facts.innerHTML = `
      <dt>OSM</dt><dd>${osm.path ? (fmtMb(osm.bytes) + " · " + (osm.mtime_label || "") + (osm.kind && osm.kind !== "osm" ? " · " + osm.kind : "")) : "none"}</dd>
      <dt>Crop</dt><dd>${crop.path ? fmtMb(crop.bytes) : "—"}</dd>
      <dt>Overlap</dt><dd>${ov}${st.file_box ? " · using extract bounds" : ""}</dd>
      <dt>Work lua</dt><dd>${work.path ? (fmtMb(work.bytes) + (st.work_loader ? " · chunked" : "")) : "none"}</dd>
      <dt>Live lua</dt><dd>${live.path ? fmtMb(live.bytes) : "none"}</dd>
      <dt>Buildings</dt><dd>${bldg.path ? fmtMb(bldg.bytes) : "none"}</dd>
      <dt>Install</dt><dd>${(st.install && st.install.note) || "—"}</dd>
    `;
  }
  if (warn) {
    warn.hidden = !st.warning;
    warn.textContent = st.warning || "";
  }
  if (preview && st.install) {
    preview.textContent = st.install.replace
      ? ("Install will replace live osmdata.lua (" + (st.install.note || "Studio work file is newer") + ").")
      : ("Install will keep live osmdata.lua (" + (st.install.note || "newer than Studio work file") + ").");
  }
  renderPipeline(st.pipeline);
}

function renderPipeline(pipe) {
  const host = document.getElementById("pipeline");
  if (!host) return;
  const steps = [
    ["place", "Place"],
    ["osm", "OSM"],
    ["convert", "Convert"],
    ["heightmap", "Height"],
    ["overlay", "Overlay"],
    ["install", "Install"],
  ];
  pipe = pipe || {};
  host.innerHTML = steps.map(([key, label]) => {
    const on = pipe[key] ? " is-on" : "";
    const panel = { place: "map", osm: "osm", convert: "osm", heightmap: "sat", overlay: "sat", install: "install" }[key];
    return `<li class="${on.trim()}" data-panel="${panel}"><span class="dot"></span>${label}</li>`;
  }).join("");
  host.querySelectorAll("li[data-panel]").forEach((li) => {
    li.onclick = () => {
      const btn = document.querySelector(`.step[data-panel="${li.dataset.panel}"]`);
      if (btn) btn.click();
    };
  });
}

async function loadTerrainPreviews() {
  try {
    const r = await api().terrain_previews();
    const hm = document.getElementById("hmPreview");
    const ov = document.getElementById("ovPreview");
    if (hm) {
      hm.hidden = !r.heightmap;
      if (r.heightmap) hm.src = r.heightmap;
    }
    if (ov) {
      ov.hidden = !r.overlay;
      if (r.overlay) ov.src = r.overlay;
    }
  } catch (err) {
    /* optional */
  }
}

async function refreshWork() {
  try {
    const st = await api().work_status();
    renderWork(st);
    if (st.osm && st.osm.path) document.getElementById("osmPath").textContent = st.osm.path;
    return st;
  } catch (err) {
    return null;
  }
}

async function ensureBox() {
  if (hasPlace()) return true;
  const st = await refreshWork();
  if (st && st.adoptable && st.osm_bounds) {
    const r = await api().use_osm_bounds();
    if (r && r.ok) {
      await applyBoxResult(r, true);
      log("Yellow box set from OSM extract bounds (" + (r.size_key || sizeKey) + ").");
      return true;
    }
  }
  return needPlace();
}

async function syncBoxFromForm() {
  const latEl = document.getElementById("lat");
  const lonEl = document.getElementById("lon");
  const keyEl = document.getElementById("sizeKey");
  if (!latEl || !lonEl || !keyEl) return box;
  const lat = Number(latEl.value);
  const lon = Number(lonEl.value);
  const key = keyEl.value;
  if (!Number.isFinite(lat) || !Number.isFinite(lon)) return box;
  if (
    box
    && Math.abs(box.center_lat - lat) < 1e-7
    && Math.abs(box.center_lon - lon) < 1e-7
    && sizeKey === key
  ) {
    return box;
  }
  await refreshBox(lat, lon, key, false);
  return box;
}

function renderFacts(payload) {
  const b = payload && payload.box;
  const s = payload && payload.scale;
  const size = (payload && payload.size) || {};
  const gameLabel = targetGame === "tf3" ? "Extraction extent" : "TPF2 preset";
  const sizeLabel = targetGame === "tf3"
    ? `${size.meters || "?"} m square`
    : `${size.label || sizeKey} · ${size.meters || "?"} m`;
  if (!b || !s) {
    document.getElementById("facts").innerHTML = `
      <dt>Place</dt><dd>Search a city or Shift-click the map</dd>
      <dt>${gameLabel}</dt><dd>${sizeLabel}</dd>
    `;
    return;
  }
  const exp = size.experimental && targetGame === "tpf2" ? " (experimental in TPF2)" : "";
  document.getElementById("facts").innerHTML = `
    <dt>${gameLabel}</dt><dd>${sizeLabel}${exp}</dd>
    <dt>Heightmap</dt><dd>${targetGame === "tf3" ? "Set output pixels explicitly" : `${size.heightmap || "?"} × ${size.heightmap || "?"} px · 16-bit`}</dd>
    <dt>Ground</dt><dd>${s.real.lon_south_m} × ${s.real.lat_m} m</dd>
    <dt>Scale</dt><dd>X ${s.x} · Y ${s.y} (1.000 = exact 1:1)</dd>
    <dt>SW</dt><dd>${b.minlat.toFixed(6)}, ${b.minlon.toFixed(6)}</dd>
    <dt>NE</dt><dd>${b.maxlat.toFixed(6)}, ${b.maxlon.toFixed(6)}</dd>
  `;
  const hint = document.getElementById("hmHint");
  if (hint && size.heightmap && targetGame === "tpf2") {
    hint.textContent = `${size.label || sizeKey} → ${size.heightmap}×${size.heightmap} px. After import, type Range min/max from the log into the map editor.`;
  }
}

function drawBox(b, fit) {
  box = b;
  const ll = boundsLatLng(b);
  if (rect) rect.setBounds(ll);
  else {
    rect = L.rectangle(ll, {
      color: "#e2c15a",
      weight: 2,
      fillColor: "#e2c15a",
      fillOpacity: 0.05,
    }).addTo(map);
  }
  document.getElementById("lat").value = b.center_lat.toFixed(6);
  document.getElementById("lon").value = b.center_lon.toFixed(6);
  if (fit) map.fitBounds(ll, { padding: [28, 28] });
}

async function refreshBox(lat, lon, key, fit) {
  sizeKey = key;
  const r = await api().compute_box(Number(lat), Number(lon), key);
  if (!r.ok) { log(r.error); return; }
  drawBox(r.box, fit);
  renderFacts(r);
}

function fmtElapsed(sec) {
  sec = Math.max(0, Math.round(Number(sec) || 0));
  if (sec < 60) return sec + "s";
  return Math.floor(sec / 60) + "m " + String(sec % 60).padStart(2, "0") + "s";
}

function setLive(state, label, stage, percent, elapsed, detail) {
  const root = document.getElementById("liveStatus");
  if (!root) return;
  root.dataset.state = state || "idle";
  document.getElementById("liveLabel").textContent = label || "Idle";
  document.getElementById("liveStage").textContent = stage || (state === "idle" ? "No process running." : "");
  const bar = document.getElementById("liveBar");
  const pct = percent == null ? -1 : Number(percent);
  bar.classList.toggle("is-indeterminate", state === "run" && pct < 0);
  bar.style.width = (state === "run" && pct < 0) ? "" : (Math.max(0, Math.min(100, pct < 0 ? 0 : pct)) + "%");
  const bits = [];
  if (state === "run") bits.push("LIVE");
  if (state === "ok") bits.push("Done");
  if (state === "err") bits.push("Failed");
  if (state === "stop") bits.push("Stopped");
  if (pct >= 0 && state !== "idle") bits.push(Math.round(pct) + "%");
  if (elapsed != null && elapsed !== "" && state !== "idle") bits.push(fmtElapsed(elapsed));
  if (state === "idle") document.getElementById("liveMeta").textContent = "Ready";
  else document.getElementById("liveMeta").textContent = bits.join(" · ");
  const cancel = document.getElementById("btnCancel");
  if (cancel) cancel.hidden = state !== "run";
  const det = document.getElementById("liveDetail");
  if (det) det.textContent = detail || "";
}

async function runJob(start, label) {
  setLive("run", label, "Starting…", -1, 0, "");
  document.body.classList.add("is-busy");
  try {
    const job = await start();
    if (!job) {
      setLive("err", label, "No response from Studio.", 0, 0);
      log(label + " failed: no response");
      return job;
    }
    if (job.error && !job.job_id) {
      setLive("err", label, job.error, 0, 0);
      log(label + " failed: " + job.error);
      return job;
    }
    currentJobId = job.job_id || "";
    return await pollJob(job.job_id, label);
  } catch (err) {
    setLive("err", label, String(err), 0, 0);
    log(label + " failed: " + err);
    throw err;
  } finally {
    document.body.classList.remove("is-busy");
    currentJobId = "";
    const cancel = document.getElementById("btnCancel");
    if (cancel) cancel.hidden = true;
  }
}

async function flashStatus(label, fn) {
  const t0 = Date.now();
  setLive("run", label, "Working…", -1, 0, "");
  try {
    const r = await fn();
    const elapsed = (Date.now() - t0) / 1000;
    if (r && r.cancelled) {
      setLive("idle", label, "Cancelled.", 0, elapsed);
      return r;
    }
    if (r && r.ok === false) {
      setLive("err", label, r.error || "Failed", 0, elapsed);
      return r;
    }
    setLive("ok", label, (r && (r.stage || r.path || r.target)) || "Done.", 100, elapsed);
    return r;
  } catch (err) {
    setLive("err", label, String(err), 0, (Date.now() - t0) / 1000);
    throw err;
  }
}

async function pollJob(jobId, label) {
  log(label + " started.");
  for (;;) {
    const st = await api().job_status(jobId);
    const running = st.status === "running";
    const stopped = st.status === "cancelled" || st.cancelled;
    const state = running ? "run" : (stopped ? "stop" : (st.ok ? "ok" : "err"));
    setLive(
      state,
      st.label || label,
      st.stage || st.log || (running ? "Working…" : ""),
      st.percent,
      st.elapsed,
      st.detail || "",
    );
    if (running) {
      await new Promise((res) => setTimeout(res, 400));
      continue;
    }
    if (st.ok) {
      log(label + " done" + (st.elapsed != null ? " in " + fmtElapsed(st.elapsed) : "") + ".");
      if (st.path && !st.recommended) log(st.path);
      if (st.png && st.min_m == null) log("Overlay PNG: " + st.png);
      if (st.min_m != null) {
        log(`Heightmap ${st.pixels}×${st.pixels}  Range min=${st.min_m}  max=${st.max_m}  water≈${st.water_m}`);
        log("Map editor IMPORT: paste those Range values. File: " + (st.copied || st.png));
        if (st.sources) log("Sources: " + st.sources.join(" · "));
      }
      if (st.out) {
        const kind = st.buildings_only ? "osmdata_buildings.lua" : "osmdata.lua";
        log(kind + ": " + st.out + (st.size ? ` (${Math.round(st.size / 1e6)} MB)` : ""));
        const hint = document.getElementById("osmdataPath");
        if (hint && !st.buildings_only) hint.textContent = "osmdata.lua: " + st.out;
      }
      if (st.edges != null) log(`Towns ${st.towns} · nodes ${st.nodes} · edges ${st.edges} · areas ${st.areas} · objects ${st.objects}` + (st.buildings != null ? ` · buildings ${st.buildings}` : ""));
      if (st.cached && st.path) log("Using cached OSM data: " + st.path);
      else if (st.bytes != null && st.source) log(`Downloaded ${(st.bytes / 1e6).toFixed(1)} MB from ${st.source}`);
      if (st.attribution) log("OSM attribution: " + st.attribution);
      if (st.warning) log(st.warning);
      if (st.cropped && st.path) {
        log("Cropped OSM: " + st.path + (st.bytes ? ` (${(st.bytes / 1e6).toFixed(1)} MB)` : ""));
        document.getElementById("osmPath").textContent = st.path;
      } else if (st.cached && st.path) {
        log("Using cached crop: " + st.path);
        document.getElementById("osmPath").textContent = st.path;
      }
      if (st.target) {
        log("Installed to " + st.target);
        if (st.osmdata_source) log("osmdata source: " + st.osmdata_source);
        if (st.osmdata_copied === false) {
          log("Kept live osmdata.lua: " + (st.osmdata_note || "newer than the Studio work file"));
        } else if (st.osmdata_note) {
          log("osmdata: " + st.osmdata_note);
        }
      }
      if (st.paths) {
        renderGamePaths(st.paths);
        if (st.paths.mods_dir) log("Mods folder: " + st.paths.mods_dir);
        if (st.paths.workshop_dir) log("Workshop: " + st.paths.workshop_dir);
        if (st.paths.heightmaps) log("Heightmaps: " + st.paths.heightmaps);
      }
      if (st.recommended) {
        const miss = (st.missing || []).length;
        log(`Recommended ${st.recommended.length} Workshop packs for this map · ${miss} not installed`);
        if (st.subscribed) log(`Opened ${st.subscribed.opened || 0} Steam subscribe pages for catalog packs. Click Subscribe in Steam, then wait for downloads. Extra search hits stay in the list — subscribe those yourself if you want them.`);
        if (st.stats) {
          const s = st.stats;
          log(`osmdata: streets ${s.streets||0} · tracks ${s.tracks||0} · tram ${s.tram||0} · signals ${s.signals||0} · bridges ${s.bridges||0} · forests ${s.forests||0}`);
        }
        if (st.path) {
          const hint = document.getElementById("osmdataPath");
          if (hint) hint.textContent = "osmdata.lua: " + st.path;
        }
      }
      if (st.geofabrik && !st.ok) {
        log("Geofabrik: " + (st.geofabrik.url || ""));
      }
      if (st.log_tail) log(st.log_tail);
    } else if (stopped) {
      log(label + " stopped" + (st.elapsed != null ? " after " + fmtElapsed(st.elapsed) : "") + ".");
    } else {
      log(label + " failed: " + (st.error || st.stage || JSON.stringify(st)));
      if (st.geofabrik && st.geofabrik.url) log("Country extract: " + st.geofabrik.url);
    }
    return st;
  }
}

function showPanel(id) {
  document.querySelectorAll(".step").forEach((b) => b.classList.toggle("is-on", b.dataset.panel === id));
  document.querySelectorAll(".panel").forEach((p) => p.classList.toggle("is-on", p.id === "panel-" + id));
}

function renderModList(rows) {
  const host = document.getElementById("modList");
  host.innerHTML = "";
  for (const row of rows) {
    const div = document.createElement("div");
    div.className = "mod";
    const dot = document.createElement("span");
    dot.className = `dot${row.installed ? " on" : ""}`;
    div.appendChild(dot);
    const details = document.createElement("span");
    details.appendChild(document.createTextNode(`${row.name} `));
    const use = document.createElement("small");
    use.style.color = "#9a907c";
    use.textContent = row.use || "";
    details.appendChild(use);
    if (row.reason) {
      details.appendChild(document.createTextNode(" "));
      const reason = document.createElement("small");
      reason.style.color = "#9a907c";
      reason.textContent = row.reason;
      details.appendChild(reason);
    }
    div.appendChild(details);
    if (row.steam && row.id) {
      const b = document.createElement("button");
      b.textContent = row.installed ? "Open" : "Subscribe";
      b.className = "ghost";
      b.onclick = () => api().open_workshop(row.id);
      div.appendChild(b);
    } else {
      div.appendChild(document.createElement("span"));
    }
    host.appendChild(div);
  }
}

async function findModsForMap() {
  showPanel("mods");
  const st = await runJob(() => api().recommend_mods_from_map(true), "Mods for this map");
  if (st && st.ok && st.recommended) renderModList(st.recommended);
}

function collectOptions() {
  const o = { log_level: 1 };
  for (const [key] of OPT_KEYS) {
    const el = document.getElementById("opt-" + key);
    o[key] = !!(el && el.checked);
  }
  return o;
}

function fillOptions(opts) {
  const grid = document.getElementById("optGrid");
  grid.innerHTML = "";
  for (const [key, label] of OPT_KEYS) {
    const id = "opt-" + key;
    const wrap = document.createElement("label");
    wrap.innerHTML = `<input id="${id}" type="checkbox" ${opts[key] ? "checked" : ""}/> ${label}`;
    grid.appendChild(wrap);
  }
}

function renderGamePaths(p) {
  const host = document.getElementById("gamePaths");
  if (!host) return;
  const rows = [
    ["Game", p.game_dir],
    ["Mods", p.mods_dir],
    ["Workshop", p.workshop_dir],
    ["Heightmaps", p.heightmaps],
  ];
  host.innerHTML = rows.map(([k, v]) => `<dt>${k}</dt><dd>${v || "—"}</dd>`).join("");
  if (p.game_dir) document.getElementById("gameDir").value = p.game_dir;
}

function waitApi() {
  return new Promise((resolve) => {
    if (window.pywebview && window.pywebview.api) return resolve();
    window.addEventListener("pywebviewready", resolve, { once: true });
  });
}

async function main() {
  await waitApi();
  const requestedGame = new URLSearchParams(window.location.search).get("game");
  if (requestedGame === "tpf2" || requestedGame === "tf3") {
    const selected = await api().select_game(requestedGame);
    if (!selected.ok) throw new Error(selected.error || "Could not select game.");
  }
  const boot = await api().get_bootstrap();
  const hmPixels = document.getElementById("hmPixels");
  hmPixels.max = boot.heightmap_max_pixels;
  targetGame = boot.target_game || "tpf2";
  document.body.dataset.game = targetGame;
  document.getElementById("gameTitle").textContent = targetGame === "tf3" ? "TPF3" : "TPF2";
  document.getElementById("gameSubtitle").textContent = targetGame === "tf3"
    ? "Prepare shared map data and terrain assets for Transport Fever 3."
    : "Pick any place on OpenStreetMap. Yellow line = TPF2 map square at 1:1.";
  document.getElementById("mapLede").textContent = targetGame === "tf3"
    ? "Search or Shift-click to choose a map-data extraction extent. The available square extents are geographic conveniences, not TF3 map-size specifications."
    : "Search a place or Shift-click the map. The yellow line is that many metres on the ground, 1:1, for any OSM area.";
  document.getElementById("sizeLabel").firstChild.textContent = targetGame === "tf3" ? "Extraction extent" : "Size";
  const notice = document.getElementById("gameNotice");
  notice.hidden = targetGame !== "tf3";
  notice.textContent =
    "TF3 mode supports place selection, OSM download/cropping, terrain and imagery export. TF2 importer/map-size presets are not treated as TF3 specifications; direct TF3 in-game import is not implemented yet.";
  document.getElementById("osmLede").textContent = targetGame === "tf3"
    ? "Download or select OpenStreetMap data for this area. This exports source OSM data; the TF2-specific osmdata.lua converter is disabled in TF3 mode."
    : "Pulls highways, railways, landuse, water, places, signals, and mapped houses/shops/industry for the yellow box. Garages, sheds and untyped building=yes are skipped.";
  document.getElementById("heightmapLede").textContent = targetGame === "tf3"
    ? "Export a 16-bit grayscale terrain PNG for the selected area. Enter the exact pixel resolution for your TF3 map; Studio will not copy it into an unverified game folder."
    : "16-bit grayscale PNG cropped to the TPF2 map square. Terrarium supplies the high-res surface; FABDEM (or Copernicus / SRTM) supplies bare-earth where available.";
  document.getElementById("overlayLede").textContent = targetGame === "tf3"
    ? "Download an attributed Esri World Imagery mosaic for the selected area. Image output is prepared as an asset; TF3 in-game overlay packaging is not implemented."
    : "Esri World Imagery mosaic for the map square. TPF2 wants 4096×4096 DDS (BC1), vertically flipped — PNG tiles are written ready to convert.";
  document.getElementById("hmPixelsLabel").hidden = targetGame !== "tf3";
  document.getElementById("hmCopyLabel").hidden = targetGame === "tf3";
  document.getElementById("hmCopy").checked = targetGame === "tpf2";
  document.getElementById("hmCopy").disabled = targetGame === "tf3";
  document.querySelector('#osmMode option[value="filtered"]').textContent = targetGame === "tf3"
    ? "Filtered OSM features (recommended)"
    : "Importer data (recommended)";
  document.getElementById("hmHint").textContent = targetGame === "tf3"
    ? `Enter the exact output dimensions required by your TF3 map format. The output is a PNG only; in-game import is not supported yet. Maximum: ${boot.heightmap_max_pixels.toLocaleString()} pixels per side because temporary grids scale quadratically and 16,385 pixels can exceed 8 GiB of peak memory.`
    : `Heightmap size is selected from the TPF2 map preset. Verify the generated range in the map editor. The ${boot.heightmap_max_pixels.toLocaleString()}-pixel ceiling includes the largest current preset; larger grids can exceed 8 GiB of peak temporary memory.`;
  document.title = targetGame === "tf3" ? "OSM-TPF3 Studio" : "OSM-TPF2 Studio";
  box = boot.box;
  sizeKey = boot.size_key;
  document.getElementById("gameDir").value = boot.paths.game_dir || "";
  renderGamePaths(boot.paths);
  document.getElementById("osmPath").textContent = boot.paths.osm_path || "";
  document.getElementById("osmdataPath").textContent = boot.paths.osmdata_path
    ? ("osmdata.lua: " + boot.paths.osmdata_path)
    : "osmdata.lua: convert the map first";

  const sel = document.getElementById("sizeKey");
  for (const [key, info] of Object.entries(boot.map_sizes)) {
    const opt = document.createElement("option");
    opt.value = key;
    opt.textContent = targetGame === "tf3"
      ? `${info.meters} m square extent`
      : `${info.label} · ${info.meters} m${info.experimental ? " *" : ""}`;
    if (key === sizeKey) opt.selected = true;
    sel.appendChild(opt);
  }
  fillOptions(boot.options);
  document.getElementById("btnTools").onclick = async () => {
    const result = await api().open_mode(targetGame === "tpf2" ? "tf3" : "tpf2");
    if (!result || !result.ok) log((result && result.error) || "Could not switch game mode.");
    else window.location.href = result.url;
  };
  document.getElementById("btnTools").textContent = targetGame === "tpf2" ? "Switch to TF3 →" : "← Switch to TPF2";
  document.getElementById("btnTools").setAttribute(
    "aria-label",
    targetGame === "tpf2" ? "Switch to Transport Fever 3" : "Switch to Transport Fever 2",
  );
  document.getElementById("btnTf3Converter").hidden = targetGame !== "tf3";
  document.getElementById("btnTf3Converter").onclick = async () => {
    const result = await api().open_mode("tf3_converter");
    if (!result || !result.ok) log((result && result.error) || "Could not open TF3 Mod Converter.");
    else window.location.href = result.url;
  };
  const view = boot.view || { lat: 20, lon: 0, zoom: 2 };
  if (boot.place_set && boot.box) {
    renderFacts({ box: boot.box, scale: boot.scale, size: boot.map_sizes[sizeKey] });
  } else {
    box = null;
    renderFacts({ size: boot.map_sizes[sizeKey] });
  }

  map = L.map("map", { zoomControl: true }).setView(
    boot.place_set && boot.box ? [boot.box.center_lat, boot.box.center_lon] : [view.lat, view.lon],
    boot.place_set && boot.box ? 12 : (view.zoom || 2),
  );
  const osmTiles = L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
    maxZoom: 19,
    attribution: "&copy; OpenStreetMap contributors",
  });
  const satTiles = L.tileLayer(
    "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
    { maxZoom: 19, attribution: "Esri, Maxar, Earthstar Geographics" },
  );
  osmTiles.addTo(map);
  document.getElementById("mapLegendText").textContent = targetGame === "tf3"
    ? "Selected extent · © OpenStreetMap contributors"
    : "TPF2 map square · © OpenStreetMap contributors";
  L.control.layers({ OpenStreetMap: osmTiles, Satellite: satTiles }, {}, { position: "topright" }).addTo(map);
  map.on("baselayerchange", (ev) => {
    const legend = document.getElementById("mapLegendText");
    if (legend) {
      legend.textContent = ev.name === "Satellite"
        ? (targetGame === "tf3" ? "Selected extent · Esri imagery" : "TPF2 map square · Esri imagery")
        : (targetGame === "tf3" ? "Selected extent · © OpenStreetMap contributors" : "TPF2 map square · © OpenStreetMap contributors");
    }
  });
  if (boot.place_set && boot.box) drawBox(boot.box, true);

  map.on("click", (ev) => {
    if (!ev.originalEvent.shiftKey) return;
    refreshBox(ev.latlng.lat, ev.latlng.lng, sel.value, false);
  });

  document.querySelectorAll(".step").forEach((btn) => {
    btn.addEventListener("click", () => {
      document.querySelectorAll(".step").forEach((b) => b.classList.remove("is-on"));
      document.querySelectorAll(".panel").forEach((p) => p.classList.remove("is-on"));
      btn.classList.add("is-on");
      document.getElementById("panel-" + btn.dataset.panel).classList.add("is-on");
      if (btn.dataset.panel === "osm" || btn.dataset.panel === "install") refreshWork();
      if (btn.dataset.panel === "sat") loadTerrainPreviews();
    });
  });

  sel.addEventListener("change", async () => {
    if (!hasPlace()) return;
    const r = await api().set_size_key(sel.value);
    if (r && r.ok && r.box) {
      await applyBoxResult(r, true);
      return;
    }
    refreshBox(document.getElementById("lat").value, document.getElementById("lon").value, sel.value, true);
  });
  document.getElementById("lat").addEventListener("change", () => syncBoxFromForm());
  document.getElementById("lon").addEventListener("change", () => syncBoxFromForm());
  document.getElementById("btnPlace").onclick = () => {
    const c = map.getCenter();
    refreshBox(c.lat, c.lng, sel.value, false);
  };
  document.getElementById("btnFit").onclick = () => {
    if (!needPlace()) return;
    map.fitBounds(boundsLatLng(box), { padding: [28, 28] });
  };
  document.getElementById("btnOsmOrg").onclick = () => {
    if (!needPlace()) return;
    api().open_osm_org(box);
  };
  document.getElementById("btnSearch").onclick = async () => {
    const q = document.getElementById("searchQ").value.trim();
    if (!q) return;
    hideHits();
    let hits;
    try {
      hits = await flashStatus("Place search", () => api().geocode(q));
    } catch (error) {
      log("Place search failed: " + String(error));
      return;
    }
    if (!hits || !hits.length) { log("No Nominatim hits."); return; }
    if (hits.length === 1) {
      log(hits[0].label);
      await refreshBox(hits[0].lat, hits[0].lon, sel.value, true);
      return;
    }
    log(hits.length + " places. Pick one from the list.");
    showHits(hits);
  };
  document.getElementById("searchQ").addEventListener("keydown", (ev) => {
    if (ev.key === "Enter") {
      ev.preventDefault();
      document.getElementById("btnSearch").click();
    }
  });
  document.getElementById("btnCancel").onclick = async () => {
    const r = await api().cancel_job(currentJobId || "");
    if (r && r.ok) {
      setLive("run", "Stopping", "Stopping…", -1, null, "");
      log("Stop requested.");
    } else {
      log((r && r.error) || "No running job");
    }
  };

  document.getElementById("btnDownload").onclick = async () => {
    await syncBoxFromForm();
    if (!needPlace()) return;
    const mode = document.getElementById("osmMode").value;
    const forceRefresh = document.getElementById("osmRefresh").checked;
    const st = await runJob(() => api().download_osm(box, mode, forceRefresh), "OSM download");
    if (st && st.path) document.getElementById("osmPath").textContent = st.path;
    await refreshWork();
  };
  document.getElementById("btnPickOsm").onclick = async () => {
    const r = await flashStatus("Pick OSM file", () => api().pick_osm_file());
    if (r.ok) {
      document.getElementById("osmPath").textContent = r.path;
      log("Using " + r.path + (r.osm && r.osm.mb != null ? ` (${r.osm.mb} MB)` : ""));
      if (r.warning) log(r.warning);
      if (r.adopted && r.bounds) {
        const used = await api().use_osm_bounds(r.path);
        if (used && used.ok) {
          await applyBoxResult(used, true);
          log("Yellow box set from this extract (" + (used.size_key || sizeKey) + ").");
        }
      }
      await refreshWork();
    }
  };
  document.getElementById("btnUseOsmBounds").onclick = async () => {
    const r = await flashStatus("Use extract bounds", () => api().use_osm_bounds());
    if (r && r.ok) {
      await applyBoxResult(r, true);
      log(targetGame === "tf3"
        ? "Yellow box now matches the OSM extract. Selected geographic extent: " + (r.size_key || sizeKey) + "."
        : "Yellow box now matches the OSM extract. Suggested TPF2 size: " + (r.size_key || sizeKey) + ".");
      await refreshWork();
    } else {
      log((r && r.error) || "No OSM bounds");
    }
  };
  document.getElementById("btnGeofabrik").onclick = async () => {
    const r = await flashStatus("Geofabrik", () => api().open_geofabrik());
    log(r && r.url ? ("Opened " + (r.label || "Geofabrik") + ": " + r.url) : (r && r.error) || "Could not open Geofabrik");
    log("Download the .osm.bz2 (Studio accepts it as-is) or use Download country .osm.bz2.");
  };
  document.getElementById("btnGeofabrikDl").onclick = async () => {
    await syncBoxFromForm();
    if (!needPlace()) return;
    const st = await runJob(() => api().download_geofabrik(), "Geofabrik extract");
    if (st && st.path) {
      document.getElementById("osmPath").textContent = st.path;
      log("Country extract saved. Crop or Convert next — both crop to the yellow box.");
    }
    await refreshWork();
  };
  document.getElementById("btnCrop").onclick = async () => {
    await syncBoxFromForm();
    if (!(await ensureBox())) return;
    const st = await runJob(
      () => api().crop_osm(box, sel.value, document.getElementById("osmPath").textContent),
      "Crop OSM",
    );
    await refreshWork();
    if (st && st.ok) log("Crop ready. Convert will reuse this file.");
  };
  document.getElementById("btnConvert").onclick = async () => {
    await syncBoxFromForm();
    if (!(await ensureBox())) return;
    const st = await runJob(
      () => api().convert(box, sel.value, document.getElementById("osmPath").textContent),
      "Convert to osmdata.lua",
    );
    await refreshWork();
    if (st && st.ok) {
      log("Next: press Find & subscribe mods for this map. Steam will open Subscribe for missing packs; skip any you do not want — vanilla types are used instead.");
    }
  };
  document.getElementById("btnConvertBuildings").onclick = async () => {
    await syncBoxFromForm();
    if (!(await ensureBox())) return;
    const st = await runJob(
      () => api().convert_buildings(box, sel.value, document.getElementById("osmPath").textContent),
      "Buildings sidecar",
    );
    await refreshWork();
    if (st && st.ok) log("Wrote osmdata_buildings.lua without replacing towns/streets.");
  };

  document.getElementById("btnScanMods").onclick = async () => {
    const data = await flashStatus("Scan Workshop mods", () => api().scan_mods());
    if (!data.ok) { log(data.error); return; }
    const rows = [...(data.catalog || []), ...(data.local_packs || []).map((p) => ({
      id: "", name: p.folder, use: p.use, installed: true, steam: false,
    }))];
    renderModList(rows);
    log(`Workshop folders: ${data.workshop_ids.length} · missing Steam deps: ${data.missing_steam.length}`);
  };
  document.getElementById("btnMapMods").onclick = findModsForMap;
  document.getElementById("btnMapMods2").onclick = findModsForMap;
  document.getElementById("btnOpenMissing").onclick = async () => {
    const r = await flashStatus("Open missing in Steam", () => api().open_missing_mods());
    log(r.ok ? `Opened ${r.opened} of ${r.total_missing} missing Workshop pages.` : r.error);
  };
  document.getElementById("btnModSearch").onclick = async () => {
    await flashStatus("Workshop search", () => api().search_workshop(document.getElementById("modQ").value));
  };

  document.getElementById("btnSat").onclick = async () => {
    await syncBoxFromForm();
    if (!needPlace()) return;
    const z = document.getElementById("satZoom").value;
    await runJob(() => api().download_overlay(box, z ? Number(z) : null), "Satellite overlay");
    await refreshWork();
    await loadTerrainPreviews();
  };
  document.getElementById("btnHeightmap").onclick = async () => {
    await syncBoxFromForm();
    if (!needPlace()) return;
    const outputPixels = targetGame === "tf3" ? Number(document.getElementById("hmPixels").value) : null;
    const maxPixels = Number(document.getElementById("hmPixels").max);
    if (targetGame === "tf3" && (!Number.isInteger(outputPixels) || outputPixels < 257 || outputPixels > maxPixels)) {
      log(`Enter a valid TF3 heightmap pixel size (257–${maxPixels}) before generating.`);
      return;
    }
    await runJob(
      () => api().download_heightmap(
        box,
        sel.value,
        document.getElementById("hmStrip").checked,
        targetGame === "tpf2" && document.getElementById("hmCopy").checked,
        outputPixels,
      ),
      "Heightmap",
    );
    await refreshWork();
    await loadTerrainPreviews();
  };

  document.getElementById("btnGameFolder").onclick = async () => {
    const r = await flashStatus("Pick game folder", () => api().pick_folder());
    if (r.ok) {
      const found = await api().set_paths(r.path, "");
      renderGamePaths(found);
      log(found.ok ? ("Using " + found.game_dir) : (found.error || "Folder not recognized as " + boot.game_name));
    }
  };
  document.getElementById("btnAutoFind").onclick = async () => {
    const hint = document.getElementById("gameDir").value.trim();
    const found = await flashStatus("Find game folders", () => api().discover_paths(hint));
    renderGamePaths(found);
    if (!found.ok) log(found.error || ("Could not find " + boot.game_name));
    else {
      const bits = found.found || [];
      log("Found " + bits.join(", ") + ".");
      if (found.game_dir) log("Game: " + found.game_dir);
      if (found.mods_dir) log("Mods: " + found.mods_dir);
      if (found.workshop_dir) log("Workshop: " + found.workshop_dir);
      if (found.heightmaps) log("Heightmaps: " + found.heightmaps);
    }
  };
  document.getElementById("btnInstall").onclick = async () => {
    const hint = document.getElementById("gameDir").value.trim();
    await runJob(() => api().install(collectOptions(), hint), "Install into Mods");
    await refreshWork();
  };
  document.getElementById("btnLaunch").onclick = async () => {
    await flashStatus("Launch " + boot.game_name, () => api().launch_game());
    log("Opening Steam: " + boot.game_name);
  };

  document.addEventListener("click", (ev) => {
    if (!ev.target.closest || !ev.target.closest(".search")) hideHits();
  });
  setLive("idle", "Idle", "No process running.", 0, "", "");
  if (boot.work) renderWork(boot.work);
  loadTerrainPreviews();
}

main().catch((err) => log(String(err)));
