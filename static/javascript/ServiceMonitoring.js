/* ════════════════════════════════════════════════════════════════════
   ServiceMonitoring.js
   Cluster → Node → Service tree nav + Scoped GlitchTip & Performance tabs
   ════════════════════════════════════════════════════════════════════ */
/* global clearInterval, fetch, SESSION_INFO, setInterval, GT_CONFIGURED, GT_ORG, GT_BASE_URL, document, window */
'use strict';

/* ── state ── */
const SM = {
    tree: {}, // raw tree from server: { cluster: { node: [svc, ...] } }
    selection: {
        // what's selected
        cluster: null,
        node: null,
        service: null,
    },
    window: '24h', // time window
    autoRefresh: true,
    refreshInterval: null,
    activeTab: 'issues', // Default to Issues & Errors tab

    // cached per-service data keyed by service_name
    healthCache: {},
    issuesCache: {},
};

/* ─── helpers ─── */
function csrfToken () {
    try {
        return document.cookie
            .split('; ')
            .find((r) => r.startsWith('csrftoken='))
            .split('=')[1];
    } catch {
        return '';
    }
}

function post (url, body) {
    return fetch(url, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': csrfToken(),
        },
        body: JSON.stringify(body),
    }).then((r) => r.json());
}

function fmtTime (iso) {
    if (!iso) return '—';
    try {
        const d = new Date(iso);
        const now = new Date();
        const diff = Math.floor((now - d) / 1000);
        if (diff < 60) return `${diff}s ago`;
        if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
        if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
        return `${Math.floor(diff / 86400)}d ago`;
    } catch {
        return iso;
    }
}

function cleanGlitchtipUrl (urlStr) {
    if (!urlStr) return '';
    let clean = urlStr.replace('/organizations/', '/');
    if (clean.endsWith('/')) {
        clean = clean.slice(0, -1);
    }
    return clean;
}

function formatIncidentResponseTime (c) {
    if (!c.isUp) return '-';
    const ms = parseFloat(c.responseTime || c.duration || 0);
    if (!ms) return '0ms';
    if (ms >= 1000) {
        return `${(ms / 1000).toFixed(2)} seconds`;
    }
    return `${ms.toFixed(0)}ms`;
}

function formatPermalink (permalink, projectSlug, issueId) {
    const externalBase = (
        GT_EXTERNAL_URL ||
        GT_BASE_URL ||
        window.location.origin
    ).replace(/\/?$/, '');
    const org = GT_ORG || 'iktara';
    let targetUrl = '';
    if (org && issueId) {
        targetUrl = `${externalBase}/${org}/issues/${issueId}`;
    } else if (projectSlug && issueId) {
        targetUrl = `${externalBase}/${projectSlug}/issues/${issueId}`;
    } else if (permalink) {
        try {
            const url = new URL(permalink);
            const base = new URL(externalBase);
            url.protocol = base.protocol;
            url.host = base.host;
            targetUrl = url.toString();
        } catch {
            targetUrl = permalink.startsWith('/')
                ? externalBase + permalink
                : permalink;
        }
    } else {
        return '#';
    }
    return cleanGlitchtipUrl(targetUrl);
}

function getTransactionDetailUrl (tId) {
    const base = (
        GT_EXTERNAL_URL ||
        GT_BASE_URL ||
        window.location.origin
    ).replace(/\/?$/, '');
    return cleanGlitchtipUrl(
        `${base}/${GT_ORG || 'iktara'}/performance/transaction-groups/${tId}`,
    );
}

function healthDotClass (health) {
    if (health === 'ok') return 'ok';
    if (health === 'warn') return 'warn';
    if (health === 'error') return 'err';
    return 'unknown';
}

/* ─── 1. fetch monitoring tree ─── */
async function fetchTree () {
    try {
        const res = await fetch('/PlatformIO/GetMonitoringTree/');
        const data = await res.json();
        if (data.success) {
            SM.tree = data.cluster_tree || {};
        } else {
            SM.tree = {};
        }
    } catch {
        SM.tree = {};
    }
    renderTree();

    // restore last-visited selection from SESSION_INFO
    if (typeof SESSION_INFO !== 'undefined' && SESSION_INFO) {
        const cn = SESSION_INFO.clusterName;
        const nn = SESSION_INFO.nodeName;
        const sn = SESSION_INFO.serviceName;
        if (cn && nn && sn) {
            selectService(cn, nn, sn);
        }
    }
}

/* ─── 2. render tree ─── */
function renderTree (filter) {
    const treeEl = document.getElementById('treeList');
    if (!treeEl) return;

    const q = (filter || '').toLowerCase().trim();
    let html = '';

    for (const [cluster, nodes] of Object.entries(SM.tree)) {
        let clusterHtml = '';
        let clusterVisible = false;

        for (const [node, services] of Object.entries(nodes || {})) {
            const filteredSvcs = q
                ? services.filter((s) => {
                    const name =
                          typeof s === 'string' ? s : s.serviceName || '';
                    return (
                        name.toLowerCase().includes(q) ||
                          node.toLowerCase().includes(q)
                    );
                })
                : services;
            if (!filteredSvcs.length) continue;
            clusterVisible = true;

            const svcsHtml = filteredSvcs
                .map((svc) => {
                    const svcName =
                        typeof svc === 'string' ? svc : svc.serviceName || '';
                    const svcType =
                        typeof svc === 'string' ? svc : svc.serviceType || '';
                    const isActive =
                        SM.selection.service === svcName &&
                        SM.selection.cluster === cluster &&
                        SM.selection.node === node;
                    const health = SM.healthCache[svcName] || {};
                    const containerRunning = health.running === true;
                    const dotCls = containerRunning
                        ? 'ok'
                        : health.running !== undefined
                            ? 'err'
                            : 'unknown';
                    return `<div class='tree-svc${isActive ? ' active' : ''}'
                             data-cluster='${esc(cluster)}' data-node='${esc(node)}' data-svc='${esc(svcName)}'
                             onclick="selectService('${esc(cluster)}','${esc(node)}','${esc(svcName)}')">
                          <svg class="ico" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="2" y="3" width="20" height="14" rx="2"/><path d="M8 21h8M12 17v4"/></svg>
                          <span class='svc-name'>${esc(svcName)}</span>
                          <span class="svc-dot">${esc(svcType)}</span>
                            </div>`;
                })
                .join('');

            const targetId = `svclist-${esc(cluster)}-${esc(node)}`;
            const targetEl = document.getElementById(targetId);
            const isExpanded = targetEl
                ? targetEl.style.display !== 'none'
                : true;

            clusterHtml += `
            <div class='tree-node-row' data-cluster='${esc(cluster)}' data-node='${esc(node)}' onclick="toggleNode(event,'${esc(cluster)}','${esc(node)}')">
              <span class='svc-toggle${isExpanded ? ' expanded' : ''}'>
                <svg class='ic' viewBox='0 0 24 24' fill='none' stroke='currentColor' stroke-width='2.4'><path d='M9 18l6-6-6-6'/></svg>
              </span>
              <span class="nstatus ok"></span>
              <span class='nname'>${esc(node)}</span>
            </div>
            <div class='tree-svc-list' id='${targetId}' style='${isExpanded ? '' : 'display:none'}'>
              ${svcsHtml}
            </div>`;
        }

        if (q && !clusterVisible) continue;

        html += `
          <div class='tree-cluster' id='cluster-${esc(cluster)}'>
            <div class='cluster-head' onclick="toggleCluster('${esc(cluster)}')">
              <svg class='caret' viewBox='0 0 24 24' fill='none' stroke='currentColor' stroke-width='2'><path d='M19 9l-7 7-7-7'/></svg>
              <span>${esc(cluster)}</span>
            </div>
            <div class='cluster-children'>${clusterHtml}</div>
          </div>`;
    }
    treeEl.innerHTML =
        html ||
        '<div style="padding:var(--s-4) var(--s-4); font-size:12px; color:var(--ink-3);">No services found</div>';
}

function esc (s) {
    return String(s || '')
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/'/g, '&quot;');
}

/* ─── 3. tree interactions ─── */
window.toggleCluster = function (cluster) {
    const el = document.getElementById(`cluster-${cluster}`);
    if (el) el.classList.toggle('collapsed');
};

window.toggleNode = function (e, cluster, node) {
    e.stopPropagation();
    const listEl = document.getElementById(`svclist-${cluster}-${node}`);
    const rowEl = document.querySelector(
        `.tree-node-row[data-cluster='${cluster}'][data-node='${node}']`,
    );
    const toggle = rowEl ? rowEl.querySelector('.svc-toggle') : null;
    if (!listEl) return;
    const hidden = listEl.style.display === 'none';
    listEl.style.display = hidden ? '' : 'none';
    if (toggle) toggle.classList.toggle('expanded', hidden);
};

let monitoringWorkspaceCache = {};
try {
    const cached = localStorage.getItem('cplatform_monitoring_cache');
    if (cached) {
        monitoringWorkspaceCache = JSON.parse(cached);
    }
} catch (e) {
    console.warn(
        'Unable to load monitoring workspace cache from localStorage:',
        e,
    );
}

function saveMonitoringWorkspaceToCache (serviceName) {
    if (!serviceName) return;
    const panel = document.getElementById('detailPanel');
    if (!panel) return;

    monitoringWorkspaceCache[serviceName] = {
        // DOM HTML Content
        panelHtml: panel.innerHTML,

        // JS States
        activeTab: SM.activeTab,
        healthData: SM.healthCache[serviceName] || null,
        issuesData: SM.issuesCache[serviceName] || null,

        timestamp: Date.now(),
    };

    // Pruning: Keep only the 10 most recently used service caches to avoid local storage quota limits
    try {
        const keys = Object.keys(monitoringWorkspaceCache);
        if (keys.length > 10) {
            const sortedKeys = keys.sort((a, b) => {
                return (
                    (monitoringWorkspaceCache[a].timestamp || 0) -
                    (monitoringWorkspaceCache[b].timestamp || 0)
                );
            });
            while (sortedKeys.length > 10) {
                const oldestKey = sortedKeys.shift();
                delete monitoringWorkspaceCache[oldestKey];
            }
        }
        localStorage.setItem(
            'cplatform_monitoring_cache',
            JSON.stringify(monitoringWorkspaceCache),
        );
    } catch (e) {
        console.warn(
            'Unable to save monitoring workspace cache to localStorage:',
            e,
        );
    }
}

function restoreMonitoringWorkspaceFromCache (serviceName) {
    if (!serviceName || !monitoringWorkspaceCache[serviceName]) return false;

    const cache = monitoringWorkspaceCache[serviceName];
    const panel = document.getElementById('detailPanel');
    if (!panel) return false;

    // Restore DOM HTML
    panel.innerHTML = cache.panelHtml;

    // Restore JS States
    SM.activeTab = cache.activeTab || 'issues';
    if (cache.healthData) SM.healthCache[serviceName] = cache.healthData;
    if (cache.issuesData) SM.issuesCache[serviceName] = cache.issuesData;

    // Re-attach tab click event listeners
    attachTabListeners();

    // Highlight active tab class
    document
        .querySelectorAll('.mon-tab')
        .forEach((b) =>
            b.classList.toggle('active', b.dataset.tab === SM.activeTab),
        );
    document
        .querySelectorAll('.mon-tab-pane')
        .forEach((p) =>
            p.classList.toggle('active', p.id === `pane-${SM.activeTab}`),
        );

    return true;
}

function selectService (cluster, node, service) {
    window.selectService = selectService;

    // Save previous active service details to cache before selecting the new one
    if (SM.selection.service) {
        saveMonitoringWorkspaceToCache(SM.selection.service);
    }

    SM.selection = { cluster, node, service };

    // highlight tree
    document
        .querySelectorAll('.tree-svc')
        .forEach((el) => el.classList.remove('active'));
    const el = document.querySelector(
        `.tree-svc[data-cluster='${cluster}'][data-node='${node}'][data-svc='${service}']`,
    );
    if (el) {
        el.classList.add('active');
        // ensure parent node list is visible
        const listEl = document.getElementById(`svclist-${cluster}-${node}`);
        if (listEl) listEl.style.display = '';
        // expand toggle
        const nodeRow = document.querySelector(
            `.tree-node-row[data-cluster='${cluster}'][data-node='${node}']`,
        );
        if (nodeRow) {
            const tog = nodeRow.querySelector('.svc-toggle');
            if (tog) tog.classList.add('expanded');
        }
    }

    // track visit
    post('/PlatformIO/Diagnostics/', {
        'user-action': 'track_visit',
        clusterName: cluster,
        nodeName: node,
        serviceName: service,
    }).catch(() => {});

    loadServiceDetail(service);
}

/* ─── 4. load service detail ─── */
async function loadServiceDetail (service) {
    const panel = document.getElementById('detailPanel');
    const emptyState = document.getElementById('emptyState');
    if (emptyState) emptyState.style.display = 'none';

    const wasRestored = restoreMonitoringWorkspaceFromCache(service);

    if (wasRestored) {
        // Trigger background refresh silently
        Promise.all([fetchHealth(service), fetchIssues(service)]).then(() => {
            // Update UI only if user has not navigated away in the meantime
            if (SM.selection.service === service) {
                const currentActiveTab = SM.activeTab;
                panel.innerHTML = renderDetailFull(service);
                attachTabListeners();
                switchTab(currentActiveTab);
                renderTree();
            }
        });
    } else {
        // Full load with skeleton
        panel.innerHTML = renderDetailShell(service);
        switchTab(SM.activeTab);

        await Promise.all([fetchHealth(service), fetchIssues(service)]);

        // re-render now that we have data
        panel.innerHTML = renderDetailFull(service);
        attachTabListeners();
        switchTab(SM.activeTab);
        renderTree(); // refresh dots in tree
    }
}

function renderDetailShell (service) {
    return `
    <div class='svc-header'>
      <div class='svc-header-left'>
        <div class='svc-header-icon'>
          <svg class='ic' viewBox='0 0 24 24' fill='none' stroke='currentColor' stroke-width='1.5'><rect x='2' y='3' width='20' height='14' rx='2'/><path d='M8 21h8M12 17v4'/></svg>
        </div>
        <div>
          <div class='svc-breadcrumb'>${esc(SM.selection.cluster)} / ${esc(SM.selection.node)}</div>
          <div class='svc-title'>${esc(service)}</div>
        </div>
      </div>
      <div class='health-pill unknown'>Loading…</div>
    </div>
    <div class='mon-tabs'>
      <button class='mon-tab' data-tab='issues'>Issues & Errors</button>
      <button class='mon-tab' data-tab='uptime'>Uptime Monitors</button>
      <button class='mon-tab' data-tab='performance'>Performance</button>
      <button class='mon-tab' data-tab='settings'>Settings & Keys</button>
    </div>
    <div class='mon-tab-pane' id='pane-issues'>
      <div class="gt-embed-container"><div class="gt-loading-overlay"><div class="spinner"></div></div></div>
    </div>
    <div class='mon-tab-pane' id='pane-uptime'></div>
    <div class='mon-tab-pane' id='pane-performance'></div>
    <div class='mon-tab-pane' id='pane-settings'></div>`;
}

async function fetchHealth (service) {
    try {
        const data = await post('/PlatformIO/Monitoring/Health/', {
            service_name: service,
            window: SM.window,
        });
        if (data.success) SM.healthCache[service] = data;
    } catch {
        /* ignore */
    }
}

async function fetchIssues (service) {
    try {
        const data = await post('/PlatformIO/Monitoring/Issues/', {
            service_name: service,
            window: SM.window,
        });
        if (data.success) SM.issuesCache[service] = data.issues || [];
    } catch {
        /* ignore */
    }
}

/* ─── 5. render full detail ─── */
function renderDetailFull (service) {
    const health = SM.healthCache[service] || {};
    const issues = SM.issuesCache[service] || [];
    const containerRunning = health.running === true;
    const hCls = containerRunning ? 'ok' : 'err';
    const hLabel = containerRunning ? 'Healthy' : 'Error';
    const errCount = issues.filter((i) =>
        ['error', 'fatal'].includes(i.level),
    ).length;
    const warnCount = issues.filter((i) => i.level === 'warning').length;
    const state = health.container_state || '—';
    const projectSlug = health.project_slug || '';

    const externalBase = (
        GT_EXTERNAL_URL ||
        GT_BASE_URL ||
        window.location.origin
    ).replace(/\/?$/, '');
    const glitchtipProjectUrl = projectSlug
        ? cleanGlitchtipUrl(
            `${externalBase}/${GT_ORG || 'iktara'}/projects/${projectSlug}`,
        )
        : cleanGlitchtipUrl(`${externalBase}/${GT_ORG || 'iktara'}/issues`);

    // summary cards
    const cards = `
    <div class='svc-summary-cards' style="border-bottom:none; margin-bottom:0; padding-bottom:var(--s-3);">
      <div class='summary-card'>
        <div class='sc-label'>Container state</div>
        <div class='sc-value ${hCls}'>${esc(state)}</div>
      </div>
      <div class='summary-card'>
        <div class='sc-label'>Errors (${esc(SM.window)})</div>
        <div class='sc-value ${errCount ? 'err' : 'ok'}'>${errCount}</div>
      </div>
      <div class='summary-card'>
        <div class='sc-label'>Warnings (${esc(SM.window)})</div>
        <div class='sc-value ${warnCount ? 'warn' : 'ok'}'>${warnCount}</div>
      </div>
    </div>`;

    return `
    <div class='svc-header'>
      <div class='svc-header-left'>
        <div class='svc-header-icon'>
          <svg class='ic' viewBox='0 0 24 24' fill='none' stroke='currentColor' stroke-width='1.5'><rect x='2' y='3' width='20' height='14' rx='2'/><path d='M8 21h8M12 17v4'/></svg>
        </div>
        <div>
          <div class='svc-breadcrumb'>${esc(SM.selection.cluster)} / ${esc(SM.selection.node)}</div>
          <div class='svc-title'>${esc(service)}</div>
        </div>
      </div>
      <div class='health-pill ${hCls}'>${hLabel}</div>
    </div>
    ${cards}
    <div class='mon-tabs'>
      <button class='mon-tab' data-tab='issues'>Issues & Errors</button>
      <button class='mon-tab' data-tab='uptime'>Uptime Monitors</button>
      <button class='mon-tab' data-tab='performance'>Performance</button>
      <button class='mon-tab' data-tab='settings'>Settings & Keys</button>
    </div>

    <div class='mon-tab-pane' id='pane-issues'>
      <div class="native-issues-container">
        <div class="pane-head-row" style="display: flex; justify-content: space-between; align-items: center; width: 100%;">
          <div style="display: flex; align-items: center; gap: var(--s-2);">
            <h4>Active Issues & Errors</h4>
            <span class="cnt-badge" id="issues-cnt">0 active</span>
          </div>
          ${
    projectSlug
        ? `
          <a href="${esc(glitchtipProjectUrl)}" target="_blank" class="btn-sec-sm" style="text-decoration: none; display: inline-flex; align-items: center; gap: 6px; font-size: 11px; padding: 4px 10px; border-radius: var(--r-sm); font-weight: 600; cursor: pointer; border: 1px solid var(--line); background: var(--bg-sunken); color: var(--navy); outline: none;">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="width: 12px; height: 12px; stroke: var(--navy);"><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6M15 3h6v6M10 14L21 3"/></svg>
            Go to GlitchTip
          </a>
          `
        : ''
}
        </div>
        ${
    projectSlug
        ? `<div class="gt-service-status-banner configured" style="margin-bottom:20px;">
                 <span class="status-dot green"></span>
                 <span>GlitchTip project mapping is active: <strong>${esc(projectSlug)}</strong></span>
               </div>`
        : `<div class="gt-service-status-banner unconfigured" style="margin-bottom:20px;">
                 <span class="status-dot red"></span>
                 <span>GlitchTip mapping is <strong>not configured</strong> for this service. Traceback events will not be collected.</span>
               </div>`
}
        <div id="native-issues-list" class="native-list">
          <div class="list-loading"><span class="spinner-small"></span> Loading issues...</div>
        </div>
      </div>
    </div>

    <div class='mon-tab-pane' id='pane-uptime'>
      <div class="native-uptime-container">
        <div class="pane-head-row">
          <div>
            <h4>Uptime Monitors</h4>
            <span class="subtext">Endpoint reachability & status checks</span>
          </div>
          ${
    projectSlug
        ? `
          <button class="btn-primary-sm" onclick="toggleAddMonitorForm(true)">
            <svg class="ic" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
            Add Monitor
          </button>
          `
        : ''
}
        </div>

        ${
    projectSlug
        ? `<div class="gt-service-status-banner configured" style="margin-bottom:20px;">
                 <span class="status-dot green"></span>
                 <span>GlitchTip project mapping is active: <strong>${esc(projectSlug)}</strong></span>
               </div>`
        : `<div class="gt-service-status-banner unconfigured" style="margin-bottom:20px;">
                 <span class="status-dot red"></span>
                 <span>GlitchTip mapping is <strong>not configured</strong> for this service. Uptime monitors cannot be configured.</span>
               </div>`
}

        ${
    projectSlug
        ? `
        <div id="add-monitor-form-card" class="add-monitor-card hidden">
          <h5>Create Uptime Monitor</h5>
          <form id="add-monitor-form" onsubmit="submitAddMonitor(event)">
            <div class="form-row">
              <div class="form-group">
                <label>Monitor Name *</label>
                <input type="text" id="add-mon-name" placeholder="e.g. Health Check" required>
              </div>
              <div class="form-group">
                <label>Target URL *</label>
                <input type="url" id="add-mon-url" placeholder="e.g. http://10.0.0.5:8000/health" required>
              </div>
            </div>
            <div class="form-row">
              <div class="form-group">
                <label>Monitor Type</label>
                <select id="add-mon-type">
                  <option value="Ping">Ping (TCP Connect)</option>
                  <option value="GET">HTTP GET</option>
                  <option value="POST">HTTP POST</option>
                  <option value="Heartbeat">Heartbeat</option>
                </select>
              </div>
              <div class="form-group">
                <label>Interval (seconds)</label>
                <input type="number" id="add-mon-interval" value="60" min="30" required>
              </div>
            </div>
            <div class="form-row">
              <div class="form-group">
                <label>Expected HTTP Status</label>
                <input type="number" id="add-mon-status" value="200" min="100" max="599" required>
              </div>
              <div class="form-group">
                <label>Expected Response Body</label>
                <input type="text" id="add-mon-expected-body" placeholder="e.g. {&quot;status&quot;:&quot;ok&quot;}">
              </div>
              <div class="form-group">
                <label>Timeout (seconds)</label>
                <input type="number" id="add-mon-timeout" value="30" min="1" max="60" required>
              </div>
            </div>
            <div class="form-actions-row">
              <button type="button" class="btn-sec-sm" onclick="toggleAddMonitorForm(false)">Cancel</button>
              <button type="submit" class="btn-prim-sm">Create Monitor</button>
            </div>
          </form>
        </div>
        `
        : ''
}

        <div id="native-uptime-list" class="native-list">
          ${projectSlug ? '<div class="list-loading"><span class="spinner-small"></span> Loading monitors...</div>' : '<div class="empty-state-small"><p>No uptime monitors configured because GlitchTip is not mapped for this service.</p></div>'}
        </div>
      </div>
    </div>

    <div class='mon-tab-pane' id='pane-performance' style="padding: 20px 0;">
    </div>

    <div class='mon-tab-pane' id='pane-settings'>
      <div class="native-settings-container">
        <div class="pane-head-row">
          <div>
            <h4>DSN Keys & SDK Integration</h4>
            <span class="subtext">Configure client SDKs to send errors to this service</span>
          </div>
        </div>
        ${
    projectSlug
        ? `<div class="gt-service-status-banner configured" style="margin-bottom:20px;">
                 <span class="status-dot green"></span>
                 <span>GlitchTip integration is configured for this service. Project slug: <strong>${esc(projectSlug)}</strong></span>
               </div>`
        : `<div class="gt-service-status-banner unconfigured" style="margin-bottom:20px;">
                 <span class="status-dot red"></span>
                 <span>GlitchTip mapping is <strong>not configured</strong> for this service. DSN keys cannot be loaded.</span>
               </div>`
}
        <div id="native-keys-container" class="native-keys-wrap">
          <div class="list-loading"><span class="spinner-small"></span> Loading DSN keys...</div>
        </div>
      </div>
    </div>`;
}

function resolveGlitchTipBaseUrl () {
    if (GT_BASE_URL) return GT_BASE_URL.replace(/\/?$/, '/');
    if (window.location.protocol === 'https:')
        return `${window.location.origin}/glitchtip/`;
    return `http://${window.location.hostname}:9008/`;
}

/* ─── 6. tabs ─── */
function attachTabListeners () {
    document.querySelectorAll('.mon-tab').forEach((btn) => {
        btn.addEventListener('click', () => switchTab(btn.dataset.tab));
    });
}

function switchTab (tabId) {
    SM.activeTab = tabId;
    document
        .querySelectorAll('.mon-tab')
        .forEach((b) => b.classList.toggle('active', b.dataset.tab === tabId));
    document
        .querySelectorAll('.mon-tab-pane')
        .forEach((p) => p.classList.toggle('active', p.id === `pane-${tabId}`));

    loadActiveTabContent(tabId);
}

function loadActiveTabContent (tabId) {
    const service = SM.selection.service;
    if (!service) return;

    if (tabId === 'issues') {
        loadNativeIssues(service);
    } else if (tabId === 'uptime') {
        loadNativeUptimeMonitors(service);
    } else if (tabId === 'settings') {
        loadNativeKeys(service);
    } else if (tabId === 'performance') {
        loadPerformanceMetrics(service);
    }
}

async function loadNativeIssues (service) {
    const listEl = document.getElementById('native-issues-list');
    if (!listEl) return;

    try {
        let issues = SM.issuesCache[service];
        if (!issues) {
            const data = await post('/PlatformIO/Monitoring/Issues/', {
                service_name: service,
                window: SM.window,
            });
            if (!data.success) {
                listEl.innerHTML = `<div class="error-msg">Error: ${data.error || 'Failed to fetch issues'}</div>`;
                return;
            }
            issues = data.issues || [];
            SM.issuesCache[service] = issues;
        }

        if (SM.lastSelectedServiceForIssues !== service) {
            SM.lastSelectedServiceForIssues = service;
            SM.visibleIssuesLimit = 20;
        }

        const cntEl = document.getElementById('issues-cnt');
        if (cntEl) cntEl.textContent = `${issues.length} active`;

        if (!issues.length) {
            listEl.innerHTML = `
            <div class="empty-state-small">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" style="width:40px; height:40px; color:var(--ink-4); margin-bottom:12px;">
                <circle cx="12" cy="12" r="10"/><path d="M8 12h8"/>
              </svg>
              <p>No active issues found for this service.</p>
            </div>`;
            return;
        }

        // Detect which cards are currently expanded to preserve their state and content
        const expandedBefore = new Set();
        document
            .querySelectorAll('.issue-details:not(.hidden)')
            .forEach((el) => {
                const id = el.id.replace('issue-details-', '');
                expandedBefore.add(id);
            });

        const limit = SM.visibleIssuesLimit || 20;
        const slicedIssues = issues.slice(0, limit);

        let html = slicedIssues
            .map((issue) => {
                const level = (issue.level || 'error').toLowerCase();
                const lastSeenStr = fmtTime(issue.last_seen);
                const statusStr = issue.status || 'unresolved';
                const isExpanded = expandedBefore.has(issue.id);

                const oldDetails = document.getElementById(
                    `issue-details-${issue.id}`,
                );
                const oldContentHtml = oldDetails
                    ? oldDetails.querySelector('.details-content').innerHTML
                    : '';
                const oldLoaded = oldDetails ? oldDetails.dataset.loaded : '';

                return `
            <div class="issue-card" id="issue-card-${issue.id}">
              <div class="issue-main">
                <div class="issue-meta">
                  <span class="level-badge ${level}">${level.toUpperCase()}</span>
                  <span class="issue-count">Seen ${issue.count} times</span>
                  <span class="issue-time">Last seen ${lastSeenStr}</span>
                </div>
                <div class="issue-title-row">
                  <h5 class="issue-title" onclick="toggleIssueDetails('${issue.id}')">${esc(issue.title)}</h5>
                </div>
                <div class="issue-card-meta-row" style="margin-top: var(--s-2); display: flex; justify-content: space-between; align-items: center; gap: var(--s-3); font-size: 11px; color: var(--ink-3);">
                  <div>
                    <strong>Status:</strong> <span style="color:var(--ink-2); font-weight:600;">${statusStr.toUpperCase()}</span> &nbsp;•&nbsp;
                    <strong>First Seen:</strong> <span style="color:var(--ink-2);">${new Date(issue.first_seen).toLocaleString()}</span>
                  </div>
                  <a href="${esc(formatPermalink(issue.permalink || '', '', issue.id))}" target="_blank" class="link-external" style="font-weight: 600; color: var(--navy); text-decoration: none;">View full stack trace in GlitchTip ↗</a>
                </div>
              </div>
              <div class="issue-actions">
                ${statusStr !== 'resolved' ? `<button class="btn-action resolve" onclick="executeIssueAction('${issue.id}', 'resolved', '${service}')">Resolve</button>` : ''}
                ${statusStr !== 'ignored' ? `<button class="btn-action ignore" onclick="executeIssueAction('${issue.id}', 'ignored', '${service}')">Ignore</button>` : ''}
              </div>
              <div class="issue-details${isExpanded ? '' : ' hidden'}" id="issue-details-${issue.id}" ${oldLoaded ? 'data-loaded="true"' : ''}>
                <div class="details-content" style="${oldContentHtml ? 'padding: 10px 14px;' : ''} background: var(--bg-card); border-top: 1px solid var(--line);">
                  ${oldContentHtml || ''}
                </div>
              </div>
            </div>`;
            })
            .join('');

        if (issues.length > limit) {
            html += `
            <div class="load-more-container" style="text-align: center; margin-top: 20px; margin-bottom: 20px;">
              <button class="btn-sec-sm" id="load-more-issues-btn" onclick="loadMoreIssues('${service}')" style="height: 36px; padding: 0 20px; font-size: 13px; font-weight: 600; cursor: pointer; border-radius: var(--r-sm); border: 1px solid var(--line); background: var(--bg-card); color: var(--ink-2); outline: none;">
                Load More Issues (${issues.length - limit} remaining)
              </button>
            </div>`;
        }

        listEl.innerHTML = html;
    } catch (err) {
        listEl.innerHTML = `<div class="error-msg">Error: ${err.message || err}</div>`;
    }
}

async function executeIssueAction (issueId, action, service) {
    try {
        const card = document.getElementById(`issue-card-${issueId}`);
        if (card) card.style.opacity = '0.5';

        const data = await post('/PlatformIO/Monitoring/IssueAction/', {
            issue_id: issueId,
            action: action,
        });
        if (data.success) {
            loadNativeIssues(service);
            fetchHealth(service); // refresh main header badge
        } else {
            alert('Failed to update issue: ' + (data.error || 'Unknown error'));
            if (card) card.style.opacity = '1';
        }
    } catch (err) {
        alert('Error: ' + err.message);
    }
}

window.executeIssueAction = executeIssueAction;

window.loadMoreIssues = function (service) {
    SM.visibleIssuesLimit = (SM.visibleIssuesLimit || 20) + 20;
    loadNativeIssues(service);
};

window.toggleIssueDetails = async function (issueId) {
    const el = document.getElementById(`issue-details-${issueId}`);
    if (!el) return;

    const isHidden = el.classList.contains('hidden');
    el.classList.toggle('hidden');

    // If we are opening and it hasn't been loaded yet
    if (isHidden && !el.dataset.loaded) {
        const contentEl = el.querySelector('.details-content');
        if (contentEl) {
            contentEl.style.padding = '10px 14px';
            contentEl.innerHTML =
                '<div class="list-loading"><span class="spinner-small"></span> Loading event details from GlitchTip...</div>';
        }

        try {
            const data = await post(
                '/PlatformIO/Monitoring/Issues/EventDetails/',
                { issue_id: issueId },
            );
            if (!data.success) {
                contentEl.innerHTML = `<div class="error-msg">Error: ${data.error || 'Failed to fetch event details'}</div>`;
                return;
            }

            const event = data.event;
            if (!event) {
                contentEl.innerHTML =
                    '<div class="empty-state-small"><p>No event occurrences found for this issue.</p></div>';
                return;
            }

            // Mark as loaded
            el.dataset.loaded = 'true';

            // Build the detailed event view
            contentEl.innerHTML = renderDetailedEvent(event, issueId);
        } catch (err) {
            contentEl.innerHTML = `<div class="error-msg">Error: ${err.message || err}</div>`;
        }
    }
};

function fmtIncidentTime (isoStr) {
    if (!isoStr) return '—';
    try {
        const d = new Date(isoStr);
        const y = d.getFullYear().toString().slice(-2);
        const m = d.getMonth() + 1;
        const day = d.getDate();
        let hrs = d.getHours();
        const mins = d.getMinutes().toString().padStart(2, '0');
        const ampm = hrs >= 12 ? 'PM' : 'AM';
        hrs = hrs % 12;
        hrs = hrs ? hrs : 12;
        return `${m}/${day}/${y}, ${hrs}:${mins} ${ampm}`;
    } catch {
        return isoStr;
    }
}

async function loadNativeUptimeMonitors (service) {
    const listEl = document.getElementById('native-uptime-list');
    if (!listEl) return;

    try {
        const data = await post('/PlatformIO/Monitoring/Uptime/', {
            service_name: service,
        });
        if (!data.success) {
            listEl.innerHTML = `<div class="error-msg">Error: ${data.error || 'Failed to fetch monitors'}</div>`;
            return;
        }

        const monitors = data.monitors || [];
        const hasProject = !!data.project_slug;

        if (!monitors.length) {
            listEl.innerHTML = `
            <div class="empty-state-small">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" style="width:40px; height:40px; color:var(--ink-4); margin-bottom:12px;">
                <polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/>
              </svg>
              <p>${hasProject ? 'No uptime monitors configured for this service.' : 'GlitchTip mapping is not configured for this service. Uptime monitors cannot be loaded.'}</p>
              ${hasProject ? '<button class="btn-sec-sm" style="margin-top: 10px;" onclick="toggleAddMonitorForm(true)">Configure Monitor</button>' : ''}
            </div>`;
            return;
        }

        // Detect which check-details cards are currently expanded to preserve their state
        const expandedBefore = new Set();
        document
            .querySelectorAll('.monitor-checks-details[open]')
            .forEach((el) => {
                const id = el.id.replace('monitor-details-', '');
                expandedBefore.add(id);
            });

        const externalBase = (
            GT_EXTERNAL_URL ||
            GT_BASE_URL ||
            window.location.origin
        ).replace(/\/?$/, '');

        listEl.innerHTML = monitors
            .map((mon) => {
                const isExpanded = expandedBefore.has(String(mon.id));
                const isUp = mon.isUp;
                const statusCls =
                    isUp === true ? 'ok' : isUp === false ? 'err' : 'unknown';
                const statusLabel =
                    isUp === true
                        ? 'ONLINE'
                        : isUp === false
                            ? 'OFFLINE'
                            : 'UNKNOWN';

                // Uptime history dots (latest 60 checks)
                const checks = mon.checks || [];
                const recentChecks = checks.slice(0, 60).reverse();
                const historyBarsHtml =
                    recentChecks
                        .map((check) => {
                            const checkUp = check.isUp;
                            const tooltipText = `Time: ${new Date(check.startCheck).toLocaleTimeString()} - ${checkUp ? 'Success' : 'Failed'}`;
                            return `<span class="uptime-history-dot ${checkUp ? 'ok' : 'err'}" title="${esc(tooltipText)}"></span>`;
                        })
                        .join('') ||
                    '<span style="font-size:10px; color:var(--ink-4)">No check history</span>';

                // Filter status changes (transitions) for the Incidents log
                const incidentChecks = mon.incidents || [];

                let incidentsHtml = '';
                if (incidentChecks.length) {
                    const rows = incidentChecks
                        .map((c) => {
                            const isCheckUp = c.isUp;
                            const statusVal = isCheckUp ? 'Up' : 'Down';
                            const statusClass = isCheckUp ? 'ok' : 'err';
                            const reasonLabel = isCheckUp
                                ? 'OK'
                                : c.reason || 'Timeout';
                            const resTime = formatIncidentResponseTime(c);
                            const timeStr = fmtIncidentTime(c.startCheck);
                            return `
                    <tr style="border-bottom: 1px solid var(--line);">
                      <td style="padding: 6px 8px;"><span class="monitor-status-pill ${statusClass}" style="padding: 2px 6px; font-size: 9px; font-weight:600; border-radius:99px; display:inline-block;">${statusVal}</span></td>
                      <td style="padding: 6px 8px; font-family: var(--mono); color: var(--ink-2); font-weight: 500;">${esc(reasonLabel)}</td>
                      <td style="padding: 6px 8px; font-family: var(--mono); color: var(--ink-2);">${esc(resTime)}</td>
                      <td style="padding: 6px 8px; font-family: var(--mono); color: var(--ink-3);">${esc(timeStr)}</td>
                    </tr>`;
                        })
                        .join('');

                    incidentsHtml = `
                <div class="monitor-incidents-wrap" style="margin-top: 12px; border: 1px solid var(--line); border-radius: var(--r-sm); background: var(--bg-card); overflow: hidden;">
                  <div class="incidents-head" style="padding: 6px 12px; font-size: 11px; font-family: var(--mono); color: var(--err); border-bottom: 1px solid var(--line); background: var(--bg-sunken); font-weight: 600; display: flex; align-items: center; gap: 6px;">
                    <span class="status-dot red"></span>
                    <span>DOWNTIME INCIDENTS (${incidentChecks.filter((c) => !c.isUp).length} failures / ${incidentChecks.filter((c) => c.isUp).length} recoveries)</span>
                  </div>
                  <div class="incidents-body" style="overflow-x: auto; max-height: 250px; overflow-y: auto;">
                    <table style="width: 100%; border-collapse: collapse; font-size: 11px; text-align: left;">
                      <thead>
                        <tr style="background: var(--bg-sunken); border-bottom: 1px solid var(--line);">
                          <th style="padding: 4px 8px; font-family: var(--mono); font-size: 9px; text-transform: uppercase; color: var(--ink-3);">Status</th>
                          <th style="padding: 4px 8px; font-family: var(--mono); font-size: 9px; text-transform: uppercase; color: var(--ink-3);">Reason</th>
                          <th style="padding: 4px 8px; font-family: var(--mono); font-size: 9px; text-transform: uppercase; color: var(--ink-3);">Response time</th>
                          <th style="padding: 4px 8px; font-family: var(--mono); font-size: 9px; text-transform: uppercase; color: var(--ink-3);">Time</th>
                        </tr>
                      </thead>
                      <tbody>
                        ${rows}
                      </tbody>
                    </table>
                  </div>
                </div>`;
                } else {
                    incidentsHtml = `
                <div class="monitor-incidents-wrap" style="margin-top: 12px; border: 1px solid var(--line); border-radius: var(--r-sm); background: var(--bg-card); padding: 8px 12px; display: flex; align-items: center; gap: 8px; font-size: 11px; color: var(--ok); font-family: var(--mono);">
                  <span class="status-dot green" style="background: var(--ok); width: 6px; height: 6px; border-radius: 50%; display: inline-block;"></span>
                  <span>No downtime incidents detected in check history.</span>
                </div>`;
                }

                // Monitor Response Time Graph
                const graphChecks = checks.slice(0, 60);
                const responseTimes = graphChecks
                    .map((c) => parseFloat(c.responseTime || c.duration || 0))
                    .filter((t) => t > 0);
                let avgLat = '—';
                let graphHtml = '';
                if (responseTimes.length) {
                    const avg =
                        responseTimes.reduce((a, b) => a + b, 0) /
                        responseTimes.length;
                    avgLat = `${avg.toFixed(1)}ms`;

                    // Calculate 95th percentile to clamp outliers and keep graph readable
                    const sortedTimes = [...responseTimes].sort(
                        (a, b) => a - b,
                    );
                    const pct95Idx = Math.floor(sortedTimes.length * 0.95);
                    const pct95 = sortedTimes[pct95Idx];
                    const maxLat = Math.max(pct95 || 0, 10);

                    const chartData = graphChecks
                        .slice()
                        .reverse()
                        .map((c, i) => {
                            const rawVal = parseFloat(
                                c.responseTime || c.duration || 0,
                            );
                            return {
                                t: (graphChecks.length - i) * 60,
                                v: Math.min(rawVal, maxLat),
                                rawVal: rawVal,
                                time: c.startCheck,
                            };
                        });

                    graphHtml = `
                <div class="monitor-latency-graph" style="margin-top: 12px; border: 1px solid var(--line); border-radius: var(--r-sm); background: var(--bg-card); overflow: hidden;">
                  <div class="lat-graph-head" style="padding: 6px 12px; font-size: 11px; font-family: var(--mono); color: var(--ink-3); border-bottom: 1px solid var(--line); background: var(--bg-sunken); display: flex; justify-content: space-between;">
                    <span>RESPONSE TIME TIMELINE (LATEST ${graphChecks.length} RUNS)</span>
                    <span>AVG: <strong>${avgLat}</strong></span>
                  </div>
                  <div class="lat-graph-body" style="padding: 8px 12px 2px;">
                    ${renderChart(chartData, { max: maxLat * 1.1, color: 'var(--navy)', unit: 'ms' })}
                  </div>
                </div>`;
                }

                const historyChecks = checks.slice(0, 60);
                const checksTableRows =
                    historyChecks
                        .map((c) => {
                            const statusLabel = c.isUp ? 'UP' : 'DOWN';
                            const statusClass = c.isUp ? 'ok' : 'err';
                            const checkTime = new Date(
                                c.startCheck,
                            ).toLocaleString();
                            const resTime = c.responseTime
                                ? `${parseFloat(c.responseTime).toFixed(0)}`
                                : '—';

                            let code = '—';
                            let err = 'None';
                            if (c.reason) {
                                const reasonStr = String(c.reason);
                                if (
                                    reasonStr.toLowerCase().includes('status')
                                ) {
                                    const match = reasonStr.match(/\d+/);
                                    if (match) code = match[0];
                                }
                                err = reasonStr;
                            }

                            return `
                <tr style="border-bottom: 1px solid var(--line);">
                  <td style="padding: 4px 8px;"><span class="monitor-status-pill ${statusClass}" style="padding: 1px 4px; font-size: 8px; font-weight: 600; border-radius: 99px;">${statusLabel}</span></td>
                  <td style="padding: 4px 8px; font-family: var(--mono); color: var(--ink-2);">${esc(checkTime)}</td>
                  <td style="padding: 4px 8px; font-family: var(--mono); color: var(--ink-2);">${resTime === '—' ? '—' : resTime + 'ms'}</td>
                  <td style="padding: 4px 8px; font-family: var(--mono); color: var(--ink-2);">${esc(code)}</td>
                  <td style="padding: 4px 8px; font-family: var(--mono); color: var(--ink-3); max-width: 150px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;" title="${esc(err)}">${esc(err)}</td>
                </tr>`;
                        })
                        .join('') ||
                    '<tr><td colspan="5" style="text-align: center; color: var(--ink-4); padding: 8px;">No checks recorded.</td></tr>';

                const detailsHtml = `
            <details class="monitor-checks-details" id="monitor-details-${mon.id}" style="margin-top: 10px;" ${isExpanded ? 'open' : ''}>
              <summary style="cursor: pointer; font-size: 11px; font-family: var(--mono); color: var(--navy); outline: none; user-select: none;">View Monitor Check History (latest ${historyChecks.length} runs)</summary>
              <div class="monitor-checks-table-wrap" style="border: 1px solid var(--line); border-radius: var(--r-sm); overflow-x: auto; background: var(--bg-card); margin-top: 6px; max-height: 200px; overflow-y: auto;">
                <table class="monitor-checks-table" style="width: 100%; border-collapse: collapse; font-size: 11px; text-align: left;">
                  <thead>
                    <tr style="background: var(--bg-sunken); border-bottom: 1px solid var(--line);">
                      <th style="padding: 4px 8px; font-family: var(--mono); font-size: 9px; text-transform: uppercase; color: var(--ink-3);">Status</th>
                      <th style="padding: 4px 8px; font-family: var(--mono); font-size: 9px; text-transform: uppercase; color: var(--ink-3);">Time</th>
                      <th style="padding: 4px 8px; font-family: var(--mono); font-size: 9px; text-transform: uppercase; color: var(--ink-3);">Latency</th>
                      <th style="padding: 4px 8px; font-family: var(--mono); font-size: 9px; text-transform: uppercase; color: var(--ink-3);">Code</th>
                      <th style="padding: 4px 8px; font-family: var(--mono); font-size: 9px; text-transform: uppercase; color: var(--ink-3);">Error</th>
                    </tr>
                  </thead>
                  <tbody>
                    ${checksTableRows}
                  </tbody>
                </table>
              </div>
            </details>`;

                const glitchtipMonitorUrl = cleanGlitchtipUrl(
                    `${externalBase}/${GT_ORG || 'iktara'}/uptime-monitors/${mon.id}`,
                );

                return `
            <div class="monitor-card" id="monitor-card-${mon.id}">
              <div class="monitor-main">
                <div class="monitor-info">
                  <div class="monitor-title-row">
                    <h5 class="monitor-name">${esc(mon.name)}</h5>
                    <span class="monitor-status-pill ${statusCls}">${statusLabel}</span>
                  </div>
                  <div class="monitor-url">${esc(mon.url)}</div>
                  <div class="monitor-meta">
                    <span>Interval: ${mon.interval}s</span>
                    <span>Type: ${mon.monitorType}</span>
                    <span>Expected Status: ${mon.expectedStatus || 200}</span>
                  </div>
                </div>
                <div class="monitor-actions" style="display:flex; align-items:center; gap: 8px;">
                  <a href="${esc(glitchtipMonitorUrl)}" target="_blank" class="btn-sec-sm" style="text-decoration: none; display: inline-flex; align-items: center; gap: 4px; font-size: 11px; padding: 4px 10px; border-radius: var(--r-sm); font-weight: 600; cursor: pointer; border: 1px solid var(--line); background: var(--bg-sunken); color: var(--navy); outline: none;">
                    View in GlitchTip ↗
                  </a>
                  <button class="btn-action delete-danger" onclick="executeDeleteMonitor('${mon.id}', '${service}')">
                    <svg class="ic" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="width:14px; height:14px;"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/><line x1="10" y1="11" x2="10" y2="17"/><line x1="14" y1="11" x2="14" y2="17"/></svg>
                  </button>
                </div>
              </div>
              <div class="monitor-history">
                <div class="history-label">Status Timeline (latest ${recentChecks.length} runs)</div>
                <div class="history-dots">${historyBarsHtml}</div>
                ${incidentsHtml}
                ${graphHtml}
                ${detailsHtml}
              </div>
            </div>`;
            })
            .join('');
    } catch (err) {
        listEl.innerHTML = `<div class="error-msg">Error: ${err.message || err}</div>`;
    }
}

async function executeDeleteMonitor (monitorId, service) {
    if (!confirm('Are you sure you want to delete this uptime monitor?'))
        return;

    try {
        const card = document.getElementById(`monitor-card-${monitorId}`);
        if (card) card.style.opacity = '0.5';

        const data = await post('/PlatformIO/Monitoring/Uptime/Delete/', {
            monitor_id: monitorId,
        });
        if (data.success) {
            loadNativeUptimeMonitors(service);
        } else {
            alert(
                'Failed to delete monitor: ' + (data.error || 'Unknown error'),
            );
            if (card) card.style.opacity = '1';
        }
    } catch (err) {
        alert('Error: ' + err.message);
    }
}

window.executeDeleteMonitor = executeDeleteMonitor;

async function submitAddMonitor (event) {
    event.preventDefault();
    const service = SM.selection.service;
    if (!service) return;

    const name = document.getElementById('add-mon-name').value;
    const url = document.getElementById('add-mon-url').value;
    const monitorType = document.getElementById('add-mon-type').value;
    const interval = document.getElementById('add-mon-interval').value;
    const expectedStatus = document.getElementById('add-mon-status').value;
    const timeout = document.getElementById('add-mon-timeout').value;
    const expectedBody = document.getElementById('add-mon-expected-body')
        ? document.getElementById('add-mon-expected-body').value
        : '';

    const btn = document.querySelector(
        '#add-monitor-form button[type="submit"]',
    );
    const originalText = btn.textContent;
    btn.disabled = true;
    btn.textContent = 'Creating...';

    try {
        const data = await post('/PlatformIO/Monitoring/Uptime/Add/', {
            service_name: service,
            name: name,
            monitor_type: monitorType,
            url: url,
            interval: interval,
            expected_status: expectedStatus,
            timeout: timeout,
            expected_body: expectedBody,
        });

        if (data.success) {
            document.getElementById('add-monitor-form').reset();
            toggleAddMonitorForm(false);
            loadNativeUptimeMonitors(service);
        } else {
            alert(
                'Failed to create monitor: ' + (data.error || 'Unknown error'),
            );
        }
    } catch (err) {
        alert('Error: ' + err.message);
    } finally {
        btn.disabled = false;
        btn.textContent = originalText;
    }
}

window.submitAddMonitor = submitAddMonitor;

function toggleAddMonitorForm (show) {
    const card = document.getElementById('add-monitor-form-card');
    if (card) {
        card.classList.toggle('hidden', !show);
    }
}

window.toggleAddMonitorForm = toggleAddMonitorForm;

async function loadNativeKeys (service) {
    const container = document.getElementById('native-keys-container');
    if (!container) return;

    try {
        const data = await post('/PlatformIO/Monitoring/Keys/', {
            service_name: service,
        });
        if (!data.success) {
            container.innerHTML = `<div class="error-msg">Error: ${data.error || 'Failed to fetch project keys'}</div>`;
            return;
        }

        const keys = data.keys || [];
        if (!keys.length) {
            container.innerHTML = `
            <div class="empty-state-small">
              <p>No project DSN keys found. Please check your project settings on GlitchTip.</p>
            </div>`;
            return;
        }

        const dsn = keys[0].dsn.public;

        container.innerHTML = `
        <div class="keys-dashboard">
          <div class="dsn-card">
            <div class="dsn-header">
              <h5>DSN (Data Source Name)</h5>
              <button class="btn-prim-sm-outline" onclick="copyToClipboard('${esc(dsn)}')">Copy Key</button>
            </div>
            <div class="dsn-value-box">
              <code>${esc(dsn)}</code>
            </div>
            <span class="dsn-info-sub">Pass this DSN to your application SDK to capture and stream exceptions.</span>
          </div>

          <div class="integration-guide">
            <h5>SDK Quick Start</h5>
            <div class="guide-tabs">
              <button class="guide-tab active" onclick="switchGuideTab('python')">Python</button>
              <button class="guide-tab" onclick="switchGuideTab('javascript')">Javascript</button>
              <button class="guide-tab" onclick="switchGuideTab('go')">Go</button>
            </div>

            <div id="guide-pane-python" class="guide-pane active">
              <h6>1. Install Sentry SDK:</h6>
              <pre><code>pip install sentry-sdk</code></pre>
              <h6>2. Initialize Sentry in your code:</h6>
              <pre><code>import sentry_sdk

sentry_sdk.init(
    dsn="${esc(dsn)}",
    traces_sample_rate=1.0,
)</code></pre>
            </div>
            <div id="guide-pane-javascript" class="guide-pane">
              <h6>1. Install Sentry Browser SDK:</h6>
              <pre><code>npm install --save @sentry/browser</code></pre>
              <h6>2. Initialize Browser integration:</h6>
              <pre><code>import * as Sentry from "@sentry/browser";

Sentry.init({
  dsn: "${esc(dsn)}",
  tracesSampleRate: 1.0,
});</code></pre>
            </div>
            <div id="guide-pane-go" class="guide-pane">
              <h6>1. Get Go SDK:</h6>
              <pre><code>go get github.com/getsentry/sentry-go</code></pre>
              <h6>2. Initialize in your main function:</h6>
              <pre><code>import (
	"fmt"
	"github.com/getsentry/sentry-go"
)

func main() {
	err := sentry.Init(sentry.ClientOptions{
		Dsn: "${esc(dsn)}",
	})
	if err != nil {
		fmt.Printf("sentry.Init: %s\\n", err)
	}
}</code></pre>
            </div>
          </div>
        </div>`;
    } catch (err) {
        container.innerHTML = `<div class="error-msg">Error: ${err.message || err}</div>`;
    }
}

function copyToClipboard (text) {
    navigator.clipboard
        .writeText(text)
        .then(() => {
            alert('DSN Key copied to clipboard!');
        })
        .catch((err) => {
            alert('Failed to copy text: ' + err);
        });
}
window.copyToClipboard = copyToClipboard;

function switchGuideTab (lang) {
    document
        .querySelectorAll('.guide-tab')
        .forEach((b) =>
            b.classList.toggle(
                'active',
                b.textContent.toLowerCase().includes(lang),
            ),
        );
    document
        .querySelectorAll('.guide-pane')
        .forEach((p) =>
            p.classList.toggle('active', p.id === `guide-pane-${lang}`),
        );
}
window.switchGuideTab = switchGuideTab;

async function loadPerformanceMetrics (service) {
    const container = document.getElementById('pane-performance');
    if (!container) return;

    container.innerHTML =
        '<div class="list-loading"><span class="spinner-small"></span> Loading performance transactions from GlitchTip...</div>';

    try {
        const data = await post('/PlatformIO/Monitoring/Performance/', {
            service_name: service,
        });
        if (!data.success) {
            container.innerHTML = `<div class="error-msg">Error: ${data.error || 'Failed to fetch performance transactions'}</div>`;
            return;
        }

        const transactions = data.transactions || [];
        const projectSlug = data.project_slug || '';

        // Cache for client-side sorting
        SM.currentTransactions = transactions;
        SM.currentProjectSlug = projectSlug;
        SM.currentSortColumn = 'duration';
        SM.currentSortOrder = 'desc';

        renderPerformanceTransactions(
            service,
            transactions,
            projectSlug,
            data.node_ip,
        );
    } catch (err) {
        container.innerHTML = `<div class="error-msg">Error: ${err.message || err}</div>`;
    }
}

function renderPerformanceTableBody (transactions, projectSlug) {
    const tbody = document.querySelector('.perf-table tbody');
    if (!tbody) return;

    if (!transactions.length) {
        tbody.innerHTML =
            '<tr><td colspan="2" style="text-align: center; color: var(--ink-4); padding: var(--s-4);">No transactions to display.</td></tr>';
        return;
    }

    const rows = transactions
        .map((t) => {
            const title = t.transaction || '—';
            const projName =
                t.projectName || projectSlug || SM.selection.service;
            const durationFormatted = formatDuration(t.avgDuration);

            // Sentry transaction detail url
            const tUrl = getTransactionDetailUrl(t.id);

            return `
        <tr>
          <td>
            <div class="transaction-title-cell" style="display: flex; flex-direction: column; gap: 2px;">
              <span class="tx-title-text" style="font-family: var(--mono); font-size: 12.5px; font-weight: 500; word-break: break-all;">
                <a href="${esc(tUrl)}" target="_blank" class="tx-title-link" style="text-decoration: none; color: var(--navy); font-weight: 500;">${esc(title)}</a>
              </span>
              <span class="tx-proj-text" style="font-family: var(--mono); font-size: 11px; color: var(--ink-4);">${esc(projName)} —</span>
            </div>
          </td>
          <td class="tx-duration-cell" style="font-family: var(--mono); font-size: 12.5px; font-weight: 500; text-align: right; color: var(--ink-2); white-space: nowrap; padding-left: 20px;">${esc(durationFormatted)}</td>
        </tr>`;
        })
        .join('');

    tbody.innerHTML = rows;
}

window.sortTransactionsFromSelect = function (sortVal) {
    if (!SM.currentTransactions) return;

    const sorted = [...SM.currentTransactions];
    if (sortVal === 'slowest') {
        SM.currentSortColumn = 'duration';
        SM.currentSortOrder = 'desc';
        sorted.sort(
            (a, b) =>
                parseFloat(b.avgDuration || 0) - parseFloat(a.avgDuration || 0),
        );
    } else if (sortVal === 'fastest') {
        SM.currentSortColumn = 'duration';
        SM.currentSortOrder = 'asc';
        sorted.sort(
            (a, b) =>
                parseFloat(a.avgDuration || 0) - parseFloat(b.avgDuration || 0),
        );
    } else if (sortVal === 'count') {
        SM.currentSortColumn = 'count';
        SM.currentSortOrder = 'desc';
        sorted.sort((a, b) => parseInt(b.count || 0) - parseInt(a.count || 0));
    } else if (sortVal === 'title') {
        SM.currentSortColumn = 'title';
        SM.currentSortOrder = 'asc';
        sorted.sort((a, b) =>
            (a.transaction || '').localeCompare(b.transaction || ''),
        );
    }

    // Update visual header indicator icons if headers exist
    const iconTitle = document.querySelector('.sort-icon-title');
    const iconDuration = document.querySelector('.sort-icon-duration');
    if (iconTitle)
        iconTitle.textContent = SM.currentSortColumn === 'title' ? ' ▲' : '';
    if (iconDuration)
        iconDuration.textContent =
            SM.currentSortColumn === 'duration'
                ? SM.currentSortOrder === 'asc'
                    ? ' ▲'
                    : ' ▼'
                : '';

    renderPerformanceTableBody(sorted, SM.currentProjectSlug || '');
};

window.toggleTransactionTableHeaderSort = function (col) {
    if (!SM.currentTransactions) return;

    if (SM.currentSortColumn === col) {
        SM.currentSortOrder = SM.currentSortOrder === 'asc' ? 'desc' : 'asc';
    } else {
        SM.currentSortColumn = col;
        SM.currentSortOrder = col === 'duration' ? 'desc' : 'asc';
    }

    // Update select dropdown value to match if applicable
    const select = document.getElementById('perf-sort-select');
    if (select) {
        if (SM.currentSortColumn === 'duration') {
            select.value =
                SM.currentSortOrder === 'desc' ? 'slowest' : 'fastest';
        } else if (SM.currentSortColumn === 'title') {
            select.value = 'title';
        }
    }

    // Update visual header indicator icons
    const iconTitle = document.querySelector('.sort-icon-title');
    const iconDuration = document.querySelector('.sort-icon-duration');
    if (iconTitle)
        iconTitle.textContent =
            SM.currentSortColumn === 'title'
                ? SM.currentSortOrder === 'asc'
                    ? ' ▲'
                    : ' ▼'
                : '';
    if (iconDuration)
        iconDuration.textContent =
            SM.currentSortColumn === 'duration'
                ? SM.currentSortOrder === 'asc'
                    ? ' ▲'
                    : ' ▼'
                : '';

    const sorted = [...SM.currentTransactions];
    if (SM.currentSortColumn === 'duration') {
        sorted.sort((a, b) => {
            const diff =
                parseFloat(b.avgDuration || 0) - parseFloat(a.avgDuration || 0);
            return SM.currentSortOrder === 'desc' ? diff : -diff;
        });
    } else {
        sorted.sort((a, b) => {
            const diff = (a.transaction || '').localeCompare(
                b.transaction || '',
            );
            return SM.currentSortOrder === 'asc' ? diff : -diff;
        });
    }

    renderPerformanceTableBody(sorted, SM.currentProjectSlug || '');
};

function renderPerformanceTransactions (
    service,
    transactions,
    projectSlug,
    nodeIp,
) {
    const container = document.getElementById('pane-performance');
    if (!container) return;

    if (!transactions.length) {
        container.innerHTML = `
        <div class="empty-state-small">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" style="width:40px; height:40px; color:var(--ink-4); margin-bottom:12px;">
            <circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/>
          </svg>
          <p>No performance transaction groups found for this project in GlitchTip.</p>
        </div>`;
        return;
    }

    // Default sort slowest first
    const sorted = [...transactions].sort(
        (a, b) =>
            parseFloat(b.avgDuration || 0) - parseFloat(a.avgDuration || 0),
    );

    container.innerHTML = `
    <div class="gt-performance-dashboard" style="padding: 10px 0;">
      <div class="perf-header-row" style="margin-bottom: 20px;">
        <h4 style="font-size: 15px; font-weight: 600; margin: 0; color: var(--ink);">Transaction Groups (${transactions.length})</h4>
        <span class="subtext" style="font-size: 12px; color: var(--ink-3);">Slowest API routes and worker executions</span>
      </div>

      <!-- Interactive GlitchTip Filter Controls -->
      <div class="perf-filters-bar" style="display: flex; flex-wrap: wrap; gap: var(--s-3); margin-bottom: 20px; background: var(--bg-sunken); padding: 12px; border-radius: var(--r-md);">
        <div class="filter-item" style="display: flex; flex-direction: column; gap: 4px;">
          <label style="font-size: 10px; font-family: var(--mono); text-transform: uppercase; color: var(--ink-4);">Project</label>
          <select class="perf-select" style="padding: 4px 8px; font-size: 11.5px; border: 1px solid var(--line); border-radius: var(--r-sm); background: var(--bg-card); color: var(--ink-3);" disabled>
            <option>${esc(projectSlug || 'All projects')}</option>
          </select>
        </div>
        <div class="filter-item" style="display: flex; flex-direction: column; gap: 4px;">
          <label style="font-size: 10px; font-family: var(--mono); text-transform: uppercase; color: var(--ink-4);">Time</label>
          <select class="perf-select" style="padding: 4px 8px; font-size: 11.5px; border: 1px solid var(--line); border-radius: var(--r-sm); background: var(--bg-card); color: var(--ink-3);" disabled>
            <option>All times</option>
          </select>
        </div>
        <div class="filter-item" style="display: flex; flex-direction: column; gap: 4px;">
          <label style="font-size: 10px; font-family: var(--mono); text-transform: uppercase; color: var(--ink-4);">Environment</label>
          <select class="perf-select" style="padding: 4px 8px; font-size: 11.5px; border: 1px solid var(--line); border-radius: var(--r-sm); background: var(--bg-card); color: var(--ink-3);" disabled>
            <option>${esc(nodeIp || 'All environments')}</option>
          </select>
        </div>
        <div class="filter-item" style="display: flex; flex-direction: column; gap: 4px;">
          <label style="font-size: 10px; font-family: var(--mono); text-transform: uppercase; color: var(--ink-4);">Sort by</label>
          <select class="perf-select" id="perf-sort-select" onchange="sortTransactionsFromSelect(this.value)" style="padding: 4px 8px; font-size: 11.5px; border: 1px solid var(--line); border-radius: var(--r-sm); background: var(--bg-card); color: var(--ink-2); cursor: pointer; outline: none;">
            <option value="slowest">Slowest</option>
            <option value="fastest">Fastest</option>
            <option value="count">Most Frequent</option>
            <option value="title">Title (A-Z)</option>
          </select>
        </div>
      </div>

      <div class="perf-table-wrap" style="border: 1px solid var(--line); border-radius: var(--r-md); overflow: hidden; background: var(--bg-card);">
        <table class="perf-table" style="width: 100%; border-collapse: collapse; font-size: 12.5px; text-align: left;">
          <thead>
            <tr style="border-bottom: 1px solid var(--line); background: var(--bg-sunken);padding-left:14px;">
              <th onclick="toggleTransactionTableHeaderSort('title')" style="cursor: pointer; padding: 10px 14px; font-family: var(--mono); font-size: 10px; text-transform: uppercase; color: var(--ink-3); user-select: none;">Title <span class="sort-icon-title"></span></th>
              <th onclick="toggleTransactionTableHeaderSort('duration')" style="cursor: pointer; padding: 10px 14px; font-family: var(--mono); font-size: 10px; text-transform: uppercase; color: var(--ink-3); text-align: right; user-select: none;">Average Duration <span class="sort-icon-duration"> ▼</span></th>
            </tr>
          </thead>
          <tbody>
          </tbody>
        </table>
      </div>
    </div>`;

    renderPerformanceTableBody(sorted, projectSlug);
}

function formatDuration (sec) {
    if (sec === undefined || sec === null) return '—';
    const val = parseFloat(sec);
    if (isNaN(val)) return sec;

    let seconds = val;
    if (val > 10) {
        seconds = val / 1000;
    }

    if (seconds >= 1.0) {
        return `${seconds.toFixed(2)} seconds`;
    } else {
        return `${(seconds * 1000).toFixed(3)}ms`;
    }
}

function renderDetailedEvent (event, issueId) {
    const eventId = event.eventID || event.id || '—';
    const dateStr =
        event.dateCreated || event.datetime
            ? new Date(event.dateCreated || event.datetime).toLocaleString()
            : '—';

    let runtimeHtml = '';
    if (event.contexts && event.contexts.runtime) {
        const rt = event.contexts.runtime;
        runtimeHtml = `
        <div class="runtime-info" style="display: inline-flex; align-items: center; gap: 6px; font-family: var(--mono); font-size: 11px; color: var(--ink-3);">
          <svg class="ic" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="width:14px; height:14px; color: var(--navy);"><path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5"/></svg>
          <strong>Runtime:</strong> ${esc(rt.name)} ${esc(rt.version || '')}
        </div>`;
    }

    let sdkHtml = '';
    if (event.sdk) {
        sdkHtml = `
        <div class="sdk-info" style="display: inline-flex; align-items: center; gap: 6px; font-family: var(--mono); font-size: 11px; color: var(--ink-3);">
          <strong>SDK:</strong> ${esc(event.sdk.name)} v${esc(event.sdk.version)}
        </div>`;
    }

    let tagsHtml = '';
    if (event.tags) {
        let tagsList = [];
        if (Array.isArray(event.tags)) {
            tagsList = event.tags;
        } else {
            tagsList = Object.entries(event.tags).map(([k, v]) => ({
                key: k,
                value: v,
            }));
        }
        if (tagsList.length) {
            tagsHtml = `
            <div class="event-tags-section" style="margin-top: 12px;">
              <strong style="font-size: 11px; color: var(--ink-3); display: block; margin-bottom: 6px;">Event Tags</strong>
              <div class="tags-badge-grid" style="display: flex; flex-wrap: wrap; gap: 6px;">
                ${tagsList
        .map(
            (t) => `
                  <span class="tag-badge" style="display: inline-flex; align-items: center; border: 1px solid var(--line); border-radius: var(--r-sm); font-size: 10px; font-family: var(--mono); overflow: hidden;">
                    <span class="tag-k" style="background: var(--bg-sunken); padding: 2px 6px; border-right: 1px solid var(--line); color: var(--ink-3);">${esc(t.key)}</span>
                    <span class="tag-v" style="background: var(--bg-card); padding: 2px 6px; color: var(--ink-2); font-weight: 500;">${esc(t.value)}</span>
                  </span>
                `,
        )
        .join('')}
              </div>
            </div>`;
        }
    }

    let messageHtml = '';
    let message = event.message || '';
    if (!message && event.entries) {
        const msgEntry = event.entries.find((e) => e.type === 'message');
        if (msgEntry && msgEntry.data) {
            message = msgEntry.data.message || msgEntry.data.formatted || '';
        }
    }
    if (message) {
        messageHtml = `
        <div class="event-message-box" style="margin-top: 14px; background: var(--bg-card); border: 1px solid var(--line); border-radius: var(--r-sm); padding: 10px 14px;">
          <strong style="font-size: 11px; color: var(--ink-3); display: block; margin-bottom: 6px;">Message</strong>
          <pre style="margin: 0; white-space: pre-wrap; font-family: var(--mono); font-size: 12px; color: var(--ink-2);"><code style="font-family: inherit;">${esc(message)}</code></pre>
        </div>`;
    }

    let exceptions = [];
    if (event.entries) {
        const excEntry = event.entries.find((e) => e.type === 'exception');
        if (excEntry && excEntry.data && excEntry.data.values) {
            exceptions = excEntry.data.values;
        }
    }
    if (!exceptions.length && event.exception && event.exception.values) {
        exceptions = event.exception.values;
    }

    let excHtml = '';
    if (exceptions.length) {
        excHtml = exceptions
            .map((exc) => {
                const frames = exc.stacktrace?.frames || [];
                const framesHtml = frames
                    .map((frame) => {
                        const filename = frame.filename || frame.abs_path || '';
                        const fnName = frame.function || 'anonymous';
                        const lineNo =
                            frame.lineNo ||
                            frame.line_no ||
                            frame.lineNumber ||
                            '?';

                        let contextLinesHtml = '';
                        if (frame.context && Array.isArray(frame.context)) {
                            contextLinesHtml = frame.context
                                .map(([num, line]) => {
                                    const isErrLine =
                                        parseInt(num) === parseInt(lineNo);
                                    return `<div class="code-line${isErrLine ? ' error-line' : ''}" style="display: flex; font-size: 11.5px; line-height: 1.4; font-family: var(--mono); ${isErrLine ? 'background: color-mix(in srgb, var(--err) 10%, var(--bg-card)); border-left: 3px solid var(--err);' : ''}"><span class="line-num" style="display: inline-block; width: 34px; text-align: right; color: var(--ink-4); padding-right: 8px; user-select: none;">${num}</span><span class="line-code" style="white-space: pre; color: ${isErrLine ? 'var(--err)' : 'var(--ink)'};">${esc(line)}</span></div>`;
                                })
                                .join('');
                        } else if (frame.context_line) {
                            contextLinesHtml = `<div class="code-line error-line" style="display: flex; font-size: 11.5px; line-height: 1.4; font-family: var(--mono); background: color-mix(in srgb, var(--err) 10%, var(--bg-card)); border-left: 3px solid var(--err);"><span class="line-num" style="display: inline-block; width: 34px; text-align: right; color: var(--ink-4); padding-right: 8px; user-select: none;">${lineNo}</span><span class="line-code" style="white-space: pre; color: var(--err);">${esc(frame.context_line)}</span></div>`;
                        }

                        let varsHtml = '';
                        const localVars = frame.vars || frame.variables;
                        if (localVars && Object.keys(localVars).length) {
                            const rows = Object.entries(localVars)
                                .map(([k, v]) => {
                                    let valStr = '';
                                    try {
                                        valStr =
                                            typeof v === 'object'
                                                ? JSON.stringify(v)
                                                : String(v);
                                    } catch {
                                        valStr = String(v);
                                    }
                                    return `<tr><td class="var-k" style="padding: 4px 8px; font-weight: 600; color: var(--ink-2); background: var(--bg-sunken); border-right: 1px solid var(--line); width: 150px; border-bottom: 1px solid var(--line);">${esc(k)}</td><td class="var-v" style="padding: 4px 8px; color: var(--navy); border-bottom: 1px solid var(--line); word-break: break-all;">${esc(valStr)}</td></tr>`;
                                })
                                .join('');
                            varsHtml = `
                    <details class="frame-vars-details" style="margin-top: 6px;">
                      <summary style="cursor: pointer; font-size: 11px; font-family: var(--mono); color: var(--navy); outline: none; margin-bottom: 4px; user-select: none;">Local Variables</summary>
                      <div class="frame-vars-table-wrap" style="border: 1px solid var(--line); border-radius: var(--r-sm); overflow-x: auto; background: var(--bg-card);">
                        <table class="frame-vars-table" style="width: 100%; border-collapse: collapse; font-family: var(--mono); font-size: 11px; text-align: left;">
                          <tbody>
                            ${rows}
                          </tbody>
                        </table>
                      </div>
                    </details>`;
                        }

                        return `
                <div class="traceback-frame" style="padding: var(--s-3) 0; border-bottom: 1px solid var(--line);">
                  <div class="frame-header" style="font-size: 12px; margin-bottom: 6px; color: var(--ink-2);">
                    <span class="frame-file" style="font-family: var(--mono); font-weight: 500; color: var(--ink);">${esc(filename)}</span> in <span class="frame-func" style="font-family: var(--mono); font-weight: 600; color: var(--navy);">${esc(fnName)}</span> at line <span class="frame-line" style="font-family: var(--mono); font-weight: 600; color: var(--ink);">${lineNo}</span>
                  </div>
                  ${contextLinesHtml ? `<div class="frame-code-block" style="border: 1px solid var(--line); border-radius: var(--r-sm); background: var(--bg-sunken); padding: var(--s-2) 0; overflow-x: auto;">${contextLinesHtml}</div>` : ''}
                  ${varsHtml}
                </div>`;
                    })
                    .join('');

                return `
            <div class="exception-block" style="margin-bottom: 20px; border: 1px solid var(--line); border-radius: var(--r-md); overflow: hidden; background: var(--bg-card);">
              <div class="exception-type-row" style="padding: 10px 14px; background: color-mix(in srgb, var(--err) 5%, var(--bg-sunken)); border-bottom: 1px solid var(--line); display: flex; flex-direction: column; gap: 2px;">
                <span class="exception-class" style="font-family: var(--mono); font-weight: 700; color: var(--err); font-size: 13.5px;">${esc(exc.type)}</span>
                <span class="exception-msg" style="font-family: var(--mono); font-size: 12px; color: var(--ink-2); word-break: break-all;">${esc(exc.value)}</span>
              </div>
              <div class="traceback-frames-list" style="padding: 0 var(--s-4);">
                ${framesHtml}
              </div>
            </div>`;
            })
            .join('');
    }

    let breadcrumbs = [];
    if (event.entries) {
        const bcEntry = event.entries.find((e) => e.type === 'breadcrumbs');
        if (bcEntry && bcEntry.data && bcEntry.data.values) {
            breadcrumbs = bcEntry.data.values;
        }
    }
    if (!breadcrumbs.length && event.breadcrumbs) {
        breadcrumbs = event.breadcrumbs.values || event.breadcrumbs;
    }

    let bcHtml = '';
    if (breadcrumbs && breadcrumbs.length) {
        const bcRows = breadcrumbs
            .map((bc) => {
                const timeStr = bc.timestamp
                    ? new Date(bc.timestamp).toLocaleTimeString()
                    : '—';
                const category = bc.category || bc.type || 'default';
                const msg = bc.message || '';
                const catClass = `category-${category.toLowerCase().replace(/[^a-z0-9]/g, '-')}`;

                let dataHtml = '';
                if (bc.data && Object.keys(bc.data).length) {
                    dataHtml = `<div class="bc-data-box" style="margin-top: 4px; font-family: var(--mono); font-size: 10px; color: var(--ink-3); background: var(--bg-card); padding: 4px 8px; border: 1px solid var(--line); border-radius: 3px;">${Object.entries(
                        bc.data,
                    )
                        .map(
                            ([k, v]) =>
                                `<span><strong>${esc(k)}:</strong> ${esc(v)}</span>`,
                        )
                        .join(' | ')}</div>`;
                }

                let badgeBg = 'var(--bg-sunken)';
                let badgeColor = 'var(--ink-2)';
                if (category.includes('query') || category.includes('db')) {
                    badgeBg = 'var(--navy-50)';
                    badgeColor = 'var(--navy)';
                } else if (category.includes('redis')) {
                    badgeBg = '#fff5eb';
                    badgeColor = '#d9480f';
                } else if (
                    category.includes('process') ||
                    category.includes('sub')
                ) {
                    badgeBg = 'var(--ok-bg)';
                    badgeColor = 'var(--ok)';
                } else if (
                    category.includes('http') ||
                    category.includes('xhr')
                ) {
                    badgeBg = '#f3e8ff';
                    badgeColor = '#7e22ce';
                }

                return `
            <div class="bc-row ${catClass}" style="display: flex; align-items: flex-start; gap: 12px; padding: 10px 0; border-bottom: 1px dashed var(--line);">
              <div class="bc-time" style="font-family: var(--mono); font-size: 10.5px; color: var(--ink-4); width: 85px; flex-shrink: 0;">${esc(timeStr)}</div>
              <div class="bc-category-badge" style="font-family: var(--mono); font-size: 10px; font-weight: 600; padding: 1px 6px; border-radius: 3px; background: ${badgeBg}; color: ${badgeColor}; text-transform: uppercase; flex-shrink: 0;">${esc(category)}</div>
              <div class="bc-content" style="flex: 1; min-width: 0;">
                <div class="bc-msg" style="font-family: var(--mono); font-size: 12px; color: var(--ink-2); word-break: break-all;">${esc(msg)}</div>
                ${dataHtml}
              </div>
            </div>`;
            })
            .join('');

        bcHtml = `
        <div class="event-breadcrumbs-wrap" style="margin-top: 20px;">
          <strong style="font-size: 11px; color: var(--ink-3); display: block; margin-bottom: 10px;">Breadcrumbs Log</strong>
          <div class="breadcrumbs-timeline" style="border-top: 1px solid var(--line); padding-top: 4px;">
            ${bcRows}
          </div>
        </div>`;
    }

    return `
    <div class="event-details-expanded" style="display: flex; flex-direction: column; gap: var(--s-3); border-top: 1px dashed var(--line); padding-top: var(--s-4); margin-top: var(--s-2);">
      <div class="event-metadata-row" style="display: flex; justify-content: space-between; font-size: 11px; color: var(--ink-3); flex-wrap: wrap; gap: 8px;">
        <div><strong>Event UUID:</strong> <code style="font-family: var(--mono); color: var(--navy); font-size: 11.5px;">${esc(eventId)}</code></div>
        <div><strong>Date/Time:</strong> ${esc(dateStr)}</div>
      </div>
      <div class="event-env-row" style="display: flex; gap: var(--s-4); font-size: 11px; color: var(--ink-3); flex-wrap: wrap;">
        ${runtimeHtml}
        ${sdkHtml}
      </div>
      ${tagsHtml}
      ${messageHtml}
      ${excHtml ? `<div class="event-exception-section" style="margin-top: 14px;">${excHtml}</div>` : ''}
      ${bcHtml}
      <div class="collapse-trace-btn-wrapper" style="padding: 10px 0 0; text-align: right; border-top: 1px solid var(--line); margin-top: var(--s-3);">
        <button class="btn-sec-sm" style="padding: 4px 10px; font-size: 11px; font-weight: 600; cursor: pointer; border: 1px solid var(--line); border-radius: var(--r-sm); background: var(--bg-sunken); color: var(--ink-2); outline: none;" onclick="toggleIssueDetails('${issueId}')">Collapse Traceback</button>
      </div>
    </div>`;
}

async function refreshActiveServiceData (service) {
    const formCard = document.getElementById('add-monitor-form-card');
    const isFormVisible = formCard && !formCard.classList.contains('hidden');

    try {
        await Promise.all([fetchHealth(service), fetchIssues(service)]);

        const health = SM.healthCache[service] || {};
        const containerRunning = health.running === true;
        const hCls = containerRunning ? 'ok' : 'err';
        const hLabel = containerRunning ? 'Healthy' : 'Error';
        const healthPill = document.querySelector('.svc-header .health-pill');
        if (healthPill) {
            healthPill.className = `health-pill ${hCls}`;
            healthPill.textContent = hLabel;
        }

        const issues = SM.issuesCache[service] || [];
        const errCount = issues.filter((i) =>
            ['error', 'fatal'].includes(i.level),
        ).length;
        const warnCount = issues.filter((i) => i.level === 'warning').length;
        const state = health.container_state || '—';

        const scValues = document.querySelectorAll('.summary-card .sc-value');
        if (scValues.length >= 3) {
            scValues[0].className = `sc-value ${hCls}`;
            scValues[0].textContent = state;
            scValues[1].className = `sc-value ${errCount ? 'err' : 'ok'}`;
            scValues[1].textContent = errCount;
            scValues[2].className = `sc-value ${warnCount ? 'warn' : 'ok'}`;
            scValues[2].textContent = warnCount;
        }

        if (SM.activeTab === 'issues') {
            loadNativeIssues(service);
        } else if (SM.activeTab === 'uptime') {
            if (!isFormVisible) {
                loadNativeUptimeMonitors(service);
            }
        } else if (SM.activeTab === 'performance') {
            loadPerformanceMetrics(service);
        }

        renderTree();
    } catch {
        /* ignore */
    }
}

function renderChart (series, opts = {}) {
    if (!series || !series.length) {
        return '<div class="empty-chart" style="padding: 20px; text-align: center; color: var(--ink-4); font-size: 11px;">No check history available</div>';
    }
    const w = 900,
        h = 100;
    const padL = 44,
        padR = 12,
        padT = 16,
        padB = 24;
    const cw = w - padL - padR,
        ch = h - padT - padB;
    const yMax = opts.max || 100;
    const color = opts.color || 'var(--navy)';
    const unit = opts.unit || '%';

    const ticks = 4;
    let yAxis = '';
    for (let i = 0; i <= ticks; i++) {
        const y = padT + (ch * i) / ticks;
        const val = yMax * (1 - i / ticks);
        yAxis += `<line x1="${padL}" y1="${y.toFixed(1)}" x2="${w - padR}" y2="${y.toFixed(1)}" stroke="var(--line)" stroke-width="0.5" stroke-dasharray="${i === ticks ? '0' : '2 3'}"/>`;
        yAxis += `<text x="${padL - 6}" y="${y.toFixed(1) + 3}" font-size="9" font-family="var(--mono)" fill="var(--ink-4)" text-anchor="end">${val.toFixed(0)}${i === 0 ? unit : ''}</text>`;
    }

    const N = series.length;
    const step = cw / N;
    const barWidth = Math.max(step * 0.75, 2);

    let barsHtml = '';
    for (let i = 0; i < N; i++) {
        const item = series[i];
        const val = item.v;
        const barHeight = Math.max((val / yMax) * ch, 1);
        const x = i * step + (step - barWidth) / 2;
        const y = ch - barHeight;
        const dateStr = item.time ? new Date(item.time).toLocaleString() : '—';
        const rawValStr =
            item.rawVal !== undefined
                ? `${item.rawVal.toFixed(1)} ms`
                : `${val.toFixed(1)} ms`;
        barsHtml += `<rect x="${x.toFixed(2)}" y="${y.toFixed(2)}" width="${barWidth.toFixed(2)}" height="${barHeight.toFixed(2)}" fill="${color}" opacity="0.85" rx="1.5" style="cursor: pointer; transition: opacity 0.15s;" onmouseover="this.setAttribute('opacity', '1')" onmouseout="this.setAttribute('opacity', '0.85')">
          <title>Time: ${dateStr}&#10;Latency: ${rawValStr}</title>
        </rect>`;
    }

    return `<svg viewBox="0 0 ${w} ${h}">
      ${yAxis}
      <g transform="translate(${padL}, ${padT})">
        ${barsHtml}
      </g>
    </svg>`;
}

/* ─── 8. auto-refresh ─── */
function startAutoRefresh () {
    stopAutoRefresh();
    SM.refreshInterval = setInterval(() => {
        if (SM.selection.service)
            refreshActiveServiceData(SM.selection.service);
    }, 30_000);
}

function stopAutoRefresh () {
    if (SM.refreshInterval) {
        clearInterval(SM.refreshInterval);
        SM.refreshInterval = null;
    }
}

/* ─── 9. initialization ─── */
document.addEventListener('DOMContentLoaded', () => {
    /* tree search */
    const searchInput = document.getElementById('treeSearch');
    if (searchInput) {
        searchInput.addEventListener('input', () =>
            renderTree(searchInput.value),
        );
    }

    /* window buttons */
    document.getElementById('windowGroup')?.addEventListener('click', (e) => {
        const btn = e.target.closest('.range-btn');
        if (!btn) return;
        SM.window = btn.dataset.window;
        document
            .querySelectorAll('#windowGroup .range-btn')
            .forEach((b) => b.classList.toggle('active', b === btn));
        SM.healthCache = {};
        SM.issuesCache = {};
        if (SM.selection.service) loadServiceDetail(SM.selection.service);
    });

    /* auto-refresh toggle */
    const rBtn = document.getElementById('refreshToggle');
    if (rBtn) {
        rBtn.addEventListener('click', () => {
            SM.autoRefresh = !SM.autoRefresh;
            rBtn.classList.toggle('on', SM.autoRefresh);
            SM.autoRefresh ? startAutoRefresh() : stopAutoRefresh();
        });
    }

    /* manual refresh button */
    const rNowBtn = document.getElementById('refreshNowBtn');
    if (rNowBtn) {
        rNowBtn.addEventListener('click', () => {
            if (SM.selection.service) {
                const originalText = rNowBtn.innerHTML;
                rNowBtn.disabled = true;
                rNowBtn.innerHTML = 'Refreshing...';
                refreshActiveServiceData(SM.selection.service).finally(() => {
                    rNowBtn.disabled = false;
                    rNowBtn.innerHTML = originalText;
                });
            } else {
                alert('Please select a service first.');
            }
        });
    }

    /* sidebar highlight */
    document
        .querySelectorAll('.sb-item')
        .forEach((el) => el.classList.remove('active'));
    const monTab = Array.from(document.querySelectorAll('.sb-item')).find(
        (el) =>
            el.textContent.includes('Monitoring') &&
            !el.textContent.includes('System') &&
            !el.textContent.includes('Perf'),
    );
    if (monTab) monTab.classList.add('active');

    /* start */
    fetchTree();
    startAutoRefresh();
});
