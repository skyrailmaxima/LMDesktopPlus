/* LMDesktopPlus tile framework — reusable widget registry + layout resolver.
 *
 * Scenes register tiles (each with one or more named "views") and render them
 * through renderTiles(). Per-scene layout (order / hidden / per-tile view) is
 * stored under settings.customization.layouts.<scene> and resolved here so a
 * saved layout survives reloads. Reordering is button-based (move earlier /
 * later) — no drag library, keeping the frontend framework-free and testable.
 *
 * Like store.js, the HTML-emitting helpers reference a few app.js globals
 * (esc / clamp / corners) at call time; the pure logic (resolveLayout /
 * currentOrder / computeReorder) has no such dependency and is unit-tested.
 */
(function (global) {
  "use strict";

  const registry = new Map(); // tileId -> definition
  const sceneOrder = [];      // registration order (stable fallback ordering)

  /**
   * Register a tile.
   * def = {
   *   id: string (slug),
   *   scene: string,
   *   title: string,
   *   accent?: boolean,
   *   default?: viewId,
   *   views: [{ id: slug, label: string, render: (ctx) => htmlString }]
   * }
   */
  function register(def) {
    if (!def || !def.id || !def.scene || !Array.isArray(def.views) || !def.views.length) {
      throw new Error("LMDPTiles.register requires {id, scene, views:[...]}");
    }
    if (!registry.has(def.id)) sceneOrder.push(def.id);
    registry.set(def.id, def);
    return def;
  }

  function reset() {
    registry.clear();
    sceneOrder.length = 0;
  }

  function tilesForScene(scene) {
    return sceneOrder.map((id) => registry.get(id)).filter((t) => t && t.scene === scene);
  }

  function viewIds(tile) {
    return tile.views.map((v) => v.id);
  }

  function defaultViewId(tile) {
    return tile.default && viewIds(tile).includes(tile.default) ? tile.default : tile.views[0].id;
  }

  // Resolve a saved layout into ordered render entries. Unknown ids in the
  // saved order/hidden/views are ignored; newly registered tiles append in
  // registration order so upgrades never hide new widgets.
  function resolveLayout(scene, layout) {
    const cfg = layout && typeof layout === "object" ? layout : {};
    const registered = tilesForScene(scene);
    const byId = new Map(registered.map((t) => [t.id, t]));
    const hidden = new Set(Array.isArray(cfg.hidden) ? cfg.hidden : []);
    const views = cfg.views && typeof cfg.views === "object" ? cfg.views : {};
    const savedOrder = Array.isArray(cfg.order) ? cfg.order : [];

    const ordered = [];
    savedOrder.forEach((id) => { if (byId.has(id) && !ordered.includes(id)) ordered.push(id); });
    registered.forEach((t) => { if (!ordered.includes(t.id)) ordered.push(t.id); });

    return ordered.map((id, index) => {
      const tile = byId.get(id);
      const requested = views[id];
      const viewId = viewIds(tile).includes(requested) ? requested : defaultViewId(tile);
      return { tile, viewId, hidden: hidden.has(id), index };
    });
  }

  function currentOrder(scene, layout) {
    return resolveLayout(scene, layout).map((e) => e.tile.id);
  }

  // Swap a tile one slot earlier ("up") or later ("down"); returns a new order
  // array (no-op at the edges).
  function computeReorder(order, id, direction) {
    const list = Array.isArray(order) ? order.slice() : [];
    const i = list.indexOf(id);
    if (i < 0) return list;
    const j = direction === "up" ? i - 1 : direction === "down" ? i + 1 : i;
    if (j < 0 || j >= list.length) return list;
    const tmp = list[i];
    list[i] = list[j];
    list[j] = tmp;
    return list;
  }

  // Toggle membership of an id in a list; returns a new array.
  function toggleInList(list, id) {
    const arr = Array.isArray(list) ? list.slice() : [];
    const i = arr.indexOf(id);
    if (i >= 0) arr.splice(i, 1);
    else arr.push(id);
    return arr;
  }

  // ---- HTML rendering (references app.js globals esc / corners at call time) -

  function renderTile(entry, ctx, opts) {
    const { tile, viewId, hidden } = entry;
    const editing = Boolean(opts.editing);
    if (hidden && !editing) return "";

    const view = tile.views.find((v) => v.id === viewId) || tile.views[0];
    const viewSwitch = tile.views.length > 1
      ? `<div class="dv-seg tile-viewswitch" role="group" aria-label="${esc(tile.title)} view">`
        + tile.views.map((v) => `<button class="dv-seg__opt tile-view${v.id === view.id ? " active" : ""}" data-tile-view="${esc(tile.id)}:${esc(v.id)}" title="${esc(v.label)} view">${esc(v.label)}</button>`).join("")
        + `</div>`
      : "";
    const editControls = editing
      ? `<div class="tile-edit">`
        + `<button class="dv-btn dv-btn--ghost tile-move" type="button" data-tile-move="${esc(tile.id)}:up" title="Move earlier" aria-label="Move ${esc(tile.title)} earlier">◀</button>`
        + `<button class="dv-btn dv-btn--ghost tile-move" type="button" data-tile-move="${esc(tile.id)}:down" title="Move later" aria-label="Move ${esc(tile.title)} later">▶</button>`
        + `<button class="dv-btn dv-btn--ghost tile-hide" type="button" data-tile-hide="${esc(tile.id)}" aria-pressed="${hidden ? "true" : "false"}" title="${hidden ? "Show tile" : "Hide tile"}">${hidden ? "▢" : "▣"}</button>`
        + `</div>`
      : "";
    const controls = (viewSwitch || editControls) ? `<div class="tile-controls">${viewSwitch}${editControls}</div>` : "";
    const accent = tile.accent ? "dv-card--mag" : "";
    const hiddenClass = hidden ? "tile--hidden" : "";
    const body = view.render(ctx);
    return `<section class="panel card dv-panel dv-card tile ${accent} ${hiddenClass}" data-tile-id="${esc(tile.id)}">`
      + corners()
      + `<div class="tile-head"><h2 class="dv-card__title">${esc(tile.title)}</h2>${controls}</div>`
      + `<div class="tile-body">${body}</div>`
      + `</section>`;
  }

  // renderTiles(scene, ctx, opts)
  //   ctx     : passed unchanged to each view's render(ctx)
  //   opts    : { layout, editing, gridClass }
  function renderTiles(scene, ctx, opts) {
    const options = opts || {};
    const entries = resolveLayout(scene, options.layout);
    const grid = options.gridClass || "grid";
    const cells = entries.map((e) => renderTile(e, ctx, options)).join("");
    return `<div class="tile-grid ${grid}" data-tile-scene="${esc(scene)}">${cells}</div>`;
  }

  // Header action button that toggles layout edit mode for a scene.
  function editButton(scene, editing) {
    const label = editing ? "DONE" : "EDIT LAYOUT";
    return `<button class="btn dv-btn ${editing ? "dv-btn--primary" : "dv-btn--outline"}" type="button" data-layout-edit="${esc(scene)}" aria-pressed="${editing ? "true" : "false"}">${label}</button>`;
  }

  global.LMDPTiles = {
    register,
    reset,
    tilesForScene,
    viewIds,
    defaultViewId,
    resolveLayout,
    currentOrder,
    computeReorder,
    toggleInList,
    renderTiles,
    renderTile,
    editButton,
    registry,
  };
})(typeof window !== "undefined" ? window : globalThis);
