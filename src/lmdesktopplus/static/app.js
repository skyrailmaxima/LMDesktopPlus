"use strict";

const TOKEN = document.querySelector('meta[name="lmdp-token"]')?.content || "";
const scenes = [
  {id:"desktop", num:"1", jp:"家", label:"Desktop", title:"~ workspace"},
  {id:"terminal", num:"2", jp:"端", label:"Agents", title:"kitty — agent sessions"},
  {id:"tmux", num:"3", jp:"多", label:"tmux", title:"tmux: dev"},
  {id:"editor", num:"4", jp:"編", label:"Editor", title:"editor — workspace"},
  {id:"browser", num:"5", jp:"網", label:"Browser", title:"browser — agent panel"},
  {id:"rofi", num:"6", jp:"起", label:"Rofi", title:"rofi launcher"},
  {id:"docs", num:"7", jp:"書", label:"Dotfiles", title:"~/.config"},
  {id:"monitor", num:"8", jp:"監", label:"Monitor", title:"system monitor"},
  {id:"apps", num:"9", jp:"蔵", label:"Apps", title:"app vault — integrations"},
  {id:"settings", num:"0", jp:"設", label:"Settings", title:"system settings"},
  {id:"kit", num:"K", jp:"部", label:"UI Kit", title:"ui kit — components"},
];

const DEV_MODE = document.documentElement.dataset.dev === "true";

class AssetMap {
  constructor() {
    this.icons = new Map();
    this.revision = null;
    this.initialized = false;
  }

  update(assets={}, revision=null) {
    if (this.initialized && (revision === null || revision === this.revision)) return;
    this.icons = new Map(Object.entries(assets.icons || {}));
    this.revision = revision;
    this.initialized = true;
  }
}

class LiveStore {
  constructor({debug=false}={}) {
    this.lastSnapshot = null;
    this.debug = debug;
  }

  update(snapshot) {
    const previous = this.lastSnapshot || {};
    const current = snapshot || {};
    const keys = new Set([...Object.keys(previous), ...Object.keys(current)]);
    const changedKeys = [...keys].filter(key => !Object.is(previous[key], current[key]));
    this.lastSnapshot = current;
    if (this.debug && changedKeys.length) console.debug("[LMDesktopPlus] state keys changed:", changedKeys);
    return changedKeys;
  }
}

const app = {
  locked: true,
  scene: "desktop",
  settingsTab: "appearance",
  state: null,
  assets: new AssetMap(),
  store: new LiveStore({debug: DEV_MODE}),
  networkScan: null,
  history: {cpu:[], ram:[], gpu:[], down:[], up:[]},
  pollTimer: null,
  pendingRender: false,
  pendingConfirm: null,
  pendingWifiSsid: null,
};

const $ = (selector, root=document) => root.querySelector(selector);
const $$ = (selector, root=document) => [...root.querySelectorAll(selector)];
const esc = value => String(value ?? "").replace(/[&<>'"]/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;","'":"&#39;",'"':"&quot;"}[c]));
const clamp = (v, min, max) => Math.max(min, Math.min(max, Number(v) || 0));

async function api(path, options={}) {
  const opts = {...options, headers:{"X-LMDP-Token":TOKEN, ...(options.headers || {})}};
  if (opts.body && typeof opts.body !== "string") {
    opts.headers["Content-Type"] = "application/json";
    opts.body = JSON.stringify(opts.body);
  }
  const response = await fetch(path, opts);
  let payload;
  try { payload = await response.json(); } catch { payload = {ok:false,error:`HTTP ${response.status}`}; }
  if (!response.ok) throw new Error(payload.error || `HTTP ${response.status}`);
  return payload;
}

function humanBytes(bytes, rate=false) {
  const n = Number(bytes) || 0;
  const units = ["B","KiB","MiB","GiB","TiB"];
  let value = n, i = 0;
  while (Math.abs(value) >= 1024 && i < units.length-1) { value /= 1024; i++; }
  const digits = value >= 100 || i === 0 ? 0 : value >= 10 ? 1 : 2;
  return `${value.toFixed(digits)} ${units[i]}${rate ? "/s" : ""}`;
}

function humanDuration(seconds) {
  let s = Math.max(0, Math.floor(Number(seconds) || 0));
  const d = Math.floor(s/86400); s %= 86400;
  const h = Math.floor(s/3600); s %= 3600;
  const m = Math.floor(s/60);
  return [d ? `${d}d` : "", h ? `${h}h` : "", `${m}m`].filter(Boolean).join(" ");
}

function toast(title, detail="", error=false) {
  if (window.Digitalvapor?.toast) {
    return window.Digitalvapor.toast({
      title,
      body: detail,
      tone: error ? "error" : "cyan",
      icon: error ? "!" : "✓",
      timeout: 4600,
    });
  }
  const node = document.createElement("div");
  node.className = `toast${error ? " error" : ""}`;
  node.innerHTML = `<strong>${esc(title)}</strong><small>${esc(detail)}</small>`;
  $("#toast-stack").append(node);
  setTimeout(() => node.remove(), 4600);
  return node;
}

function setClock() {
  const now = new Date();
  const clock = now.toLocaleTimeString([], {hour:"2-digit", minute:"2-digit", hour12:false});
  const jpWeek = ["日","月","火","水","木","金","土"][now.getDay()];
  $("#lock-clock").textContent = clock;
  $("#status-clock").textContent = clock;
  $("#lock-date").textContent = `${now.getFullYear()}年${now.getMonth()+1}月${now.getDate()}日 (${jpWeek})`;
}

function unlock() {
  if (!app.locked) return;
  app.locked = false;
  $("#lock-screen").classList.add("hidden");
  $("#machine-ui").classList.remove("hidden");
  renderChrome();
  renderScene(true);
}

function lockUi() {
  app.locked = true;
  $("#machine-ui").classList.add("hidden");
  $("#lock-screen").classList.remove("hidden");
  $("#lock-screen").focus();
}

function setScene(id) {
  if (!scenes.some(x => x.id === id)) return;
  app.scene = id;
  renderChrome();
  renderScene(true);
}

function renderChrome() {
  const current = scenes.find(x => x.id === app.scene) || scenes[0];
  $("#window-title").textContent = current.title;
  $("#workspace-strip").innerHTML = scenes.map(scene => {
    const active = scene.id === app.scene;
    return `<button class="workspace-chip dv-bar__ws ${active ? "active is-active" : ""}" data-scene="${scene.id}" title="${esc(scene.label)}">${scene.num}<span class="jp dv-jp">${scene.jp}</span></button>`;
  }).join("");
  $("#dock").innerHTML = scenes.map(scene => {
    const active = scene.id === app.scene;
    return `<button class="dock-item dv-dock__item ${active ? "active is-active" : ""}" data-scene="${scene.id}" title="${esc(scene.label)}"><span class="jp dv-dock__glyph">${scene.jp}</span><span class="dock-label dv-dock__label">${esc(scene.label)}</span></button>`;
  }).join("");
  $$('[data-scene]').forEach(node => node.addEventListener("click", () => setScene(node.dataset.scene)));
}

function updateHistory(metrics) {
  const max = 90;
  const push = (key, value) => { app.history[key].push(Number(value) || 0); if (app.history[key].length > max) app.history[key].shift(); };
  push("cpu", metrics.cpu?.percent);
  push("ram", metrics.memory?.percent);
  push("gpu", metrics.gpu?.percent ?? 0);
  push("down", metrics.network?.down_bps ?? 0);
  push("up", metrics.network?.up_bps ?? 0);
}

function applyAppearance() {
  const settings = app.state?.settings?.appearance;
  if (!settings) return;
  const accents = app.state.accents || {};
  const accent = accents[settings.accent] || "#ff2e97";
  const secondaryByAccent = {
    mag: accents.cyan || "#01cdfe",
    pink: accents.mint || "#05ffa1",
    cyan: accents.mag || "#ff2e97",
    mint: accents.purple || "#b967ff",
    purple: accents.cyan || "#01cdfe",
    green: accents.mag || "#ff2e97",
    amber: accents.cyan || "#01cdfe",
  };
  const secondary = secondaryByAccent[settings.accent] || "#01cdfe";
  const opacity = clamp(settings.opacity, 40, 100) / 100;
  const blur = clamp(settings.blur, 0, 24);
  const fontMap = {
    "JetBrains Mono": '"JetBrains Mono", "DejaVu Sans Mono", ui-monospace, monospace',
    "DotGothic16": '"DotGothic16", "Noto Sans CJK JP", "DejaVu Sans Mono", sans-serif',
    "Zen Dots": '"Zen Dots", "Orbitron", "DejaVu Sans Mono", sans-serif',
    "System UI": 'system-ui, sans-serif',
  };
  const uiFont = fontMap[settings.font] || fontMap["JetBrains Mono"];
  const root = document.documentElement.style;
  root.setProperty("--accent", accent);
  root.setProperty("--dv-accent", accent);
  root.setProperty("--dv-accent-2", secondary);
  root.setProperty("--surface-opacity", opacity.toFixed(2));
  root.setProperty("--blur", `${blur}px`);
  root.setProperty("--dv-blur", `${blur}px`);
  root.setProperty("--dv-panel", `rgba(7,7,16,${Math.max(.40, opacity * .87).toFixed(2)})`);
  root.setProperty("--dv-panel-2", `rgba(6,8,14,${Math.max(.28, opacity * .61).toFixed(2)})`);
  root.setProperty("--dv-radius", settings.rounded ? "8px" : "0px");
  root.setProperty("--ui-font", uiFont);
  root.setProperty("--dv-mono", uiFont);
  root.setProperty("--jp-font", fontMap.DotGothic16);
  root.setProperty("--dv-jp", fontMap.DotGothic16);
  root.setProperty("--display-font", fontMap["Zen Dots"]);
  root.setProperty("--dv-disp", fontMap["Zen Dots"]);
  const rain = $("#matrix-rain");
  if (rain) rain.dataset.dvIntensity = String(clamp(settings.rain_intensity, 0, 100));
  document.body.classList.toggle("dv-crt", Boolean(settings.scanlines));
}
async function poll() {
  try {
    const state = await api("/api/v1/state");
    app.store.update(state);
    app.assets.update(state.assets, state.assets_revision ?? null);
    app.state = app.store.lastSnapshot;
    updateHistory(state.metrics || {});
    applyAppearance();
    updateStatus();
    const active = document.activeElement;
    const editing = active && ["INPUT","SELECT","TEXTAREA"].includes(active.tagName);
    const transientOpen = Boolean(document.querySelector(".dv-dialog-backdrop.is-open, .dv-dropdown.is-open, .dv-menu[data-dv-live]"));
    if (!app.locked && !editing && !transientOpen) renderScene(false);
  } catch (error) {
    toast("Backend unavailable", error.message, true);
  } finally {
    const delay = app.state?.settings?.behavior?.poll_interval_ms || 1000;
    clearTimeout(app.pollTimer);
    app.pollTimer = setTimeout(poll, delay);
  }
}

function updateStatus() {
  if (!app.state) return;
  const m = app.state.metrics;
  $("#status-cpu").textContent = `CPU ${Math.round(m.cpu?.percent || 0)}%`;
  $("#status-ram").textContent = `RAM ${Math.round(m.memory?.percent || 0)}%`;
  $("#status-net").textContent = `↓ ${humanBytes(m.network?.down_bps || 0, true)}`;
  $("#status-battery").textContent = m.battery ? `BAT ${m.battery.percent}%` : "AC POWER";
}

function heading(jp, title, sub, actions="") {
  return `<div class="scene-heading"><div><div class="eyebrow dv-kicker dv-jp">${jp}</div><h1 class="dv-disp">${esc(title)}</h1><p class="dv-muted">${esc(sub)}</p></div>${actions}</div>`;
}

function corners() {
  return '<i class="dv-corner tl"></i><i class="dv-corner tr"></i><i class="dv-corner bl"></i><i class="dv-corner br"></i>';
}

function panel(title, body, extra="") {
  const accentClass = extra.includes("accent") ? "dv-card--mag" : "";
  return `<section class="panel card dv-panel dv-card ${accentClass} ${extra}">${corners()}<h2 class="dv-card__title">${title}</h2>${body}</section>`;
}

function capability(name) {
  return app.state?.capabilities?.[name] || {available:false,path:null};
}

function renderScene(force=false) {
  if (!app.state || app.locked) return;
  const liveScenes = new Set(["desktop", "terminal", "monitor"]);
  if (!force && !liveScenes.has(app.scene)) return;
  const root = $("#scene");
  const renderers = {
    desktop: renderDesktop,
    terminal: renderAgents,
    tmux: renderTmux,
    editor: renderEditor,
    browser: renderBrowser,
    rofi: renderRofi,
    docs: renderDocs,
    monitor: renderMonitor,
    apps: renderApps,
    settings: renderSettings,
    kit: renderKit,
  };
  root.innerHTML = `<div class="scene-shell">${(renderers[app.scene] || renderDesktop)()}</div>`;
  bindSceneEvents();
}

function renderDesktop() {
  const s = app.state, m = s.metrics, id = s.identity;
  const agents = s.agents.map(agentCard).join("");
  const media = s.media || {};
  const gpu = m.gpu?.percent == null ? "n/a" : `${Math.round(m.gpu.percent)}%`;
  return heading("機械界面", "VAPOR//MATRIX", `${id.user}@${id.hostname} · ${id.os}`) + `
    <div class="grid four">
      ${panel("CPU", `<div class="kpi">${Math.round(m.cpu.percent)}<small>% · ${m.cpu.count} threads</small></div><div class="progress dv-progress"><span class="dv-progress__bar" style="width:${clamp(m.cpu.percent,0,100)}%"></span></div>`)}
      ${panel("MEMORY", `<div class="kpi">${Math.round(m.memory.percent)}<small>% · ${humanBytes(m.memory.used)}</small></div><div class="progress dv-progress"><span class="dv-progress__bar" style="width:${clamp(m.memory.percent,0,100)}%"></span></div>`)}
      ${panel("GPU", `<div class="kpi">${gpu}<small>${esc(m.gpu?.name || "unavailable")}</small></div><div class="progress dv-progress"><span class="dv-progress__bar" style="width:${clamp(m.gpu?.percent || 0,0,100)}%"></span></div>`)}
      ${panel("UPTIME", `<div class="kpi">${humanDuration(m.uptime_seconds)}<small>load ${m.load_average.map(x=>Number(x).toFixed(2)).join(" · ")}</small></div>`)}
    </div>
    <div class="grid two" style="margin-top:16px">
      ${panel("QUICK LAUNCH", `<div class="button-row">
        <button class="btn primary dv-btn dv-btn--primary" data-launch="terminal">OPEN KITTY</button>
        <button class="btn dv-btn dv-btn--outline" data-launch="tmux">TMUX DEV</button>
        <button class="btn dv-btn dv-btn--outline" data-launch="editor">EDITOR</button>
        <button class="btn dv-btn dv-btn--outline" data-launch="browser">BROWSER</button>
        <button class="btn dv-btn dv-btn--outline" data-launch="rofi">ROFI</button>
        <button class="btn dv-btn dv-btn--outline" data-launch="monitor">BTOP</button>
      </div><div class="terminal" style="margin-top:14px;min-height:160px"><span class="green">root@vaporframe</span> <span class="muted">~</span>\n<span class="mint">❯</span> <span class="cmd">agent ls --scope</span>\n${s.agents.map(a=>`<span class="out">${esc(a.name.padEnd(8))} → ${esc(a.home)}  ${a.available?"ready":"missing"}</span>`).join("\n")}\n<span class="mint">❯</span> <span class="cursor"></span></div>`, "accent")}
      ${panel("NOW PLAYING", `<div class="card-title"><div><div class="kpi" style="font-size:24px">${esc(media.title || "No active player")}</div><div class="muted">${esc(media.artist || "playerctl")}${media.album ? ` · ${esc(media.album)}` : ""}</div></div><span class="badge dv-tag ${media.status==="Playing"?"ok dv-tag--mint":"off dv-tag--off"}">${esc(media.status || "Stopped")}</span></div><div class="button-row"><button class="btn dv-btn dv-btn--outline" data-media="previous">◀</button><button class="btn primary dv-btn dv-btn--primary" data-media="play-pause">▶ / Ⅱ</button><button class="btn dv-btn dv-btn--outline" data-media="next">▶</button></div>
      <div style="margin-top:18px">${statRow("Network down",humanBytes(m.network.down_bps,true))}${statRow("Network up",humanBytes(m.network.up_bps,true))}${statRow("Disk",`${Math.round(m.disk.percent)}% · ${humanBytes(m.disk.free)} free`)}</div>`)}
    </div>
    <div class="grid three" style="margin-top:16px">${agents}</div>`;
}

function statRow(label, value) { return `<div class="stat-row"><span class="label">${esc(label)}</span><span class="value">${esc(value)}</span></div>`; }

function agentCard(agent) {
  const status = agent.available ? `<span class="badge ok dv-tag dv-tag--mint"><span class="dot"></span>ready</span>` : `<span class="badge warn dv-tag dv-tag--warn">missing</span>`;
  return `<section class="panel card dv-panel dv-card"><div class="agent-card dv-card"><div class="agent-glyph">代</div><div class="agent-meta"><strong>${esc(agent.label)}</strong><small>${esc(agent.description)}</small><small>${esc(agent.workspace_resolved)} · ${agent.sandbox ? (agent.sandbox_available ? "bwrap scoped" : "sandbox requested") : "host session"}</small></div>${status}</div><div class="button-row" style="margin-top:12px"><button class="btn primary dv-btn dv-btn--primary" data-agent="${esc(agent.name)}" ${agent.available?"":"disabled"}>SPAWN</button><button class="btn dv-btn dv-btn--outline" data-scene-jump="settings" data-settings-tab="agents">CONFIG</button></div></section>`;
}

function renderAgents() {
  const list = app.state.agents.map(agentCard).join("");
  return heading("代理端末", "AGENT SESSIONS", "Launch local agents in dedicated homes and selected workspaces.", `<button class="btn dv-btn dv-btn--outline" data-launch="terminal">OPEN RAW TERMINAL</button>`) + `
    <div class="grid three">${list}</div>
    <section class="panel terminal dv-window dv-window--borderless" style="margin-top:16px"><span class="green">scope policy</span>\n<span class="out">agent home   → ~/.local/share/lmdesktopplus/agents/&lt;name&gt;</span>\n<span class="out">workspace    → configurable, default ~/work</span>\n<span class="out">sandbox      → Bubblewrap when enabled and installed</span>\n<span class="out">network      → per-agent allow/deny flag</span>\n\n<span class="amber">Note:</span> enabling sandboxing isolates filesystem writes; it is not a complete VM boundary.</section>`;
}

function renderTmux() {
  const cap = capability("tmux");
  return heading("多重端末", "TMUX DEV", "Attach to the persistent lmdesktopplus session.") + `
    <div class="grid two">
      ${panel("SESSION", `<div class="kpi">dev<small>tmux new-session -A -s lmdesktopplus</small></div><div class="button-row" style="margin-top:18px"><button class="btn primary dv-btn dv-btn--primary" data-launch="tmux" ${cap.available?"":"disabled"}>ATTACH / CREATE</button></div>${statRow("Executable",cap.path || "not installed")}`, "accent")}
      ${panel("LAYOUT", `<pre class="code-block">┌ agent ──────────┬ tests ──────────┐\n│ claude / aider  │ pytest / cargo  │\n├─────────────────┴─────────────────┤\n│ logs · services · git status      │\n└───────────────────────────────────┘</pre><p class="muted">The launcher leaves your tmux configuration in control and only chooses the stable session name.</p>`)}
    </div>`;
}

function renderEditor() {
  const cap = capability("editor");
  return heading("編集環境", "WORKSPACE EDITOR", "Open the best available editor against ~/work.") + `
    <div class="grid two">
      ${panel("DETECTED EDITOR", `<div class="kpi" style="font-size:30px">${esc(cap.path ? cap.path.split("/").pop() : "missing")}</div>${statRow("Path",cap.path || "Install Pulsar, Cursor, VSCodium, VS Code, or Xed")}<div class="button-row" style="margin-top:18px"><button class="btn primary dv-btn dv-btn--primary" data-launch="editor" ${cap.available?"":"disabled"}>OPEN ~/work</button></div>`, "accent")}
      ${panel("PROTOTYPE MAPPING", `<pre class="code-block"><span class="purple">fn</span> spawn_agent(name: &amp;str) {\n  <span class="cyan">home</span> = "~/agents/" + name;\n  scope.mount(home, RW::Agent);\n  scope.mount("~/work", RW::Work);\n}</pre><p class="muted">This concept is implemented by the agent registry and optional Bubblewrap runner rather than an editor-specific mock panel.</p>`)}
    </div>`;
}

function renderBrowser() {
  const cap = capability("browser");
  return heading("網接続", "BROWSER + AGENT PANEL", "Launch a browser while keeping agent state visible in the machine UI.") + `
    <div class="grid two">
      ${panel("BROWSER", `<div class="kpi" style="font-size:30px">${esc(cap.path ? cap.path.split("/").pop() : "missing")}</div><div class="button-row" style="margin-top:18px"><button class="btn primary dv-btn dv-btn--primary" data-launch="browser" ${cap.available?"":"disabled"}>OPEN BROWSER</button></div>${statRow("Backend",cap.path || "not installed")}`, "accent")}
      ${panel("ACTIVE AGENTS", app.state.agents.map(a=>`<div class="list-row"><span><span class="${a.available?"green":"amber"}">●</span> ${esc(a.name)}</span><button class="btn dv-btn dv-btn--outline" data-agent="${esc(a.name)}" ${a.available?"":"disabled"}>SPAWN</button></div>`).join(""))}
    </div>`;
}

function renderRofi() {
  const cap = capability("rofi");
  return heading("起動器", "ROFI", "Use the installed Matrix Rofi theme and desktop application index.") + `
    <div class="grid two">
      ${panel("APPLICATION LAUNCHER", `<div class="terminal"><span class="mag">墨</span> <span class="muted">search applications</span>\n\n<span class="mint">❯</span> <span class="cmd">rofi -show drun</span>\n<span class="out">kitty</span>\n<span class="out">pulsar / cursor</span>\n<span class="out">system settings</span></div><div class="button-row" style="margin-top:14px"><button class="btn primary dv-btn dv-btn--primary" data-launch="rofi" ${cap.available?"":"disabled"}>OPEN ROFI</button></div>`, "accent")}
      ${panel("STATUS", `${statRow("Available",cap.available?"yes":"no")}${statRow("Path",cap.path || "not installed")}${statRow("Theme","~/.config/rofi/themes/matrix.rasi")}`)}
    </div>`;
}

function renderDocs() {
  const id = app.state.identity;
  return heading("構成資料", "DOTFILES + PACKAGE", "The UI package is separate from the desktop rice, but both share one settings and palette model.") + `
    <div class="grid two">
      ${panel("CONFIG PATHS", `<pre class="code-block">~/.config/lmdesktopplus/settings.json\n~/.config/lmdesktopplus/agents.json\n~/.config/lmdesktopplus/hypr-generated.conf\n~/.config/vapor-matrix.theme\n~/.local/share/lmdesktopplus/agents/</pre><div class="button-row" style="margin-top:14px"><button class="btn dv-btn dv-btn--outline" data-action="open-config">OPEN LMDP CONFIG</button><button class="btn dv-btn dv-btn--outline" data-launch="docs">OPEN ~/.config</button></div>`)}
      ${panel("SYSTEM", `${statRow("Host",`${id.user}@${id.hostname}`)}${statRow("OS",id.os)}${statRow("Kernel",id.kernel)}${statRow("Session",`${id.session} · ${id.session_type}`)}${statRow("Architecture",id.architecture)}${statRow("UI version",app.state.version)}`)}
    </div>
    ${panel("PACKAGE COMMANDS", `<pre class="code-block">./install.sh                  # user-local rice + control center\n./install.sh --with-hyprland # include compositor setup\n./packaging/build-deb.sh     # build installable .deb\nlmdesktopplus               # launch machine UI\nlmdesktopplus --browser     # browser fallback\nlmdesktopplus --kiosk       # fullscreen embedded UI</pre>`, "accent")}`;
}

function chartSvg(values, maxValue=100) {
  const vals = values.length ? values : [0,0];
  const w=560,h=110;
  const max = Math.max(maxValue, ...vals, 1);
  const points = vals.map((v,i)=>`${(i*(w/(Math.max(1,vals.length-1)))).toFixed(1)},${(h-(clamp(v,0,max)/max*h)).toFixed(1)}`).join(" ");
  const area = `${points} ${w},${h} 0,${h}`;
  return `<svg class="chart" viewBox="0 0 ${w} ${h}" preserveAspectRatio="none"><g class="chart-grid"><line x1="0" y1="27" x2="560" y2="27"/><line x1="0" y1="55" x2="560" y2="55"/><line x1="0" y1="82" x2="560" y2="82"/></g><polygon class="chart-area" points="${area}"/><polyline class="chart-line" points="${points}"/></svg>`;
}

function renderMonitor() {
  const m=app.state.metrics;
  const temp = m.temperatures?.[0];
  const maxNet = Math.max(1024*1024, ...app.history.down, ...app.history.up);
  const cores = (m.cpu.cores || []).map(v=>`<div class="core-bar" title="${Math.round(v)}%" style="height:${Math.max(3,clamp(v,0,100))}%"></div>`).join("");
  return heading("監視系", "SYSTEM MONITOR", "Live values are sampled from /proc, sysfs, and vendor tools when available.", `<button class="btn dv-btn dv-btn--outline" data-launch="monitor">OPEN BTOP</button>`) + `
    <div class="grid two">
      ${panel(`CPU · ${Math.round(m.cpu.percent)}%`, `${chartSvg(app.history.cpu)}<div class="core-grid">${cores}</div>`, "accent")}
      ${panel(`MEMORY · ${Math.round(m.memory.percent)}%`, `${chartSvg(app.history.ram)}${statRow("Used",humanBytes(m.memory.used))}${statRow("Available",humanBytes(m.memory.available))}`)}
      ${panel(`GPU · ${m.gpu.percent == null ? "n/a" : Math.round(m.gpu.percent)+"%"}`, `${chartSvg(app.history.gpu)}${statRow("Device",m.gpu.name || "unavailable")}${statRow("Temperature",m.gpu.temperature_c != null ? `${m.gpu.temperature_c} °C` : "n/a")}`)}
      ${panel("NETWORK", `${chartSvg(app.history.down,maxNet)}${statRow("Download",humanBytes(m.network.down_bps,true))}${statRow("Upload",humanBytes(m.network.up_bps,true))}`)}
    </div>
    <div class="grid three" style="margin-top:16px">
      ${panel("DISK", `<div class="kpi">${Math.round(m.disk.percent)}<small>% used</small></div><div class="progress dv-progress"><span class="dv-progress__bar" style="width:${clamp(m.disk.percent,0,100)}%"></span></div>${statRow("Free",humanBytes(m.disk.free))}`)}
      ${panel("THERMALS", m.temperatures?.length ? m.temperatures.slice(0,6).map(t=>statRow(t.label,`${t.celsius} °C`)).join("") : `<p class="muted">No readable thermal zones.</p>`)}
      ${panel("POWER", m.battery ? `${statRow("Battery",`${m.battery.percent}%`)}${statRow("Status",m.battery.status)}` : `<div class="kpi" style="font-size:30px">AC<small>no battery detected</small></div>`)}
    </div>`;
}

function renderApps() {
  const caps = app.state.capabilities;
  const features = app.state.settings.features;
  const entries = [
    ["kitty","Terminal","terminal"],["tmux","Persistent sessions","tmux"],["rofi","Application launcher","rofi"],["waybar","Hyprland bar","hyprctl"],
    ["claude","Claude agent","bubblewrap"],["cursor","Cursor editor","editor"],["aider","Aider agent","bubblewrap"],["starship","Shell prompt",null],
    ["rust","Rust tooling",null],["minimap","Editor minimap",null],["gitn","Git integration",null],["vapor","Vapor theme",null],
  ];
  const cards = entries.map(([id,label,cap])=>{
    const enabled = !!features[id];
    const available = cap ? !!caps[cap]?.available : true;
    return `<div class="app-card dv-card"><div class="app-head"><strong>${esc(label)}</strong><span class="badge dv-tag ${available?"ok dv-tag--mint":"warn dv-tag--warn"}">${available?"detected":"optional"}</span></div><p class="muted">${esc(id)}</p><label class="toggle dv-toggle"><input type="checkbox" data-feature="${id}" ${enabled?"checked":""}><span class="toggle-track dv-track"><span class="toggle-knob"></span></span><span>${enabled?"ENABLED":"OFF"}</span></label></div>`;
  }).join("");
  return heading("拡張蔵", "APP VAULT", "Feature switches are persisted; capability badges reflect installed executables.") + `<div class="app-grid">${cards}</div>`;
}

const settingTabs = [
  ["appearance","外観","Appearance"],["display","画面","Display"],["network","網","Network"],["agents","代理","Agents"],["keybinds","鍵","Keybinds"],["about","情報","About"]
];

function renderSettings() {
  const nav = settingTabs.map(([id,jp,label])=>`<button class="settings-tab dv-navitem ${id===app.settingsTab?"active is-active":""}" data-settings-tab="${id}"><span class="jp dv-jp">${jp}</span>${label}</button>`).join("");
  return heading("設定系", "SYSTEM SETTINGS", "Appearance changes persist immediately and generate GTK/Hyprland overlays.") + `<div class="settings-layout"><nav class="panel settings-nav dv-panel dv-sidepanel">${nav}</nav><section class="panel card dv-panel dv-card">${renderSettingsTab()}</section></div>`;
}

function renderSettingsTab() {
  const s=app.state.settings, ap=s.appearance, behavior=s.behavior;
  if (app.settingsTab === "appearance") {
    const swatches = Object.entries(app.state.accents).map(([name,hex])=>`<button class="swatch ${name===ap.accent?"active":""}" data-accent="${name}" title="${name}" style="background:${hex};box-shadow:0 0 10px ${hex}"></button>`).join("");
    const modes = ["tiled","floating","tabbed"].map(x=>`<button class="segment dv-seg__opt ${ap.window_mode===x?"active":""}" data-window-mode="${x}">${x}</button>`).join("");
    return `<div class="setting-group"><h3>Accent</h3><div class="swatches">${swatches}</div></div>
      ${control("Interface font","Applied to the machine UI",`<select class="dv-input" data-setting="appearance.font"><option ${ap.font==="JetBrains Mono"?"selected":""}>JetBrains Mono</option><option ${ap.font==="DotGothic16"?"selected":""}>DotGothic16</option><option ${ap.font==="Zen Dots"?"selected":""}>Zen Dots</option><option ${ap.font==="System UI"?"selected":""}>System UI</option></select>`)}
      ${control("Surface opacity",`${ap.opacity}%`,`<input class="dv-slider" type="range" min="40" max="100" value="${ap.opacity}" data-setting="appearance.opacity" data-number>`)}
      ${control("Blur radius",`${ap.blur}px`,`<input class="dv-slider" type="range" min="0" max="24" value="${ap.blur}" data-setting="appearance.blur" data-number>`)}
      ${control("Matrix intensity",`${ap.rain_intensity}%`,`<input class="dv-slider" type="range" min="0" max="100" value="${ap.rain_intensity}" data-setting="appearance.rain_intensity" data-number>`)}
      ${control("Window mode","Hyprland preference",`<div class="segmented dv-seg">${modes}</div>`)}
      ${toggleControl("Scanlines","CRT overlay in this UI","appearance.scanlines",ap.scanlines)}
      ${toggleControl("Window gaps","Generated Hyprland overlay","appearance.gaps",ap.gaps)}
      ${toggleControl("Rounded corners","Generated Hyprland overlay","appearance.rounded",ap.rounded)}
      ${toggleControl("Drop shadows","Generated Hyprland overlay","appearance.shadows",ap.shadows)}`;
  }
  if (app.settingsTab === "display") {
    return `${toggleControl("Start fullscreen","Open the embedded machine UI fullscreen","behavior.start_fullscreen",behavior.start_fullscreen)}
      ${toggleControl("Show shortcut hints","Show keyboard hints on the desktop scene","behavior.show_hints",behavior.show_hints)}
      ${control("Poll interval",`${behavior.poll_interval_ms} ms`,`<input class="dv-slider" type="range" min="500" max="5000" step="250" value="${behavior.poll_interval_ms}" data-setting="behavior.poll_interval_ms" data-number>`)}
      ${toggleControl("Allow power actions","Required before logout, reboot, suspend, or poweroff API calls","behavior.allow_power_actions",behavior.allow_power_actions)}
      <div class="button-row" style="margin-top:16px"><button class="btn dv-btn dv-btn--outline" data-action="lock">LOCK SYSTEM</button><button class="btn danger dv-btn dv-btn--danger" data-power="suspend">SUSPEND</button><button class="btn danger dv-btn dv-btn--danger" data-power="logout">LOG OUT</button></div>`;
  }
  if (app.settingsTab === "network") return renderNetworkSettings();
  if (app.settingsTab === "agents") return renderAgentSettings();
  if (app.settingsTab === "keybinds") return renderKeybinds();
  return renderAbout();
}

function control(label,note,widget) { return `<div class="control-row"><div><label>${esc(label)}</label><small>${esc(note)}</small></div><div>${widget}</div></div>`; }
function toggleControl(label,note,path,checked) { return control(label,note,`<label class="toggle dv-toggle"><input type="checkbox" data-setting="${path}" ${checked?"checked":""}><span class="toggle-track dv-track"><span class="toggle-knob"></span></span><span>${checked?"ON":"OFF"}</span></label>`); }

function renderNetworkSettings() {
  const current = app.state.network;
  const active = current.connections?.length ? current.connections.map(c=>`${esc(c.name)} (${esc(c.device)})`).join(", ") : "not connected";
  const networks = app.networkScan?.networks || [];
  const rows = networks.map(n=>`<div class="network-row"><div><strong class="white">${esc(n.ssid)}</strong><div class="muted">${esc(n.security)} · ${esc(n.device)} ${n.active?"· active":""}</div></div><div class="signal"><div class="progress dv-progress"><span class="dv-progress__bar" style="width:${clamp(n.signal,0,100)}%"></span></div><small>${n.signal}%</small></div><button class="btn dv-btn dv-btn--outline" data-connect-ssid="${encodeURIComponent(n.ssid)}">${n.active?"ACTIVE":"CONNECT"}</button></div>`).join("");
  return `<div class="setting-group"><h3>NetworkManager</h3>${statRow("Active",active)}${statRow("Adapter",current.available?"nmcli":"unavailable")}</div><div class="button-row"><button class="btn primary dv-btn dv-btn--primary" data-network-scan>SCAN WI-FI</button>${current.connections?.filter(c=>c.device).map(c=>`<button class="btn danger dv-btn dv-btn--danger" data-disconnect="${esc(c.device)}">DISCONNECT ${esc(c.device)}</button>`).join("") || ""}</div><div style="margin-top:16px">${app.networkScan ? (rows || `<p class="muted">No networks returned.</p>`) : `<p class="muted">Scan to populate live SSIDs. Passwords are sent directly to nmcli and are not persisted by LMDesktopPlus.</p>`}</div>`;
}

function renderAgentSettings() {
  return `<p class="muted">Agent definitions are stored in <span class="cyan">~/.config/lmdesktopplus/agents.json</span>. Commands are intentionally edited in the file rather than through the web UI, so a stray click cannot create a new arbitrary command.</p><div class="grid two">${app.state.agents.map(a=>`<div class="app-card dv-card"><div class="app-head"><strong>${esc(a.label)}</strong><span class="badge dv-tag ${a.available?"ok dv-tag--mint":"warn dv-tag--warn"}">${a.available?"ready":"missing"}</span></div>${statRow("Command",a.command.join(" "))}${statRow("Home",a.home)}${statRow("Workspace",a.workspace_resolved)}${statRow("Sandbox",a.sandbox?(a.sandbox_available?"Bubblewrap":"requested; bwrap missing"):"off")}${statRow("Network",a.network?"allowed":"isolated")}<button class="btn primary dv-btn dv-btn--primary" data-agent="${esc(a.name)}" ${a.available?"":"disabled"}>SPAWN</button></div>`).join("")}</div><div class="button-row" style="margin-top:16px"><button class="btn dv-btn dv-btn--outline" data-action="open-config">OPEN CONFIG FOLDER</button></div>`;
}

function renderKeybinds() {
  const keys = [
    ["1–0 / K","Switch UI scenes"],["Escape","Internal lock screen"],["F11","Toggle application fullscreen"],
    ["Super + Enter","Kitty (Hyprland config)"],["Super + Space","Rofi"],["Super + A","Agent surface"],
    ["Super + Q","Close window"],["Super + F","Fullscreen window"],["Super + V","Toggle floating"],["Super + Esc","System lock"],
  ];
  return keys.map(([combo,act])=>`<div class="list-row"><span class="badge dv-tag">${esc(combo)}</span><span class="value">${esc(act)}</span></div>`).join("");
}

function renderAbout() {
  const id=app.state.identity;
  return `<div class="grid two">${panel("LMDesktopPlus", `${statRow("Version",app.state.version)}${statRow("API","loopback-only + per-launch token")}${statRow("Frontend","plain HTML/CSS/JavaScript")}${statRow("Host shell",id.session)}${statRow("Python",id.python)}`)}${panel("BOUNDARIES", `<p class="muted">This UI manages the current user session. It does not expose a remote management port, store Wi-Fi passwords, or accept arbitrary shell commands over the API.</p><p class="muted">Power operations remain disabled until explicitly enabled. Bubblewrap adds useful filesystem isolation for agents but is not equivalent to a virtual machine.</p>`)}</div>`;
}

function renderKit() {
  return heading("部品庫", "DIGITALVAPOR KIT", "The live control center now shares one token, component, chrome, and interaction layer.") + `
    <div class="grid three">
      ${panel("BUTTONS", `<div class="button-row"><button class="dv-btn dv-btn--primary" data-demo-toast="Primary action">PRIMARY</button><button class="dv-btn dv-btn--outline" data-demo-toast="Outline action">OUTLINE</button><button class="dv-btn dv-btn--ghost" data-demo-toast="Ghost action">GHOST</button><button class="dv-btn dv-btn--danger" data-demo-toast="Danger action">DANGER</button></div>`)}
      ${panel("TAGS + STATES", `<div class="button-row"><span class="dv-tag dv-tag--mag"><span class="dv-tag__dot"></span>agent</span><span class="dv-tag dv-tag--cyan">network</span><span class="dv-tag dv-tag--mint">healthy</span><span class="dv-tag dv-tag--purple">isolated</span><span class="dv-tag dv-tag--warn">degraded</span></div>`)}
      ${panel("FIELDS", `<div class="dv-col"><div class="dv-field"><label>Workspace</label><input class="dv-input" value="~/work" aria-label="Workspace example"></div><div class="dv-field"><label>Search</label><input class="dv-input" placeholder="agent, app, setting…" aria-label="Search example"></div><label class="dv-toggle"><input type="checkbox" checked><span class="dv-track"></span><span style="margin-left:9px">enabled</span></label></div>`)}
      ${panel("SEGMENT + SLIDER", `<div class="dv-seg" role="group" aria-label="Window mode demo"><label class="dv-seg__opt"><input type="radio" name="kit-mode" checked>tiled</label><label class="dv-seg__opt"><input type="radio" name="kit-mode">float</label><label class="dv-seg__opt"><input type="radio" name="kit-mode">tabs</label></div><div style="margin-top:22px"><input class="dv-slider dv-slider--cyan" type="range" min="0" max="100" value="68" aria-label="Intensity demo"></div>`)}
      ${panel("TABS", `<div data-dv-tabs data-dv-panels="#kit-tab-panels"><div class="dv-tabs"><button class="dv-tab is-active" data-dv-panel="agents">AGENTS</button><button class="dv-tab" data-dv-panel="system">SYSTEM</button><button class="dv-tab" data-dv-panel="theme">THEME</button></div></div><div id="kit-tab-panels" style="padding-top:14px"><div data-dv-panel-content="agents">Scoped homes and workspaces.</div><div data-dv-panel-content="system" hidden>Live local machine telemetry.</div><div data-dv-panel-content="theme" hidden>Semantic tokens drive every surface.</div></div>`)}
      ${panel("DROPDOWN", `<div class="dv-dropdown" data-dv-dropdown><button class="dv-dropdown__toggle" type="button"><span data-dv-dropdown-label>Balanced profile</span><span>⌄</span></button><div class="dv-dropdown__list"><div class="dv-dropdown__item is-active" data-value="balanced">Balanced profile</div><div class="dv-dropdown__item" data-value="high-contrast">High contrast</div><div class="dv-dropdown__item" data-value="minimal-effects">Minimal effects</div></div></div>`)}
      ${panel("PROGRESS", `<div class="stat-row"><span>Build</span><span>65%</span></div><div class="dv-progress"><span class="dv-progress__bar" style="display:block;width:65%"></span></div><div class="stat-row"><span>Agent context</span><span>41%</span></div><div class="dv-progress"><span class="dv-progress__bar" style="display:block;width:41%"></span></div><div style="margin-top:18px"><span class="dv-spinner" aria-label="Loading"></span></div>`)}
      ${panel("CONTEXT MENU", `<div class="context-demo" data-dv-menu><p class="dv-muted">Right-click this panel surface.</p><div class="dv-menu" hidden><div class="dv-menu__item" data-demo-toast="Open module">Open module</div><div class="dv-menu__item" data-demo-toast="Pin module">Pin to dock</div><div class="dv-menu__sep"></div><div class="dv-menu__item" data-demo-toast="Module settings">Settings</div></div></div>`)}
      ${panel("DIALOG + TOAST", `<p class="dv-muted">Modal and notification surfaces now use the same chrome.</p><div class="button-row"><button class="dv-btn dv-btn--primary" data-dv-dialog="kit-dialog">OPEN DIALOG</button><button class="dv-btn dv-btn--outline" data-demo-toast="Digitalvapor notification">SHOW TOAST</button></div>`)}
      ${panel("WINDOW CHROME", `<div class="dv-window dv-window--borderless"><div class="dv-window__bar"><span class="dv-window__title">agent://claude/workspace</span><span class="dv-window__dots"><i></i><i></i><i></i></span></div><div class="dv-window__body terminal compact"><span class="green">root@vaporframe</span> <span class="muted">~</span><br><span class="mint">❯</span> agent status<br><span class="out">ready · scoped · network on</span></div></div>`)}
    </div>
    <div id="kit-dialog" class="dv-dialog-backdrop" role="dialog" aria-modal="true" aria-hidden="true" aria-labelledby="kit-dialog-title">
      <div class="dv-dialog"><div class="dv-dialog__bar"><span class="dv-mag">墨</span><span id="kit-dialog-title">DIGITALVAPOR DIALOG</span><button type="button" class="dv-dialog__close" data-dv-close aria-label="Close">×</button></div><div class="dv-dialog__body">This is the same modal component used for Wi-Fi credentials and destructive-action confirmation.</div><div class="dv-dialog__actions"><button class="dv-btn dv-btn--ghost" data-dv-close>CANCEL</button><button class="dv-btn dv-btn--primary" data-demo-toast="Dialog accepted" data-dv-close>ACCEPT</button></div></div>
    </div>`;
}

function nestedPatch(path, value) {
  const keys = path.split(".");
  const root = {};
  let cursor = root;
  keys.forEach((key,i) => { if (i === keys.length-1) cursor[key]=value; else cursor=cursor[key]={}; });
  return root;
}

async function saveSetting(path, value) {
  try {
    const result = await api("/api/v1/settings", {method:"POST", body:{patch:nestedPatch(path,value), apply:true}});
    app.state.settings = result.settings;
    applyAppearance();
    toast("Settings saved", path);
    renderScene(true);
  } catch (error) { toast("Settings failed",error.message,true); }
}

async function runAction(action,target="") {
  try {
    const result = await api("/api/v1/action", {method:"POST", body:{action,target}});
    toast("Action started", target || action);
    return result;
  } catch (error) { toast("Action failed", error.message, true); }
}

async function connectWifi(ssid, password="") {
  try {
    await api("/api/v1/network/connect", {method:"POST", body:{ssid, password}});
    toast("Network connected", ssid);
    app.networkScan = await api("/api/v1/network/scan");
    renderScene(true);
  } catch (error) {
    toast("Connection failed", error.message, true);
  }
}

function requestWifiPassword(ssid) {
  app.pendingWifiSsid = ssid;
  $("#wifi-dialog-ssid").textContent = ssid;
  const form = $("#wifi-form");
  form.reset();
  form.elements.ssid.value = ssid;
  window.Digitalvapor?.openDialog("wifi-dialog");
}

function requestConfirmation(action) {
  app.pendingConfirm = () => runAction(action);
  $("#confirm-dialog-title").textContent = `CONFIRM ${action.toUpperCase()}`;
  $("#confirm-dialog-body").textContent = `Run the allowlisted system action “${action}”?`;
  $("#confirm-dialog-accept").textContent = action.toUpperCase();
  window.Digitalvapor?.openDialog("confirm-dialog");
}

function bindSceneEvents() {
  const root = $("#scene");
  $$('[data-launch]', root).forEach(n=>n.addEventListener("click",()=>runAction("launch",n.dataset.launch)));
  $$('[data-action]', root).forEach(n=>n.addEventListener("click",()=>runAction(n.dataset.action)));
  $$('[data-agent]', root).forEach(n=>n.addEventListener("click",async()=>{
    try { await api("/api/v1/agents/launch",{method:"POST",body:{name:n.dataset.agent}}); toast("Agent spawned",n.dataset.agent); }
    catch(error){ toast("Agent launch failed",error.message,true); }
  }));
  $$('[data-media]', root).forEach(n=>n.addEventListener("click",async()=>{
    try { await api("/api/v1/media",{method:"POST",body:{action:n.dataset.media}}); toast("Media",n.dataset.media); }
    catch(error){ toast("Media action failed",error.message,true); }
  }));
  $$('[data-settings-tab]', root).forEach(n=>n.addEventListener("click",()=>{ app.settingsTab=n.dataset.settingsTab; if(n.dataset.sceneJump) setScene(n.dataset.sceneJump); else renderScene(true); }));
  $$('[data-scene-jump]', root).forEach(n=>n.addEventListener("click",()=>{ app.settingsTab=n.dataset.settingsTab || app.settingsTab; setScene(n.dataset.sceneJump); }));
  $$('[data-setting]', root).forEach(n=>n.addEventListener("change",()=>{
    let value = n.type === "checkbox" ? n.checked : n.value;
    if (n.hasAttribute("data-number")) value = Number(value);
    saveSetting(n.dataset.setting,value);
  }));
  $$('[data-accent]', root).forEach(n=>n.addEventListener("click",()=>saveSetting("appearance.accent",n.dataset.accent)));
  $$('[data-window-mode]', root).forEach(n=>n.addEventListener("click",()=>saveSetting("appearance.window_mode",n.dataset.windowMode)));
  $$('[data-feature]', root).forEach(n=>n.addEventListener("change",()=>saveSetting(`features.${n.dataset.feature}`,n.checked)));
  $$('[data-network-scan]', root).forEach(n=>n.addEventListener("click",async()=>{
    n.disabled=true; n.textContent="SCANNING…";
    try { app.networkScan=await api("/api/v1/network/scan"); renderScene(true); }
    catch(error){ toast("Wi-Fi scan failed",error.message,true); n.disabled=false; }
  }));
  $$('[data-connect-ssid]', root).forEach(n=>n.addEventListener("click",()=>{
    const ssid=decodeURIComponent(n.dataset.connectSsid);
    const network=(app.networkScan?.networks||[]).find(x=>x.ssid===ssid);
    if(network?.active){ toast("Already connected",ssid); return; }
    const security=String(network?.security || "").toLowerCase();
    const needsPassword=Boolean(network && security && security!=="open" && security!=="--");
    if(needsPassword) requestWifiPassword(ssid);
    else connectWifi(ssid);
  }));
  $$('[data-disconnect]', root).forEach(n=>n.addEventListener("click",async()=>{
    try { await api("/api/v1/network/disconnect",{method:"POST",body:{device:n.dataset.disconnect}}); toast("Network disconnected",n.dataset.disconnect); }
    catch(error){ toast("Disconnect failed",error.message,true); }
  }));
  $$('[data-power]', root).forEach(n=>n.addEventListener("click",()=>requestConfirmation(n.dataset.power)));
  $$('[data-ui-lock]', root).forEach(n=>n.addEventListener("click",lockUi));
}

function bindGlobal() {
  $("#unlock-button").addEventListener("click",unlock);
  $("#lock-screen").addEventListener("click",unlock);

  $("#wifi-form").addEventListener("submit", (event) => {
    event.preventDefault();
    const form = event.currentTarget;
    const ssid = form.elements.ssid.value || app.pendingWifiSsid;
    const password = form.elements.password.value;
    window.Digitalvapor?.closeDialog("wifi-dialog");
    app.pendingWifiSsid = null;
    if (ssid) connectWifi(ssid, password);
  });

  $("#confirm-dialog-accept").addEventListener("click", () => {
    const callback = app.pendingConfirm;
    app.pendingConfirm = null;
    window.Digitalvapor?.closeDialog("confirm-dialog");
    if (callback) callback();
  });

  document.addEventListener("click", (event) => {
    const demo = event.target.closest("[data-demo-toast]");
    if (demo) toast(demo.dataset.demoToast, "Digitalvapor component event");
  });

  document.addEventListener("keydown",event=>{
    if(app.locked){ unlock(); return; }
    if (document.querySelector(".dv-dialog-backdrop.is-open")) return;
    const tag=document.activeElement?.tagName;
    if(["INPUT","SELECT","TEXTAREA"].includes(tag)) return;
    const map={"1":"desktop","2":"terminal","3":"tmux","4":"editor","5":"browser","6":"rofi","7":"docs","8":"monitor","9":"apps","0":"settings","k":"kit","K":"kit"};
    if(map[event.key]) setScene(map[event.key]);
    if(event.key==="Escape") lockUi();
  });
  $(".topbar [data-action=\"lock\"]").addEventListener("click",()=>runAction("lock"));
}

setClock();
setInterval(setClock,1000);
bindGlobal();
poll();
