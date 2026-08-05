/* LMDesktopPlus scene binding helpers — dependency-free dispatch utilities. */
(function (global) {
  "use strict";

  /**
   * Memory hashmap of use-level annotated UI callables for O(1) resolve.
   * Levels: "high use" | "medium use" | "low use"
   */
  const FnCache = {
    map: new Map(),
    register(name, level, purpose, fn) {
      // Index callable + metadata; hits track UI→operation heat.
      const entry = { fn, level, purpose, hits: 0 };
      this.map.set(name, entry);
      return fn;
    },
    resolve(name) {
      // Hot-path lookup — prefer this over walking nested app objects.
      const entry = this.map.get(name);
      if (!entry) throw new Error(`fncache miss: ${name}`);
      entry.hits += 1;
      return entry.fn;
    },
    meta(name) {
      const entry = this.map.get(name);
      if (!entry) return null;
      return { name, level: entry.level, purpose: entry.purpose, hits: entry.hits };
    },
    warmHighUse() {
      return [...this.map.entries()]
        .filter(([, entry]) => entry.level === "high use")
        .map(([name]) => name);
    },
    snapshot() {
      const out = {};
      for (const [name, entry] of this.map.entries()) {
        out[name] = { level: entry.level, purpose: entry.purpose, hits: entry.hits };
      }
      return out;
    },
  };

  /**
   * @use: high use — purpose: bind SCENE_BINDINGS table under a scene root
   * Bind a table of {sel, type?, run(el, event)} entries under root.
   * queryAll(sel, root) defaults to Element.querySelectorAll.
   */
  function bindFromTable(root, bindings, queryAll) {
    const list =
      queryAll ||
      ((sel, scope) => Array.from((scope || document).querySelectorAll(sel)));
    for (const entry of bindings) {
      const type = entry.type || "click";
      // Prefer cached run handler when binding names a fncache key.
      const run =
        typeof entry.fn === "string"
          ? (el, event) => FnCache.resolve(entry.fn)(el, event)
          : entry.run;
      list(entry.sel, root).forEach((el) => {
        el.addEventListener(type, (event) => run(el, event));
      });
    }
  }

  FnCache.register(
    "bindings.bindFromTable",
    "high use",
    "Attach SCENE_BINDINGS listeners for the active scene",
    bindFromTable
  );

  /** @use: high use — purpose: Monitor CPU core bars without full scene rebuild */
  function syncCoreBars(root, cores, clampFn) {
    if (!root) return;
    const clamp = clampFn || ((v, min, max) => Math.max(min, Math.min(max, Number(v) || 0)));
    while (root.children.length > cores.length) root.lastElementChild.remove();
    while (root.children.length < cores.length) {
      const bar = document.createElement("div");
      bar.className = "core-bar";
      root.append(bar);
    }
    cores.forEach((value, index) => {
      const bar = root.children[index];
      bar.title = `${Math.round(value)}%`;
      bar.style.height = `${Math.max(3, clamp(value, 0, 100))}%`;
    });
  }

  /** @use: medium use — purpose: append a labeled stat row into a panel */
  function appendStatRow(parent, name, current) {
    const row = document.createElement("div");
    row.className = "stat-row";
    const label = document.createElement("span");
    label.className = "label";
    label.textContent = name;
    const value = document.createElement("span");
    value.className = "value";
    value.textContent = current;
    row.append(label, value);
    parent.append(row);
  }

  /** @use: high use — purpose: patch Monitor thermal list on metrics ticks */
  function renderThermalRows(root, temperatures) {
    if (!root) return;
    root.replaceChildren();
    if (!temperatures.length) {
      const empty = document.createElement("p");
      empty.className = "muted";
      empty.textContent = "No readable thermal zones.";
      root.append(empty);
      return;
    }
    temperatures.forEach((item) => {
      appendStatRow(root, item.label, `${item.celsius} °C`);
    });
  }

  /** @use: high use — purpose: patch Monitor power/battery panel on metrics ticks */
  function renderPowerPanel(root, battery) {
    if (!root) return;
    root.replaceChildren();
    if (battery) {
      appendStatRow(root, "Battery", `${battery.percent}%`);
      appendStatRow(root, "Status", battery.status);
      return;
    }
    const kpi = document.createElement("div");
    kpi.className = "kpi";
    kpi.style.fontSize = "30px";
    kpi.append("AC");
    const detail = document.createElement("small");
    detail.textContent = "no battery detected";
    kpi.append(detail);
    root.append(kpi);
  }

  FnCache.register(
    "bindings.syncCoreBars",
    "high use",
    "Resize Monitor CPU core bars from metrics samples",
    syncCoreBars
  );
  FnCache.register(
    "bindings.renderThermalRows",
    "high use",
    "Patch thermal zone rows without rebuilding the scene",
    renderThermalRows
  );
  FnCache.register(
    "bindings.renderPowerPanel",
    "high use",
    "Patch battery/AC panel without rebuilding the scene",
    renderPowerPanel
  );

  global.LMDPBindings = {
    bindFromTable,
    syncCoreBars,
    renderThermalRows,
    renderPowerPanel,
    FnCache,
  };
  global.LMDPFnCache = FnCache;
})(typeof window !== "undefined" ? window : globalThis);
