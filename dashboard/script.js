const API = window.location.origin;
console.log("NexusMind Dashboard linked to:", API);

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

const chatMessages = document.getElementById('chatMessages');
const sendBtn = document.getElementById('sendBtn');
const chatInput = document.getElementById('chatInput');

function addMessage(role, content) {
    const div = document.createElement('div');
    div.className = `message ${role}`;
    div.innerHTML = `<div class="avatar">${role==='user'?'👤':'🧠'}</div><div class="bubble">${content}</div>`;
    chatMessages.appendChild(div);
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

sendBtn.addEventListener('click', async () => {
    const text = chatInput.value;
    if (!text) return;
    addMessage('user', text);
    chatInput.value = '';
    
    try {
        const res = await fetch(`${API}/message`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({message: text})
        });
        
        if (!res.ok) throw new Error(`Server Error: ${res.status}`);
        
        const data = await res.json();
        addMessage('assistant', data.reply || "I received your message but have no reply.");
    } catch (err) {
        console.error("Fetch failed:", err);
        addMessage('assistant', `⚠️ Connection Error: ${err.message}. Check Hugging Face Logs.`);
    }
});

// Auto-focus input
chatInput.addEventListener('keypress', (e) => {
    if (e.key === 'Enter') sendBtn.click();
});
