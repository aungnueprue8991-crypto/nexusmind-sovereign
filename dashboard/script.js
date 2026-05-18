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
    if (!text || sendBtn.disabled) return;
    
    addMessage('user', text);
    chatInput.value = '';
    
    // UI Loading state
    sendBtn.disabled = true;
    sendBtn.innerText = "Thinking...";
    
    try {
        // Use relative path for HF compatibility
        const res = await fetch('../message', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({message: text})
        });
        
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        
        const data = await res.json();
        addMessage('assistant', data.reply || "No response received.");
    } catch (err) {
        console.error("Error:", err);
        addMessage('assistant', `⚠️ System Error: ${err.message}. Please check if GROQ_API_KEY is set in Space Secrets.`);
    } finally {
        sendBtn.disabled = false;
        sendBtn.innerText = "Send";
    }
});

chatInput.addEventListener('keypress', (e) => {
    if (e.key === 'Enter') sendBtn.click();
});
