/* ============================================
   NEXUS CORTEX — Application Logic
   ============================================ */

document.addEventListener('DOMContentLoaded', () => {

  // ==========================================
  // 1. TAB SWITCHING
  // ==========================================
  const navItems = document.querySelectorAll('.nav-item[data-tab]');
  const panels = {
    overview: document.getElementById('tab-overview'),
    upload: document.getElementById('tab-upload'),
    'agent-matrix': document.getElementById('tab-agent-matrix'),
    chat: document.getElementById('tab-chat'),
  };
  const breadcrumb = document.querySelector('.bc-current');
  const tabNames = {
    overview: 'Overview',
    upload: 'Data Upload',
    'agent-matrix': 'Agent Matrix',
    chat: 'Chat History',
  };

  function switchTab(tabId) {
    navItems.forEach(el => el.classList.remove('active'));
    const activeNav = document.querySelector(`.nav-item[data-tab="${tabId}"]`);
    if (activeNav) activeNav.classList.add('active');

    Object.entries(panels).forEach(([id, panel]) => {
      if (panel) panel.classList.toggle('active', id === tabId);
    });

    if (breadcrumb) breadcrumb.textContent = tabNames[tabId] || tabId;

    document.getElementById('sidebar')?.classList.remove('open');
    document.querySelector('.chat-history-sidebar')?.classList.remove('open');
  }

  navItems.forEach(item => {
    item.addEventListener('click', (e) => {
      e.preventDefault();
      const tab = item.dataset.tab;
      if (tab) switchTab(tab);
    });
  });

  const sidebarToggle = document.getElementById('sidebarToggle');
  const sidebar = document.getElementById('sidebar');
  if (sidebarToggle && sidebar) {
    sidebarToggle.addEventListener('click', () => {
      sidebar.classList.toggle('open');
    });
  }

  // ==========================================
  // 2. RAM OPTIMIZATION
  // ==========================================
  const ramBtns = document.querySelectorAll('.ram-btn');
  const ramBarFill = document.getElementById('ramBarFill');
  const ramUsedLabel = document.getElementById('ramUsedLabel');
  const ramTotalLabel = document.getElementById('ramTotalLabel');
  const ramAllocated = document.getElementById('ramAllocated');
  const ramInUse = document.getElementById('ramInUse');
  const ramAvailable = document.getElementById('ramAvailable');
  const sidebarRamText = document.querySelector('.ram-mini-text');
  const sidebarRamFill = document.querySelector('.ram-mini-fill');
  const summaryRamUsage = document.getElementById('ramUsage');

  const ramConfig = {
    4:  { total: 4,  usedPct: 0.875, activeCount: 3 },
    8:  { total: 8,  usedPct: 1.00,  activeCount: 12 },
    16: { total: 16, usedPct: 0.50,  activeCount: 12 },
  };

  const activeIndices = {
    4: {
      market:     [0],
      financial:  [0],
      operations: [0],
    },
    8: {
      market:     [0, 1, 2, 3],
      financial:  [0, 1, 2, 3],
      operations: [0, 1, 2, 3],
    },
    16: {
      market:     [0, 1, 2, 3],
      financial:  [0, 1, 2, 3],
      operations: [0, 1, 2, 3],
    },
  };

  let currentRam = 8;
  let lastRamPct = 1.0;

  function updateRAM(gb) {
    currentRam = gb;
    const config = ramConfig[gb];
    if (!config) return;

    const pct = config.usedPct * 100;
    const usedGB = (config.total * config.usedPct).toFixed(1);
    const freeGB = (config.total - parseFloat(usedGB)).toFixed(1);

    if (ramBarFill) ramBarFill.style.width = pct + '%';
    if (ramUsedLabel) ramUsedLabel.textContent = usedGB + ' GB';
    if (ramTotalLabel) ramTotalLabel.textContent = gb + ' GB';
    if (ramAllocated) ramAllocated.textContent = gb + ' GB';
    if (ramInUse) ramInUse.textContent = usedGB + ' GB';
    if (ramAvailable) ramAvailable.textContent = freeGB + ' GB';
    if (sidebarRamText) sidebarRamText.textContent = gb + 'GB';
    if (sidebarRamFill) sidebarRamFill.style.width = pct + '%';

    lastRamPct = config.usedPct;

    if (summaryRamUsage) summaryRamUsage.textContent = Math.round(pct);

    drawRamDonut(config.usedPct);

    ramBtns.forEach(btn => {
      btn.classList.toggle('active', parseInt(btn.dataset.ram) === gb);
    });

    const indices = activeIndices[gb];
    if (!indices) return;

    const agents = ['market', 'financial', 'operations'];
    let totalActive = 0;

    agents.forEach(agent => {
      const grid = document.getElementById(`subagents-${agent}`);
      const badge = document.getElementById(`badge-${agent}`);
      const activeForAgent = indices[agent] || [];

      if (grid) {
        const subs = grid.querySelectorAll('.subagent');
        subs.forEach((sub, idx) => {
          const shouldBeActive = activeForAgent.includes(idx);
          sub.classList.toggle('active', shouldBeActive);
          const status = sub.querySelector('.sg-status');
          if (status) {
            status.textContent = shouldBeActive ? 'Active' : 'Standby';
          }
        });
      }

      if (badge) {
        const count = activeForAgent.length;
        badge.textContent = `${count}/4 Active`;
        badge.classList.toggle('standby', count === 0);
      }

      totalActive += activeForAgent.length;
    });

    const totalStandbyEl = document.getElementById('totalStandby');
    const totalActiveEl = document.getElementById('totalActive');
    if (totalActiveEl) totalActiveEl.textContent = totalActive;
    if (totalStandbyEl) totalStandbyEl.textContent = 12 - totalActive;
  }

  ramBtns.forEach(btn => {
    btn.addEventListener('click', () => {
      const gb = parseInt(btn.dataset.ram);
      if (!isNaN(gb)) updateRAM(gb);
    });
  });

  updateRAM(8);

  // ==========================================
  // 3. SESSION ID & BACKEND URL
  // ==========================================
  const SESSION_ID = localStorage.getItem('nexusSessionId') || crypto.randomUUID();
  localStorage.setItem('nexusSessionId', SESSION_ID);
  console.log('[Nexus] Session ID:', SESSION_ID);

  // 🔽 SIRF YE 1 LINE CHANGE HUI HAI 🔽
  const BACKEND_URL = 'https://nexus-cortex.onrender.com';  
  // ==========================================
  // 4. FILE UPLOAD
  // ==========================================
  const dropzone = document.getElementById('dropzone');
  const fileInput = document.getElementById('fileInput');
  const fileList = document.getElementById('fileList');
  const fileCount = document.getElementById('fileCount');
  const uploadLink = document.getElementById('uploadLink');

  const uploadedFiles = [];

  if (uploadLink && fileInput) {
    uploadLink.addEventListener('click', (e) => {
      e.stopPropagation();
      fileInput.click();
    });
  }

  if (dropzone && fileInput) {
    dropzone.addEventListener('click', () => fileInput.click());

    ['dragenter', 'dragover'].forEach(evt => {
      dropzone.addEventListener(evt, (e) => {
        e.preventDefault();
        e.stopPropagation();
        dropzone.classList.add('dragover');
      });
    });

    ['dragleave', 'drop'].forEach(evt => {
      dropzone.addEventListener(evt, (e) => {
        e.preventDefault();
        e.stopPropagation();
        dropzone.classList.remove('dragover');
      });
    });

    dropzone.addEventListener('drop', (e) => {
      const files = e.dataTransfer?.files;
      if (files) handleFiles(files);
    });

    fileInput.addEventListener('change', () => {
      if (fileInput.files) handleFiles(fileInput.files);
      fileInput.value = '';
    });
  }

  async function handleFiles(files) {
    const validExts = ['.csv', '.xlsx', '.xls', '.json'];
    const results = { success: 0, failed: 0, skipped: 0 };

    const tasks = Array.from(files)
      .filter(file => {
        const ext = '.' + file.name.split('.').pop().toLowerCase();
        if (!validExts.includes(ext)) {
          results.skipped++;
          return false;
        }
        if (uploadedFiles.some(f => f.name === file.name && f.size === file.size)) {
          results.skipped++;
          return false;
        }
        return true;
      })
      .map(async (file) => {
        try {
          const fd = new FormData();
          fd.append('file', file);
          fd.append('session_id', SESSION_ID);
          const resp = await fetch(BACKEND_URL + '/upload-file', { method: 'POST', body: fd });
          const data = await resp.json();
          if (data.error) {
            results.failed++;
            console.warn('[Upload] Backend error:', data.detail);
          } else {
            results.success++;
            console.log('[Upload] Backend accepted:', file.name, '—', data.rows_sampled, 'rows,', data.columns, 'cols');
          }
        } catch (err) {
          results.failed++;
          console.warn('[Upload] Backend unreachable, file stored locally only:', err.message);
        }
        uploadedFiles.push(file);
      });

    await Promise.all(tasks);
    renderFiles();

    if (results.failed > 0) {
      console.log(`[Upload] ${results.success} success, ${results.failed} failed, ${results.skipped} skipped`);
    }
  }

  function formatSize(bytes) {
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
    return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
  }

  function renderFiles() {
    if (!fileList || !fileCount) return;
    if (uploadedFiles.length === 0) {
      fileList.innerHTML = `
        <div class="file-empty">
          <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" opacity="0.3"><path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>
          <p>No files uploaded yet</p>
        </div>`;
      fileCount.textContent = '0 files';
      return;
    }
    fileCount.textContent = uploadedFiles.length + ' file' + (uploadedFiles.length !== 1 ? 's' : '');
    fileList.innerHTML = uploadedFiles.map((file, idx) => `
      <div class="file-item">
        <div class="file-item-icon"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/></svg></div>
        <div class="file-item-info"><div class="file-item-name">${file.name}</div><div class="file-item-meta">${formatSize(file.size)}</div></div>
        <button class="file-item-remove" data-idx="${idx}" title="Remove file"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 01-2 2H7a2 2 0 01-2-2V6m3 0V4a2 2 0 012-2h4a2 2 0 012 2v2"/></svg></button>
      </div>
    `).join('');
    fileList.querySelectorAll('.file-item-remove').forEach(btn => {
      btn.addEventListener('click', (e) => {
        e.stopPropagation();
        const idx = parseInt(btn.dataset.idx);
        if (!isNaN(idx) && idx >= 0 && idx < uploadedFiles.length) {
          uploadedFiles.splice(idx, 1);
          renderFiles();
        }
      });
    });
  }

  // ==========================================
  // 5. CHAT FUNCTIONALITY
  // ==========================================
  const chatInput = document.getElementById('chatInput');
  const chatSendBtn = document.getElementById('chatSendBtn');
  const chatMessages = document.getElementById('chatMessages');
  const chatItems = document.querySelectorAll('.ch-item');

  let pendingAgentResponses = 0;

  const fallbackReplies = [
    "I've analyzed the data and found 3 key trends emerging in Q3. Would you like me to generate a detailed report?",
    "The margin analysis shows 5 products running below target. I recommend a pricing review.",
    "Operations scan complete: 2 workflow bottlenecks identified in the supply chain.",
    "Data from your latest upload has been processed. I found 4 actionable insights.",
    "Risk assessment updated: 2 sectors flagged for moderate exposure. 1 requires immediate attention.",
  ];

  function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
  }

  function addUserMessage(text) {
    if (!chatMessages) return;
    const msg = document.createElement('div');
    msg.className = 'msg msg-user';
    msg.innerHTML = `
      <div class="msg-avatar" style="background:#374151;">U</div>
      <div class="msg-content">
        <div class="msg-meta"><strong>You</strong><span class="msg-time">Just now</span></div>
        <p>${escapeHtml(text)}</p>
      </div>`;
    chatMessages.appendChild(msg);
    chatMessages.scrollTop = chatMessages.scrollHeight;
  }

  function renderMarkdown(text) {
    if (window.marked) {
      return window.marked.parse(text);
    }
    let escaped = escapeHtml(text);
    escaped = escaped.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
    const lines = escaped.split('\n');
    let inList = false;
    const result = [];
    for (const line of lines) {
      const listMatch = line.match(/^\* (.+)$/);
      const numMatch = line.match(/^(\d+\)) (.+)$/);
      if (listMatch || numMatch) {
        if (!inList) { result.push('<ul>'); inList = true; }
        const content = listMatch ? listMatch[1] : numMatch[2];
        result.push(`<li>${content.replace(/\*(.+?)\*/g, '<em>$1</em>')}</li>`);
      } else {
        if (inList) { result.push('</ul>'); inList = false; }
        result.push(line.replace(/\*(.+?)\*/g, '<em>$1</em>'));
      }
    }
    if (inList) result.push('</ul>');
    let output = result.join('\n');
    output = output.replace(/^### (.+)$/gm, '<h4>$1</h4>');
    output = output.replace(/^## (.+)$/gm, '<h3>$1</h3>');
    output = output.replace(/^# (.+)$/gm, '<h2>$1</h2>');
    return output.replace(/\n/g, '<br>');
  }

  function addSystemMessage(agentName, color, text) {
    if (!chatMessages) return;
    const lastMsg = chatMessages.lastElementChild;
    if (lastMsg && lastMsg.classList.contains('msg-system')) {
      const lastText = lastMsg.querySelector('.msg-md')?.dataset.raw;
      if (lastText === escapeHtml(text)) return;
    }
    const msg = document.createElement('div');
    msg.className = 'msg msg-system';
    msg.innerHTML = `
      <div class="msg-avatar" style="background:${color};">${agentName[0]}</div>
      <div class="msg-content">
        <div class="msg-meta"><strong>${agentName}</strong><span class="msg-time">Just now</span></div>
        <div class="msg-md" data-raw="${escapeHtml(text)}">${renderMarkdown(text)}</div>
      </div>`;
    chatMessages.appendChild(msg);
    chatMessages.scrollTop = chatMessages.scrollHeight;
  }

  function showTypingIndicator() {
    if (!chatMessages) return;
    hideTypingIndicator();
    const indicator = document.createElement('div');
    indicator.className = 'msg msg-system msg-typing';
    indicator.id = 'typingIndicator';
    indicator.innerHTML = `
      <div class="msg-avatar" style="background:#6366F1;">N</div>
      <div class="msg-content">
        <div class="msg-meta"><strong>Nexus Cortex</strong><span class="msg-time">Thinking...</span></div>
        <p><span class="typing-dots"><span>.</span><span>.</span><span>.</span></span></p>
      </div>`;
    chatMessages.appendChild(indicator);
    chatMessages.scrollTop = chatMessages.scrollHeight;
  }

  function hideTypingIndicator() {
    const indicator = document.getElementById('typingIndicator');
    if (indicator) indicator.remove();
  }

  function agentDisplayName(agentType) {
    const labels = {
      'market_strategist': 'Market Strategist',
      'financial_analyst': 'Financial Analyst',
      'operations_optimizer': 'Ops Optimizer',
      'nexus_cortex': 'Nexus Cortex',
    };
    return labels[agentType] || 'Nexus Cortex';
  }

  function agentColor(agentType) {
    const colors = {
      'market_strategist': '#6366F1',
      'financial_analyst': '#22C55E',
      'operations_optimizer': '#F97316',
      'nexus_cortex': '#6366F1',
    };
    return colors[agentType] || '#6366F1';
  }

  function handleChatEvent(event) {
    console.log('[Chat] SSE event:', event);
    switch (event.type) {
      case 'status':
        if (event.message && event.message.includes('main agents')) {
          const match = event.message.match(/(\d+) main agents/);
          if (match) pendingAgentResponses = parseInt(match[1]);
        }
        break;
      case 'scope_error':
        pendingAgentResponses = 0;
        hideTypingIndicator();
        addSystemMessage('Nexus Cortex', '#EF4444', event.message);
        break;
      case 'agent_response':
        pendingAgentResponses = Math.max(0, pendingAgentResponses - 1);
        if (pendingAgentResponses <= 0) hideTypingIndicator();
        addSystemMessage(agentDisplayName(event.agent), agentColor(event.agent), event.content || '(empty)');
        break;
      case 'error':
        pendingAgentResponses = 0;
        hideTypingIndicator();
        addSystemMessage('Nexus Cortex', '#EF4444', event.detail || 'An error occurred.');
        break;
      case 'done':
        pendingAgentResponses = 0;
        hideTypingIndicator();
        break;
    }
  }

  async function sendMessage(text) {
    if (!text.trim() || !chatMessages) return;
    addUserMessage(text);
    if (chatInput) chatInput.value = '';
    showTypingIndicator();

    try {
      const formData = new FormData();
      formData.append('query', text);
      formData.append('session_id', SESSION_ID);
      const response = await fetch(BACKEND_URL + '/chat', { method: 'POST', body: formData });

      if (!response.ok) {
        hideTypingIndicator();
        addSystemMessage('Nexus Cortex', '#EF4444', `Backend error (${response.status}).`);
        simulateFallbackReply(text);
        return;
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const parts = buffer.split('\n\n');
        buffer = parts.pop() || '';
        for (const part of parts) {
          for (const line of part.split('\n')) {
            if (line.startsWith('data: ')) {
              try { handleChatEvent(JSON.parse(line.slice(6))); } catch (e) {}
            }
          }
        }
      }
      hideTypingIndicator();

    } catch (err) {
      hideTypingIndicator();
      addSystemMessage('Nexus Cortex', '#EF4444', 'Cannot reach backend.');
      simulateFallbackReply(text);
    }
  }

  function simulateFallbackReply(text) {
    setTimeout(() => {
      const reply = fallbackReplies[Math.floor(Math.random() * fallbackReplies.length)];
      const names = ['Nexus Cortex', 'Market Strategist', 'Financial Analyst', 'Ops Optimizer'];
      const name = names[Math.floor(Math.random() * names.length)];
      const colors = ['#6366F1', '#6366F1', '#22C55E', '#F97316'];
      addSystemMessage(name, colors[names.indexOf(name)], reply);
    }, 600 + Math.random() * 400);
  }

  if (chatSendBtn && chatInput) {
    chatSendBtn.addEventListener('click', () => sendMessage(chatInput.value));
    chatInput.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        sendMessage(chatInput.value);
      }
    });
  }

  chatItems.forEach(item => {
    item.addEventListener('click', () => {
      chatItems.forEach(i => i.classList.remove('active'));
      item.classList.add('active');
    });
  });

  const chatSearch = document.getElementById('chatSearch');
  if (chatSearch) {
    chatSearch.addEventListener('input', () => {
      const q = chatSearch.value.toLowerCase();
      chatItems.forEach(item => {
        const name = item.querySelector('strong')?.textContent?.toLowerCase() || '';
        const desc = item.querySelector('p')?.textContent?.toLowerCase() || '';
        item.style.display = (name.includes(q) || desc.includes(q)) ? 'flex' : 'none';
      });
    });
  }

  const chatSidebarClose = document.getElementById('chatSidebarClose');
  const chatHistorySidebar = document.querySelector('.chat-history-sidebar');
  if (chatSidebarClose && chatHistorySidebar) {
    chatSidebarClose.addEventListener('click', () => {
      chatHistorySidebar.classList.remove('open');
    });
  }

  const chatUploadBtn = document.getElementById('chatUploadBtn');
  if (chatUploadBtn) {
    chatUploadBtn.addEventListener('click', () => {
      const hiddenInput = document.createElement('input');
      hiddenInput.type = 'file';
      hiddenInput.accept = '.csv,.xlsx,.xls,.json';
      hiddenInput.onchange = async () => {
        const file = hiddenInput.files?.[0];
        if (!file) return;
        try {
          const fd = new FormData();
          fd.append('file', file);
          fd.append('session_id', SESSION_ID);
          const resp = await fetch(BACKEND_URL + '/upload-file', { method: 'POST', body: fd });
          const data = await resp.json();
          if (data.error) {
            addSystemMessage('Nexus Cortex', '#EF4444', 'Upload failed: ' + (data.detail || ''));
          } else {
            addSystemMessage('Nexus Cortex', '#6366F1', `✅ Uploaded "${file.name}" — ${data.rows_sampled} rows, ${data.columns} columns.`);
            uploadedFiles.push(file);
            renderFiles();
          }
        } catch (err) {
          addSystemMessage('Nexus Cortex', '#EF4444', 'Upload failed: cannot reach backend.');
        }
      };
      hiddenInput.click();
    });
  }

  // ==========================================
  // CANVAS CHARTS
  // ==========================================
  function drawActivityChart() {
    const canvas = document.getElementById('activityCanvas');
    if (!canvas) return;
    const rect = canvas.parentElement.getBoundingClientRect();
    const dpr = window.devicePixelRatio || 1;
    const w = rect.width;
    const h = rect.height || 200;
    canvas.width = w * dpr;
    canvas.height = h * dpr;
    canvas.style.width = w + 'px';
    canvas.style.height = h + 'px';
    const ctx = canvas.getContext('2d');
    ctx.scale(dpr, dpr);
    const data = [35, 55, 42, 78, 65, 90, 72, 58, 85, 60, 45, 70];
    const chartW = w - 20;
    const chartH = h - 30;
    const barW = chartW / 12 - 6;
    ctx.clearRect(0, 0, w, h);
    data.forEach((val, i) => {
      const x = 10 + (chartW / 12) * i + 3;
      const barH = (val / 100) * chartH;
      const y = 10 + chartH - barH;
      const grad = ctx.createLinearGradient(x, y, x, 10 + chartH);
      grad.addColorStop(0, '#6366F1');
      grad.addColorStop(1, '#8B5CF6');
      ctx.fillStyle = grad;
      ctx.beginPath();
      ctx.roundRect(x, y, barW, barH, [3, 3, 0, 0]);
      ctx.fill();
      ctx.shadowColor = 'rgba(99, 102, 241, 0.3)';
      ctx.shadowBlur = 8;
      ctx.fill();
      ctx.shadowBlur = 0;
    });
  }

  function drawRamDonut(percent) {
    const canvas = document.getElementById('ramCanvas');
    if (!canvas) return;
    const pct = percent !== undefined ? percent : 1.0;
    const rect = canvas.parentElement.getBoundingClientRect();
    const dpr = window.devicePixelRatio || 1;
    const size = Math.min(rect.width, rect.height || 180);
    canvas.width = size * dpr;
    canvas.height = size * dpr;
    canvas.style.width = size + 'px';
    canvas.style.height = size + 'px';
    const ctx = canvas.getContext('2d');
    ctx.scale(dpr, dpr);
    const cx = size / 2, cy = size / 2;
    const outerR = size * 0.38, innerR = size * 0.22;
    ctx.clearRect(0, 0, size, size);
    ctx.beginPath();
    ctx.arc(cx, cy, outerR, 0, Math.PI * 2);
    ctx.arc(cx, cy, innerR, Math.PI * 2, 0, true);
    ctx.closePath();
    ctx.fillStyle = 'rgba(255,255,255,0.04)';
    ctx.fill();
    ctx.beginPath();
    ctx.arc(cx, cy, outerR, -Math.PI / 2, -Math.PI / 2 + Math.PI * 2 * pct);
    ctx.arc(cx, cy, innerR, -Math.PI / 2 + Math.PI * 2 * pct, -Math.PI / 2, true);
    ctx.closePath();
    const grad = ctx.createLinearGradient(0, 0, size, size);
    grad.addColorStop(0, '#6366F1');
    grad.addColorStop(1, '#8B5CF6');
    ctx.fillStyle = grad;
    ctx.fill();
    ctx.fillStyle = 'rgba(255,255,255,0.7)';
    ctx.font = `600 ${size * 0.1}px Inter, sans-serif`;
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.fillText(Math.round(pct * 100) + '%', cx, cy);
  }

  setTimeout(() => { drawActivityChart(); drawRamDonut(); }, 100);

  let resizeTimer;
  window.addEventListener('resize', () => {
    clearTimeout(resizeTimer);
    resizeTimer = setTimeout(() => { drawActivityChart(); drawRamDonut(lastRamPct); }, 200);
  });

});