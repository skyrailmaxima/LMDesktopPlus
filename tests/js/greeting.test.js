"use strict";

/*
 * Deterministic, dependency-free check of the editable-greeting selection logic
 * in static/app.js (resolveGreeting). app.js is a global-heavy, non-modular
 * boot script (it calls poll()/bindGlobal() at load), so instead of executing
 * the whole file we extract the pure resolveGreeting() function by brace
 * matching and run it in an isolated vm context with injected dependencies
 * (customization(), greetingIndex, Math, Date). This keeps the test hermetic
 * and free of a DOM/jsdom.
 */

const fs = require("fs");
const path = require("path");
const vm = require("vm");
const assert = require("assert");

const APP = path.join(__dirname, "..", "..", "src", "lmdesktopplus", "static", "app.js");
const source = fs.readFileSync(APP, "utf8");

// Extract a top-level `function name(...) { ... }` by matching braces. The
// targeted function bodies contain no braces inside string/template literals,
// so a plain depth counter is sufficient and robust here.
function extractFunction(name) {
  const start = source.indexOf(`function ${name}(`);
  assert.ok(start >= 0, `could not find function ${name} in app.js`);
  const open = source.indexOf("{", start);
  let depth = 0;
  for (let i = open; i < source.length; i += 1) {
    const c = source[i];
    if (c === "{") depth += 1;
    else if (c === "}") {
      depth -= 1;
      if (depth === 0) return source.slice(start, i + 1);
    }
  }
  throw new Error(`unbalanced braces extracting ${name}`);
}

const resolveGreetingSrc = extractFunction("resolveGreeting");

// Build an isolated context that provides the free variables resolveGreeting
// closes over in app.js (customization, greetingIndex) plus deterministic
// Math/Date so random/time modes are testable.
function makeResolver({ greeting, greetingIndex = 0, random = 0, hour = 12 }) {
  const fakeMath = Object.create(Math);
  fakeMath.random = () => random;
  function FakeDate() { return { getHours: () => hour }; }
  const sandbox = {
    customization: () => ({ greeting }),
    greetingIndex,
    Math: fakeMath,
    Date: FakeDate,
    Array,
    console,
  };
  vm.createContext(sandbox);
  vm.runInContext(`${resolveGreetingSrc}\nglobalThis.__resolve = resolveGreeting;`, sandbox, {
    filename: "app.js#resolveGreeting",
  });
  return { call: () => sandbox.__resolve(), sandbox };
}

// Case 1: default / static mode -> first message (preserves today's look).
{
  const { call } = makeResolver({ greeting: { messages: ["VAPOR//MATRIX"], mode: "static" } });
  assert.strictEqual(call(), "VAPOR//MATRIX", "static mode should return the first message");
  console.log("ok  static mode -> first message");
}

// Case 2: missing/empty greeting -> falls back to VAPOR//MATRIX.
{
  assert.strictEqual(makeResolver({ greeting: undefined }).call(), "VAPOR//MATRIX", "no greeting falls back");
  assert.strictEqual(makeResolver({ greeting: { messages: [], mode: "static" } }).call(), "VAPOR//MATRIX", "empty messages falls back");
  console.log("ok  empty/absent greeting -> VAPOR//MATRIX fallback");
}

// Case 3: sequential mode indexes by greetingIndex modulo length.
{
  const msgs = ["ALPHA", "BETA", "GAMMA"];
  assert.strictEqual(makeResolver({ greeting: { messages: msgs, mode: "sequential" }, greetingIndex: 0 }).call(), "ALPHA");
  assert.strictEqual(makeResolver({ greeting: { messages: msgs, mode: "sequential" }, greetingIndex: 1 }).call(), "BETA");
  assert.strictEqual(makeResolver({ greeting: { messages: msgs, mode: "sequential" }, greetingIndex: 4 }).call(), "BETA", "index wraps modulo length");
  console.log("ok  sequential mode -> greetingIndex modulo length");
}

// Case 4: random mode uses Math.random over the message list.
{
  const msgs = ["ONE", "TWO", "THREE", "FOUR"];
  // random=0 -> floor(0*4)=0; random just below 1 -> last item.
  assert.strictEqual(makeResolver({ greeting: { messages: msgs, mode: "random" }, random: 0 }).call(), "ONE");
  assert.strictEqual(makeResolver({ greeting: { messages: msgs, mode: "random" }, random: 0.9999 }).call(), "FOUR");
  console.log("ok  random mode -> Math.random bucket");
}

// Case 5: time mode buckets the hour into night/morning/afternoon/evening.
{
  const msgs = ["NIGHT", "MORNING", "AFTERNOON", "EVENING"];
  const g = { messages: msgs, mode: "time" };
  assert.strictEqual(makeResolver({ greeting: g, hour: 2 }).call(), "NIGHT", "hour<5 -> bucket 0");
  assert.strictEqual(makeResolver({ greeting: g, hour: 9 }).call(), "MORNING", "hour<12 -> bucket 1");
  assert.strictEqual(makeResolver({ greeting: g, hour: 15 }).call(), "AFTERNOON", "hour<18 -> bucket 2");
  assert.strictEqual(makeResolver({ greeting: g, hour: 22 }).call(), "EVENING", "hour>=18 -> bucket 3");
  console.log("ok  time mode -> hour buckets");
}

// Case 6: renderPersonalizeSettings executes end-to-end. This guards against
// ReferenceErrors from constants that live only in config.py (e.g. the
// GREETING_MODES regression, which silently blanked the Personalize tab). We
// pull the REAL GREETING_MODES declaration out of app.js so an absent/renamed
// constant makes this test throw, and stub only generic utilities.
{
  const modesMatch = source.match(/const GREETING_MODES\s*=\s*\[[^\]]*\];/);
  assert.ok(modesMatch, "GREETING_MODES must be declared in app.js");
  const renderSrc = extractFunction("renderPersonalizeSettings");

  const sandbox = {
    // Real constant under test, injected verbatim from app.js below.
    customization: () => ({
      greeting: { messages: ["ALPHA", "BETA"], mode: "sequential", rotate_seconds: 30 },
      text: { "monitor.subtitle": "CUSTOM SUB" },
    }),
    DEFAULT_TITLES: { desktop: "VAPOR//MATRIX", monitor: "SYSTEM MONITOR" },
    defaultTitleFor: (id) => ({ desktop: "VAPOR//MATRIX", monitor: "SYSTEM MONITOR" }[id] || ""),
    control: (label, note, widget) => `<row>${label}:${note}:${widget}</row>`,
    esc: (s) => String(s),
    clamp: (n, lo, hi) => Math.max(lo, Math.min(hi, n)),
    Object,
    Array,
    Number,
    console,
  };
  vm.createContext(sandbox);
  vm.runInContext(
    `${modesMatch[0]}\n${renderSrc}\nglobalThis.__render = renderPersonalizeSettings;`,
    sandbox,
    { filename: "app.js#renderPersonalizeSettings" }
  );
  const html = sandbox.__render();
  assert.ok(/data-greeting-messages/.test(html), "renders the greeting textarea");
  assert.ok(/ALPHA\nBETA/.test(html), "greeting textarea seeded with saved messages");
  assert.ok(/active[^>]*data-greeting-mode="sequential"/.test(html), "active mode reflects saved mode");
  assert.ok(/data-text-key="monitor.subtitle"/.test(html), "renders per-scene subtitle input");
  assert.ok(/CUSTOM SUB/.test(html), "subtitle input seeded with saved override");
  console.log("ok  renderPersonalizeSettings executes (GREETING_MODES defined)");
}

console.log("greeting tests OK");
