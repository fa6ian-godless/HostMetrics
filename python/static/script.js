// ---------- State ----------
let currentServerId = null;
let serversList = [];

// ---------- Helpers ----------
function buildGaugeHtml(usagePercent, title, subtitle) {
    const percent = Number(usagePercent) || 0;
    const isHigh = percent > 80;
    const circleLength = 2 * Math.PI * 58;
    const dashOffset = circleLength - (circleLength * Math.min(percent, 100) / 100);

    return `
    <div class="gauge-card">
    <div class="gauge">
    <svg width="130" height="130" viewBox="0 0 140 140">
    <circle class="bg" cx="70" cy="70" r="58"></circle>
    <circle class="progress ${isHigh ? 'high' : ''}"
    cx="70" cy="70" r="58"
    stroke-dasharray="${circleLength}"
    stroke-dashoffset="${dashOffset}"></circle>
    </svg>
    <div class="percent ${isHigh ? 'high' : ''}">${Math.round(percent)}%</div>
    </div>
    <div class="gauge-label">${title}</div>
    <div class="gauge-sub">${subtitle || ''}</div>
    </div>
    `;
}

function checkServerOnline(lastSeenTime) {
    if (!lastSeenTime) return false;
    const timestamp = new Date(
        lastSeenTime + (lastSeenTime.includes('Z') ? '' : 'Z')
    ).getTime();
    // онлайн, если данные были меньше 30 секунд назад
    return (Date.now() - timestamp) < 30_000;
}

function formatDateTime(dateString) {
    if (!dateString) return 'нет данных';
    try {
        const date = new Date(
            dateString + (dateString.includes('Z') ? '' : 'Z')
        );
        return date.toLocaleString('ru-RU');
    } catch {
        return dateString;
    }
}

// ---------- Render sidebar ----------
function renderServersList(servers) {
    const listElement = document.getElementById('servers-list');
    serversList = servers;

    if (!servers.length) {
        listElement.innerHTML = '<div class="empty-state">Нет серверов</div>';
        return;
    }

    listElement.innerHTML = servers.map(server => {
        const isOnline = checkServerOnline(server.last_seen);
        const isActive = currentServerId === server.id ? 'active' : '';
        const statusClass = isOnline ? 'online' : 'offline';

        return `
        <div class="server-item ${isActive}" data-id="${server.id}">
        <span class="status-dot ${statusClass}"></span>
        <span class="server-name" title="${server.name}">${server.name}</span>
        </div>
        `;
    }).join('');

    listElement.querySelectorAll('.server-item').forEach(itemElement => {
        itemElement.addEventListener('click', () => {
            const serverId = Number(itemElement.dataset.id);
            selectServer(serverId);
        });
    });
}

// ---------- Select server & show metrics ----------
async function selectServer(serverId) {
    currentServerId = serverId;

    document.querySelectorAll('.server-item').forEach(itemElement => {
        itemElement.classList.toggle(
            'active',
            Number(itemElement.dataset.id) === serverId
        );
    });

    await loadServerMetrics(serverId);
}

async function loadServerMetrics(serverId) {
    const contentElement = document.getElementById('content');

    try {
        const response = await fetch(`/servers/${serverId}/metrics`);

        if (!response.ok) {
            if (response.status === 404) {
                contentElement.innerHTML = `
                <div class="placeholder">
                <div class="placeholder-icon">⏳</div>
                <div class="placeholder-text">Метрики ещё не поступали</div>
                </div>`;
                return;
            }
            throw new Error(`HTTP ${response.status}`);
        }

        const metrics = await response.json();
        const server = serversList.find(item => item.id === serverId);
        const serverName = server ? server.name : `Server #${serverId}`;

        contentElement.innerHTML = `
        <div class="detail-header">
        <div class="detail-title">${serverName}</div>
        <div class="detail-meta">обновлено: ${formatDateTime(metrics.created_at)}</div>
        </div>

        <div class="gauges">
        ${buildGaugeHtml(
            metrics.cpu_percent,
            'ЦПУ',
            `${metrics.cpu_cores || '—'} Core • ${metrics.cpu_frequency || '—'}`
        )}
        ${buildGaugeHtml(
            metrics.memory_percent,
            'ОЗУ',
            `${metrics.memory_used || '—'} / ${metrics.memory_total || '—'}`
        )}
        ${buildGaugeHtml(
            metrics.swap_percent,
            'Файл подкачки',
            `${metrics.swap_used || '—'} / ${metrics.swap_total || '—'}`
        )}
        ${buildGaugeHtml(
            metrics.storage_percent,
            'Диск',
            `${metrics.storage_used || '—'} / ${metrics.storage_total || '—'}`
        )}
        </div>

        <div class="section">
        <div class="section-header">Время работы</div>
        <div class="uptime">${metrics.uptime || '—'}</div>
        </div>

        <div class="section">
        <div class="section-header">Скорость передачи трафика</div>
        <div class="network-info">
        <div>
        <strong>↑ Отправка</strong>
        <span class="network-value">${metrics.upload_speed || '—'}</span>
        </div>
        <div>
        <strong>↓ Загрузка</strong>
        <span class="network-value">${metrics.download_speed || '—'}</span>
        </div>
        </div>
        </div>

        <div class="section">
        <div class="section-header">Общий объём трафика</div>
        <div class="network-info">
        <div>
        <strong>Отправлено</strong>
        <span class="network-value">${metrics.total_sent || '—'}</span>
        </div>
        <div>
        <strong>Получено</strong>
        <span class="network-value">${metrics.total_received || '—'}</span>
        </div>
        </div>
        </div>
        `;
    } catch (error) {
        console.error('Ошибка загрузки метрик:', error);
        contentElement.innerHTML = `
        <div class="placeholder">
        <div class="placeholder-icon">⚠️</div>
        <div class="placeholder-text">Не удалось загрузить метрики</div>
        </div>`;
    }
}

// ---------- Polling ----------
async function refreshServers() {
    try {
        const response = await fetch('/servers');
        if (!response.ok) return;

        const servers = await response.json();
        renderServersList(servers);

        if (currentServerId !== null) {
            const serverExists = servers.some(server => server.id === currentServerId);

            if (serverExists) {
                await loadServerMetrics(currentServerId);
            } else {
                currentServerId = null;
                document.getElementById('content').innerHTML = `
                <div class="placeholder">
                <div class="placeholder-icon">🖥</div>
                <div class="placeholder-text">Выберите сервер в списке слева</div>
                </div>`;
            }
        }
    } catch (error) {
        console.error('Ошибка получения списка серверов:', error);
    }
}

// ---------- Init ----------
refreshServers();
setInterval(refreshServers, 3000);
