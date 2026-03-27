const container = document.getElementById("matches-container");
const connStatus = document.getElementById("connection-status");
const lastUpdated = document.getElementById("last-updated");

let ws = null;
let reconnectDelay = 1000;
let matches = [];

const EVENT_ICONS = {
    goal: "\u26bd",
    own_goal: "\u26bd\ufe0f(OG)",
    penalty_goal: "\u26bd(P)",
    yellow_card: "\ud83d\udfe8",
    red_card: "\ud83d\udfe5",
    second_yellow: "\ud83d\udfe8\ud83d\udfe5",
    substitution: "\ud83d\udd04",
};

// Competition display order
const COMP_ORDER = [
    "Premier League",
    "La Liga",
    "Champions League",
    "Europa League",
    "Conference League",
    "FA Cup",
    "Carabao Cup",
    "Copa del Rey",
];

function getStatusClass(status) {
    if (["1H", "2H", "ET", "PEN"].includes(status)) return "live";
    if (status === "FT") return "finished";
    if (status === "PPD" || status === "CAN") return "postponed";
    return "scheduled";
}

function estimateClock(match) {
    // Estimate a ticking clock based on kickoff time and match status
    const kickoff = new Date(match.kickoff).getTime();
    const now = Date.now();
    const elapsedMs = now - kickoff;
    const elapsedMin = Math.floor(elapsedMs / 60000);

    if (match.status === "1H") {
        const min = Math.max(1, Math.min(elapsedMin, 45));
        return `${min}'`;
    }
    if (match.status === "HT") return "HT";
    if (match.status === "2H") {
        // 2H starts ~15 min after kickoff + 45 min = 60 min mark
        // But halftime length varies, so estimate: 2H clock = elapsed - 60, starting at 45
        const secondHalfMin = Math.max(45, Math.min(elapsedMin - 15, 90));
        return `${secondHalfMin}'`;
    }
    if (match.status === "ET") {
        const etMin = Math.max(90, Math.min(elapsedMin - 30, 120));
        return `${etMin}'`;
    }
    return null;
}

function getStatusText(match) {
    // For live matches, estimate a ticking clock
    if (["1H", "2H", "ET"].includes(match.status)) {
        return estimateClock(match) || match.match_clock || match.status;
    }
    const map = {
        SCHEDULED: formatKickoff(match.kickoff),
        HT: "HT",
        PEN: "PEN",
        FT: "FT",
        PPD: "PPD",
        CAN: "CAN",
    };
    return map[match.status] || match.status;
}

function formatKickoff(isoStr) {
    const d = new Date(isoStr);
    return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

function renderEvent(ev) {
    const icon = EVENT_ICONS[ev.type] || "";
    const min = ev.added_time ? `${ev.minute}'+${ev.added_time}'` : `${ev.minute}'`;
    const player = ev.player_name || "";
    return `<span class="event"><span class="event-icon">${icon}</span>${min} ${player}</span>`;
}

function renderStats(stats) {
    if (!stats) return "";
    const parts = [];
    if (stats.possession_home != null && stats.possession_away != null) {
        parts.push(`<span class="stat"><span class="stat-label">Poss:</span> ${stats.possession_home}%-${stats.possession_away}%</span>`);
    }
    if (stats.shots_home != null) {
        parts.push(`<span class="stat"><span class="stat-label">Shots:</span> ${stats.shots_home}-${stats.shots_away}</span>`);
    }
    if (stats.shots_on_target_home != null) {
        parts.push(`<span class="stat"><span class="stat-label">On target:</span> ${stats.shots_on_target_home}-${stats.shots_on_target_away}</span>`);
    }
    if (stats.corners_home != null) {
        parts.push(`<span class="stat"><span class="stat-label">Corners:</span> ${stats.corners_home}-${stats.corners_away}</span>`);
    }
    if (!parts.length) return "";
    return `<div class="stats">${parts.join("")}</div>`;
}

function renderMatch(match) {
    const cls = getStatusClass(match.status);
    const scoreText =
        match.home_score != null
            ? `${match.home_score} - ${match.away_score}`
            : "vs";
    const eventsHtml = match.events.length
        ? `<div class="events">${match.events.map(renderEvent).join("")}</div>`
        : "";
    const statsHtml = renderStats(match.stats);

    return `
    <div class="match-card ${cls}" data-match-id="${match.id}">
        <div class="match-top">
            <div class="teams-score">
                <span class="team-name home">${match.home_team.short_name || match.home_team.name}</span>
                <span class="score">${scoreText}</span>
                <span class="team-name away">${match.away_team.short_name || match.away_team.name}</span>
            </div>
            <span class="match-status ${cls}">${getStatusText(match)}</span>
        </div>
        ${eventsHtml}
        ${statsHtml}
    </div>`;
}

function renderAll() {
    if (!matches.length) {
        container.innerHTML = '<p class="loading">No matches today</p>';
        return;
    }

    // Group by competition
    const groups = {};
    for (const m of matches) {
        const comp = m.competition || "Other";
        if (!groups[comp]) groups[comp] = [];
        groups[comp].push(m);
    }

    // Sort groups by predefined order
    const sortedComps = Object.keys(groups).sort((a, b) => {
        const ia = COMP_ORDER.indexOf(a);
        const ib = COMP_ORDER.indexOf(b);
        return (ia === -1 ? 999 : ia) - (ib === -1 ? 999 : ib);
    });

    let html = "";
    for (const comp of sortedComps) {
        html += `<div class="competition-group">`;
        html += `<div class="competition-header">${comp}</div>`;
        for (const m of groups[comp]) {
            html += renderMatch(m);
        }
        html += `</div>`;
    }
    container.innerHTML = html;
}

function updateMatch(data) {
    const matchData = data.match;
    const idx = matches.findIndex((m) => m.id === matchData.id);
    if (idx >= 0) {
        matches[idx] = matchData;
    } else {
        matches.push(matchData);
    }
    renderAll();

    // Flash on goal
    if (data.score_changed) {
        const card = document.querySelector(`[data-match-id="${matchData.id}"]`);
        if (card) {
            card.classList.add("goal-scored");
            setTimeout(() => card.classList.remove("goal-scored"), 1500);
        }
    }
}

function updateTimestamp() {
    lastUpdated.textContent = "Updated " + new Date().toLocaleTimeString();
}

function connect() {
    const proto = location.protocol === "https:" ? "wss:" : "ws:";
    ws = new WebSocket(`${proto}//${location.host}/ws`);

    ws.onopen = () => {
        connStatus.textContent = "Connected";
        connStatus.className = "connected";
        reconnectDelay = 1000;
    };

    ws.onmessage = (event) => {
        const msg = JSON.parse(event.data);
        if (msg.type === "full_state") {
            matches = msg.data;
            renderAll();
        } else if (msg.type === "match_update") {
            updateMatch(msg.data);
        }
        updateTimestamp();
    };

    ws.onclose = () => {
        connStatus.textContent = "Disconnected";
        connStatus.className = "disconnected";
        setTimeout(() => {
            reconnectDelay = Math.min(reconnectDelay * 2, 30000);
            connect();
        }, reconnectDelay);
    };

    ws.onerror = () => {
        ws.close();
    };
}

connect();

// Tick live match clocks every second by updating just the clock elements
setInterval(() => {
    const hasLive = matches.some((m) => ["1H", "2H", "ET"].includes(m.status));
    if (!hasLive) return;

    for (const match of matches) {
        if (!["1H", "2H", "ET"].includes(match.status)) continue;
        const card = document.querySelector(`[data-match-id="${match.id}"] .match-status`);
        if (card) {
            card.textContent = getStatusText(match);
        }
    }
}, 1000);
