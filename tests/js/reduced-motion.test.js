"use strict";

/*
 * Deterministic, dependency-free check that DV.rain honours
 * prefers-reduced-motion: no requestAnimationFrame loop when reduced motion is
 * requested, a normal animation loop otherwise. Runs digitalvapor.js inside a
 * minimal stubbed DOM using node's vm module (no jsdom required).
 */

const fs = require("fs");
const path = require("path");
const vm = require("vm");
const assert = require("assert");

const SOURCE = path.join(__dirname, "..", "..", "src", "lmdesktopplus", "static", "digitalvapor.js");

function makeContext(mql) {
  const counters = {raf: 0, fillRect: 0, fillText: 0};

  class HTMLCanvasElement {}

  function makeCanvas() {
    const canvas = new HTMLCanvasElement();
    canvas.clientWidth = 800;
    canvas.clientHeight = 600;
    canvas.width = 0;
    canvas.height = 0;
    canvas.dataset = {};
    canvas.getContext = () => ({
      set font(_v) {},
      set fillStyle(_v) {},
      setTransform() {},
      fillRect() { counters.fillRect += 1; },
      fillText() { counters.fillText += 1; },
    });
    return canvas;
  }

  const listeners = {};
  const windowStub = {
    devicePixelRatio: 1,
    innerWidth: 800,
    innerHeight: 600,
    matchMedia: () => mql,
    addEventListener(type, fn) { (listeners[type] = listeners[type] || []).push(fn); },
    removeEventListener() {},
    setTimeout() {},
  };

  const documentStub = {
    readyState: "complete",
    querySelectorAll: () => [],
    querySelector: () => null,
    addEventListener() {},
    createElement: () => ({ classList: { add() {} }, appendChild() {}, setAttribute() {}, append() {} }),
    createTextNode: () => ({}),
    body: { appendChild() {} },
    documentElement: {},
  };

  const sandbox = {
    window: windowStub,
    document: documentStub,
    HTMLCanvasElement,
    requestAnimationFrame: () => { counters.raf += 1; return counters.raf; },
    cancelAnimationFrame: () => {},
    getComputedStyle: () => ({ getPropertyValue: () => "monospace" }),
    console,
  };
  sandbox.globalThis = sandbox;

  vm.createContext(sandbox);
  vm.runInContext(fs.readFileSync(SOURCE, "utf8"), sandbox, { filename: "digitalvapor.js" });

  return { sandbox, counters, makeCanvas };
}

// Case 1: motion allowed -> animation loop starts (requestAnimationFrame used).
{
  const mql = { matches: false, addEventListener() {}, removeEventListener() {} };
  const { sandbox, counters, makeCanvas } = makeContext(mql);
  const DV = sandbox.window.Digitalvapor;
  assert.strictEqual(typeof DV.rain, "function", "DV.rain should be exposed");
  assert.strictEqual(DV.prefersReducedMotion(), false, "prefersReducedMotion false when matches=false");
  DV.rain(makeCanvas());
  assert.ok(counters.raf >= 1, `motion-allowed rain should schedule frames (got ${counters.raf})`);
  console.log(`ok  motion allowed -> ${counters.raf} animation frame(s) scheduled`);
}

// Case 2: reduced motion -> no animation loop, but a static frame is painted.
{
  const mql = { matches: true, addEventListener() {}, removeEventListener() {} };
  const { sandbox, counters, makeCanvas } = makeContext(mql);
  const DV = sandbox.window.Digitalvapor;
  assert.strictEqual(DV.prefersReducedMotion(), true, "prefersReducedMotion true when matches=true");
  DV.rain(makeCanvas());
  assert.strictEqual(counters.raf, 0, `reduced-motion rain must not schedule frames (got ${counters.raf})`);
  assert.ok(counters.fillRect >= 1, "reduced-motion rain should still paint one static frame");
  console.log(`ok  reduced motion -> 0 animation frames, static frame painted (${counters.fillText} glyphs)`);
}

// Case 3: a live change to the media query stops the running loop.
{
  const handlers = [];
  const mql = {
    matches: false,
    addEventListener(_type, fn) { handlers.push(fn); },
    removeEventListener() {},
  };
  const { sandbox, counters, makeCanvas } = makeContext(mql);
  const DV = sandbox.window.Digitalvapor;
  DV.rain(makeCanvas());
  const before = counters.raf;
  assert.ok(before >= 1, "loop should be running before the change");
  assert.ok(handlers.length >= 1, "rain should subscribe to media-query changes");
  mql.matches = true;
  const framesBefore = counters.raf;
  handlers.forEach((fn) => fn());
  assert.strictEqual(counters.raf, framesBefore, "flipping to reduced motion must not schedule new frames");
  console.log("ok  live reduced-motion toggle stops the animation loop");
}

console.log("reduced-motion tests OK");
