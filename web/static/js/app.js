const chatHistory = document.getElementById('chat-history');
const chatInput = document.getElementById('chat-input');
const sendBtn = document.getElementById('send-btn');

// Ask user for their user ID (for demo/authentication purposes in local)
let userId = localStorage.getItem('opennexus_user_id');
if (!userId) {
    userId = prompt("Enter your OpenNexus User ID:");
    localStorage.setItem('opennexus_user_id', userId);
}

function appendMessage(role, content) {
    const el = document.createElement('div');
    el.className = `message ${role}-msg`;
    if (role === 'execution') {
        el.textContent = content;
    } else {
        el.innerHTML = content.replace(/\n/g, '<br>');
    }
    chatHistory.appendChild(el);
    chatHistory.scrollTop = chatHistory.scrollHeight;
    return el;
}

async function sendMessage() {
    const text = chatInput.value.trim();
    if (!text) return;
    
    appendMessage('user', text);
    chatInput.value = '';
    chatInput.focus();

    try {
        const response = await fetch('/api/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ user_id: parseInt(userId), message: text })
        });
        
        if (!response.ok) {
            appendMessage('system', 'Error: ' + response.statusText);
            return;
        }

        const reader = response.body.getReader();
        const decoder = new TextDecoder('utf-8');
        let assistantEl = null;

        while (true) {
            const {done, value} = await reader.read();
            if (done) break;
            
            const chunk = decoder.decode(value, {stream: true});
            const lines = chunk.split('\n').filter(line => line.trim() !== '');
            
            for (const line of lines) {
                try {
                    const data = JSON.parse(line);
                    if (data.type === 'chunk') {
                        if (!assistantEl) {
                            assistantEl = appendMessage('assistant', '');
                        }
                        assistantEl.innerHTML += data.content.replace(/\n/g, '<br>');
                        chatHistory.scrollTop = chatHistory.scrollHeight;
                    } else if (data.type === 'execution_start') {
                        appendMessage('system', `Executing: ${data.command}`);
                        assistantEl = null; // start a new block after execution
                    } else if (data.type === 'execution_result') {
                        appendMessage('execution', data.output);
                    }
                } catch(e) {
                    console.error("Parse error", e, line);
                }
            }
        }
    } catch (e) {
        appendMessage('system', 'Connection failed.');
    }
}

sendBtn.addEventListener('click', sendMessage);
chatInput.addEventListener('keypress', (e) => {
    if (e.key === 'Enter') sendMessage();
});
