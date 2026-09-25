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
  const noteContent = document.getElementById('note-content')
  const noteText = document.getElementById('note-text')
  const newNoteDialog = document.getElementById('new-note-dialog')
  const newNoteForm = document.getElementById('new-note-form')
  const noteNameInput = document.getElementById('note-name-input')
  const btnCancelNote = document.getElementById('btn-cancel-note')
  const dialogError = document.getElementById('dialog-error')

  let currentRepo = null
  let currentNote = null

  // ── Initialize ───────────────────────────────────────────────

  async function init() {
    await loadRepo()
    await loadNotes()
  }

  // ── Load repository ──────────────────────────────────────────

  async function loadRepo() {
    try {
      // For now, we just show a placeholder since we only support one repo
      // In the future, this will load all repos from the database
      repoSelect.innerHTML = '<option value="default">我的笔记仓库</option>'
      currentRepo = 'default'
    } catch (err) {
      console.error('Failed to load repo:', err)
    }
  }

  // ── Load notes list ──────────────────────────────────────────

  async function loadNotes() {
    try {
      const res = await fetch('/api/notes/list')
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
        item.addEventListener('click', () => loadNote(note.path))
        notesList.appendChild(item)
      })
    } catch (err) {
      console.error('Failed to load notes:', err)
      notesList.innerHTML = '<div class="notes-empty">加载失败</div>'
    }
  }

  // ── Load note content ────────────────────────────────────────

  async function loadNote(notePath) {
    try {
      // Update active state in list
      document.querySelectorAll('.note-item').forEach(item => {
        item.classList.toggle('active', item.dataset.path === notePath)
      })

      const res = await fetch(`/api/notes/${encodeURIComponent(notePath)}`)
      const data = await res.json()

      if (!data.ok) {
        console.error('Failed to load note:', data.error)
        return
      }

      currentNote = notePath
      notePlaceholder.style.display = 'none'
      noteContent.style.display = 'block'
      noteText.textContent = data.content
    } catch (err) {
      console.error('Failed to load note:', err)
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
        }),
      })

      const data = await res.json()

      if (!data.ok) {
        dialogError.textContent = data.error || '创建失败'
        return
      }

      // Close dialog and reload notes list
      newNoteDialog.close()
      await loadNotes()

      // Auto-select the new note
      loadNote(data.path)
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
