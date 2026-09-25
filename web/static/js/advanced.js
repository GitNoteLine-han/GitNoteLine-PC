/**
 * advanced.js — Advanced settings page logic.
 */

;(function () {
  'use strict'

  // DOM elements
  const warningModal = document.getElementById('warning-modal')
  const btnWarningBack = document.getElementById('btn-warning-back')
  const btnWarningConfirm = document.getElementById('btn-warning-confirm')
  const advancedContent = document.getElementById('advanced-content')
  const syncMode = document.getElementById('sync-mode')
  const conflictMode = document.getElementById('conflict-mode')
  const conflictDesc = document.getElementById('conflict-desc')

  // ── Initialize ───────────────────────────────────────────────

  async function init() {
    // Show warning modal on first visit
    const hasSeenWarning = localStorage.getItem('advanced_warning_seen')

    if (!hasSeenWarning) {
      warningModal.showModal()
    } else {
      showContent()
    }

    // Load saved settings
    await loadSettings()
    setupEventListeners()
  }

  function setupEventListeners() {
    // Warning modal buttons
    btnWarningBack.addEventListener('click', () => {
      window.location.href = '/setting'
    })

    btnWarningConfirm.addEventListener('click', () => {
      localStorage.setItem('advanced_warning_seen', 'true')
      warningModal.close()
      showContent()
    })

    // Sync mode change
    syncMode.addEventListener('change', () => {
      const mode = syncMode.value
      localStorage.setItem('sync_mode', mode)
    })

    // Conflict mode change
    conflictMode.addEventListener('change', () => {
      const mode = conflictMode.value
      localStorage.setItem('conflict_mode', mode)
      updateConflictDesc()
    })
  }

  function showContent() {
    advancedContent.style.opacity = '1'
    advancedContent.style.transition = 'opacity 0.2s ease'
  }

  function updateConflictDesc() {
    const mode = conflictMode.value
    if (mode === 'auto-merge') {
      conflictDesc.textContent = '尝试合并后重新推送'
    } else {
      conflictDesc.textContent = '仅报错，不自动处理'
    }
  }

  // ── Load settings ────────────────────────────────────────────

  async function loadSettings() {
    // Load sync mode
    const savedSyncMode = localStorage.getItem('sync_mode') || 'auto'
    syncMode.value = savedSyncMode

    // Load conflict mode
    const savedConflictMode = localStorage.getItem('conflict_mode') || 'auto-merge'
    conflictMode.value = savedConflictMode
    updateConflictDesc()
  }

  // ── Start ────────────────────────────────────────────────────

  init()
})()
