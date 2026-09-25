/**
 * init-2-3.js — Link existing local repository.
 */

;(function () {
  'use strict'

  const form = document.getElementById('form-step2-3')
  const localPathField = document.getElementById('field-local-path')
  const btnCheck = document.getElementById('btn-check')
  const checkText = document.getElementById('check-text')
  const checkSpinner = document.getElementById('check-spinner')
  const repoInfo = document.getElementById('repo-info')
  const repoStatus = document.getElementById('repo-status')
  const remoteInfoRow = document.getElementById('remote-info-row')
  const remoteUrl = document.getElementById('remote-url')
  const credentialSection = document.getElementById('credential-section')
  const credentialNameField = document.getElementById('field-credential-name')
  const credentialSecretField = document.getElementById('field-credential-secret')
  const githubWarning = document.getElementById('github-warning')
  const errorEl = document.getElementById('form-error')
  const submitBtn = document.getElementById('btn-submit')
  const btnText = document.getElementById('btn-text')
  const spinner = document.getElementById('btn-spinner')

  let hasRemote = false
  let remoteHost = ''

  // ── Check repo ───────────────────────────────────────────────

  btnCheck.addEventListener('click', async () => {
    const localPath = localPathField.value.trim()
    errorEl.classList.add('hidden')

    if (!localPath) {
      showError('请输入本地仓库路径')
      localPathField.focus()
      return
    }

    setChecking(true)

    try {
      const res = await fetch('/api/init/step2/3/check', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ local_path: localPath }),
      })
      const data = await res.json()

      setChecking(false)

      if (!data.ok) {
        showError(data.error || '检查失败')
        repoInfo.classList.add('hidden')
        credentialSection.classList.add('hidden')
        submitBtn.classList.add('hidden')
        return
      }

      // Show repo info
      repoInfo.classList.remove('hidden')
      repoStatus.textContent = '✓ 有效的 Git 仓库'
      repoStatus.style.color = '#16a34a'

      hasRemote = data.has_remote || false

      if (hasRemote) {
        remoteInfoRow.classList.remove('hidden')
        remoteUrl.textContent = data.remote_url || ''
        
        // Extract host for GitHub warning
        try {
          const parsed = new URL(data.remote_url)
          remoteHost = parsed.hostname
        } catch (_e) {
          remoteHost = ''
        }

        // Show credential section
        credentialSection.classList.remove('hidden')
      } else {
        remoteInfoRow.classList.add('hidden')
        credentialSection.classList.add('hidden')
      }

      // Show submit button
      submitBtn.classList.remove('hidden')

    } catch (_err) {
      setChecking(false)
      showError('网络错误，请重试')
      repoInfo.classList.add('hidden')
      credentialSection.classList.add('hidden')
      submitBtn.classList.add('hidden')
    }
  })

  // ── Credential type change ───────────────────────────────────

  document.querySelectorAll('input[name="credential-type"]').forEach(radio => {
    radio.addEventListener('change', updateWarning)
  })

  function updateWarning() {
    const isGitHub = remoteHost.toLowerCase().includes('github.com')
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

    const localPath = localPathField.value.trim()
    const credentialName = credentialNameField.value.trim()
    const credentialType = document.querySelector('input[name="credential-type"]:checked')?.value || 'fine_grained'
    const credentialSecret = credentialSecretField.value

    errorEl.classList.add('hidden')

    // If has remote, credentials are required
    if (hasRemote) {
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
    }

    setLoading(true)

    try {
      const body = { local_path: localPath }
      
      if (hasRemote) {
        body.credential_name = credentialName
        body.credential_type = credentialType
        body.credential_secret = credentialSecret
      }

      const res = await fetch('/api/init/step2/3', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      })
      const data = await res.json()

      if (!data.ok) {
        showError(data.error || '关联失败')
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

  function setChecking(checking) {
    btnCheck.disabled = checking
    checkText.classList.toggle('hidden', checking)
    checkSpinner.classList.toggle('hidden', !checking)
  }

  function setLoading(loading) {
    submitBtn.disabled = loading
    btnText.classList.toggle('hidden', loading)
    spinner.classList.toggle('hidden', !loading)
  }
})()
