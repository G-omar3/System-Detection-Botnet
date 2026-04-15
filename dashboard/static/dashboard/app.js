const state = {
    csv: "",
    analysis: null,
    selectedIp: null,
    currentView: "overview",
    liveStatus: null,
    refreshTimer: null,
    lastNotificationKey: null,
    readAlertKeys: [],
    dataMode: "sample",
    machineFilters: {
        primaryClass: "all",
        activityType: "all",
        severity: "all",
    },
};

const el = {
    thresholdInput: document.getElementById("thresholdInput"),
    thresholdValue: document.getElementById("thresholdValue"),
    sensitivityInput: document.getElementById("sensitivityInput"),
    loadSampleBtn: document.getElementById("loadSampleBtn"),
    analyzeBtn: document.getElementById("analyzeBtn"),
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
    if (score >= 70) {
        return "#e24b4a";
    }
    if (score >= 30) {
        return "#ba7517";
    }
    return "#1d9e75";
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
    state.dataMode = "sample";
    state.liveStatus = payload.live;
    renderLiveStatus();
    render();
}

async function analyzeLive() {
    if (state.dataMode !== "live") {
        return;
    }
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
    const source = state.liveStatus && state.liveStatus.mode !== "stopped" ? "live" : "sample";
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
        return `<div class="panel empty">Chargez un scenario ou lancez le mode live pour voir l'analyse.</div>`;
    }
    const summary = analysis.summary;
    const notifications = renderNotifications(analysis.notifications);
    const sortedMachines = analysis.machines.slice(0, 6);
    const botnetCount = analysis.machines.filter((item) => item.primary_class === "botnet").length;
    const suspectCount = analysis.machines.filter((item) => item.primary_class === "suspect").length;
    const normalCount = analysis.machines.filter((item) => item.primary_class === "normal").length;
    const total = Math.max(analysis.machines.length, 1);
    const botnetAngle = (botnetCount / total) * 360;
    const suspectAngle = botnetAngle + (suspectCount / total) * 360;
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
                <h3>Machines prioritaires</h3>
                <div class="panel-list">
                    ${analysis.machines.slice(0, 5).map(renderMachineCard).join("") || '<div class="empty">Aucune machine analysee</div>'}
                </div>
            </div>
            <div class="panel">
                <h3>Centre de notifications</h3>
                <div class="panel-list">${notifications}</div>
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
                                <strong>${alert.machine_ip}</strong>
                                <div class="meta">${alert.timestamp}</div>
                            </div>
                            ${severityBadge(alert.severity)}
                        </div>
                        <div>Type: ${alert.type}</div>
                        <div>Score: ${alert.score}</div>
                        <div>Justification: ${alert.justification}</div>
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
el.thresholdInput.addEventListener("input", updateThresholdLabel);
el.loadSampleBtn.addEventListener("click", async () => {
    await switchToScenario();
    await loadSample();
    await analyzeSample();
    pushToast({
        level: "info",
        title: "Scenario charge",
        message: "Le jeu de test a ete recharge et l'analyse a ete relancee.",
    });
});
el.analyzeBtn.addEventListener("click", async () => {
    if (state.dataMode !== "live") {
        await switchToScenario();
        await analyzeSample();
        return;
    }
    await analyzeLive();
});
el.startLiveBtn.addEventListener("click", startLive);
el.stopLiveBtn.addEventListener("click", stopLive);

window.setMachineFilter = setMachineFilter;

updateThresholdLabel();
loadSample().then(analyzeSample).then(refreshLiveStatus);
