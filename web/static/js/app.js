/**
 * app.js — Main application logic.
 * All API calls go through `window.api` (see api-adapter.js).
 */

;(function () {
  'use strict'

  // ── Status check ───────────────────────────────────────────────

  const statusMsg = document.getElementById('status-message')
  if (statusMsg) {
    api
      .hello()
      .then((data) => {
        statusMsg.textContent = `✅ 已连接 — ${data.message}`
        statusMsg.className = 'status-ok'
      })
      .catch((err) => {
        statusMsg.textContent = `❌ 连接失败 — ${err.message}`
        statusMsg.className = 'status-err'
      })
  }

  // ── Hello button ───────────────────────────────────────────────

  const btn = document.getElementById('btn-hello')
  const out = document.getElementById('api-output')

  if (btn && out) {
    btn.addEventListener('click', async () => {
      out.textContent = '请求中…'
      try {
        const data = await api.hello()
        out.textContent = JSON.stringify(data, null, 2)
      } catch (err) {
        out.textContent = `错误: ${err.message}`
      }
    })
  }
})()