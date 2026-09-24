/**
 * init.js — Step 1 identity setup.
 */

;(function () {
  'use strict'

  const form = document.getElementById('form-step1')
  const nameField = document.getElementById('field-name')
  const emailField = document.getElementById('field-email')
  const errorEl = document.getElementById('form-error')
  const submitBtn = document.getElementById('btn-submit')
  const btnText = document.getElementById('btn-text')
  const spinner = document.getElementById('btn-spinner')

  const gitConfirm = document.getElementById('git-confirm')
  const gitNameEl = document.getElementById('git-name')
  const gitEmailEl = document.getElementById('git-email')
  const btnUseGit = document.getElementById('btn-use-git')
  const btnManual = document.getElementById('btn-manual')

  let currentSource = 'manual'
  let gitData = { name: '', email: '' }

  // ── Load prefilled identity ──────────────────────────────────

  ;(async function loadPrefill() {
    try {
      const data = await api.initPrefill()

      if (data.source === 'git' && data.name && data.email) {
        // Git config detected — show confirm card
        gitData = { name: data.name, email: data.email }
        gitNameEl.textContent = data.name
        gitEmailEl.textContent = data.email
        gitConfirm.classList.remove('hidden')
        form.classList.add('hidden')
      } else {
        // No git config — show form with prefill
        nameField.value = data.name || ''
        emailField.value = data.email || ''
      }
    } catch (_err) {
      // Network error — user types manually
    }
  })()

  // ── Git confirm: "使用" ─────────────────────────────────────

  btnUseGit.addEventListener('click', async () => {
    currentSource = 'git'
    await submitIdentity(gitData.name, gitData.email, 'git')
  })

  // ── Git confirm: "手动填写" ─────────────────────────────────

  btnManual.addEventListener('click', () => {
    gitConfirm.classList.add('hidden')
    form.classList.remove('hidden')
    nameField.value = gitData.name
    emailField.value = gitData.email
    nameField.focus()
  })

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

    await submitIdentity(name, email, 'manual')
  })

  // ── Submit helper ────────────────────────────────────────────

  async function submitIdentity(name, email, source) {
    setLoading(true)

    try {
      const res = await fetch('/api/init/step1', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name, email, source }),
      })
      const data = await res.json()

      if (!data.ok) {
        if (source === 'git') {
          // Git submit failed — fall back to manual form
          gitConfirm.classList.add('hidden')
          form.classList.remove('hidden')
          nameField.value = gitData.name
          emailField.value = gitData.email
          showError(data.error || '提交失败，请手动填写')
        } else {
          showError(data.error || '创建失败')
        }
        setLoading(false)
        return
      }

      window.location.href = '/init/2'
    } catch (_err) {
      if (source === 'git') {
        gitConfirm.classList.add('hidden')
        form.classList.remove('hidden')
        nameField.value = gitData.name
        emailField.value = gitData.email
        showError('网络错误，请手动填写')
      } else {
        showError('网络错误，请重试')
      }
      setLoading(false)
    }
  }

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