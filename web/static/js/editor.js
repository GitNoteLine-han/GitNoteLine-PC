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
  const btnUploadImage = document.getElementById('btn-upload-image')

  // Delete image dialog
  const deleteImageDialog = document.getElementById('delete-image-dialog')
  const deleteImageText = document.getElementById('delete-image-text')
  const btnCancelDeleteImage = document.getElementById('btn-delete-image-cancel')
  const btnConfirmDeleteImage = document.getElementById('btn-delete-image-confirm')
  let pendingImageDelete = null

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

    // Auto-pull on startup (in background, don't block UI)
    syncPull()

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

  // ── Sync operations ──────────────────────────────────────────

  async function syncPull() {
    if (!currentRepoId) return

    // Don't overwrite editor if user has unsaved changes
    if (isDirty) return

    try {
      const res = await fetch(`/api/repo/${currentRepoId}/pull`, { method: 'POST' })
      const data = await res.json()

      if (data.ok) {
        // Reload note content after pull
        await loadNote()
        // Update editor content if already initialized
        if (currentMode === 'monaco' && monacoEditor) {
          monacoEditor.setValue(noteContent)
          updatePreview()
        } else if (currentMode === 'tiptap' && quillEditor) {
          const displayContent = noteContent.replace(
            /!\[([^\]]*)\]\(\.\/img\/([^)]+)\)/g,
            `![$1](/repo/${currentRepoId}/img/$2)`
          )
          const htmlContent = marked.parse(displayContent)
          quillEditor.clipboard.dangerouslyPasteHTML(htmlContent)
        }
      } else {
        console.warn('Auto-pull failed:', data.error)
      }
    } catch (err) {
      console.warn('Auto-pull failed:', err.message)
    }
  }

  async function syncPush() {
    if (!currentRepoId) return

    try {
      const res = await fetch(`/api/repo/${currentRepoId}/push`, { method: 'POST' })
      const data = await res.json()

      if (!data.ok) {
        console.warn('Auto-push failed:', data.error)
      }
    } catch (err) {
      console.warn('Auto-push failed:', err.message)
    }
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
        // Rewrite image paths for display: ./img/xxx -> /repo/<repo_id>/img/xxx
        const displayMarkdown = markdown.replace(
          /!\[([^\]]*)\]\(\.\/img\/([^)]+)\)/g,
          `![$1](/repo/${currentRepoId}/img/$2)`
        )
        previewContent.innerHTML = marked.parse(displayMarkdown)
      } catch (err) {
        console.error('Failed to parse markdown:', err)
        previewContent.innerHTML = '<p style="color: red;">预览渲染失败</p>'
      }
    }
  }

  // Start TipTap Editor (now using Quill)
  function startTipTap() {
    monacoMode.classList.add('hidden')
    tiptapMode.classList.remove('hidden')

    // Load existing images for the image panel
    loadExistingImages()

    if (!quillEditor) {
      // Initialize Quill editor with custom image handler
      quillEditor = new Quill('#quill-editor', {
        theme: 'snow',
        modules: {
          toolbar: {
            container: [
              ['bold', 'italic', 'strike'],
              [{ 'header': [1, 2, 3, false] }],
              ['list', 'bullet', 'code-block'],
              ['link', 'image'],
              ['clean']
            ],
            handlers: {
              image: handleQuillImage
            }
          }
        }
      })

      // Custom clipboard matcher: preserve img src as-is (prevent Quill from resolving URLs)
      quillEditor.clipboard.addMatcher('img', function (node, delta) {
        const src = node.getAttribute('src')
        if (src) {
          delta.ops = [{ insert: { image: src } }]
        }
        return delta
      })

      // Convert Markdown to HTML and set content
      // Rewrite image paths for display: ./img/xxx -> /repo/<repo_id>/img/xxx
      const displayContent = noteContent.replace(
        /!\[([^\]]*)\]\(\.\/img\/([^)]+)\)/g,
        `![$1](/repo/${currentRepoId}/img/$2)`
      )
      const htmlContent = marked.parse(displayContent)
      // Use Quill's clipboard API to properly set HTML content
      quillEditor.clipboard.dangerouslyPasteHTML(htmlContent)

      // Track changes
      quillEditor.on('text-change', () => {
        isDirty = true
      })

      // Handle drop events for images
      quillEditor.root.addEventListener('drop', handleQuillDrop)
      quillEditor.root.addEventListener('dragover', (e) => {
        e.preventDefault()
        e.dataTransfer.dropEffect = 'copy'
        quillEditor.root.classList.add('drag-over')
      })
      quillEditor.root.addEventListener('dragleave', () => {
        quillEditor.root.classList.remove('drag-over')
      })
      quillEditor.root.addEventListener('drop', () => {
        quillEditor.root.classList.remove('drag-over')
      })
    } else {
      // Update content
      const displayContent = noteContent.replace(
        /!\[([^\]]*)\]\(\.\/img\/([^)]+)\)/g,
        `![$1](/repo/${currentRepoId}/img/$2)`
      )
      const htmlContent = marked.parse(displayContent)
      // Use Quill's clipboard API to properly set HTML content
      quillEditor.clipboard.dangerouslyPasteHTML(htmlContent)
    }
  }

  // Custom image handler for Quill - shows image panel instead of file picker
  function handleQuillImage() {
    // Toggle image panel visibility
    const imagePanel = document.getElementById('image-panel')
    if (imagePanel) {
      imagePanel.classList.toggle('hidden')
    }
  }

  // Handle drop events in Quill editor
  function handleQuillDrop(e) {
    e.preventDefault()
    e.stopPropagation()

    // Get the dropped data
    const markdown = e.dataTransfer.getData('text/plain')
    if (!markdown) return

    // Parse markdown image syntax: ![alt](path)
    const match = markdown.match(/^!\[([^\]]*)\]\(([^)]+)\)$/)
    if (!match) return

    const alt = match[1]
    let imagePath = match[2]

    // Convert relative path to display path
    if (imagePath.startsWith('./img/')) {
      imagePath = imagePath.replace('./img/', `/repo/${currentRepoId}/img/`)
    }

    // Calculate drop position using Quill's built-in method
    const bounds = quillEditor.root.getBoundingClientRect()
    const x = e.clientX - bounds.left
    const y = e.clientY - bounds.top

    // Use Quill's getPosition to find the index at drop location
    let index
    try {
      // Try to get position from Quill
      const position = quillEditor.getBounds(0)
      if (position) {
        // Use the container's scrollTop to adjust y coordinate
        const adjustedY = y + quillEditor.root.scrollTop
        index = quillEditor.getIndex({ left: x, top: adjustedY })
      }
    } catch (err) {
      // Fallback: insert at end
      index = quillEditor.getLength()
    }

    // Ensure index is valid
    if (index === null || index === undefined || index < 0) {
      index = quillEditor.getLength()
    }

    // Insert image at drop position
    quillEditor.insertEmbed(index, 'image', imagePath)
    quillEditor.setSelection(index + 1)
    isDirty = true
  }

  // Show toast notification
  function showToast(message) {
    const toast = document.createElement('div')
    toast.className = 'toast-notification'
    toast.innerHTML = `
      <div class="toast-content">
        <span class="toast-icon">✓</span>
        <span class="toast-message">${message.replace(/\n/g, '<br>')}</span>
      </div>
    `
    document.body.appendChild(toast)

    // Animate in
    setTimeout(() => toast.classList.add('show'), 10)

    // Remove after 4 seconds
    setTimeout(() => {
      toast.classList.remove('show')
      setTimeout(() => toast.remove(), 300)
    }, 4000)
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
      
      // Convert display paths back to relative paths for storage
      // /repo/<repo_id>/img/xxx -> ./img/xxx
      content = content.replace(
        new RegExp(`!\\[([^\\]]*)\\]\\(/repo/${currentRepoId}/img/([^)]+)\\)`, 'g'),
        '![$1](./img/$2)'
      )
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

    // Convert display paths back to relative paths for storage
    // /repo/<repo_id>/img/xxx -> ./img/xxx
    content = content.replace(
      new RegExp(`!\\[([^\\]]*)\\]\\(/repo/${currentRepoId}/img/([^)]+)\\)`, 'g'),
      '![$1](./img/$2)'
    )

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

      // Refresh preview after save
      updatePreview()

      // Reload images if in Monaco mode
      if (currentMode === 'monaco') {
        loadExistingImages()
      }

      // Auto-push after save
      syncPush()

      alert('保存成功！')
    } catch (err) {
      alert('保存失败：' + err.message)
    }
  }

  // Helper function to escape regex special characters
  function escapeRegExp(string) {
    return string.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
  }

  // ── Image Panel Functions ──────────────────────────────────────

  // Image panel state
  let allImagesLoaded = false
  let allImages = []

  // Load existing images from repository (paginated)
  async function loadExistingImages(loadAll = false) {
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

      // Store all images
      allImages = data.images

      // Determine how many to show
      const imagesToShow = loadAll ? allImages : allImages.slice(0, 10)
      allImagesLoaded = loadAll || allImages.length <= 10

      // Render images
      existingImagesList.innerHTML = ''
      imagesToShow.forEach(img => {
        const item = createImageItem(img.path, img.name)
        existingImagesList.appendChild(item)
      })

      // Add "view more" button if needed
      if (!allImagesLoaded) {
        const viewMoreBtn = document.createElement('div')
        viewMoreBtn.className = 'image-view-more'
        viewMoreBtn.textContent = `查看更多 (${allImages.length - 10} 张)`
        viewMoreBtn.addEventListener('click', () => {
          loadExistingImages(true)
        })
        existingImagesList.appendChild(viewMoreBtn)
      }
    } catch (err) {
      console.error('Failed to load images:', err)
      existingImagesList.innerHTML = '<div class="image-empty">加载失败</div>'
    }
  }

  // Create image item element
  function createImageItem(imagePath, imageName) {
    const item = document.createElement('div')
    item.className = 'image-item'
    item.draggable = true

    // Create thumbnail - use actual image from repository
    const thumbnail = document.createElement('img')
    thumbnail.className = 'image-thumbnail'
    // Convert relative path to display path
    let displayPath = imagePath
    if (imagePath.startsWith('./')) {
      displayPath = imagePath.replace('./', `/repo/${currentRepoId}/`)
    } else if (!imagePath.startsWith('/')) {
      displayPath = `/repo/${currentRepoId}/${imagePath}`
    }
    thumbnail.src = displayPath
    thumbnail.alt = imageName
    thumbnail.onerror = () => {
      // Fallback to placeholder if image fails to load
      thumbnail.src = 'data:image/svg+xml,%3Csvg xmlns="http://www.w3.org/2000/svg" width="40" height="40"%3E%3Crect width="40" height="40" fill="%23e5e7eb"/%3E%3Ctext x="50%25" y="50%25" dominant-baseline="middle" text-anchor="middle" font-family="sans-serif" font-size="10" fill="%236b7280"%3EIMG%3C/text%3E%3C/svg%3E'
    }

    const info = document.createElement('div')
    info.className = 'image-info'

    const name = document.createElement('div')
    name.className = 'image-name'
    name.textContent = imageName

    const path = document.createElement('div')
    path.className = 'image-path'
    path.textContent = imagePath

    info.appendChild(name)
    info.appendChild(path)

    // Delete button
    const deleteBtn = document.createElement('button')
    deleteBtn.className = 'btn-delete-image-panel'
    deleteBtn.title = '删除图片'
    deleteBtn.innerHTML = '<img src="/icons/trash-can-solid-full.svg" alt="删除" width="14" height="14">'
    deleteBtn.addEventListener('click', (e) => {
      e.stopPropagation()
      pendingImageDelete = { path: imagePath, name: imageName }
      deleteImageText.textContent = `确定要删除图片「${imageName}」吗？删除后所有引用都会失效。`
      deleteImageDialog.showModal()
    })

    item.appendChild(thumbnail)
    item.appendChild(info)
    item.appendChild(deleteBtn)

    // Drag start event
    item.addEventListener('dragstart', (e) => {
      // Use ./ prefix for relative paths in Markdown
      const mdPath = imagePath.startsWith('./') ? imagePath : './' + imagePath
      const markdown = `![${imageName}](${mdPath})`
      e.dataTransfer.setData('text/plain', markdown)
      e.dataTransfer.effectAllowed = 'copy'
    })

    return item
  }

  // Handle image upload - upload directly to repository
  async function handleImageUpload() {
    const input = document.createElement('input')
    input.type = 'file'
    input.accept = 'image/*'
    input.multiple = true

    input.addEventListener('change', async (e) => {
      const files = Array.from(e.target.files)
      if (files.length === 0) return

      const formData = new FormData()
      files.forEach(file => formData.append('images', file))

      try {
        const res = await fetch(`/api/repo/${currentRepoId}/images/upload`, {
          method: 'POST',
          body: formData
        })
        const data = await res.json()

        if (data.ok && data.uploaded.length > 0) {
          // Insert images into editor
          for (const uploaded of data.uploaded) {
            const imagePath = `./img/${uploaded.name}`
            const displayPath = `/repo/${currentRepoId}/img/${uploaded.name}`

            if (currentMode === 'monaco' && monacoEditor) {
              // Insert markdown at cursor position in Monaco
              const markdown = `![${uploaded.name}](${imagePath})`
              const position = monacoEditor.getPosition()
              monacoEditor.executeEdits('', [{
                range: new monaco.Range(position.lineNumber, position.column, position.lineNumber, position.column),
                text: markdown,
                forceMoveMarkers: true,
              }])
            } else if (currentMode === 'tiptap' && quillEditor) {
              // Insert image at cursor position in Quill
              const range = quillEditor.getSelection(true)
              quillEditor.insertEmbed(range.index, 'image', displayPath)
              quillEditor.setSelection(range.index + 1)
            }
          }

          isDirty = true
          loadExistingImages() // Refresh image list
          showToast('图片已保存到仓库的 `img/` 目录。\n如需管理图片，请使用图片面板。')
        } else {
          alert('图片上传失败：' + (data.error || '未知错误'))
        }
      } catch (err) {
        alert('图片上传失败：' + err.message)
      }
    })

    input.click()
  }

  // Delete image dialog handlers
  if (btnCancelDeleteImage) {
    btnCancelDeleteImage.addEventListener('click', () => {
      deleteImageDialog.close()
      pendingImageDelete = null
    })
  }

  if (deleteImageDialog) {
    deleteImageDialog.addEventListener('cancel', () => {
      pendingImageDelete = null
    })
  }

  if (btnConfirmDeleteImage) {
    btnConfirmDeleteImage.addEventListener('click', async () => {
      if (!pendingImageDelete) return

      const { path, name } = pendingImageDelete
      deleteImageDialog.close()

      try {
        const res = await fetch(`/api/repo/${currentRepoId}/images/${encodeURIComponent(path)}`, {
          method: 'DELETE'
        })
        const data = await res.json()

        if (!data.ok) {
          alert(data.error || '删除失败')
          return
        }

        loadExistingImages(allImagesLoaded)
      } catch (err) {
        console.error('Delete image failed:', err)
        alert('网络错误，请重试')
      }

      pendingImageDelete = null
    })
  }

  // Start
  init()
})()
