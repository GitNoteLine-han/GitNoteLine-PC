/**
 * init-2-4.js — Create local-only repository.
 */

;(function () {
  'use strict'

  const form = document.getElementById('form-step2-4')
  const localPathField = document.getElementById('field-local-path')
  const errorEl = document.getElementById('form-error')
  const submitBtn = document.getElementById('btn-submit')
  const btnText = document.getElementById('btn-text')
  const spinner = document.getElementById('btn-spinner')

  // ── Form submit ──────────────────────────────────────────────

  form.addEventListener('submit', async (e) => {
    e.preventDefault()

    const localPath = localPathField.value.trim()

    errorEl.classList.add('hidden')

    if (!localPath) {
      showError('本地路径不能为空')
      localPathField.focus()
      return
    }

    setLoading(true)

    try {
      const res = await fetch('/api/init/step2/4', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          local_path: localPath,
        }),
      })
      const data = await res.json()

      if (!data.ok) {
        showError(data.error || '创建失败')
        setLoading(false)
        return
      }

      // Success — redirect to main page
      window.location.href = '/'
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
