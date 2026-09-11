"use strict";

/*
 * Deterministic, dependency-free check of the tile framework (static/tiles.js).
 * tiles.js is an IIFE that attaches LMDPTiles to the global object and whose
 * pure logic (register / resolveLayout / currentOrder / computeReorder /
 * toggleInList) has no DOM or app.js dependency, so we load it into an isolated
 * vm context and exercise the registry + layout resolver directly. The
 * HTML-emitting renderTiles path is also smoke-tested with stubbed esc/corners.
 */

const fs = require("fs");
const path = require("path");
const vm = require("vm");
const assert = require("assert");

const SOURCE = path.join(__dirname, "..", "..", "src", "lmdesktopplus", "static", "tiles.js");

// tiles.js runs in a separate vm realm, so arrays it returns have a different
// Array.prototype than this module. Normalize through JSON before comparing so
// deepStrictEqual checks values, not cross-realm prototype identity.
const sameList = (actual, expected, msg) =>
  assert.deepStrictEqual(JSON.parse(JSON.stringify(actual)), expected, msg);

function loadTiles() {
  const sandbox = { console };
  sandbox.window = sandbox;
  // Stubs used only by the HTML rendering helpers.
  sandbox.esc = (v) => String(v == null ? "" : v);
  sandbox.corners = () => "<corners/>";
  vm.createContext(sandbox);
  vm.runInContext(fs.readFileSync(SOURCE, "utf8"), sandbox, { filename: "tiles.js" });
  return sandbox.LMDPTiles;
}

function registerSample(T) {
  T.reset();
  const view = (id, label) => ({ id, label, render: (ctx) => `<${id}:${ctx ? ctx.v : ""}>` });
  T.register({ id: "cpu", scene: "desktop", title: "CPU", default: "kpi", views: [view("kpi", "Number"), view("sparkline", "Spark"), view("gauge", "Gauge")] });
  T.register({ id: "memory", scene: "desktop", title: "Memory", views: [view("kpi", "Number"), view("gauge", "Gauge")] });
  T.register({ id: "uptime", scene: "desktop", title: "Uptime", views: [view("kpi", "Number")] });
  T.register({ id: "netchart", scene: "monitor", title: "Network", views: [view("chart", "Chart")] });
}

// Case 1: registration + scene filtering + registration-order fallback.
{
  const T = loadTiles();
  registerSample(T);
  sameList(T.tilesForScene("desktop").map((t) => t.id), ["cpu", "memory", "uptime"], "desktop tiles in registration order");
  sameList(T.tilesForScene("monitor").map((t) => t.id), ["netchart"], "monitor tiles filtered by scene");
  sameList(T.currentOrder("desktop", {}), ["cpu", "memory", "uptime"], "empty layout -> registration order");
  console.log("ok  register + scene filter + default order");
}

// Case 2: default view resolution (explicit default, first-view fallback, invalid saved view).
{
  const T = loadTiles();
  registerSample(T);
  const entries = T.resolveLayout("desktop", { views: { cpu: "sparkline", memory: "bogus" } });
  const byId = Object.fromEntries(entries.map((e) => [e.tile.id, e.viewId]));
  assert.strictEqual(byId.cpu, "sparkline", "saved valid view honored");
  assert.strictEqual(byId.memory, "kpi", "invalid saved view falls back to first view");
  assert.strictEqual(byId.uptime, "kpi", "no saved view -> default/first view");
  console.log("ok  view resolution (valid / invalid / default)");
}

// Case 3: saved order applied, unknown ids dropped, new tiles appended.
{
  const T = loadTiles();
  registerSample(T);
  const order = T.currentOrder("desktop", { order: ["uptime", "ghost", "cpu"] });
  sameList(order, ["uptime", "cpu", "memory"], "saved order first (ghost dropped), unlisted appended");
  console.log("ok  saved order honored, unknown dropped, new appended");
}

// Case 4: hidden set surfaced in entries.
{
  const T = loadTiles();
  registerSample(T);
  const entries = T.resolveLayout("desktop", { hidden: ["memory"] });
  const hidden = entries.filter((e) => e.hidden).map((e) => e.tile.id);
  sameList(hidden, ["memory"], "hidden ids marked");
  console.log("ok  hidden ids surfaced");
}

// Case 5: computeReorder swaps within bounds and no-ops at edges.
{
  const T = loadTiles();
  sameList(T.computeReorder(["a", "b", "c"], "b", "up"), ["b", "a", "c"], "move up swaps earlier");
  sameList(T.computeReorder(["a", "b", "c"], "b", "down"), ["a", "c", "b"], "move down swaps later");
  sameList(T.computeReorder(["a", "b", "c"], "a", "up"), ["a", "b", "c"], "move up at head is a no-op");
  sameList(T.computeReorder(["a", "b", "c"], "c", "down"), ["a", "b", "c"], "move down at tail is a no-op");
  sameList(T.computeReorder(["a", "b"], "z", "up"), ["a", "b"], "unknown id is a no-op");
  console.log("ok  computeReorder swap + edge no-ops");
}

// Case 6: toggleInList adds then removes.
{
  const T = loadTiles();
  sameList(T.toggleInList([], "x"), ["x"], "toggle adds when absent");
  sameList(T.toggleInList(["x", "y"], "x"), ["y"], "toggle removes when present");
  console.log("ok  toggleInList add/remove");
}

// Case 7: renderTiles emits per-tile markup, hides tiles outside edit mode,
// shows hidden + move/hide controls in edit mode, and marks the active view.
{
  const T = loadTiles();
  registerSample(T);
  const normal = T.renderTiles("desktop", { v: "x" }, { layout: { hidden: ["memory"], views: { cpu: "gauge" } }, gridClass: "grid four" });
  assert.ok(normal.includes('data-tile-scene="desktop"'), "grid carries scene marker");
  assert.ok(normal.includes('data-tile-id="cpu"'), "cpu tile rendered");
  assert.ok(!normal.includes('data-tile-id="memory"'), "hidden tile omitted outside edit mode");
  assert.ok(normal.includes('data-tile-view="cpu:gauge"'), "view switch buttons present");
  assert.ok(!normal.includes("data-tile-move"), "no edit controls outside edit mode");

  const editing = T.renderTiles("desktop", { v: "x" }, { layout: { hidden: ["memory"] }, editing: true });
  assert.ok(editing.includes('data-tile-id="memory"'), "hidden tile shown in edit mode");
  assert.ok(editing.includes('data-tile-move="cpu:up"'), "reorder controls present in edit mode");
  assert.ok(editing.includes('data-tile-hide="memory"'), "hide toggle present in edit mode");
  console.log("ok  renderTiles markup + edit-mode controls");
}

console.log("tiles tests OK");
