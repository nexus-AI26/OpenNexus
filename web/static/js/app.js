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

function showPanel(name, btn) {
  document.querySelectorAll('.panel').forEach(p => p.classList.remove('active'));
  document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
  document.getElementById('panel-' + name).classList.add('active');
  if (btn) btn.classList.add('active');
  if (name === 'skills') loadSkills();
  if (name === 'history') loadHistory();
  if (name === 'model') loadModelPanel();
  if (name === 'system') loadSystemPanel();
  if (name === 'tokens') loadTokensPanel();
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

function appendAssistantStreamingShell() {
  const div = document.createElement('div');
  div.className = 'msg assistant';
  div.innerHTML =
    `<div class="msg-label">nexus</div><div class="msg-bubble streaming">` +
    `<span class="stream-md"></span><span class="stream-caret" aria-hidden="true"></span></div>`;
  chatMessages.appendChild(div);
  scrollBottom();
  return div;
}

function finalizeStreamingBubble(assistantRow) {
  if (!assistantRow) return;
  const bubble = assistantRow.querySelector('.msg-bubble');
  const caret = assistantRow.querySelector('.stream-caret');
  if (caret) caret.remove();
  if (bubble) bubble.classList.remove('streaming');
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

  const lower = text.toLowerCase();
  if (lower === '/stop') {
    chatInput.value = '';
    chatInput.style.height = 'auto';
    appendSystemNote('Stop requested…');
    try {
      await fetch('/api/chat/stop', { method: 'POST' });
    } catch (e) {
      appendSystemNote('Stop request failed: ' + e.message);
    }
    chatInput.focus();
    return;
  }
  const waitMatch = text.match(/^\/wait\s*(.*)$/i);
  if (waitMatch) {
    const note = (waitMatch[1] || '').trim();
    chatInput.value = '';
    chatInput.style.height = 'auto';
    if (!note) {
      appendSystemNote('Usage: /wait <your note>');
      chatInput.focus();
      return;
    }
    try {
      const r = await fetch('/api/chat/wait', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: note }),
      });
      if (r.ok) appendSystemNote('Note queued for the current reply.');
      else appendSystemNote('Could not queue note.');
    } catch (e) {
      appendSystemNote('Could not queue note: ' + e.message);
    }
    chatInput.focus();
    return;
  }

  appendUserMsg(text);
  chatInput.value = '';
  chatInput.style.height = 'auto';
  chatInput.focus();
  sendBtn.disabled = true;

  let assistantEl = appendAssistantStreamingShell();
  let assistantText = '';

  try {
    const response = await fetch('/api/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message: text })
    });

    if (!response.ok) {
      assistantEl.remove();
      assistantEl = null;
      appendSystemNote('Error: ' + response.statusText);
      sendBtn.disabled = false;
      return;
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder('utf-8');
    let pendingExecCmd = null;

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      const raw = decoder.decode(value, { stream: true });
      const lines = raw.split('\n').filter(l => l.trim());

      for (const line of lines) {
        let data;
        try { data = JSON.parse(line); } catch { continue; }

        if (data.type === 'chunk') {
          if (!assistantEl) {
            assistantEl = appendAssistantStreamingShell();
            assistantText = '';
          }
          assistantText += data.content;
          const md = assistantEl.querySelector('.stream-md');
          const caret = assistantEl.querySelector('.stream-caret');
          if (md) md.innerHTML = renderMarkdown(assistantText);
          if (caret && md && md.nextSibling !== caret) md.parentNode.appendChild(caret);
          totalChars += (data.content || '').length;
          updateTokenCount();
          scrollBottom();

        } else if (data.type === 'execution_start') {
          finalizeStreamingBubble(assistantEl);
          assistantEl = null;
          assistantText = '';
          pendingExecCmd = data.command;
          appendSystemNote('Executing: ' + data.command);

        } else if (data.type === 'execution_result') {
          appendExecBlock(data.command || pendingExecCmd || '', data.output || '');
          assistantEl = null;
          assistantText = '';

        } else if (data.type === 'error') {
          if (assistantEl && !assistantText) {
            assistantEl.remove();
            assistantEl = null;
          } else {
            finalizeStreamingBubble(assistantEl);
          }
          appendSystemNote('Error: ' + data.content);

        } else if (data.type === 'stopped') {
          finalizeStreamingBubble(assistantEl);
          assistantEl = null;
          assistantText = '';
          appendSystemNote('Stopped by user.');

        } else if (data.type === 'done') {
          if (assistantEl && !assistantText.trim()) {
            assistantEl.remove();
            assistantEl = null;
          } else {
            finalizeStreamingBubble(assistantEl);
          }
        }
      }
    }

  } catch(e) {
    if (assistantEl && !assistantText) assistantEl.remove();
    else finalizeStreamingBubble(assistantEl);
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

async function loadModelPanel() {
  const sel = document.getElementById('model-provider');
  const nameEl = document.getElementById('model-name');
  const cat = document.getElementById('model-catalog');
  cat.innerHTML = '<div class="empty-state">Loading…</div>';
  try {
    const [r1, r2] = await Promise.all([fetch('/api/providers'), fetch('/api/model')]);
    const catalog = await r1.json();
    const cur = await r2.json();
    sel.innerHTML = '';
    for (const p of catalog.providers || []) {
      const o = document.createElement('option');
      o.value = p.id;
      o.textContent = p.id + (p.configured ? '' : ' (no key)');
      sel.appendChild(o);
    }
    if (cur.provider && [...sel.options].some(x => x.value === cur.provider)) {
      sel.value = cur.provider;
    }
    nameEl.value = cur.model || '';
    cat.innerHTML = '';
    const t = document.createElement('div');
    t.className = 'form-hint';
    t.style.marginBottom = '0.5rem';
    t.textContent = 'Provider defaults from config:';
    cat.appendChild(t);
    for (const p of catalog.providers || []) {
      const row = document.createElement('div');
      row.className = 'row';
      row.textContent = `${p.id}: ${p.default_model || '—'}`;
      cat.appendChild(row);
    }
  } catch (e) {
    cat.innerHTML = '<div class="empty-state">Failed to load model panel.</div>';
  }
}

async function saveModel() {
  const provider = document.getElementById('model-provider').value;
  const model = document.getElementById('model-name').value.trim();
  if (!model) {
    appendSystemNote('Model ID is required.');
    return;
  }
  try {
    const r = await fetch('/api/model', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ provider, model }),
    });
    if (!r.ok) {
      let msg = r.statusText;
      try {
        const err = await r.json();
        if (typeof err.detail === 'string') msg = err.detail;
      } catch (_) {}
      appendSystemNote('Model save failed: ' + msg);
      return;
    }
    await loadInfo();
    appendSystemNote('Model updated.');
  } catch (e) {
    appendSystemNote('Model save failed: ' + e.message);
  }
}

async function loadSystemPanel() {
  try {
    const r = await fetch('/api/system-prompt');
    const d = await r.json();
    document.getElementById('system-prompt-text').value = d.prompt || '';
  } catch (e) {}
}

async function saveSystemPrompt() {
  const prompt = document.getElementById('system-prompt-text').value;
  try {
    const r = await fetch('/api/system-prompt', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ prompt }),
    });
    if (!r.ok) {
      appendSystemNote('Could not save system prompt.');
      return;
    }
    appendSystemNote('System prompt updated (session).');
  } catch (e) {
    appendSystemNote('Error: ' + e.message);
  }
}

async function loadTokensPanel() {
  try {
    const r = await fetch('/api/tokens');
    const d = await r.json();
    document.getElementById('tok-messages').textContent =
      d.messages != null ? String(d.messages) : '—';
    document.getElementById('tok-chars').textContent =
      d.chars != null ? d.chars.toLocaleString() : '—';
    document.getElementById('tok-approx').textContent =
      d.approx_tokens != null ? d.approx_tokens.toLocaleString() : '—';
  } catch (e) {}
}

async function runWebSearch() {
  const q = document.getElementById('search-query').value.trim();
  const box = document.getElementById('search-results');
  if (!q) return;
  box.innerHTML = '<div class="empty-state">Searching…</div>';
  try {
    const r = await fetch('/api/search', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ query: q }),
    });
    const d = await r.json();
    if (!d.results || !d.results.length) {
      box.innerHTML = '<div class="empty-state">No results.</div>';
      return;
    }
    box.innerHTML = '';
    for (const item of d.results) {
      const div = document.createElement('div');
      div.className = 'search-hit';
      const title = escapeHtml(item.title || '');
      const url = escapeHtml(item.url || '#');
      const snip = escapeHtml(item.snippet || '');
      div.innerHTML =
        `<a href="${url}" target="_blank" rel="noopener noreferrer">${title}</a>` +
        `<div class="search-snippet">${snip}</div>`;
      box.appendChild(div);
    }
  } catch (e) {
    box.innerHTML =
      '<div class="empty-state">Search failed: ' + escapeHtml(e.message) + '</div>';
  }
}

const searchQueryEl = document.getElementById('search-query');
if (searchQueryEl) {
  searchQueryEl.addEventListener('keydown', e => {
    if (e.key === 'Enter') {
      e.preventDefault();
      runWebSearch();
    }
  });
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
