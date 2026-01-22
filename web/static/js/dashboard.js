/**
 * Dashboard status polling and log viewer logic
 */

document.addEventListener('DOMContentLoaded', function() {
    // Elements
    const statusIndicator = document.getElementById('status-indicator');
    const statusText = statusIndicator.querySelector('.status-text');
    const startBtn = document.getElementById('start-btn');
    const stopBtn = document.getElementById('stop-btn');
    const reinitBtn = document.getElementById('reinit-btn');
    const controlStatus = document.getElementById('control-status');
    const logContent = document.getElementById('log-content');
    const clearLogsBtn = document.getElementById('clear-logs-btn');
    const autoScrollCheckbox = document.getElementById('auto-scroll');

    let eventSource = null;
    let isRunning = false;

    // Update status indicator
    function updateStatus(status) {
        isRunning = status.running;

        statusIndicator.className = 'status-indicator ' + (isRunning ? 'running' : 'stopped');
        statusText.textContent = isRunning ? 'Running' : 'Stopped';

        startBtn.disabled = isRunning;
        stopBtn.disabled = !isRunning;
        reinitBtn.disabled = isRunning;
    }

    // Fetch current status
    async function fetchStatus() {
        try {
            const response = await fetch('/api/sync/status');
            const data = await response.json();
            updateStatus(data);
        } catch (error) {
            console.error('Error fetching status:', error);
        }
    }

    // Start sync
    startBtn.addEventListener('click', async function() {
        setLoading(startBtn, true);
        hideStatus(controlStatus);

        try {
            const response = await fetch('/api/sync/start', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({})
            });
            const data = await response.json();

            if (data.success) {
                showStatus(controlStatus, 'success', 'Sync daemon started (PID: ' + data.pid + ')');
                updateStatus({ running: true });
                startLogStream();
            } else {
                showStatus(controlStatus, 'error', data.error);
            }
        } catch (error) {
            showStatus(controlStatus, 'error', 'Network error: ' + error.message);
        } finally {
            setLoading(startBtn, false);
        }
    });

    // Stop sync
    stopBtn.addEventListener('click', async function() {
        setLoading(stopBtn, true);
        hideStatus(controlStatus);

        try {
            const response = await fetch('/api/sync/stop', {
                method: 'POST'
            });
            const data = await response.json();

            if (data.success) {
                showStatus(controlStatus, 'success', 'Sync daemon stopped');
                updateStatus({ running: false });
            } else {
                showStatus(controlStatus, 'error', data.error);
            }
        } catch (error) {
            showStatus(controlStatus, 'error', 'Network error: ' + error.message);
        } finally {
            setLoading(stopBtn, false);
        }
    });

    // Re-initialize
    reinitBtn.addEventListener('click', async function() {
        if (!confirm('This will remove the working directory and database schemas to reinitialize from scratch. Continue?')) {
            return;
        }

        setLoading(reinitBtn, true);
        hideStatus(controlStatus);

        try {
            const response = await fetch('/api/sync/start', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ force_init: true })
            });
            const data = await response.json();

            if (data.success) {
                showStatus(controlStatus, 'success', 'Sync daemon started with re-initialization (PID: ' + data.pid + ')');
                updateStatus({ running: true });
                startLogStream();
            } else {
                showStatus(controlStatus, 'error', data.error);
            }
        } catch (error) {
            showStatus(controlStatus, 'error', 'Network error: ' + error.message);
        } finally {
            setLoading(reinitBtn, false);
        }
    });

    // Clear logs
    clearLogsBtn.addEventListener('click', function() {
        logContent.innerHTML = '<p class="log-placeholder">Logs cleared. New logs will appear here...</p>';
    });

    // Log streaming via SSE
    function startLogStream() {
        if (eventSource) {
            eventSource.close();
        }

        eventSource = new EventSource('/api/logs/stream');

        eventSource.onmessage = function(event) {
            const data = JSON.parse(event.data);
            if (data.logs && data.logs.length > 0) {
                appendLogs(data.logs);
            }
        };

        eventSource.addEventListener('status', function(event) {
            const status = JSON.parse(event.data);
            updateStatus(status);

            // Stop stream if daemon stopped
            if (!status.running && eventSource) {
                // Keep stream open to catch final logs
            }
        });

        eventSource.onerror = function(error) {
            console.error('SSE error:', error);
            // Reconnect after a delay
            setTimeout(function() {
                if (isRunning) {
                    startLogStream();
                }
            }, 3000);
        };
    }

    function appendLogs(logs) {
        // Remove placeholder if present
        const placeholder = logContent.querySelector('.log-placeholder');
        if (placeholder) {
            placeholder.remove();
        }

        logs.forEach(line => {
            const logLine = document.createElement('p');
            logLine.className = 'log-line';
            logLine.textContent = line;
            logContent.appendChild(logLine);
        });

        // Auto-scroll
        if (autoScrollCheckbox.checked) {
            logContent.scrollTop = logContent.scrollHeight;
        }

        // Limit displayed lines
        while (logContent.children.length > 1000) {
            logContent.removeChild(logContent.firstChild);
        }
    }

    // Load recent logs
    async function loadRecentLogs() {
        try {
            const response = await fetch('/api/logs/recent?n=100');
            const data = await response.json();

            if (data.success && data.logs.length > 0) {
                logContent.innerHTML = '';
                appendLogs(data.logs);
            }
        } catch (error) {
            console.error('Error loading recent logs:', error);
        }
    }

    // Utility functions
    function setLoading(btn, loading) {
        const text = btn.querySelector('.btn-text');
        const spinner = btn.querySelector('.btn-spinner');
        if (loading) {
            text.style.display = 'none';
            spinner.style.display = 'inline-block';
            btn.disabled = true;
        } else {
            text.style.display = 'inline';
            spinner.style.display = 'none';
            btn.disabled = false;
        }
    }

    function showStatus(element, type, message) {
        element.className = 'status-message ' + type;
        element.textContent = message;
        element.style.display = 'block';
    }

    function hideStatus(element) {
        element.style.display = 'none';
        element.className = 'status-message';
    }

    // Poll status periodically
    function startStatusPolling() {
        fetchStatus();
        setInterval(fetchStatus, 5000);
    }

    // Initialize
    startStatusPolling();
    loadRecentLogs();

    // Start log stream if already running
    fetchStatus().then(() => {
        if (isRunning) {
            startLogStream();
        }
    });
});
