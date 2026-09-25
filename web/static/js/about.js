/**
 * about.js — About page logic.
 */

;(function () {
  'use strict'

  const buildNotice = document.getElementById('build-notice')

  async function init() {
    try {
      const res = await fetch('/api/build-info')
      const data = await res.json()
      if (data.ok && data.content) {
        buildNotice.textContent = data.content.trim()
      }
    } catch (err) {
      buildNotice.textContent = '加载失败'
    }
  }

  init()
})()
