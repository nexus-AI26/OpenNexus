const chatMessages = document.getElementById('chat-messages');
const chatInput = document.getElementById('chat-input');
const sendBtn = document.getElementById('send-btn');
const tokenCount = document.getElementById('token-count');

let totalChars = 0;

async function loadInfo() {
  try {
    const r = await fetch('/api/info');
    const d = await r.json();
    document.getElementById('sb-provider').textContent = d.provider || '—';
    document.getElementById('sb-model').textContent = (d.model || '—').split('/').pop();
  } catch(e) {}
}

function showPanel(name) {
  document.querySelectorAll('.panel').forEach(p => p.classList.remove('active'));
  document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
  document.getElementById('panel-' + name).classList.add('active');
  event.currentTarget.classList.add('active');
  if (name === 'skills') loadSkills();
  if (name === 'history') loadHistory();
}

function updateTokenCount() {
  const approx = Math.round(totalChars / 4);
  tokenCount.textContent = approx.toLocaleString() + ' tokens';
}

function escapeHtml(str) {
  return str.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}

function renderMarkdown(text) {
  let html = escapeHtml(text);
  html = html.replace(/```(\w*)\n?([\s\S]*?)```/g, (_, lang, code) => {
    return `<pre><code>${code.trim()}</code></pre>`;
  });
  html = html.replace(/`([^`]+)`/g, '<code>$1</code>');
  html = html.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
  html = html.replace(/\*(.*?)\*/g, '<em>$1</em>');
  html = html.replace(/\n/g, '<br>');
  return html;
}

function appendUserMsg(text) {
  const div = document.createElement('div');
  div.className = 'msg user';
  div.innerHTML = `<div class="msg-label">you</div><div class="msg-bubble">${escapeHtml(text).replace(/\n/g,'<br>')}</div>`;
  chatMessages.appendChild(div);
  scrollBottom();
  totalChars += text.length;
  updateTokenCount();
  return div;
}

function appendTyping() {
  const div = document.createElement('div');
  div.className = 'msg assistant';
  div.innerHTML = `<div class="msg-label">nexus</div><div class="typing-indicator"><div class="typing-dot"></div><div class="typing-dot"></div><div class="typing-dot"></div></div>`;
  chatMessages.appendChild(div);
  scrollBottom();
  return div;
}

function appendAssistantMsg(text) {
  const div = document.createElement('div');
  div.className = 'msg assistant';
  div.innerHTML = `<div class="msg-label">nexus</div><div class="msg-bubble">${renderMarkdown(text)}</div>`;
  chatMessages.appendChild(div);
  scrollBottom();
  totalChars += text.length;
  updateTokenCount();
  return div;
}

function appendExecBlock(cmd, output) {
  const div = document.createElement('div');
  div.className = 'msg execution';
  div.innerHTML = `
    <div class="exec-block">
      <div class="exec-header">
        <span class="exec-label">EXEC</span>
        <span class="exec-cmd">$ ${escapeHtml(cmd)}</span>
      </div>
      <div class="exec-output">${escapeHtml(output || '(no output)')}</div>
    </div>`;
  chatMessages.appendChild(div);
  scrollBottom();
  return div;
}

function appendSystemNote(text) {
  const div = document.createElement('div');
  div.className = 'msg system-note';
  div.innerHTML = `<div class="msg-bubble">${escapeHtml(text)}</div>`;
  chatMessages.appendChild(div);
  scrollBottom();
}

function scrollBottom() {
  chatMessages.scrollTop = chatMessages.scrollHeight;
}

async function sendMessage() {
  const text = chatInput.value.trim();
  if (!text || sendBtn.disabled) return;

  appendUserMsg(text);
  chatInput.value = '';
  chatInput.style.height = 'auto';
  chatInput.focus();
  sendBtn.disabled = true;

  const typingEl = appendTyping();

  try {
    const response = await fetch('/api/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message: text })
    });

    if (!response.ok) {
      typingEl.remove();
      appendSystemNote('Error: ' + response.statusText);
      sendBtn.disabled = false;
      return;
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder('utf-8');
    let assistantEl = null;
    let assistantText = '';
    let pendingExecCmd = null;
    let firstChunk = true;

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      const raw = decoder.decode(value, { stream: true });
      const lines = raw.split('\n').filter(l => l.trim());

      for (const line of lines) {
        let data;
        try { data = JSON.parse(line); } catch { continue; }

        if (data.type === 'chunk') {
          if (firstChunk) {
            typingEl.remove();
            firstChunk = false;
          }
          if (!assistantEl) {
            assistantEl = appendAssistantMsg('');
            assistantText = '';
          }
          assistantText += data.content;
          const bubble = assistantEl.querySelector('.msg-bubble');
          if (bubble) bubble.innerHTML = renderMarkdown(assistantText);
          scrollBottom();

        } else if (data.type === 'execution_start') {
          assistantEl = null;
          pendingExecCmd = data.command;
          appendSystemNote('Executing: ' + data.command);

        } else if (data.type === 'execution_result') {
          appendExecBlock(data.command || pendingExecCmd || '', data.output || '');
          assistantEl = null;
          assistantText = '';

        } else if (data.type === 'error') {
          if (firstChunk) { typingEl.remove(); firstChunk = false; }
          appendSystemNote('Error: ' + data.content);

        } else if (data.type === 'done') {
          if (firstChunk) { typingEl.remove(); firstChunk = false; }
        }
      }
    }

  } catch(e) {
    typingEl.remove();
    appendSystemNote('Connection failed: ' + e.message);
  }

  sendBtn.disabled = false;
  chatInput.focus();
}

async function clearChat() {
  try {
    await fetch('/api/clear', { method: 'POST' });
  } catch(e) {}
  chatMessages.innerHTML = `
    <div class="welcome-banner">
      <div class="welcome-title">&gt; Context cleared</div>
      <div class="welcome-sub">Conversation history has been reset.</div>
    </div>`;
  totalChars = 0;
  updateTokenCount();
}

async function exportChat() {
  try {
    const r = await fetch('/api/history');
    const d = await r.json();
    const lines = ['# OpenNexus Conversation Export\n'];
    for (const msg of d.history) {
      lines.push(`## ${msg.role.toUpperCase()}\n\n${msg.content}\n`);
    }
    const blob = new Blob([lines.join('\n')], { type: 'text/markdown' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'opennexus-export.md';
    a.click();
    URL.revokeObjectURL(url);
  } catch(e) {
    appendSystemNote('Export failed: ' + e.message);
  }
}

async function loadSkills() {
  const grid = document.getElementById('skills-grid');
  grid.innerHTML = '<div class="empty-state">Loading...</div>';
  try {
    const r = await fetch('/api/skills');
    const d = await r.json();
    if (!d.skills || d.skills.length === 0) {
      grid.innerHTML = '<div class="empty-state">No skills generated yet. Start chatting to build skills automatically.</div>';
      return;
    }
    grid.innerHTML = '';
    for (const s of d.skills) {
      const card = document.createElement('div');
      card.className = 'skill-card';
      const keywords = (s.trigger_keywords || []).slice(0,5).map(k => `<span class="skill-keyword">${escapeHtml(k)}</span>`).join('');
      card.innerHTML = `
        <div class="skill-card-header">
          <div class="skill-name">${escapeHtml(s.name)}</div>
          <div class="skill-uses">${s.use_count || 0}x</div>
        </div>
        <div class="skill-desc">${escapeHtml(s.description || '')}</div>
        <div class="skill-keywords">${keywords}</div>
        <div style="display:flex;justify-content:space-between;align-items:center">
          <span class="skill-id">${s.id.slice(0,8)}</span>
          <button class="skill-delete" onclick="deleteSkill('${s.id}', this)">Delete</button>
        </div>`;
      grid.appendChild(card);
    }
  } catch(e) {
    grid.innerHTML = '<div class="empty-state">Failed to load skills.</div>';
  }
}

async function deleteSkill(id, btn) {
  btn.textContent = '...';
  try {
    await fetch('/api/skills/' + id, { method: 'DELETE' });
    btn.closest('.skill-card').remove();
  } catch(e) {
    btn.textContent = 'Error';
  }
}

async function loadHistory() {
  const list = document.getElementById('history-list');
  list.innerHTML = '<div class="empty-state">Loading...</div>';
  try {
    const r = await fetch('/api/history');
    const d = await r.json();
    if (!d.history || d.history.length === 0) {
      list.innerHTML = '<div class="empty-state">No conversation history yet.</div>';
      return;
    }
    list.innerHTML = '';
    for (const msg of d.history) {
      const item = document.createElement('div');
      item.className = 'history-item';
      const preview = (msg.content || '').slice(0, 300) + (msg.content.length > 300 ? '...' : '');
      item.innerHTML = `
        <span class="history-role ${msg.role}">${msg.role}</span>
        <div class="history-content">${escapeHtml(preview)}</div>`;
      list.appendChild(item);
    }
  } catch(e) {
    list.innerHTML = '<div class="empty-state">Failed to load history.</div>';
  }
}

chatInput.addEventListener('keydown', e => {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault();
    sendMessage();
  }
});

chatInput.addEventListener('input', () => {
  chatInput.style.height = 'auto';
  chatInput.style.height = Math.min(chatInput.scrollHeight, 140) + 'px';
});

loadInfo();
