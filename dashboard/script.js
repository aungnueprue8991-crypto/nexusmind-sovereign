const API = '';
document.querySelectorAll('.nav-btn').forEach(btn => {
    btn.addEventListener('click', () => {
        document.querySelectorAll('.nav-btn').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        document.querySelectorAll('.panel').forEach(p => p.classList.remove('active'));
        document.getElementById(`panel-${btn.dataset.panel}`).classList.add('active');
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
    const res = await fetch('/message', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({message:text})});
    const data = await res.json();
    addMessage('assistant', data.reply);
});
