const state = {
    csv: "",
    analysis: null,
    selectedIp: null,
    currentView: "overview",
    liveStatus: null,
    refreshTimer: null,
    lastNotificationKey: null,
    readAlertKeys: [],
    dataMode: "idle",
    machineFilters: {
        primaryClass: "all",
        activityType: "all",
        severity: "all",
    },
    refreshDebounce: null,
    analysisSource: null,
};

const CASABLANCA_TIMEZONE = "Africa/Casablanca";
const casablancaTimeFormatter = new Intl.DateTimeFormat("fr-FR", {
    hour: "2-digit",
    minute: "2-digit",
    timeZone: CASABLANCA_TIMEZONE,
});

const el = {
    thresholdInput: document.getElementById("thresholdInput"),
    thresholdValue: document.getElementById("thresholdValue"),
    sensitivityInput: document.getElementById("sensitivityInput"),
    contentView: document.getElementById("contentView"),
    liveMode: document.getElementById("liveMode"),
    liveHost: document.getElementById("liveHost"),
    livePort: document.getElementById("livePort"),
    startLiveBtn: document.getElementById("startLiveBtn"),
    stopLiveBtn: document.getElementById("stopLiveBtn"),
    liveStatus: document.getElementById("liveStatus"),
    notificationCount: document.getElementById("notificationCount"),
    toastStack: document.getElementById("toastStack"),
};

function config() {
    return {
        threshold: Number(el.thresholdInput.value),
        sensitivity: el.sensitivityInput.value,
    };
}

async function getJson(url, options = {}) {
    const response = await fetch(url, options);
    return response.json();
}

function severityBadge(severity) {
    return `<span class="badge ${severity}">${severity}</span>`;
}

function signalBadge(label) {
    return `<span>${label}</span>`;
}

function componentValue(machine, key) {
    if (key === "upload_download_ratio") {
        return Number(machine[key] || 0);
    }
    if (key === "periodicity") {
        return Number(machine[key] || 0);
    }
    return Number(machine[key] || 0);
}

function componentDisplay(machine, key) {
    const value = componentValue(machine, key);
    if (key === "upload_download_ratio" || key === "periodicity") {
        return value.toFixed(1);
    }
    return Math.round(value);
}

function componentIntensity(machine, key, maxValue) {
    const value = componentValue(machine, key);
    if (!maxValue || maxValue <= 0) {
        return 0.12;
    }
    return Math.max(0.12, Math.min(value / maxValue, 1));
}

function isNotificationRead(key) {
    return state.readAlertKeys.includes(key);
}

function actionableNotifications(notifications) {
    return (notifications || []).filter((item) => item.level !== "info");
}

function alertKey(alert) {
    return `${alert.machine_ip}|${alert.timestamp}|${alert.type}|${alert.score}`;
}

function currentUnreadAlerts() {
    const alerts = state.analysis?.alerts || [];
    return alerts.filter((item) => !isNotificationRead(alertKey(item)));
}

function markAlertRead(key) {
    if (!key || isNotificationRead(key)) {
        return;
    }
    state.readAlertKeys.push(key);
    updateNotificationCount();
}

function updateNotificationCount() {
    el.notificationCount.textContent = currentUnreadAlerts().length;
}

function reconcileReadNotifications() {
    const activeKeys = new Set((state.analysis?.alerts || []).map((item) => alertKey(item)));
    state.readAlertKeys = state.readAlertKeys.filter((key) => activeKeys.has(key));
}

function markCurrentAlertsRead() {
    const unread = currentUnreadAlerts();
    unread.forEach((item) => markAlertRead(alertKey(item)));
}

function riskColor(score) {
    if (score >= 60) {
        return "#e24b4a";
    }
    if (score >= 30) {
        return "#ba7517";
    }
    return "#1d9e75";
}

function formatTimeLabel(value) {
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) {
        return String(value).slice(11, 16) || String(value);
    }
    return casablancaTimeFormatter.format(date);
}

function linePath(points, width, height, padding, valueKey) {
    if (!points.length) {
        return "";
    }
    const innerWidth = width - padding.left - padding.right;
    const innerHeight = height - padding.top - padding.bottom;
    const xFor = (index) => {
        if (points.length === 1) {
            return padding.left + (innerWidth / 2);
        }
        return padding.left + ((innerWidth / (points.length - 1)) * index);
    };
    const yFor = (value) => padding.top + innerHeight - ((Number(value || 0) / 100) * innerHeight);
    return points.map((point, index) => `${index === 0 ? "M" : "L"} ${xFor(index).toFixed(2)} ${yFor(point[valueKey]).toFixed(2)}`).join(" ");
}

function buildRiskTimelineSvg(points) {
    if (!points.length) {
        return `<div class="empty">Aucune donnee temporelle disponible pour ce lot.</div>`;
    }
    const width = 720;
    const height = 260;
    const padding = { left: 44, right: 20, top: 18, bottom: 42 };
    const innerWidth = width - padding.left - padding.right;
    const innerHeight = height - padding.top - padding.bottom;
    const steps = [0, 25, 50, 75, 100];
    const maxAlerts = Math.max(...points.map((point) => Number(point.alert_machines || 0)), 1);
    const xFor = (index) => {
        if (points.length === 1) {
            return padding.left + (innerWidth / 2);
        }
        return padding.left + ((innerWidth / (points.length - 1)) * index);
    };
    const yForRisk = (value) => padding.top + innerHeight - ((Number(value || 0) / 100) * innerHeight);
    const alertBars = points.map((point, index) => {
        const barWidth = Math.max(16, Math.min(34, innerWidth / Math.max(points.length * 1.7, 1)));
        const barHeight = (Number(point.alert_machines || 0) / maxAlerts) * (innerHeight * 0.42);
        const x = xFor(index) - (barWidth / 2);
        const y = padding.top + innerHeight - barHeight;
        return `<rect x="${x.toFixed(2)}" y="${y.toFixed(2)}" width="${barWidth.toFixed(2)}" height="${barHeight.toFixed(2)}" rx="8" fill="rgba(186, 117, 23, 0.22)"></rect>`;
    }).join("");
    const avgPath = linePath(points, width, height, padding, "average_risk");
    const maxPath = linePath(points, width, height, padding, "max_risk");
    const dots = points.map((point, index) => {
        const x = xFor(index);
        const y = yForRisk(point.average_risk);
        return `<circle cx="${x.toFixed(2)}" cy="${y.toFixed(2)}" r="4.5" fill="${riskColor(point.average_risk)}" stroke="#ffffff" stroke-width="2"></circle>`;
    }).join("");
    const labels = points.map((point, index) => {
        const x = xFor(index);
        return `
            <text x="${x.toFixed(2)}" y="${height - 16}" text-anchor="middle" class="timeline-axis-label">${formatTimeLabel(point.timestamp)}</text>
            <text x="${x.toFixed(2)}" y="${height - 2}" text-anchor="middle" class="timeline-axis-sub">${point.active_machines} mach.</text>
        `;
    }).join("");
    const grid = steps.map((step) => {
        const y = yForRisk(step);
        return `
            <line x1="${padding.left}" y1="${y.toFixed(2)}" x2="${width - padding.right}" y2="${y.toFixed(2)}" class="timeline-grid-line"></line>
            <text x="${padding.left - 10}" y="${(y + 4).toFixed(2)}" text-anchor="end" class="timeline-axis-label">${step}</text>
        `;
    }).join("");
    return `
        <svg viewBox="0 0 ${width} ${height}" class="timeline-svg" role="img" aria-label="Evolution du risque dans le temps">
            ${grid}
            ${alertBars}
            <path d="${maxPath}" class="timeline-line timeline-line-secondary"></path>
            <path d="${avgPath}" class="timeline-line timeline-line-primary"></path>
            ${dots}
            ${labels}
        </svg>
    `;
}

function buildClassTimelineSvg(points) {
    if (!points.length) {
        return `<div class="empty">Aucune donnee temporelle disponible pour ce lot.</div>`;
    }
    const width = 720;
    const height = 260;
    const padding = { left: 44, right: 20, top: 18, bottom: 42 };
    const innerWidth = width - padding.left - padding.right;
    const innerHeight = height - padding.top - padding.bottom;
    const maxMachines = Math.max(...points.map((point) => Number(point.active_machines || 0)), 1);
    const xFor = (index) => {
        const step = innerWidth / Math.max(points.length, 1);
        return padding.left + (step * index) + (step * 0.18);
    };
    const barWidth = Math.max(18, Math.min(38, innerWidth / Math.max(points.length * 1.8, 1)));
    const yForCount = (value) => padding.top + innerHeight - ((Number(value || 0) / maxMachines) * innerHeight);
    const bars = points.map((point, index) => {
        const x = xFor(index);
        const normalHeight = (Number(point.normal_machines || 0) / maxMachines) * innerHeight;
        const suspectHeight = (Number(point.suspect_machines || 0) / maxMachines) * innerHeight;
        const botnetHeight = (Number(point.botnet_machines || 0) / maxMachines) * innerHeight;
        const baseY = padding.top + innerHeight;
        const normalY = baseY - normalHeight;
        const suspectY = normalY - suspectHeight;
        const botnetY = suspectY - botnetHeight;
        return `
            <rect x="${x.toFixed(2)}" y="${normalY.toFixed(2)}" width="${barWidth.toFixed(2)}" height="${normalHeight.toFixed(2)}" rx="8" fill="#1d9e75"></rect>
            <rect x="${x.toFixed(2)}" y="${suspectY.toFixed(2)}" width="${barWidth.toFixed(2)}" height="${suspectHeight.toFixed(2)}" rx="8" fill="#ba7517"></rect>
            <rect x="${x.toFixed(2)}" y="${botnetY.toFixed(2)}" width="${barWidth.toFixed(2)}" height="${botnetHeight.toFixed(2)}" rx="8" fill="#e24b4a"></rect>
            <text x="${(x + (barWidth / 2)).toFixed(2)}" y="${height - 16}" text-anchor="middle" class="timeline-axis-label">${formatTimeLabel(point.timestamp)}</text>
        `;
    }).join("");
    const steps = [0, Math.ceil(maxMachines / 2), maxMachines];
    const grid = [...new Set(steps)].map((step) => {
        const y = yForCount(step);
        return `
            <line x1="${padding.left}" y1="${y.toFixed(2)}" x2="${width - padding.right}" y2="${y.toFixed(2)}" class="timeline-grid-line"></line>
            <text x="${padding.left - 10}" y="${(y + 4).toFixed(2)}" text-anchor="end" class="timeline-axis-label">${step}</text>
        `;
    }).join("");
    return `
        <svg viewBox="0 0 ${width} ${height}" class="timeline-svg" role="img" aria-label="Repartition des classes dans le temps">
            ${grid}
            ${bars}
        </svg>
    `;
}

function setView(view) {
    state.currentView = view;
    document.querySelectorAll(".menu-item").forEach((button) => {
        button.classList.toggle("active", button.dataset.view === view);
    });
    if (view === "alerts") {
        markCurrentAlertsRead();
    }
    render();
}

function updateThresholdLabel() {
    el.thresholdValue.textContent = el.thresholdInput.value;
}

async function loadSample() {
    const payload = await getJson("/api/sample");
    state.csv = payload.csv || "";
    return payload;
}

async function analyzeSample() {
    state.dataMode = "sample";
    state.analysisSource = "sample";
    const payload = await getJson("/api/analyze", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ csv: state.csv, config: config() }),
    });
    state.analysis = payload;
    reconcileReadNotifications();
    if (!state.selectedIp && payload.machines.length) {
        state.selectedIp = payload.machines[0].machine_ip;
    }
    syncNotifications();
    render();
}

async function refreshLiveStatus() {
    state.liveStatus = await getJson("/api/live/status");
    renderLiveStatus();
}

async function startLive() {
    state.dataMode = "live";
    const payload = await getJson("/api/live/start", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
            mode: el.liveMode.value,
            host: el.liveHost.value,
            port: Number(el.livePort.value),
        }),
    });
    state.liveStatus = payload.live;
    renderLiveStatus();
    if (!payload.ok) {
        pushToast({
            level: "critical",
            title: "Source live indisponible",
            message: payload.live.last_error || "Impossible de demarrer la source choisie.",
        });
        render();
        return;
    }
    if (state.refreshTimer) {
        clearInterval(state.refreshTimer);
    }
    state.refreshTimer = window.setInterval(analyzeLive, 3000);
    pushToast({
        level: "info",
        title: "Source active",
        message: payload.live.source_label || "Collecte en attente d'evenements",
    });
    await analyzeLive();
}

async function stopLive() {
    const payload = await getJson("/api/live/stop", { method: "POST" });
    if (state.refreshTimer) {
        clearInterval(state.refreshTimer);
        state.refreshTimer = null;
    }
    state.dataMode = "idle";
    state.liveStatus = payload.live;
    renderLiveStatus();
    render();
}

async function analyzeLive() {
    if (state.dataMode !== "live") {
        return;
    }
    state.analysisSource = "live";
    const payload = await getJson(`/api/live/analyze?threshold=${config().threshold}`);
    state.analysis = payload;
    state.liveStatus = payload.live;
    reconcileReadNotifications();
    if (!state.selectedIp && payload.machines.length) {
        state.selectedIp = payload.machines[0].machine_ip;
    }
    syncNotifications();
    render();
}

async function switchToScenario() {
    if (state.refreshTimer) {
        clearInterval(state.refreshTimer);
        state.refreshTimer = null;
    }
    if (state.liveStatus && state.liveStatus.mode !== "stopped") {
        try {
            const payload = await getJson("/api/live/stop", { method: "POST" });
            state.liveStatus = payload.live;
        } catch (error) {
            void error;
        }
    }
    state.dataMode = "sample";
    renderLiveStatus();
}

function exportReport(type) {
    const source = state.analysisSource || "sample";
    window.open(`/api/export/report.${type}?source=${source}&threshold=${config().threshold}`, "_blank");
}

function renderLiveStatus() {
    const live = state.liveStatus;
    if (!live) {
        el.liveStatus.innerHTML = `<div class="empty">Aucune session live active</div>`;
        return;
    }
    el.liveStatus.innerHTML = `
        <div><strong>Source</strong>: ${live.source_label || live.mode}</div>
        <div><strong>Evenements</strong>: ${live.row_count}</div>
        <div><strong>Etat</strong>: ${live.mode === "stopped" ? "arrete" : (live.collector_running ? "ecoute active" : "en attente de flux")}</div>
        <div><strong>Entree</strong>: ${live.ingest_hint || "Aucune source configuree"}</div>
        ${live.last_error ? `<div><strong>Erreur</strong>: ${live.last_error}</div>` : ""}
    `;
}

function renderOverview() {
    const analysis = state.analysis;
    if (!analysis) {
        return `<div class="panel empty">Aucune analyse chargee. Lancez le mode live puis rejouez un scenario depuis test_env.</div>`;
    }
    const summary = analysis.summary;
    const timeline = analysis.timeline || [];
    const sortedMachines = analysis.machines.slice(0, 6);
    const botnetCount = analysis.machines.filter((item) => item.primary_class === "botnet").length;
    const suspectCount = analysis.machines.filter((item) => item.primary_class === "suspect").length;
    const normalCount = analysis.machines.filter((item) => item.primary_class === "normal").length;
    const total = Math.max(analysis.machines.length, 1);
    const botnetAngle = (botnetCount / total) * 360;
    const suspectAngle = botnetAngle + (suspectCount / total) * 360;
    const scoreAverage = (analysis.machines.reduce((sum, machine) => sum + Number(machine.risk_score || 0), 0) / total).toFixed(2);
    const scoreMax = analysis.machines.reduce((max, machine) => Math.max(max, Number(machine.risk_score || 0)), 0).toFixed(2);
    const peakRiskPoint = timeline.reduce((best, point) => {
        if (!best || Number(point.max_risk || 0) > Number(best.max_risk || 0)) {
            return point;
        }
        return best;
    }, null);
    const peakAlertPoint = timeline.reduce((best, point) => {
        if (!best || Number(point.alert_machines || 0) > Number(best.alert_machines || 0)) {
            return point;
        }
        return best;
    }, null);
    const lastPoint = timeline[timeline.length - 1];
    const timeRange = timeline.length > 1
        ? `${formatTimeLabel(timeline[0].timestamp)} - ${formatTimeLabel(timeline[timeline.length - 1].timestamp)} | Casablanca`
        : (timeline[0] ? `${formatTimeLabel(timeline[0].timestamp)} | Casablanca` : "Aucun intervalle");
    return `
        <div class="stats-grid">
            <div class="stat-card"><span>Machines analysees</span><strong>${summary.machine_count}</strong></div>
            <div class="stat-card"><span>Alertes</span><strong>${summary.alert_count}</strong></div>
            <div class="stat-card"><span>Critiques</span><strong>${summary.critical_count}</strong></div>
            <div class="stat-card"><span>Suspectes</span><strong>${summary.suspect_count}</strong></div>
        </div>
        <div class="chart-grid">
            <div class="panel chart-panel">
                <div class="chart-header">
                    <h3>Score de risque par machine</h3>
                    <span class="mini-label">Top machines</span>
                </div>
                <div class="bar-chart">
                    ${sortedMachines.map((machine) => `
                        <div class="bar-col">
                            <div class="bar-value" style="color:${riskColor(machine.risk_score)}">${machine.risk_score}</div>
                            <div class="bar-track">
                                <div class="bar-fill" style="height:${machine.risk_score}%;background:${riskColor(machine.risk_score)}"></div>
                            </div>
                            <div class="bar-name">${machine.machine_ip}</div>
                        </div>
                    `).join("")}
                </div>
            </div>
            <div class="panel chart-panel">
                <div class="chart-header">
                    <h3>Distribution des classes</h3>
                    <span class="mini-label">Vue globale</span>
                </div>
                <div class="donut-wrap">
                    <div class="donut-chart" style="background:conic-gradient(#e24b4a 0deg ${botnetAngle}deg, #ba7517 ${botnetAngle}deg ${suspectAngle}deg, #1d9e75 ${suspectAngle}deg 360deg)">
                        <div class="donut-center">
                            <strong>${summary.machine_count}</strong>
                            <span>machines</span>
                        </div>
                    </div>
                    <div class="legend-list">
                        <div class="legend-item">
                            <div class="legend-label"><span class="legend-dot" style="background:#e24b4a"></span>Botnet</div>
                            <strong>${botnetCount}</strong>
                        </div>
                        <div class="legend-item">
                            <div class="legend-label"><span class="legend-dot" style="background:#ba7517"></span>Suspect</div>
                            <strong>${suspectCount}</strong>
                        </div>
                        <div class="legend-item">
                            <div class="legend-label"><span class="legend-dot" style="background:#1d9e75"></span>Normal</div>
                            <strong>${normalCount}</strong>
                        </div>
                    </div>
                </div>
            </div>
        </div>
        <div class="split-grid">
            <div class="panel">
                <div class="chart-header">
                    <h3>Evolution du risque dans le temps</h3>
                    <span class="mini-label">${timeRange}</span>
                </div>
                <div class="timeline-legend">
                    <span><i class="legend-swatch line-primary"></i>Risque moyen</span>
                    <span><i class="legend-swatch line-secondary"></i>Risque max</span>
                    <span><i class="legend-swatch bar-alert"></i>Machines alertees</span>
                </div>
                ${buildRiskTimelineSvg(timeline)}
                <div class="detail-kpis timeline-kpis">
                    <div class="report-metric"><span>Score moyen du lot</span><strong>${scoreAverage}</strong></div>
                    <div class="report-metric"><span>Score max du lot</span><strong>${scoreMax}</strong></div>
                    <div class="report-metric"><span>Pic de risque</span><strong>${peakRiskPoint ? `${peakRiskPoint.max_risk} a ${formatTimeLabel(peakRiskPoint.timestamp)}` : "-"}</strong></div>
                    <div class="report-metric"><span>Pic d'alertes</span><strong>${peakAlertPoint ? `${peakAlertPoint.alert_machines} a ${formatTimeLabel(peakAlertPoint.timestamp)}` : "-"}</strong></div>
                </div>
            </div>
            <div class="panel">
                <div class="chart-header">
                    <h3>Repartition des classes par intervalle</h3>
                    <span class="mini-label">heure locale Casablanca</span>
                </div>
                <div class="timeline-legend">
                    <span><i class="legend-swatch bar-normal"></i>Normal</span>
                    <span><i class="legend-swatch bar-suspect"></i>Suspect</span>
                    <span><i class="legend-swatch bar-botnet"></i>Botnet</span>
                </div>
                ${buildClassTimelineSvg(timeline)}
                <div class="detail-kpis timeline-kpis">
                    <div class="report-metric"><span>Dernier intervalle</span><strong>${lastPoint ? formatTimeLabel(lastPoint.timestamp) : "-"}</strong></div>
                    <div class="report-metric"><span>Machines actives</span><strong>${lastPoint ? lastPoint.active_machines : 0}</strong></div>
                    <div class="report-metric"><span>Evenements DNS</span><strong>${lastPoint ? lastPoint.dns_events : 0}</strong></div>
                    <div class="report-metric"><span>Echecs reseau</span><strong>${lastPoint ? lastPoint.failed_events : 0}</strong></div>
                </div>
            </div>
        </div>
    `;
}

function renderMachineCard(machine) {
    return `
        <div class="machine-item ${state.selectedIp === machine.machine_ip ? "active" : ""}" data-ip="${machine.machine_ip}">
            <div class="machine-head">
                <div>
                    <strong>${machine.machine_ip}</strong>
                    <div class="meta">${machine.window_start}</div>
                </div>
                ${severityBadge(machine.severity)}
            </div>
            <div class="machine-tags">
                <span>Classe: ${machine.primary_class}</span>
                <span>Activite: ${machine.activity_type}</span>
                <span>Score: ${machine.risk_score}</span>
            </div>
            <div class="explain-list">${machine.explanations.slice(0, 3).map(signalBadge).join("")}</div>
        </div>
    `;
}

function renderMachineDetail(machine) {
    if (!machine) {
        return `<div class="panel empty">Selectionnez une machine pour voir le detail.</div>`;
    }
    return `
        <div class="panel">
            <h3>Detail machine ${machine.machine_ip}</h3>
            <div class="split-grid">
                <div class="report-card">
                    <div><strong>Classe principale</strong>: ${machine.primary_class}</div>
                    <div><strong>Type d'activite</strong>: ${machine.activity_type}</div>
                    <div><strong>Score global</strong>: ${machine.risk_score}</div>
                    <div><strong>Score regles</strong>: ${machine.rule_score}</div>
                    <div><strong>Score comportement</strong>: ${machine.ml_score}</div>
                    <div><strong>Score anomalie</strong>: ${machine.dl_score}</div>
                </div>
                <div class="report-card">
                    <div><strong>Connexions</strong>: ${machine.total_connections}</div>
                    <div><strong>IPs destinations</strong>: ${machine.distinct_destination_ips}</div>
                    <div><strong>Ports</strong>: ${machine.distinct_ports}</div>
                    <div><strong>Requetes DNS</strong>: ${machine.dns_requests}</div>
                    <div><strong>Periodicite</strong>: ${machine.periodicity.toFixed(2)}</div>
                    <div><strong>Burst</strong>: ${machine.traffic_burst_score.toFixed(2)}</div>
                </div>
            </div>
            <div class="report-card">
                <strong>Explications</strong>
                <div class="explain-list">${machine.explanations.map(signalBadge).join("")}</div>
            </div>
            <div class="report-card">
                <strong>Signaux dominants</strong>
                <div class="signal-list">${(machine.ml_model.top_signals || []).map(signalBadge).join("")}</div>
            </div>
        </div>
    `;
}

function renderMachines() {
    const analysis = state.analysis;
    if (!analysis) {
        return `<div class="panel empty">Aucun resultat machine disponible.</div>`;
    }
    const filtered = analysis.machines.filter((item) => {
        if (state.machineFilters.primaryClass !== "all" && item.primary_class !== state.machineFilters.primaryClass) {
            return false;
        }
        if (state.machineFilters.activityType !== "all" && item.activity_type !== state.machineFilters.activityType) {
            return false;
        }
        if (state.machineFilters.severity !== "all" && item.severity !== state.machineFilters.severity) {
            return false;
        }
        return true;
    });
    const selected = filtered.find((item) => item.machine_ip === state.selectedIp) || filtered[0];
    const activityOptions = ["all", ...new Set(analysis.machines.map((item) => item.activity_type))];
    return `
        <div class="split-grid">
            <div class="panel">
                <h3>Liste des machines</h3>
                <div class="row">
                    <select onchange="setMachineFilter('primaryClass', this.value)">
                        <option value="all" ${state.machineFilters.primaryClass === "all" ? "selected" : ""}>Toutes les classes</option>
                        <option value="botnet" ${state.machineFilters.primaryClass === "botnet" ? "selected" : ""}>Botnet</option>
                        <option value="suspect" ${state.machineFilters.primaryClass === "suspect" ? "selected" : ""}>Suspect</option>
                        <option value="normal" ${state.machineFilters.primaryClass === "normal" ? "selected" : ""}>Normal</option>
                    </select>
                    <select onchange="setMachineFilter('activityType', this.value)">
                        ${activityOptions.map((value) => `<option value="${value}" ${state.machineFilters.activityType === value ? "selected" : ""}>${value === "all" ? "Toutes les activites" : value}</option>`).join("")}
                    </select>
                    <select onchange="setMachineFilter('severity', this.value)">
                        <option value="all" ${state.machineFilters.severity === "all" ? "selected" : ""}>Tous les niveaux</option>
                        <option value="critical" ${state.machineFilters.severity === "critical" ? "selected" : ""}>Critique</option>
                        <option value="warning" ${state.machineFilters.severity === "warning" ? "selected" : ""}>Warning</option>
                        <option value="info" ${state.machineFilters.severity === "info" ? "selected" : ""}>Info</option>
                    </select>
                </div>
                <div class="machine-list">${filtered.map(renderMachineCard).join("") || '<div class="empty">Aucune machine pour ce filtre.</div>'}</div>
            </div>
            ${renderMachineDetail(selected)}
        </div>
    `;
}

function renderAlertsView() {
    const alerts = state.analysis?.alerts || [];
    return `
        <div class="panel">
            <h3>Alertes SOC</h3>
            <div class="alert-list">
                ${alerts.map((alert) => `
                    <div class="alert-item ${alert.severity}">
                        <div class="alert-head">
                            <div>
                                <strong class="alert-title">${alert.machine_ip}</strong>
                                <div class="meta">${alert.timestamp}</div>
                            </div>
                            ${severityBadge(alert.severity)}
                        </div>
                        <div class="alert-meta-row">
                            <span class="alert-meta-pill">Type: ${alert.type}</span>
                            <span class="alert-meta-pill">Score: ${alert.score}</span>
                        </div>
                        <div class="alert-copy"><strong>Justification:</strong> ${alert.justification}</div>
                    </div>
                `).join("") || '<div class="empty">Aucune alerte pour ce jeu de donnees.</div>'}
            </div>
        </div>
    `;
}

function renderReportView() {
    const analysis = state.analysis;
    if (!analysis) {
        return `<div class="panel empty">Lancez une analyse pour generer un rapport.</div>`;
    }
    const summary = analysis.summary;
    const topMachines = analysis.machines.slice(0, 3).map((machine) => `
        <div class="report-metric">
            <span>${machine.machine_ip}</span>
            <strong>${machine.risk_score} | ${machine.activity_type}</strong>
        </div>
    `).join("") || `<div class="report-metric"><span>Aucune machine</span><strong>-</strong></div>`;
    const topAlerts = analysis.alerts.slice(0, 3).map((alert) => `
        <div class="report-metric">
            <span>${alert.machine_ip}</span>
            <strong>${alert.type} | ${alert.score}</strong>
        </div>
    `).join("") || `<div class="report-metric"><span>Aucune alerte</span><strong>-</strong></div>`;
    return `
        <div class="report-hero">
            <h3>Rapport d'analyse SOC</h3>
            <p>
                Cette section synthétise les résultats du pipeline hybride. Elle met en avant le volume de machines
                analysées, les alertes générées, les types d'activités détectées et fournit un export PDF plus propre
                pour la présentation du projet.
            </p>
        </div>
        <div class="report-sections">
            <div class="panel">
                <h3>Resume executif</h3>
                <div class="report-block">
                    <div class="report-metric"><span>Machines analysees</span><strong>${summary.machine_count}</strong></div>
                    <div class="report-metric"><span>Machines suspectes</span><strong>${summary.suspect_count}</strong></div>
                    <div class="report-metric"><span>Alertes critiques</span><strong>${summary.critical_count}</strong></div>
                    <div class="report-metric"><span>Types detectes</span><strong>${Object.keys(summary.attack_types).join(", ")}</strong></div>
                </div>
                <div class="report-card">
                    <strong>Vision globale</strong>
                    <p class="report-copy">
                        Le rapport met l'accent sur l'analyse par machine, l'explicabilité des décisions et la
                        combinaison entre detection comportementale et anomalie. Cette approche garde un bon équilibre entre
                        compréhension opérationnelle et capacité de détection.
                    </p>
                </div>
            </div>
            <div class="panel">
                <h3>Exports</h3>
                <div class="row">
                    <button onclick="exportReport('csv')">Exporter CSV</button>
                    <button class="primary" onclick="exportReport('pdf')">Exporter PDF</button>
                </div>
                <div class="report-card">
                    Le rapport PDF explique le projet, la logique de detection, les resultats courants et les ameliorations attendues.
                </div>
                <div class="report-card">
                    <strong>Machines prioritaires</strong>
                    <div class="report-block">${topMachines}</div>
                </div>
                <div class="report-card">
                    <strong>Alertes majeures</strong>
                    <div class="report-block">${topAlerts}</div>
                </div>
                <div class="report-card">
                    <strong>Test sur reseau reel</strong>
                    <p class="report-copy">
                        Pour un deploiement de test, utilisez une machine de capture Zeek, Suricata ou tshark,
                        convertissez les flows au format attendu puis injectez-les vers <code>/api/live/ingest</code>
                        ou le mode <code>UDP collector</code>. Le dashboard affichera ensuite les machines analysees,
                        les alertes et les explications en quasi temps reel.
                    </p>
                </div>
            </div>
        </div>
    `;
}

function renderNotifications(notifications) {
    if (!notifications.length) {
        return '<div class="empty">Aucune notification.</div>';
    }
    return notifications.map((item) => `
        <div class="notification-item">
            <div class="alert-head">
                <strong>${item.title}</strong>
                ${severityBadge(item.level)}
            </div>
            <div class="meta">${item.message}</div>
        </div>
    `).join("");
}

function requestRefresh() {
    if (state.refreshDebounce) {
        clearTimeout(state.refreshDebounce);
    }
    state.refreshDebounce = window.setTimeout(async () => {
        updateThresholdLabel();
        if (state.dataMode === "live") {
            await analyzeLive();
            return;
        }
        if (state.dataMode === "sample" && state.analysis) {
            await analyzeSample();
        }
    }, 220);
}

function pushToast(notification) {
    const toast = document.createElement("div");
    toast.className = `toast ${notification.level}`;
    toast.innerHTML = `<div class="toast-title">${notification.title}</div><div class="toast-copy">${notification.message}</div>`;
    el.toastStack.prepend(toast);
    window.setTimeout(() => toast.remove(), 6000);
}

function syncNotifications() {
    const notifications = actionableNotifications(state.analysis?.notifications || []);
    updateNotificationCount();
    const unreadAlerts = currentUnreadAlerts();
    if (!unreadAlerts.length) {
        state.lastNotificationKey = null;
        return;
    }
    const latestAlert = unreadAlerts[0];
    const latest = notifications.find((item) => item.message.includes(latestAlert.machine_ip)) || notifications[0];
    if (state.lastNotificationKey !== latest.key) {
        state.lastNotificationKey = latest.key;
        pushToast(latest);
    }
}

function render() {
    renderLiveStatus();
    if (state.currentView === "machines") {
        el.contentView.innerHTML = renderMachines();
    } else if (state.currentView === "alerts") {
        el.contentView.innerHTML = renderAlertsView();
    } else if (state.currentView === "report") {
        el.contentView.innerHTML = renderReportView();
    } else {
        el.contentView.innerHTML = renderOverview();
    }
    document.querySelectorAll("[data-ip]").forEach((card) => {
        card.addEventListener("click", () => {
            state.selectedIp = card.dataset.ip;
            if (state.currentView !== "machines") {
                setView("machines");
                return;
            }
            render();
        });
    });
}

function setMachineFilter(key, value) {
    state.machineFilters[key] = value;
    render();
}

document.querySelectorAll(".menu-item").forEach((button) => {
    button.addEventListener("click", () => setView(button.dataset.view));
});
el.thresholdInput.addEventListener("input", requestRefresh);
el.sensitivityInput.addEventListener("change", requestRefresh);
el.startLiveBtn.addEventListener("click", startLive);
el.stopLiveBtn.addEventListener("click", stopLive);

window.setMachineFilter = setMachineFilter;

updateThresholdLabel();
render();
refreshLiveStatus();
