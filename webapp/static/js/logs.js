// logs.js - client-side logic for /logs page
let rawLog = document.getElementById('logContent').textContent;
const logContent = document.getElementById('logContent');
const searchBox = document.getElementById('logSearch');
const autoRefresh = document.getElementById('autoRefresh');
const logStatus = document.getElementById('logStatus');
let refreshTimer = null;

function scrollLogToBottom() {
    logContent.parentElement.scrollTop = logContent.parentElement.scrollHeight;
}

function filterLog() {
    const q = searchBox.value.toLowerCase();
    if (!q) {
        logContent.textContent = rawLog;
        logStatus.textContent = '';
        scrollLogToBottom();
        return;
    }
    const lines = rawLog.split('\n');
    const filtered = lines.filter(line => line.toLowerCase().includes(q));
    logContent.textContent = filtered.join('\n');
    logStatus.textContent = `${filtered.length} of ${lines.length} lines shown`;
    scrollLogToBottom();
}

searchBox.addEventListener('input', filterLog);

function fetchLog() {
    fetch(window.location.pathname)
        .then(r => r.text())
        .then(html => {
            // Extract log_content from the HTML (simple, not robust to template changes)
            const match = html.match(/<pre id="logContent"[^>]*>([\s\S]*?)<\/pre>/);
            if (match) {
                rawLog = match[1].replace(/&lt;/g, '<').replace(/&gt;/g, '>').replace(/&amp;/g, '&');
                filterLog();
            }
        });
}

autoRefresh.addEventListener('change', function() {
    if (autoRefresh.checked) {
        refreshTimer = setInterval(fetchLog, 5000);
        logStatus.textContent = 'Auto-refreshing every 5s';
    } else {
        clearInterval(refreshTimer);
        logStatus.textContent = '';
    }
});

// Scroll to bottom on initial load
window.onload = function() {
    scrollLogToBottom();
};
