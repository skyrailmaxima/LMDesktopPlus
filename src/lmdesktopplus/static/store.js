"use strict";

/*
 * LMDesktopPlus front-end state layer.
 *
 * Extracted from app.js so the growing UI keeps a clear split:
 *   - store.js  : state containers + diff/render plumbing (this file)
 *   - bindings.js: declarative data-bind table + fn cache
 *   - app.js    : scenes, panels, event wiring
 *
 * These classes are instantiated by app.js (loaded after this file) and their
 * methods reference app.js globals ($ / bindSceneEvents) at call time, which
 * resolve from the shared classic-script global scope.
 */

class AssetMap {
  constructor() {
    this.icons = new Map();
    this.wallpapers = new Map();
    this.revision = null;
    this.initialized = false;
  }

  update(assets={}, revision=null) {
    if (this.initialized && revision !== null && revision === this.revision) return;
    if (this.initialized && revision === null && this.revision === null) return;
    this.icons = new Map(Object.entries(assets.icons || {}));
    this.wallpapers = new Map(Object.entries(assets.wallpapers || {}));
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
    const changedKeys = [];
    const visit = (before, after, path="") => {
      if (Object.is(before, after)) return;
      const beforeObject = before !== null && typeof before === "object";
      const afterObject = after !== null && typeof after === "object";
      if (!beforeObject || !afterObject || Array.isArray(before) !== Array.isArray(after)) {
        changedKeys.push(path);
        return;
      }
      const keys = new Set([...Object.keys(before), ...Object.keys(after)]);
      if (!keys.size) return;
      keys.forEach(key => visit(before[key], after[key], path ? `${path}.${key}` : key));
    };
    visit(previous, current);
    this.lastSnapshot = current;
    if (this.debug && changedKeys.length) console.debug("[LMDesktopPlus] state paths changed:", changedKeys);
    return changedKeys;
  }
}

class DiffRenderer {
  constructor(rootSelector) {
    this.rootSelector = rootSelector;
    this.scene = null;
    this.binders = new Map();
  }

  register(scene, dependencies, patch) {
    this.binders.set(scene, {dependencies, patch});
  }

  mount(scene, markup) {
    $(this.rootSelector).innerHTML = `<div class="scene-shell">${markup}</div>`;
    this.scene = scene;
    bindSceneEvents();
  }

  update(scene, changedPaths) {
    if (scene !== this.scene) return false;
    const binding = this.binders.get(scene);
    if (!binding) return true;
    const relevant = changedPaths.filter(path => binding.dependencies.some(prefix => path === prefix || path.startsWith(`${prefix}.`)));
    if (!relevant.length) return true;
    return binding.patch(relevant) !== false;
  }
}
