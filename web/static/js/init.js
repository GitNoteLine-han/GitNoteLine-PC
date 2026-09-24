/**
 * init.js — Step 1 identity setup.
 */

;(function () {
  'use strict'

  const form = document.getElementById('form-step1')
  const nameField = document.getElementById('field-name')
  const emailField = document.getElementById('field-email')
  const gitHint = document.getElementById('git-hint')
  const errorEl = document.getElementById('form-error')
  const submitBtn = document.getElementById('btn-submit')
  const btnText = document.getElementById('btn-text')
  const spinner = document.getElementById('btn-spinner')

  // ── Load prefilled identity ──────────────────────────────────

  ;(async function loadPrefill() {
    try {
      const data = await api.initPrefill()
      nameField.value = data.name || ''
      emailField.value = data.email || ''

      if (data.source === 'git' && data.name && data.email) {
        gitHint.classList.remove('hidden')
      }
    } catch (_err) {
      // Network error — user types manually
    }
  })()

  // ── Form submit ──────────────────────────────────────────────

  form.addEventListener('submit', async (e) => {
    e.preventDefault()

    const name = nameField.value.trim()
    const email = emailField.value.trim()

    errorEl.classList.add('hidden')

    if (!name) {
      showError('用户名不能为空')
      nameField.focus()
      return
    }
    if (!email) {
      showError('邮箱不能为空')
      emailField.focus()
      return
    }
    if (!email.includes('@') || !email.includes('.')) {
      showError('邮箱格式不正确')
      emailField.focus()
      return
    }

    setLoading(true)

    try {
      const res = await fetch('/api/init/step1', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name, email }),
      })
      const data = await res.json()

      if (!data.ok) {
        showError(data.error || '创建失败')
        setLoading(false)
        return
      }

      window.location.href = '/init/2'
    } catch (_err) {
      showError('网络错误，请重试')
      setLoading(false)
    }
  })

  // ── Helpers ──────────────────────────────────────────────────

  function showError(msg) {
    errorEl.textContent = msg
    errorEl.classList.remove('hidden')
  }

  function setLoading(loading) {
    submitBtn.disabled = loading
    btnText.classList.toggle('hidden', loading)
    spinner.classList.toggle('hidden', !loading)
  }
})()