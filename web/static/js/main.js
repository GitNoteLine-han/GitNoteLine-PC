/**
 * main.js — Main page logic for note management.
 */

;(function () {
  'use strict'

  // DOM elements
  const repoSelect = document.getElementById('repo-select')
  const notesList = document.getElementById('notes-list')
  const btnNewNote = document.getElementById('btn-new-note')
  const notePlaceholder = document.getElementById('note-placeholder')
  const notePreview = document.getElementById('note-preview')
  const notePreviewTitle = document.getElementById('note-preview-title')
  const notePreviewContent = document.getElementById('note-preview-content')
  const btnEditNote = document.getElementById('btn-edit-note')
  const newNoteDialog = document.getElementById('new-note-dialog')
  const newNoteForm = document.getElementById('new-note-form')
  const noteNameInput = document.getElementById('note-name-input')
  const btnCancelNote = document.getElementById('btn-cancel-note')
  const dialogError = document.getElementById('dialog-error')
  const btnSync = document.getElementById('btn-sync')

  let currentRepo = null
  let currentNotePath = null

  // ── Initialize ───────────────────────────────────────────────

  async function init() {
    await loadRepos()
    await loadNotes()
    setupEventListeners()
    // Auto-pull on startup
    if (currentRepo) {
      syncPull()
    }
  }

  function setupEventListeners() {
    // Edit button → redirect to editor
    btnEditNote.addEventListener('click', () => {
      if (currentNotePath) {
        window.location.href = `/editor?path=${encodeURIComponent(currentNotePath)}&repo_id=${currentRepo}`
      }
    })
  }

  // ── Sync operations ──────────────────────────────────────────

  async function syncPull() {
    if (!currentRepo) return

    setSyncState('syncing')

    try {
      const res = await fetch(`/api/repo/${currentRepo}/pull`, { method: 'POST' })
      const data = await res.json()

      if (data.ok) {
        setSyncState('success')
        // Reload notes after pull
        await loadNotes()
      } else {
        setSyncState('error', data.error)
      }
    } catch (err) {
      setSyncState('error', '网络错误')
    }
  }

  function setSyncState(state, message) {
    if (!btnSync) return

    btnSync.classList.remove('syncing', 'error')

    switch (state) {
      case 'syncing':
        btnSync.classList.add('syncing')
        btnSync.title = '同步中...'
        break
      case 'success':
        btnSync.title = '已同步'
        // Clear success state after 3 seconds
        setTimeout(() => {
          if (btnSync.title === '已同步') {
            btnSync.title = '同步'
          }
        }, 3000)
        break
      case 'error':
        btnSync.classList.add('error')
        btnSync.title = message || '同步失败'
        break
      default:
        btnSync.title = '同步'
    }
  }

  // ── Load repositories ────────────────────────────────────────

  async function loadRepos() {
    try {
      const res = await fetch('/api/repos/list')
      const data = await res.json()

      if (!data.ok || data.repos.length === 0) {
        repoSelect.innerHTML = '<option value="">未配置仓库</option>'
        return
      }

      // Populate repo options
      repoSelect.innerHTML = ''
      data.repos.forEach(repo => {
        const option = document.createElement('option')
        option.value = repo.id
        option.textContent = repo.name
        repoSelect.appendChild(option)
      })

      // Add "create new repo" option
      const createOption = document.createElement('option')
      createOption.value = 'create-new'
      createOption.textContent = '+ 新建笔记仓库'
      repoSelect.appendChild(createOption)

      // Set first repo as current
      currentRepo = data.repos[0].id
      repoSelect.value = currentRepo

      // Listen for repo changes
      repoSelect.addEventListener('change', handleRepoChange)
    } catch (err) {
      console.error('Failed to load repos:', err)
      repoSelect.innerHTML = '<option value="">加载失败</option>'
    }
  }

  function handleRepoChange() {
    const selectedValue = repoSelect.value

    if (selectedValue === 'create-new') {
      // Redirect to init/2
      window.location.href = '/init/2'
    } else {
      // Switch to selected repo
      currentRepo = parseInt(selectedValue)
      loadNotes()
    }
  }

  // ── Load notes list ──────────────────────────────────────────

  async function loadNotes() {
    try {
      const res = await fetch(`/api/notes/list?repo_id=${currentRepo}`)
      const data = await res.json()

      if (!data.ok) {
        console.error('Failed to load notes:', data.error)
        notesList.innerHTML = '<div class="notes-empty">加载失败</div>'
        return
      }

      if (data.notes.length === 0) {
        notesList.innerHTML = '<div class="notes-empty">暂无笔记<br>点击 + 创建第一个笔记</div>'
        return
      }

      // Render notes list
      notesList.innerHTML = ''
      data.notes.forEach(note => {
        const item = document.createElement('div')
        item.className = 'note-item'
        item.dataset.path = note.path

        // Show directory structure if note is in subdirectory
        const displayName = note.name.includes('/')
          ? `<span class="note-dir">${note.name.split('/').slice(0, -1).join('/')}/</span>${note.name.split('/').pop()}`
          : note.name

        item.innerHTML = `<span class="note-name">${displayName}</span>`
        item.addEventListener('click', () => previewNote(note.path))
        notesList.appendChild(item)
      })
    } catch (err) {
      console.error('Failed to load notes:', err)
      notesList.innerHTML = '<div class="notes-empty">加载失败</div>'
    }
  }

  // ── Preview note (read-only) ─────────────────────────────────

  async function previewNote(notePath) {
    // Update selected state in list
    document.querySelectorAll('.note-item').forEach(item => {
      item.classList.toggle('active', item.dataset.path === notePath)
    })

    currentNotePath = notePath

    try {
      const res = await fetch(`/api/notes/${encodeURIComponent(notePath)}`)
      const data = await res.json()

      if (!data.ok) {
        console.error('Failed to load note:', data.error)
        return
      }

      // Show preview, hide placeholder
      notePlaceholder.style.display = 'none'
      notePreview.style.display = 'flex'

      // Set title (filename without .md)
      const title = notePath.split('/').pop().replace(/\.md$/, '')
      notePreviewTitle.textContent = title

      // Rewrite ./ paths to /repo/<repo_id>/ for display
      const displayContent = data.content.replace(
        /\.\//g,
        `/repo/${currentRepo}/`
      )

      // Render Markdown to HTML
      notePreviewContent.innerHTML = marked.parse(displayContent)
    } catch (err) {
      console.error('Failed to preview note:', err)
    }
  }

  // ── New note dialog ──────────────────────────────────────────

  btnNewNote.addEventListener('click', () => {
    noteNameInput.value = ''
    dialogError.textContent = ''
    newNoteDialog.showModal()
    noteNameInput.focus()
  })

  btnCancelNote.addEventListener('click', () => {
    newNoteDialog.close()
  })

  newNoteForm.addEventListener('submit', async (e) => {
    e.preventDefault()

    const noteName = noteNameInput.value.trim()
    if (!noteName) {
      dialogError.textContent = '请输入笔记名称'
      return
    }

    try {
      const res = await fetch('/api/notes', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: noteName,
          content: `# ${noteName.split('/').pop()}\n\n`,
          repo_id: currentRepo,
        }),
      })

      const data = await res.json()

      if (!data.ok) {
        dialogError.textContent = data.error || '创建失败'
        return
      }

      // Close dialog and redirect to editor
      newNoteDialog.close()

      // Build the full path for editor
      const notePath = data.path.endsWith('.md') ? data.path : data.path + '.md'
      window.location.href = `/editor?path=${encodeURIComponent(notePath)}&repo_id=${currentRepo}`
    } catch (err) {
      console.error('Failed to create note:', err)
      dialogError.textContent = '网络错误，请重试'
    }
  })

  // Close dialog on Escape
  newNoteDialog.addEventListener('cancel', () => {
    dialogError.textContent = ''
  })

  // ── Start ────────────────────────────────────────────────────

  init()
})()
