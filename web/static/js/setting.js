/**
 * setting.js — Settings page logic.
 */

;(function () {
  'use strict'

  // DOM elements
  const gitName = document.getElementById('git-name')
  const gitEmail = document.getElementById('git-email')
  const editButtons = document.querySelectorAll('.btn-edit-setting')

  // ── Initialize ───────────────────────────────────────────────

  async function init() {
    await loadSettings()
    setupEventListeners()
  }

  function setupEventListeners() {
    // Edit buttons
    editButtons.forEach(btn => {
      btn.addEventListener('click', () => {
        const field = btn.dataset.field
        const currentValue = field === 'git_name' ? gitName.textContent : gitEmail.textContent
        const newValue = prompt(`请输入新的${field === 'git_name' ? '用户名' : '邮箱'}:`, currentValue === '未设置' ? '' : currentValue)

        if (newValue !== null && newValue.trim() !== '') {
          updateSetting(field, newValue.trim())
        }
      })
    })
  }

  // ── Update setting ───────────────────────────────────────────

  async function updateSetting(key, value) {
    try {
      const res = await fetch('/api/settings', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ key, value }),
      })

      const data = await res.json()

      if (data.ok) {
        // Update display
        if (key === 'git_name') {
          gitName.textContent = value
        } else if (key === 'git_email') {
          gitEmail.textContent = value
        }
      } else {
        alert('更新失败：' + (data.error || '未知错误'))
      }
    } catch (err) {
      alert('更新失败：' + err.message)
    }
  }

  // ── Load settings ────────────────────────────────────────────

  async function loadSettings() {
    try {
      const res = await fetch('/api/settings')
      const data = await res.json()

      if (data.ok) {
        gitName.textContent = data.git_name || '未设置'
        gitEmail.textContent = data.git_email || '未设置'
      }
    } catch (err) {
      console.error('Failed to load settings:', err)
      gitName.textContent = '加载失败'
      gitEmail.textContent = '加载失败'
    }
  }

  // ── Start ────────────────────────────────────────────────────

  init()
})()
