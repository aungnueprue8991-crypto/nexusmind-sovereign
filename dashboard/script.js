const chatMessages = document.getElementById('chatMessages');
const sendBtn = document.getElementById('sendBtn');
const chatInput = document.getElementById('chatInput');

// Navigation
document.querySelectorAll('.nav-btn').forEach(btn => {
    btn.addEventListener('click', () => {
        document.querySelectorAll('.nav-btn').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        document.querySelectorAll('.panel').forEach(p => p.classList.remove('active'));
        const panelId = `panel-${btn.dataset.panel}`;
        const target = document.getElementById(panelId);
        if (target) target.classList.add('active');
    });
});

// Chat Logic
function addMessage(role, content) {
    const div = document.createElement('div');
    div.className = `message ${role}`;
    div.innerHTML = `<div class="avatar">${role==='user'?'👤':'🧠'}</div><div class="bubble">${content}</div>`;
    chatMessages.appendChild(div);
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

sendBtn.addEventListener('click', async () => {
    const text = chatInput.value;
    if (!text || sendBtn.disabled) return;
    
    addMessage('user', text);
    chatInput.value = '';
    
    sendBtn.disabled = true;
    sendBtn.innerText = "Thinking...";
    
    try {
        const res = await fetch('../message', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({message: text})
        });
        const data = await res.json();
        addMessage('assistant', data.reply || "No response received.");
    } catch (err) {
        addMessage('assistant', `⚠️ System Error: ${err.message}. Check API key.`);
    } finally {
        sendBtn.disabled = false;
        sendBtn.innerText = "Send";
    }
});

chatInput.addEventListener('keypress', (e) => { if (e.key === 'Enter') sendBtn.click(); });

// Stats Logic
document.getElementById('refreshStats').addEventListener('click', async () => {
    const btn = document.getElementById('refreshStats');
    btn.innerText = "Loading...";
    try {
        const res = await fetch('../stats');
        const data = await res.json();
        let html = `<h3>Budget Remaining: ${data.budget_remaining}</h3><ul class="stats-list">`;
        for (const [provider, usage] of Object.entries(data.llm_usage)) {
            html += `<li><strong>${provider}:</strong> ${usage.used} / ${usage.limit} (${usage.pct}%)</li>`;
        }
        html += `</ul><p>Memory Size: ${data.memory_size} facts</p>`;
        document.getElementById('statsContent').innerHTML = html;
    } catch (err) {
        document.getElementById('statsContent').innerHTML = `<p class="error">Failed to load stats: ${err.message}</p>`;
    } finally {
        btn.innerText = "Refresh";
    }
});

// Memory Logic
document.getElementById('memoryForm').addEventListener('submit', async (e) => {
    e.preventDefault();
    const query = document.getElementById('memoryQuery').value;
    const box = document.getElementById('memoryResults');
    box.innerHTML = "Searching...";
    try {
        const res = await fetch('../memory/recall', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({query: query})
        });
        const data = await res.json();
        let html = '<h4>Facts</h4><ul>' + (data.facts.map(f => `<li>${f}</li>`).join('') || "None") + '</ul>';
        html += '<h4>Skills</h4><ul>' + (data.skills.map(s => `<li>${s}</li>`).join('') || "None") + '</ul>';
        box.innerHTML = html;
    } catch (err) {
        box.innerHTML = `<p class="error">Search failed: ${err.message}</p>`;
    }
});

// Terminal Logic
document.getElementById('runTerminalBtn').addEventListener('click', async () => {
    const code = document.getElementById('terminalInput').value;
    const output = document.getElementById('terminalOutput');
    output.innerHTML += `\n>>> ${code}`;
    try {
        const res = await fetch('../code/execute', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({code: code})
        });
        const data = await res.json();
        output.innerHTML += `\n${data.output}`;
    } catch (err) {
        output.innerHTML += `\nError: ${err.message}`;
    }
    output.scrollTop = output.scrollHeight;
    document.getElementById('terminalInput').value = '';
});

// Dream Logic
document.getElementById('dreamOnlyBtn').addEventListener('click', async () => {
    const box = document.getElementById('dreamSynthResult');
    box.style.display = 'block';
    box.innerHTML = "Dreaming started...";
    const res = await fetch('../dream/now', {method: 'POST'});
    const data = await res.json();
    box.innerHTML = `Success: ${data.status}`;
});
