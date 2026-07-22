"use strict";

/* Dependency-free Digitalvapor interactions used by LMDesktopPlus. */
(function () {
  const DV = {};
  const rainStops = new WeakMap();

  function text(value) {
    return document.createTextNode(String(value ?? ""));
  }

  DV.rain = function rain(canvas, options = {}) {
    if (!(canvas instanceof HTMLCanvasElement)) return () => {};
    if (rainStops.has(canvas)) return rainStops.get(canvas);

    const context = canvas.getContext("2d");
    if (!context) return () => {};
    const fontSize = Number(options.fontSize) || 15;
    const glyphs = String(options.glyphs ||
      "アイウエオカキクケコサシスセソタチツテトナニヌネノハヒフヘホマミムメモヤユヨラリルレロワヲン0123456789=+*<>#%$").split("");
    const accents = ["#ff2e97", "#01cdfe", "#b967ff", "#ff71ce"];
    let drops = [];
    let frame = 0;

    function resize() {
      const ratio = Math.max(1, window.devicePixelRatio || 1);
      const width = Math.max(1, canvas.clientWidth || window.innerWidth);
      const height = Math.max(1, canvas.clientHeight || window.innerHeight);
      canvas.width = Math.floor(width * ratio);
      canvas.height = Math.floor(height * ratio);
      context.setTransform(ratio, 0, 0, ratio, 0, 0);
      drops = Array.from({length: Math.ceil(width / fontSize)}, () => Math.random() * -60);
    }

    function draw() {
      const width = canvas.clientWidth || window.innerWidth;
      const height = canvas.clientHeight || window.innerHeight;
      const intensity = Math.max(0, Math.min(1, Number(canvas.dataset.dvIntensity ?? options.intensity ?? 55) / 100));
      context.fillStyle = "rgba(5,6,10,0.085)";
      context.fillRect(0, 0, width, height);
      context.font = `${fontSize}px ${getComputedStyle(document.documentElement).getPropertyValue("--dv-mono") || "monospace"}`;
      const accentProbability = 0.02 + (1 - intensity) * 0.10;
      for (let i = 0; i < drops.length; i += 1) {
        const glyph = glyphs[(Math.random() * glyphs.length) | 0];
        const x = i * fontSize;
        const y = drops[i] * fontSize;
        const roll = Math.random();
        context.fillStyle = roll < accentProbability
          ? accents[(Math.random() * accents.length) | 0]
          : roll < accentProbability + 0.12 ? "#d6ffe8" : "#00ff70";
        context.fillText(glyph, x, y);
        if (y > height && Math.random() > 0.972) drops[i] = 0;
        drops[i] += 0.5 + Math.random() * 0.35;
      }
      frame = requestAnimationFrame(draw);
    }

    resize();
    window.addEventListener("resize", resize);
    draw();
    const stop = () => {
      cancelAnimationFrame(frame);
      window.removeEventListener("resize", resize);
      rainStops.delete(canvas);
    };
    rainStops.set(canvas, stop);
    return stop;
  };

  DV.toast = function toast(options = {}) {
    let host = document.querySelector(".dv-toasts");
    if (!host) {
      host = document.createElement("div");
      host.className = "dv-toasts";
      document.body.appendChild(host);
    }
    const node = document.createElement("div");
    const tone = options.tone ? ` dv-toast--${options.tone}` : "";
    node.className = `dv-toast${tone}`;

    const head = document.createElement("div");
    head.className = "dv-toast__head";
    const icon = document.createElement("span");
    icon.append(text(options.icon || (options.tone === "error" ? "!" : "✓")));
    const title = document.createElement("span");
    title.append(text(options.title || ""));
    const close = document.createElement("button");
    close.className = "dv-toast__close";
    close.type = "button";
    close.dataset.dvToastClose = "";
    close.setAttribute("aria-label", "Dismiss notification");
    close.append(text("×"));
    head.append(icon, title, close);

    const body = document.createElement("div");
    body.className = "dv-toast__body";
    body.append(text(options.body || ""));
    node.append(head, body);
    host.appendChild(node);
    if (options.timeout !== 0) window.setTimeout(() => node.remove(), Number(options.timeout) || 4600);
    return node;
  };

  DV.openDialog = function openDialog(id, values = {}) {
    const backdrop = document.getElementById(id);
    if (!backdrop) return false;
    Object.entries(values).forEach(([name, value]) => {
      if (!/^[A-Za-z0-9_-]+$/.test(name)) return;
      const field = backdrop.querySelector(`[name="${name}"]`);
      if (field) field.value = String(value ?? "");
    });
    backdrop.classList.add("is-open");
    backdrop.setAttribute("aria-hidden", "false");
    const focus = backdrop.querySelector("[autofocus], input, select, textarea, button");
    if (focus) window.setTimeout(() => focus.focus(), 0);
    return true;
  };

  DV.closeDialog = function closeDialog(node) {
    const backdrop = typeof node === "string" ? document.getElementById(node) : node?.closest?.(".dv-dialog-backdrop") || node;
    if (!backdrop?.classList?.contains("dv-dialog-backdrop")) return false;
    backdrop.classList.remove("is-open");
    backdrop.setAttribute("aria-hidden", "true");
    return true;
  };

  function closeTransient() {
    document.querySelectorAll(".dv-dropdown.is-open").forEach((node) => node.classList.remove("is-open"));
    document.querySelectorAll(".dv-menu[data-dv-live]").forEach((node) => node.remove());
  }

  function init() {
    document.querySelectorAll("[data-dv-rain]").forEach((canvas) => DV.rain(canvas));

    document.addEventListener("click", (event) => {
      const toastClose = event.target.closest("[data-dv-toast-close]");
      if (toastClose) {
        toastClose.closest(".dv-toast")?.remove();
        return;
      }

      const dialogTrigger = event.target.closest("[data-dv-dialog]");
      if (dialogTrigger) {
        DV.openDialog(dialogTrigger.dataset.dvDialog);
        return;
      }
      if (event.target.closest("[data-dv-close]") || event.target.classList.contains("dv-dialog-backdrop")) {
        DV.closeDialog(event.target);
        return;
      }

      const toggle = event.target.closest(".dv-dropdown__toggle");
      if (toggle) {
        const dropdown = toggle.closest("[data-dv-dropdown], .dv-dropdown");
        document.querySelectorAll(".dv-dropdown.is-open").forEach((node) => {
          if (node !== dropdown) node.classList.remove("is-open");
        });
        dropdown?.classList.toggle("is-open");
        event.stopPropagation();
        return;
      }

      const item = event.target.closest(".dv-dropdown__item");
      if (item) {
        const dropdown = item.closest(".dv-dropdown");
        dropdown?.querySelectorAll(".dv-dropdown__item").forEach((node) => node.classList.remove("is-active"));
        item.classList.add("is-active");
        const label = dropdown?.querySelector("[data-dv-dropdown-label]");
        if (label) label.textContent = item.textContent.trim();
        dropdown?.classList.remove("is-open");
        dropdown?.dispatchEvent(new CustomEvent("dv:select", {bubbles: true, detail: {value: item.dataset.value ?? item.textContent.trim()}}));
        return;
      }

      const tab = event.target.closest(".dv-tab");
      const tabBox = tab?.closest("[data-dv-tabs]");
      if (tab && tabBox) {
        tabBox.querySelectorAll(".dv-tab").forEach((node) => node.classList.remove("is-active"));
        tab.classList.add("is-active");
        const selector = tab.dataset.dvPanel;
        const scope = tabBox.dataset.dvPanels ? document.querySelector(tabBox.dataset.dvPanels) : tabBox.parentElement;
        scope?.querySelectorAll("[data-dv-panel-content]").forEach((panel) => {
          panel.hidden = panel.dataset.dvPanelContent !== selector;
        });
        return;
      }

      closeTransient();
    });

    document.addEventListener("contextmenu", (event) => {
      const area = event.target.closest("[data-dv-menu]");
      if (!area) return;
      const template = area.querySelector(":scope > .dv-menu:not([data-dv-live])");
      if (!template) return;
      event.preventDefault();
      closeTransient();
      const menu = template.cloneNode(true);
      menu.hidden = false;
      menu.style.display = "block";
      menu.dataset.dvLive = "";
      const bounds = area.getBoundingClientRect();
      if (getComputedStyle(area).position === "static") area.style.position = "relative";
      menu.style.left = `${Math.max(0, Math.min(event.clientX - bounds.left, area.clientWidth - 190))}px`;
      menu.style.top = `${Math.max(0, event.clientY - bounds.top)}px`;
      area.appendChild(menu);
    });

    document.addEventListener("keydown", (event) => {
      if (event.key !== "Escape") return;
      document.querySelectorAll(".dv-dialog-backdrop.is-open").forEach((node) => DV.closeDialog(node));
      closeTransient();
    });
  }

  window.Digitalvapor = DV;
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init, {once: true});
  else init();
}());
