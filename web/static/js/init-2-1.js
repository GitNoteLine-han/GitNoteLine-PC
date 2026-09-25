/**
 * init-2-1.js — Create online repository with credentials.
 */

;(function () {
  'use strict'

  const form = document.getElementById('form-step2-1')
  const remoteUrlField = document.getElementById('field-remote-url')
  const localPathField = document.getElementById('field-local-path')
  const credentialNameField = document.getElementById('field-credential-name')
  const credentialSecretField = document.getElementById('field-credential-secret')
  const hostDisplay = document.getElementById('host-display')
  const hostValue = document.getElementById('host-value')
  const githubWarning = document.getElementById('github-warning')
  const errorEl = document.getElementById('form-error')
  const submitBtn = document.getElementById('btn-submit')
  const btnText = document.getElementById('btn-text')
  const spinner = document.getElementById('btn-spinner')

  let currentHost = ''
  let credentialNameManuallyEdited = false

  // ── Host detection & auto-fill local path ────────────────────

  let defaultPathDebounce = null

  remoteUrlField.addEventListener('input', () => {
    const url = remoteUrlField.value.trim()
    if (!url) {
      hostDisplay.classList.add('hidden')
      currentHost = ''
      updateWarning()
      return
    }

    try {
      const parsed = new URL(url)
      currentHost = parsed.hostname
      hostValue.textContent = currentHost
      hostDisplay.classList.remove('hidden')
      
      // Auto-fill credential name if not manually edited
      if (!credentialNameManuallyEdited) {
        const defaultName = getDefaultCredentialName(currentHost)
        credentialNameField.value = defaultName
      }
    } catch (_e) {
      hostDisplay.classList.add('hidden')
      currentHost = ''
    }
    updateWarning()

    // Auto-fill local path (debounced)
    clearTimeout(defaultPathDebounce)
    defaultPathDebounce = setTimeout(() => {
      fetchDefaultPath(url)
    }, 500)
  })

  // Track if user manually edits credential name
  credentialNameField.addEventListener('input', () => {
    credentialNameManuallyEdited = true
  })

  function getDefaultCredentialName(host) {
    const hostLower = host.toLowerCase()
    if (hostLower.includes('github.com')) {
      return 'GitHub 个人账户'
    } else if (hostLower.includes('gitlab.com')) {
      return 'GitLab 个人账户'
    } else if (hostLower.includes('gitee.com')) {
      return 'Gitee 个人账户'
    } else if (hostLower.includes('coding.net')) {
      return 'Coding 个人账户'
    } else {
      // For other hosts, use the domain name
      return `${host} 账户`
    }
  }

  async function fetchDefaultPath(remoteUrl) {
    try {
      const res = await fetch(`/api/init/step2/1/default-path?remote_url=${encodeURIComponent(remoteUrl)}`)
      const data = await res.json()
      if (data.ok && data.default_path) {
        localPathField.value = data.default_path
      }
    } catch (_err) {
      // Ignore errors, user can still type manually
    }
  }

  // ── Credential type change ───────────────────────────────────

  document.querySelectorAll('input[name="credential-type"]').forEach(radio => {
    radio.addEventListener('change', updateWarning)
  })

  function updateWarning() {
    const isGitHub = currentHost.toLowerCase().includes('github.com')
    const isPassword = document.querySelector('input[name="credential-type"]:checked')?.value === 'password'
    
    if (isGitHub && isPassword) {
      githubWarning.classList.remove('hidden')
    } else {
      githubWarning.classList.add('hidden')
    }
  }

  // ── Form submit ──────────────────────────────────────────────

  form.addEventListener('submit', async (e) => {
    e.preventDefault()

    const remoteUrl = remoteUrlField.value.trim()
    const localPath = localPathField.value.trim()
    const credentialName = credentialNameField.value.trim()
    const credentialType = document.querySelector('input[name="credential-type"]:checked')?.value || 'fine_grained'
    const credentialSecret = credentialSecretField.value

    errorEl.classList.add('hidden')

    if (!localPath) {
      showError('本地路径不能为空')
      localPathField.focus()
      return
    }
    if (!credentialName) {
      showError('凭证名称不能为空')
      credentialNameField.focus()
      return
    }
    if (!credentialSecret) {
      showError('凭证不能为空')
      credentialSecretField.focus()
      return
    }

    setLoading(true)

    try {
      const res = await fetch('/api/init/step2/1', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          remote_url: remoteUrl,
          local_path: localPath,
          credential_name: credentialName,
          credential_type: credentialType,
          credential_secret: credentialSecret,
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
