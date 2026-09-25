/**
 * editor.js — Dual-mode editor (Monaco + TipTap)
 */

;(function () {
  'use strict'

  // State
  let currentMode = null
  let monacoEditor = null
  let notePath = null
  let noteContent = ''
  let isDirty = false

  // DOM elements
  const selectionDialog = document.getElementById('editor-selection-dialog')
  const monacoContainer = document.getElementById('monaco-container')
  const tiptapContainer = document.getElementById('tiptap-container')
  const tiptapEditor = document.getElementById('tiptap-editor')
  const noteTitle = document.getElementById('note-title')
  const btnSave = document.getElementById('btn-save')
  const modeButtons = document.querySelectorAll('.mode-btn')
  const editorOptions = document.querySelectorAll('.editor-option')

  // Initialize
  async function init() {
    // Get note path from URL
    const urlParams = new URLSearchParams(window.location.search)
    notePath = urlParams.get('path')
    
    if (!notePath) {
      alert('错误：未指定笔记路径')
      window.history.back()
      return
    }

    // Load note content
    await loadNote()

    // Check if user has a preference
    const savedMode = localStorage.getItem('editor_mode')
    
    if (savedMode) {
      currentMode = savedMode
      startEditor()
    } else {
      // Show selection dialog
      selectionDialog.classList.remove('hidden')
    }

    // Event listeners
    setupEventListeners()
  }

  // Load note content from server
  async function loadNote() {
    try {
      const res = await fetch(`/api/notes/${encodeURIComponent(notePath)}`)
      const data = await res.json()

      if (!data.ok) {
        alert('加载笔记失败：' + data.error)
        window.history.back()
        return
      }

      noteContent = data.content
      noteTitle.textContent = notePath.split('/').pop().replace('.md', '')
    } catch (err) {
      alert('加载笔记失败：' + err.message)
      window.history.back()
    }
  }

  // Setup event listeners
  function setupEventListeners() {
    // Editor selection
    editorOptions.forEach(option => {
      option.addEventListener('click', () => {
        const mode = option.dataset.mode
        currentMode = mode
        localStorage.setItem('editor_mode', mode)
        selectionDialog.classList.add('hidden')
        startEditor()
      })
    })

    // Mode toggle buttons
    modeButtons.forEach(btn => {
      btn.addEventListener('click', () => {
        const mode = btn.dataset.mode
        if (mode !== currentMode) {
          switchMode(mode)
        }
      })
    })

    // Save button
    btnSave.addEventListener('click', saveNote)

    // Track changes
    tiptapEditor.addEventListener('input', () => {
      isDirty = true
    })

    // Warn before leaving if unsaved
    window.addEventListener('beforeunload', (e) => {
      if (isDirty) {
        e.preventDefault()
        e.returnValue = ''
      }
    })
  }

  // Start the selected editor
  function startEditor() {
    // Update mode buttons
    modeButtons.forEach(btn => {
      btn.classList.toggle('active', btn.dataset.mode === currentMode)
    })

    if (currentMode === 'monaco') {
      startMonaco()
    } else {
      startTipTap()
    }
  }

  // Start Monaco Editor
  function startMonaco() {
    tiptapContainer.classList.add('hidden')
    monacoContainer.classList.remove('hidden')

    if (!monacoEditor) {
      // Initialize Monaco with local path
      require.config({
        paths: {
          'vs': '/lib/monaco-editor/min/vs'
        }
      })

      require(['vs/editor/editor.main'], () => {
        monacoEditor = monaco.editor.create(monacoContainer, {
          value: noteContent,
          language: 'markdown',
          theme: 'vs',
          automaticLayout: true,
          fontSize: 14,
          minimap: { enabled: false },
          scrollBeyondLastLine: false,
          wordWrap: 'on'
        })

        monacoEditor.onDidChangeModelContent(() => {
          isDirty = true
        })
      })
    } else {
      // Update content
      monacoEditor.setValue(noteContent)
    }
  }

  // Start TipTap Editor
  function startTipTap() {
    monacoContainer.classList.add('hidden')
    tiptapContainer.classList.remove('hidden')

    // Convert Markdown to HTML
    const htmlContent = marked.parse(noteContent)
    tiptapEditor.innerHTML = htmlContent
  }

  // Switch between modes
  function switchMode(newMode) {
    // Get current content
    let content = ''
    
    if (currentMode === 'monaco' && monacoEditor) {
      content = monacoEditor.getValue()
    } else if (currentMode === 'tiptap') {
      // Convert HTML to Markdown
      const turndownService = new TurndownService()
      content = turndownService.turndown(tiptapEditor.innerHTML)
    }

    // Update mode
    currentMode = newMode
    localStorage.setItem('editor_mode', newMode)
    noteContent = content

    // Update UI
    modeButtons.forEach(btn => {
      btn.classList.toggle('active', btn.dataset.mode === newMode)
    })

    // Start new editor
    if (newMode === 'monaco') {
      startMonaco()
    } else {
      startTipTap()
    }
  }

  // Save note
  async function saveNote() {
    // Get current content
    let content = ''
    
    if (currentMode === 'monaco' && monacoEditor) {
      content = monacoEditor.getValue()
    } else if (currentMode === 'tiptap') {
      // Convert HTML to Markdown
      const turndownService = new TurndownService()
      content = turndownService.turndown(tiptapEditor.innerHTML)
    }

    // Get repo_id from URL
    const urlParams = new URLSearchParams(window.location.search)
    const repoId = urlParams.get('repo_id')

    try {
      const res = await fetch(`/api/notes/${encodeURIComponent(notePath)}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ 
          content,
          repo_id: repoId ? parseInt(repoId) : undefined
        }),
      })

      const data = await res.json()

      if (!data.ok) {
        alert('保存失败：' + data.error)
        return
      }

      noteContent = content
      isDirty = false
      alert('保存成功！')
    } catch (err) {
      alert('保存失败：' + err.message)
    }
  }

  // Start
  init()
})()
