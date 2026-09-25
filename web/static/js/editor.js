/**
 * editor.js — Dual-mode editor (Monaco + TipTap)
 */

;(function () {
  'use strict'

  // State
  let currentMode = null
  let monacoEditor = null
  let quillEditor = null
  let notePath = null
  let noteContent = ''
  let isDirty = false
  let currentRepoId = null
  let stagedImages = [] // Array of {file, preview, tempPath}

  // DOM elements
  const selectionDialog = document.getElementById('editor-selection-dialog')
  const monacoMode = document.getElementById('monaco-mode')
  const tiptapMode = document.getElementById('tiptap-mode')
  const monacoContainer = document.getElementById('monaco-container')
  const quillEditorContainer = document.getElementById('quill-editor')
  const previewContent = document.getElementById('preview-content')
  const noteTitle = document.getElementById('note-title')
  const btnSave = document.getElementById('btn-save')
  const modeButtons = document.querySelectorAll('.mode-btn')
  const editorOptions = document.querySelectorAll('.editor-option')
  
  // Image panel elements
  const imagePanel = document.getElementById('image-panel')
  const existingImagesList = document.getElementById('existing-images')
  const stagedImagesList = document.getElementById('staged-images')
  const btnUploadImage = document.getElementById('btn-upload-image')

  // Initialize
  async function init() {
    // Get note path and repo_id from URL
    const urlParams = new URLSearchParams(window.location.search)
    notePath = urlParams.get('path')
    currentRepoId = parseInt(urlParams.get('repo_id')) || 1

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

    // Track changes for Quill
    if (quillEditorContainer) {
      quillEditorContainer.addEventListener('input', () => {
        isDirty = true
      })
    }

    // Image panel upload button
    if (btnUploadImage) {
      btnUploadImage.addEventListener('click', handleImageUpload)
    }

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
    tiptapMode.classList.add('hidden')
    monacoMode.classList.remove('hidden')

    // Load existing images
    loadExistingImages()

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
          updatePreview()
        })

        // Initial preview
        updatePreview()
      })
    } else {
      // Update content
      monacoEditor.setValue(noteContent)
      updatePreview()
    }
  }

  // Update preview pane
  function updatePreview() {
    if (monacoEditor && previewContent) {
      const markdown = monacoEditor.getValue()
      try {
        previewContent.innerHTML = marked.parse(markdown)
      } catch (err) {
        console.error('Failed to parse markdown:', err)
        previewContent.innerHTML = '<p style="color: red;">预览渲染失败</p>'
      }
    } else {
      console.warn('Preview update skipped:', { monacoEditor: !!monacoEditor, previewContent: !!previewContent })
    }
  }

  // Start TipTap Editor (now using Quill)
  function startTipTap() {
    monacoMode.classList.add('hidden')
    tiptapMode.classList.remove('hidden')

    if (!quillEditor) {
      // Initialize Quill editor
      quillEditor = new Quill('#quill-editor', {
        theme: 'snow',
        modules: {
          toolbar: [
            ['bold', 'italic', 'strike'],
            [{ 'header': [1, 2, 3, false] }],
            ['list', 'bullet', 'code-block'],
            ['link', 'image'],
            ['clean']
          ]
        }
      })

      // Convert Markdown to HTML and set content
      const htmlContent = marked.parse(noteContent)
      quillEditor.root.innerHTML = htmlContent

      // Track changes
      quillEditor.on('text-change', () => {
        isDirty = true
      })
    } else {
      // Update content
      const htmlContent = marked.parse(noteContent)
      quillEditor.root.innerHTML = htmlContent
    }
  }

  // Switch between modes
  function switchMode(newMode) {
    // Get current content
    let content = ''

    if (currentMode === 'monaco' && monacoEditor) {
      content = monacoEditor.getValue()
    } else if (currentMode === 'tiptap' && quillEditor) {
      // Convert Quill HTML to Markdown
      const turndownService = new TurndownService()
      content = turndownService.turndown(quillEditor.root.innerHTML)
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
    } else if (currentMode === 'tiptap' && quillEditor) {
      // Convert Quill HTML to Markdown
      const turndownService = new TurndownService()
      content = turndownService.turndown(quillEditor.root.innerHTML)
    }

    // Get repo_id from URL
    const urlParams = new URLSearchParams(window.location.search)
    const repoId = urlParams.get('repo_id')

    try {
      // If there are staged images, upload them first
      if (stagedImages.length > 0) {
        const formData = new FormData()
        stagedImages.forEach((img, index) => {
          formData.append('images', img.file, img.file.name)
        })

        const uploadRes = await fetch(`/api/repo/${currentRepoId}/images/upload`, {
          method: 'POST',
          body: formData,
        })

        const uploadData = await uploadRes.json()

        if (!uploadData.ok) {
          alert('图片上传失败：' + uploadData.error)
          return
        }

        // Replace temporary paths in content with actual paths
        uploadData.uploaded.forEach((uploaded, index) => {
          const tempPath = stagedImages[index].tempPath
          content = content.replace(new RegExp(escapeRegExp(tempPath), 'g'), uploaded.path)
        })

        stagedImages = []
        updateStagedImagesList()
      }

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
      
      // Reload images if in Monaco mode
      if (currentMode === 'monaco') {
        loadExistingImages()
      }
    } catch (err) {
      alert('保存失败：' + err.message)
    }
  }

  // Helper function to escape regex special characters
  function escapeRegExp(string) {
    return string.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
  }

  // ── Image Panel Functions ──────────────────────────────────────

  // Load existing images from repository
  async function loadExistingImages() {
    if (!existingImagesList) return

    try {
      const res = await fetch(`/api/repo/${currentRepoId}/images`)
      const data = await res.json()

      if (!data.ok) {
        existingImagesList.innerHTML = '<div class="image-empty">加载失败</div>'
        return
      }

      if (data.images.length === 0) {
        existingImagesList.innerHTML = '<div class="image-empty">暂无图片</div>'
        return
      }

      existingImagesList.innerHTML = ''
      data.images.forEach(img => {
        const item = createImageItem(img.path, img.name, false)
        existingImagesList.appendChild(item)
      })
    } catch (err) {
      console.error('Failed to load images:', err)
      existingImagesList.innerHTML = '<div class="image-empty">加载失败</div>'
    }
  }

  // Create image item element
  function createImageItem(imagePath, imageName, isStaged = false) {
    const item = document.createElement('div')
    item.className = 'image-item' + (isStaged ? ' staged' : '')
    item.draggable = true

    // Create thumbnail (for existing images, use the actual image; for staged, use preview)
    const thumbnail = document.createElement('img')
    thumbnail.className = 'image-thumbnail'
    if (isStaged) {
      // Find the staged image and use its preview
      const stagedImg = stagedImages.find(img => img.tempPath === imagePath)
      if (stagedImg) {
        thumbnail.src = stagedImg.preview
      }
    } else {
      // For existing images, we can't easily show thumbnails without serving them
      // So we'll just show a placeholder
      thumbnail.src = 'data:image/svg+xml,%3Csvg xmlns="http://www.w3.org/2000/svg" width="40" height="40"%3E%3Crect width="40" height="40" fill="%23e5e7eb"/%3E%3Ctext x="50%25" y="50%25" dominant-baseline="middle" text-anchor="middle" font-family="sans-serif" font-size="10" fill="%236b7280"%3EIMG%3C/text%3E%3C/svg%3E'
    }

    const info = document.createElement('div')
    info.className = 'image-info'

    const name = document.createElement('div')
    name.className = 'image-name'
    name.textContent = imageName

    const path = document.createElement('div')
    path.className = 'image-path'
    if (isStaged) {
      // Make path editable for staged images
      const pathInput = document.createElement('input')
      pathInput.type = 'text'
      pathInput.className = 'image-path-input'
      pathInput.value = imagePath
      pathInput.addEventListener('change', (e) => {
        // Update the staged image's temp path
        const stagedImg = stagedImages.find(img => img.tempPath === imagePath)
        if (stagedImg) {
          const oldPath = stagedImg.tempPath
          stagedImg.tempPath = e.target.value
          // Update all references in the editor content
          if (monacoEditor) {
            const content = monacoEditor.getValue()
            const newContent = content.replace(new RegExp(escapeRegExp(oldPath), 'g'), e.target.value)
            monacoEditor.setValue(newContent)
          }
        }
      })
      info.appendChild(name)
      info.appendChild(pathInput)
    } else {
      path.textContent = imagePath
      info.appendChild(name)
      info.appendChild(path)
    }

    item.appendChild(thumbnail)
    item.appendChild(info)

    // Drag start event
    item.addEventListener('dragstart', (e) => {
      const markdown = `![${imageName}](${imagePath})`
      e.dataTransfer.setData('text/plain', markdown)
      e.dataTransfer.effectAllowed = 'copy'
    })

    return item
  }

  // Handle image upload
  function handleImageUpload() {
    const input = document.createElement('input')
    input.type = 'file'
    input.accept = 'image/*'
    input.multiple = true

    input.addEventListener('change', async (e) => {
      const files = Array.from(e.target.files)
      if (files.length === 0) return

      for (const file of files) {
        // Create preview
        const reader = new FileReader()
        reader.onload = (event) => {
          const preview = event.target.result
          const timestamp = Date.now()
          const tempPath = `img/pending-${timestamp}-${file.name}`
          
          stagedImages.push({
            file,
            preview,
            tempPath,
          })

          // Add to staged images list
          const item = createImageItem(tempPath, file.name, true)
          stagedImagesList.appendChild(item)

          // Insert markdown at cursor position in Monaco
          if (monacoEditor) {
            const markdown = `![${file.name}](${tempPath})`
            const position = monacoEditor.getPosition()
            monacoEditor.executeEdits('', [{
              range: new monaco.Range(position.lineNumber, position.column, position.lineNumber, position.column),
              text: markdown,
              forceMoveMarkers: true,
            }])
            isDirty = true
          }
        }
        reader.readAsDataURL(file)
      }
    })

    input.click()
  }

  // Update staged images list display
  function updateStagedImagesList() {
    if (!stagedImagesList) return
    
    if (stagedImages.length === 0) {
      stagedImagesList.innerHTML = '<div class="image-empty">暂无暂存图片</div>'
    } else {
      stagedImagesList.innerHTML = ''
      stagedImages.forEach(img => {
        const item = createImageItem(img.tempPath, img.file.name, true)
        stagedImagesList.appendChild(item)
      })
    }
  }

  // Start
  init()
})()
