/* LMDesktopPlus scene binding helpers — dependency-free dispatch utilities. */
(function (global) {
  "use strict";

  /**
   * Bind a table of {sel, type?, run(el, event)} entries under root.
   * queryAll(sel, root) defaults to Element.querySelectorAll.
   */
  function bindFromTable(root, bindings, queryAll) {
    const list =
      queryAll ||
      ((sel, scope) => Array.from((scope || document).querySelectorAll(sel)));
    for (const entry of bindings) {
      const type = entry.type || "click";
      list(entry.sel, root).forEach((el) => {
        el.addEventListener(type, (event) => entry.run(el, event));
      });
    }
  }

  /** Resize/sync core bar children without rebuilding the parent. */
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

  global.LMDPBindings = {
    bindFromTable,
    syncCoreBars,
    renderThermalRows,
    renderPowerPanel,
  };
})(typeof window !== "undefined" ? window : globalThis);
