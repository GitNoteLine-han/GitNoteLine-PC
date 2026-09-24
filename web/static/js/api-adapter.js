/**
 * api-adapter.js — Unified API bridge for Flask (web) and pywebview (desktop).
 *
 * All application code calls `api.*` instead of raw fetch / pywebview.api.*.
 * The adapter detects the runtime environment once and wires the correct
 * transport automatically.
 *
 * In Flask mode:    api.hello()      → fetch('/api/hello')
 * In pywebview mode: api.hello()      → pywebview.api.hello()
 */

;(function () {
  'use strict'

  const isPywebview = typeof window.pywebview !== 'undefined'

  window.api = {
    /** GET /api/hello → { message } */
    async hello() {
      if (isPywebview) {
        return await pywebview.api.hello()
      }
      const res = await fetch('/api/hello')
      return res.json()
    },
  }
})()