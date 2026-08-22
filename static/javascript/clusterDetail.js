/* global fetch, window, document, setTimeout, clearTimeout, Event, FormData */
const csrfToken = window.clusterConfig.csrfToken;
const clusterId = window.clusterConfig.clusterId;
const clusterName = window.clusterConfig.clusterName;

const state = {
    activeNodeId: '',
    nodeInfoCache: {},
    nodeMode: 'add',
    editingNodeId: '',
    serviceMode: 'add',
    editingServiceId: '',
    editingServiceCard: null,
    editingServiceConfig: {},
    pendingSvc: null,
    serviceStaticDefaults: null,
    detailType: '',
    detailNodeId: '',
    detailServiceId: '',
    detailTab: 'overview',
    detailServiceContext: null,
    detailServiceEvents: [],
    serviceLiveStatusCache: {},
    serviceEventsCache: {},
    nodeEventsCache: {},
    pendingDependencyDetails: null,
    pendingRequests: {},
    workspaceLoadToken: 0,
};

const INFRA_CONTAINER_SLUGS = {
    InfraPostgreSQLCore: 'postgresql-core',
    InfraRabbitMQ: 'rabbitmq',
    InfraRedisCore: 'redis-core',
    InfraAirflowPostgreSQL: 'airflow-postgresql',
    InfraAirflowRedis: 'airflow-redis',
    InfraAirflowScheduler: 'airflow-scheduler',
    InfraAirflowWorker: 'airflow-worker',
    InfraAirflowDagProcessor: 'airflow-dagprocessor',
    InfraAirflowTriggerer: 'airflow-triggerer',
    InfraClickHouse: 'clickhouse',
    InfraMilvus: 'milvus',
    InfraEtcd: 'etcd',
    InfraMinio: 'minio',
    InfraNiFi: 'nifi',
    InfraPrometheusANS: 'prometheus-ans',
    InfraPrometheusRAG: 'prometheus-rag',
    InfraPrometheus: 'prometheus',
    InfraNodeExporter: 'node-exporter',
    InfraProcessExporter: 'process-exporter',
    InfraKafkaExporter: 'kafka-exporter',
    InfraDcgmExporter: 'dcgm-exporter',
};

const INFRA_SCHEMA_ALIASES = {
    InfraPrometheusANS: 'InfraPrometheus',
    InfraPrometheusRAG: 'InfraPrometheus',
};

const actionModalHandlers = {
    primary: null,
    secondary: null,
};

// ── session visit tracking ────────────────────────
const currentVisit = {
    cluster_id: clusterId, // already available from window.clusterConfig
    node_id: '',
    service_name: '',
};

function trackVisit () {
    fetch(window.location.href, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': csrfToken,
        },
        body: JSON.stringify({
            'user-action': 'track_visit',
            cluster_id: currentVisit.cluster_id,
            node_id: currentVisit.node_id,
            service_name: currentVisit.service_name,
        }),
    });
}

function $ (s, r) {
    return (r || document).querySelector(s);
}
function $$ (s, r) {
    return Array.from((r || document).querySelectorAll(s));
}

function normalizeSuccess (data) {
    if (!data) return false;
    const v = data.success;
    return v === true || v === 'True' || v === 'true' || v === 1 || v === '1';
}

function getMessage (data, fallback) {
    return (
        (data && (data.msg || data.message || data.error)) ||
        fallback ||
        'Request failed'
    );
}

function showToast (msg, kind) {
    const t = $('#toast');
    const m = $('#toastMsg');
    if (!t || !m) return;
    m.textContent = msg || 'Done';
    t.classList.remove('ok', 'err');
    if (kind) t.classList.add(kind);
    t.classList.add('show');
    clearTimeout(showToast._t);
    showToast._t = setTimeout(() => t.classList.remove('show'), 3200);
}

function setButtonLoading (button, loading, text) {
    if (!button) return;
    if (loading) {
        if (!button.dataset.originalHtml)
            button.dataset.originalHtml = button.innerHTML;
        if (!button.dataset.originalDisabled)
            button.dataset.originalDisabled = button.disabled ? '1' : '0';
        button.disabled = true;
        button.classList.add('btn-loading');
        button.innerHTML =
            '<span class="btn-spinner" aria-hidden="true"></span>' +
            '<span class="btn-loading-label">' +
            esc(text || 'Loading...') +
            '</span>';
        return;
    }
    if (button.dataset.originalHtml)
        button.innerHTML = button.dataset.originalHtml;
    button.disabled = button.dataset.originalDisabled === '1';
    button.classList.remove('btn-loading');
    delete button.dataset.originalHtml;
    delete button.dataset.originalDisabled;
}

function setBusyState (target, loading) {
    if (!target) return;
    target.classList.toggle('is-busy', !!loading);
}

function renderPanelLoading (target, message) {
    if (!target) return;
    target.innerHTML =
        '<div class="detail-loading-shell cluster-inline-loading">' +
        '<span class="detail-loading-dot"></span>' +
        '<span>' +
        esc(message || 'Loading...') +
        '</span></div>';
}

function setDrawerActionLoading (drawerId, loading) {
    const drawer = document.getElementById(drawerId);
    if (!drawer) return;
    const body = $('.drawer-body', drawer);
    if (body) setBusyState(body, loading);
    $$('button', $('.drawer-foot', drawer) || drawer).forEach((button) => {
        if (button.classList.contains('btn-loading')) return;
        button.disabled = !!loading;
    });
}

async function withPending (key, fn) {
    if (state.pendingRequests[key]) return state.pendingRequests[key];
    const promise = (async function () {
        try {
            return await fn();
        } finally {
            delete state.pendingRequests[key];
        }
    })();
    state.pendingRequests[key] = promise;
    return promise;
}

function esc (v) {
    return String(v || '')
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;');
}

function attrEsc (v) {
    return esc(v).replace(/"/g, '&quot;');
}

function isInfrastructureServiceType (value) {
    return String(value || '').indexOf('Infra') === 0;
}

function getInfraContainerSlug (serviceType, displayName) {
    const type = String(serviceType || '').trim();
    if (INFRA_CONTAINER_SLUGS[type]) return INFRA_CONTAINER_SLUGS[type];
    return (
        String(displayName || type || 'service')
            .replace(/Core$/i, '')
            .replace(/[^A-Za-z0-9]+/g, '-')
            .replace(/^-+|-+$/g, '')
            .toLowerCase() || 'service'
    );
}

function buildCatalogServiceInfo (item) {
    if (!item) return null;
    const serviceType = item.dataset.serviceType || item.dataset.svc || '';
    const nameEl = $('.nm', item);
    const iconEl = $('.ico', item);
    const displayName =
        item.dataset.displayName ||
        (nameEl ? nameEl.textContent : '') ||
        serviceType ||
        'Service';
    return {
        id: item.dataset.svc || serviceType,
        serviceType: serviceType,
        isInfra: item.dataset.infra === 'true',
        name: displayName,
        letter: (iconEl ? iconEl.textContent : displayName.charAt(0)).trim(),
        version: item.dataset.version || '',
        displayVersion:
            item.dataset.displayVersion || item.dataset.version || '',
        internalPort: item.dataset.internalPort || '',
        sourceRole: item.dataset.sourceRole || '',
        containerSlug: item.dataset.containerSlug || '',
        category: item.dataset.cat || '',
    };
}

function findCatalogItemForServiceType (serviceType) {
    const wanted = String(serviceType || '').trim();
    if (!wanted) return null;
    return (
        $$('.catalog-item').find((item) => {
            return (
                item.dataset.serviceType === wanted ||
                item.dataset.svc === wanted ||
                normalizeServiceSchemaKey(item.dataset.svc) ===
                    normalizeServiceSchemaKey(wanted)
            );
        }) || null
    );
}

function formatValue (value, fallback) {
    if (value === undefined || value === null || value === '') {
        return fallback || 'NA';
    }
    return String(value);
}

function formatMono (value, fallback) {
    return (
        '<span style="font-family:var(--mono);">' +
        esc(formatValue(value, fallback)) +
        '</span>'
    );
}

function getStateTone (stateLabel) {
    const normalized = String(stateLabel || 'unknown')
        .toLowerCase()
        .trim();
    if (!normalized || normalized === 'unknown') return 'neutral';
    if (
        normalized === 'not deployed' ||
        normalized === 'not tracked' ||
        normalized === 'external'
    ) {
        return 'neutral';
    }
    if (
        normalized.indexOf('running') >= 0 ||
        normalized.indexOf('healthy') >= 0 ||
        normalized.indexOf('ok') >= 0 ||
        normalized.indexOf('success') >= 0 ||
        normalized.indexOf('up') >= 0 ||
        normalized.indexOf('active') >= 0 ||
        normalized.indexOf('ready') >= 0 ||
        normalized.indexOf('deployed') >= 0
    ) {
        return 'ok';
    }
    if (
        normalized.indexOf('warn') >= 0 ||
        normalized.indexOf('degraded') >= 0 ||
        normalized.indexOf('starting') >= 0 ||
        normalized.indexOf('restart') >= 0 ||
        normalized.indexOf('pending') >= 0 ||
        normalized.indexOf('initial') >= 0 ||
        normalized.indexOf('creating') >= 0 ||
        normalized.indexOf('provision') >= 0
    ) {
        return 'warn';
    }
    if (
        normalized.indexOf('error') >= 0 ||
        normalized.indexOf('fail') >= 0 ||
        normalized.indexOf('missing') >= 0 ||
        normalized.indexOf('stopped') >= 0 ||
        normalized.indexOf('exited') >= 0 ||
        normalized.indexOf('dead') >= 0 ||
        normalized.indexOf('unhealthy') >= 0 ||
        normalized.indexOf('down') >= 0 ||
        normalized.indexOf('crash') >= 0 ||
        normalized.indexOf('not running') >= 0
    ) {
        return 'err';
    }
    return 'neutral';
}

function renderStatePillMarkup (stateLabel) {
    const raw = String(stateLabel || 'unknown');
    const tone = getStateTone(raw);
    return '<span class="state-pill ' + tone + '">' + esc(raw) + '</span>';
}

async function sendRequest (payload, options) {
    const cfg = Object.assign(
        {
            url: window.location.href,
            method: 'POST',
            showAlert: false,
            errorMessage: 'Something went wrong.',
        },
        options || {},
    );

    try {
        const response = await fetch(cfg.url, {
            method: cfg.method,
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': csrfToken,
            },
            body: JSON.stringify(payload),
        });
        const rawText = await response.text();
        let data = {};
        try {
            data = rawText ? JSON.parse(rawText) : {};
            //} catch (parseErr) {
        } catch {
            data = {
                success: false,
                error: 'Non-JSON response (' + response.status + ')',
                message: rawText ? rawText.slice(0, 240) : 'Empty response',
            };
            //console.error('Failed to parse JSON response', parseErr, rawText);
        }
        if (!response.ok && data.success === undefined) {
            data.success = false;
        }
        if (!normalizeSuccess(data) && cfg.showAlert)
            showToast(getMessage(data, cfg.errorMessage), 'err');
        return data;
    } catch (err) {
        //console.error(err);
        if (cfg.showAlert) showToast(cfg.errorMessage, 'err');
        return { success: false, error: String(err) };
    }
}

function getActiveNodeRow () {
    return $('.node-row.active');
}

function buildNodeRowElement (node, isActive) {
    const cfg = node.node_provision_config || {};
    const row = document.createElement('div');
    row.className = 'node-row' + (isActive ? ' active' : '');
    row.dataset.node = node.node_name || '';
    row.dataset.nodeId = node.node_id || '';
    row.dataset.nodeName = node.node_name || '';
    row.dataset.nodeCloud = cfg.provider || 'aws';
    row.dataset.region = cfg.region || '';
    row.dataset.vcpu = cfg.vcpu || '';
    row.dataset.memory = cfg.memory || '';
    row.dataset.storage = cfg.storage || '';
    row.dataset.gpu = cfg.gpu_status || cfg.gpu_type || '';
    row.dataset.os = cfg.os_variant || '';
    row.dataset.nodeIp = node.ip_address || node.node_ip || '';
    row.dataset.nodeVolume = node.node_volume || cfg.node_volume || '';
    row.dataset.nodeAuthType = node.auth_type || cfg.auth_type || '';
    row.dataset.nodeUsername = node.username || cfg.username || '';
    row.innerHTML = [
        '<div class="nstat ready"></div>',
        '<div class="info">',
        '  <div class="nm">' +
            esc(node.node_name || node.node_id || 'Node') +
            '</div>',
        '  <div class="sub"><span class="cloud">' +
            esc(String(cfg.provider || 'aws').toUpperCase()) +
            '</span> ' +
            esc((cfg.vcpu || '?') + ' vCPU / ' + (cfg.memory || '?') + ' GB') +
            '</div>',
        '</div>',
        '<div class="svc-count">' +
            esc(Object.keys(node.service_info || {}).length) +
            ' svc</div>',
        '<button class="icon-btn node-edit-btn" title="Edit node" style="margin-left:8px;"><svg class="ic ic-sm" viewBox="0 0 24 24"><path d="M11 4H4a2 2 0 00-2 2v14a2 2 0 002 2h14a2 2 0 002-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 013 3L12 15l-4 1 1-4 9.5-9.5z"/></svg></button>',
    ].join('');
    attachNodeRowEvents(row);
    return row;
}

function applyNodeSearchFilter () {
    const input = $('#nodeSearch');
    const query = input ? String(input.value || '').toLowerCase() : '';
    $$('.node-row').forEach((row) => {
        const haystack = String(row.textContent || '').toLowerCase();
        row.style.display = !query || haystack.includes(query) ? '' : 'none';
    });
}

function refreshNodeList (clusterInfo) {
    const list = $('#nodeList');
    if (!list) return null;
    const activeId =
        state.activeNodeId ||
        (getActiveNodeRow() ? getActiveNodeRow().dataset.nodeId : '');
    const nodes =
        clusterInfo && clusterInfo.node_info ? clusterInfo.node_info : {};
    const keys = Object.keys(nodes).sort(
        (a, b) => parseInt(a, 10) - parseInt(b, 10),
    );
    list.innerHTML = '';
    let selectedRow = null;
    keys.forEach((key, index) => {
        const node = nodes[key] || {};
        const isActive = !!activeId ? node.node_id === activeId : index === 0;
        const row = buildNodeRowElement(node, isActive);
        list.appendChild(row);
        if (isActive) selectedRow = row;
    });
    if (!selectedRow) selectedRow = $('.node-row', list);
    const totalLabel = $('.node-list-head span');
    if (totalLabel) totalLabel.textContent = keys.length + ' total';
    applyNodeSearchFilter();
    return selectedRow;
}

function setActiveRow (row) {
    $$('.node-row').forEach((x) => x.classList.remove('active'));
    row.classList.add('active');
    state.activeNodeId = row.dataset.nodeId || '';
}

function updateNodeSpecFromRow (row) {
    $('#specNodeName').textContent = row.dataset.nodeName || '';
    $('#specRegion').textContent = row.dataset.region || '';
    $('#specNodeId').textContent = (row.dataset.nodeId || '') + ' · --';
    $('#specVcpu').textContent = row.dataset.vcpu || '';
    $('#specMemory').innerHTML =
        (row.dataset.memory || '') + ' <span class="unit">GB</span>';
    $('#specStorage').innerHTML =
        (row.dataset.storage || '') + ' <span class="unit">GB SSD</span>';
    $('#specGpu').textContent = row.dataset.gpu || '—';
    $('#specOs').textContent = row.dataset.os || '';
}

function renderEvents (panelId, statusId, list, emptyMsg) {
    const panel = document.getElementById(panelId);
    const status = document.getElementById(statusId);
    if (!panel || !status) return;

    if (!Array.isArray(list) || !list.length) {
        panel.innerHTML =
            '<div style="color:var(--ink-4);">' +
            esc(emptyMsg || 'No events') +
            '</div>';
        status.textContent = '0 events';
        return;
    }

    const rows = list
        .slice(0, 20)
        .map((ev) => {
            const rawMsg =
                ev.event_msg || ev.message || ev.msg || ev.Event_Msg || '';
            let title =
                ev.event_title ||
                ev.event_type ||
                ev.title ||
                ev.level ||
                ev.event_trigger ||
                ev.Event_Trigger ||
                '';
            let msg = rawMsg;
            if (!title && rawMsg.indexOf('-') > 0) {
                title = rawMsg.split('-', 1)[0];
                msg = rawMsg.substring(rawMsg.indexOf('-') + 1);
            }
            if (!title) title = 'Event';
            const date =
                ev.create_date ||
                ev.event_date ||
                ev.date ||
                ev.Event_Date ||
                '';
            const time =
                ev.create_time ||
                ev.event_time ||
                ev.time ||
                ev.Event_Time ||
                '';
            const when =
                date || time
                    ? ' (' + String(date || '') + ' ' + String(time || '') + ')'
                    : '';
            return (
                '<div style="padding:6px 0; border-bottom:1px dashed var(--line);">' +
                esc(title + ': ' + msg + when) +
                '</div>'
            );
        })
        .join('');

    panel.innerHTML = rows;
    status.textContent = list.length + ' events';
}

function setDetailTab (tabName) {
    state.detailTab = tabName;
    $$('#detailTabs .tab').forEach((tab) => {
        tab.classList.toggle('active', tab.dataset.detailTab === tabName);
    });
    $$('[data-detail-pane]').forEach((pane) => {
        pane.classList.toggle('active', pane.dataset.detailPane === tabName);
    });
}

function closeInfoDetailDrawer () {
    $('#infoDetailBack').classList.remove('open');
    $('#infoDetailDrawer').classList.remove('open');
    state.detailType = '';
    state.detailNodeId = '';
    state.detailServiceId = '';
    state.detailTab = 'overview';
    state.detailServiceContext = null;
    state.detailServiceEvents = [];

    const btn = document.getElementById('btnRuntimePatchFooter');
    if (btn) {
        btn.style.display = 'none';
        btn.disabled = true;
    }
    const statusEl = document.getElementById('runtimePatchStatusText');
    if (statusEl) {
        statusEl.style.display = 'none';
        statusEl.textContent = '';
    }
}

function openInfoDetailDrawer () {
    $('#infoDetailBack').classList.add('open');
    $('#infoDetailDrawer').classList.add('open');
}

function renderDetailSummaryCards (cards) {
    const target = $('#detailSummary');
    if (!target) return;
    target.innerHTML = (cards || [])
        .map(
            (card) =>
                '<div class="detail-card"><div class="k">' +
                esc(card.label || '') +
                '</div><div class="v">' +
                esc(formatValue(card.value)) +
                '</div>' +
                (card.sub
                    ? '<div class="sub">' + esc(card.sub) + '</div>'
                    : '') +
                '</div>',
        )
        .join('');
}

function renderDetailGrid (targetId, rows) {
    const target = document.getElementById(targetId);
    if (!target) return;
    target.innerHTML = (rows || [])
        .map(
            (row) =>
                '<dt>' +
                esc(row.label || '') +
                '</dt><dd>' +
                (row.html !== undefined
                    ? row.html
                    : esc(formatValue(row.value))) +
                '</dd>',
        )
        .join('');
}

function renderDetailOverviewExtra (rows) {
    const target = $('#detailOverviewExtra');
    if (!target) return;
    if (!rows || !rows.length) {
        target.innerHTML = '';
        return;
    }
    target.innerHTML =
        '<div class="detail-kv-list">' +
        rows
            .map(
                (row) =>
                    '<div class="detail-kv"><span class="k">' +
                    esc(row.label || '') +
                    '</span><span class="v">' +
                    (row.html !== undefined
                        ? row.html
                        : esc(formatValue(row.value))) +
                    '</span></div>',
            )
            .join('') +
        '</div>';
}

function renderDetailEvents (list, emptyMsg) {
    renderEvents(
        'detailEventsPanel',
        'detailEventsStatus',
        list || [],
        emptyMsg || 'No events',
    );
}

function renderDependenciesTable (dependencies) {
    const body = $('#detailDependenciesBody');
    if (!body) return;
    if (!dependencies || !dependencies.length) {
        body.innerHTML =
            '<tr><td colspan="7">No runtime dependencies detected.</td></tr>';
        return;
    }
    body.innerHTML = dependencies
        .map((item) => {
            const targetValue =
                item.target_host ||
                item.container_ip ||
                item.service_name ||
                item.host ||
                item.port ||
                'External';
            const sourceValue = item.source_type || item.source || 'Unknown';
            const upForValue = item.running_since
                ? formatValue(item.running_since)
                : 'External';
            return (
                '<tr>' +
                '<td>' +
                esc(formatValue(item.name)) +
                '</td>' +
                '<td>' +
                esc(formatValue(targetValue)) +
                '</td>' +
                '<td>' +
                esc(formatValue(sourceValue)) +
                '</td>' +
                '<td>' +
                renderStatePillMarkup(item.state) +
                '</td>' +
                '<td>' +
                esc(formatValue(item.running_since, 'External')) +
                '</td>' +
                '<td>' +
                esc(formatValue(upForValue, 'External')) +
                '</td>' +
                '<td>' +
                esc(formatValue(item.restart_count, 'Not tracked')) +
                '</td>' +
                '</tr>'
            );
        })
        .join('');
}

function renderLiveStatusLoading (message) {
    const summary = $('#detailLiveStatusSummary');
    const checkedAt = $('#detailLiveStatusCheckedAt');
    if (checkedAt) checkedAt.textContent = 'Loading…';
    if (summary) {
        summary.innerHTML =
            '<div class="detail-card"><div class="detail-loading-shell">' +
            '<span class="detail-loading-dot"></span>' +
            '<span>' +
            esc(message || 'Fetching runtime status…') +
            '</span></div></div>';
    }
    renderDetailGrid('detailLiveStatusGrid', [
        { label: 'State', value: 'Loading…' },
        { label: 'Container', value: 'Waiting for runtime response' },
    ]);
    renderDependenciesTable([]);
}

function renderServiceLiveStatus (payload) {
    const summary = $('#detailLiveStatusSummary');
    const checkedAt = $('#detailLiveStatusCheckedAt');
    if (summary) {
        summary.innerHTML = [
            {
                label: 'Overall status',
                value: formatValue(payload.overall_status, 'Unknown'),
                sub: formatValue(payload.error, ''),
            },
            {
                label: 'Node IP',
                value: formatValue(payload.node_ip, 'NA'),
                sub: formatValue(payload.node_id, ''),
            },
            {
                label: 'Checked at',
                value: formatValue(payload.checked_at, 'NA'),
                sub: formatValue(payload.service_id, ''),
            },
        ]
            .map(
                (card) =>
                    '<div class="detail-card"><div class="k">' +
                    esc(card.label) +
                    '</div><div class="v">' +
                    esc(card.value) +
                    '</div>' +
                    (card.sub
                        ? '<div class="sub">' + esc(card.sub) + '</div>'
                        : '') +
                    '</div>',
            )
            .join('');
    }
    if (checkedAt)
        checkedAt.textContent = payload.checked_at
            ? 'Checked ' + payload.checked_at
            : 'Not loaded';

    const main = payload.main_container || {};
    renderDetailGrid('detailLiveStatusGrid', [
        { label: 'Container', value: main.name || payload.service_id },
        {
            label: 'State',
            html: renderStatePillMarkup(main.state || 'Unknown'),
        },
        { label: 'Service port', value: main.service_port },
        { label: 'Created at', value: main.created_at },
        { label: 'Running since', value: main.running_since },
        { label: 'Restart count', value: main.restart_count },
        { label: 'OOM killed', value: main.oom_killed },
        { label: 'Port listening', value: main.expected_port_listening },
        { label: 'Container IP', value: main.container_ip },
        { label: 'Image', value: main.image },
    ]);
    renderDependenciesTable(payload.dependencies || []);
}

function renderServiceDetailOverview (service, events, liveStatus, options) {
    const opts = options || {};
    const statusValue = opts.loading
        ? 'Loading…'
        : (liveStatus && liveStatus.overall_status) ||
          service.service_status ||
          'Unknown';
    const checkedAtValue = opts.loading
        ? 'Loading…'
        : liveStatus && liveStatus.checked_at;
    const nodeIpValue = opts.loading
        ? 'Loading…'
        : liveStatus && liveStatus.node_ip;
    const runtimeErrorValue = opts.loading
        ? 'Loading…'
        : liveStatus && liveStatus.error && liveStatus.error !== 'None'
            ? liveStatus.error
            : 'None';

    setDetailHeader(
        service.service_name || 'Service',
        statusValue,
        (service.service_id || '') +
            ' · node ' +
            formatValue(state.detailNodeId, 'NA'),
    );
    renderDetailSummaryCards([
        {
            label: 'Status',
            value: statusValue,
            sub: formatValue(service.service_type, ''),
        },
        {
            label: 'Port',
            value: formatValue(service.service_port, 'NA'),
            sub: 'Exposed port',
        },
        {
            label: 'Events',
            value: String((events || []).length),
            sub: 'Recent history',
        },
    ]);
    renderDetailGrid('detailOverviewGrid', [
        { label: 'Service ID', html: formatMono(service.service_id) },
        { label: 'Service type', value: service.service_type },
        { label: 'Version', value: service.service_version },
        { label: 'Install mode', value: service.service_install },
        { label: 'Deploy status', value: statusValue },
        { label: 'Node ID', html: formatMono(state.detailNodeId) },
        { label: 'Node IP', html: formatMono(nodeIpValue) },
        { label: 'Checked at', value: checkedAtValue },
    ]);
    renderDetailOverviewExtra([
        {
            label: 'Latest event',
            value:
                events && events.length
                    ? events[0].Event_Msg ||
                      events[0].event_msg ||
                      events[0].msg
                    : 'No events yet',
        },
        {
            label: 'Runtime error',
            value: runtimeErrorValue,
        },
    ]);
}

async function fetchServiceLiveStatus (serviceId) {
    if (!serviceId) return null;
    const res = await sendRequest({
        'user-action': 'service_live_status',
        service_id: serviceId,
    });
    const payload = res.service_live_status || {};
    state.serviceLiveStatusCache[serviceId] = payload;
    return payload;
}

async function loadAndRenderServiceLiveStatus (serviceId, options) {
    const opts = options || {};
    if (!serviceId) return null;
    if (!opts.silent) {
        if (state.detailServiceContext) {
            renderServiceDetailOverview(
                state.detailServiceContext,
                state.detailServiceEvents || [],
                null,
                { loading: true },
            );
        }
        renderLiveStatusLoading(
            opts.message || 'Fetching runtime status from the cluster…',
        );
    }
    const refreshBtn = $('#detailLiveStatusRefreshBtn');
    setButtonLoading(refreshBtn, true, 'Refreshing...');
    try {
        const payload = await fetchServiceLiveStatus(serviceId);
        if (
            state.detailType !== 'service' ||
            state.detailServiceId !== serviceId
        ) {
            return payload || {};
        }
        if (state.detailServiceContext) {
            renderServiceDetailOverview(
                state.detailServiceContext,
                state.detailServiceEvents || [],
                payload || {},
                { loading: false },
            );
        }
        renderServiceLiveStatus(payload || {});
        return payload || {};
    } finally {
        setButtonLoading(refreshBtn, false);
    }
}

function setDetailHeader (title, statusText, metaText) {
    $('#detailTitle').textContent = title || 'Details';
    const statusEl = $('#detailStatus');
    if (statusEl) {
        const raw = String(statusText || 'Unknown');
        const tone = getStateTone(raw);
        statusEl.className = 'pill state-pill ' + tone;
        statusEl.textContent = raw;
    }
    $('#detailMeta').textContent = metaText || '';
}

function getServiceCardContext (card) {
    if (!card) return null;
    return {
        service_id: card.dataset.serviceId || card.dataset.svcId || '',
        service_name: card.dataset.serviceName || card.dataset.svcName || '',
        service_type: card.dataset.serviceType || card.dataset.svcType || '',
        service_version:
            card.dataset.serviceVersion || card.dataset.svcVersion || '',
        service_port: card.dataset.servicePort || card.dataset.svcPort || '',
        service_install:
            card.dataset.serviceInstall || card.dataset.svcInstall || '',
        service_status:
            card.dataset.serviceStatus || card.dataset.svcStatus || '',
        service_debug: card.dataset.serviceDebug || card.dataset.svcDebug || '',
    };
}

async function openNodeDetailDrawer (row, tabName) {
    if (!row) return;
    const nodeId = row.dataset.nodeId;
    let info = state.nodeInfoCache[nodeId];
    if (!info) {
        renderDetailSummaryCards([
            {
                label: 'Node',
                value: row.dataset.nodeName || 'Loading...',
                sub: 'Fetching details',
            },
        ]);
        renderDetailGrid('detailOverviewGrid', [
            { label: 'Node ID', value: nodeId || 'Loading...' },
            { label: 'Provider', value: 'Loading...' },
        ]);
        renderDetailOverviewExtra([]);
        openInfoDetailDrawer();
        const res = await sendRequest({
            'user-action': 'get_node_info',
            node_id: nodeId,
        });
        if (normalizeSuccess(res)) {
            info = res;
            state.nodeInfoCache[nodeId] = res;
        } else {
            info = {};
        }
    }
    state.detailType = 'node';
    state.detailNodeId = nodeId;
    state.detailServiceId = '';
    setDetailHeader(
        row.dataset.nodeName || 'Node',
        'Healthy',
        (nodeId || '') +
            ' · ' +
            formatValue(row.dataset.region, 'Unknown region'),
    );
    $('#detailLiveStatusTab').style.display = 'none';
    $('#detailLaunchBtn').style.display = '';
    $('#detailDeleteBtn').style.display = '';
    $('#detailEditBtn').textContent = 'Edit';
    const patchBtn = $('#btnRuntimePatchFooter');
    if (patchBtn) {
        patchBtn.style.display = 'none';
        patchBtn.disabled = true;
    }
    const patchStatus = $('#runtimePatchStatusText');
    if (patchStatus) {
        patchStatus.style.display = 'none';
        patchStatus.textContent = '';
    }
    renderDetailSummaryCards([
        {
            label: 'Services',
            value: Object.keys((info && info.service_info) || {}).length,
            sub: 'Attached services',
        },
        {
            label: 'vCPU',
            value: formatValue(row.dataset.vcpu, 'NA'),
            sub: 'Allocated',
        },
        {
            label: 'Memory',
            value: formatValue(row.dataset.memory, 'NA') + ' GB',
            sub: formatValue(row.dataset.os, 'OS unknown'),
        },
    ]);
    renderDetailGrid('detailOverviewGrid', [
        { label: 'Node ID', html: formatMono(nodeId) },
        { label: 'Provider', value: row.dataset.nodeCloud },
        { label: 'Region', value: row.dataset.region },
        {
            label: 'IP address',
            html: formatMono(info.node_ip || row.dataset.nodeIp),
        },
        { label: 'Username', value: info.username || row.dataset.nodeUsername },
        {
            label: 'Auth type',
            value: info.auth_type || row.dataset.nodeAuthType,
        },
        { label: 'Operating system', value: row.dataset.os },
        { label: 'GPU', value: row.dataset.gpu || 'None' },
        { label: 'Volume', value: info.node_volume || row.dataset.nodeVolume },
    ]);
    renderDetailOverviewExtra([
        {
            label: 'Service count',
            value: Object.keys((info && info.service_info) || {}).length,
        },
        { label: 'Availability zone', value: info.availability_zone },
        {
            label: 'VPC / subnet',
            value: [info.vpc, info.subnet].filter(Boolean).join(' / '),
        },
        {
            label: 'Ports',
            value: Array.isArray(info.ports) ? info.ports.join(', ') : '',
        },
    ]);
    if (tabName === 'events') {
        await fetchNodeEvents(nodeId);
        renderDetailEvents(
            state.nodeEventsCache[nodeId] || [],
            'No node events found',
        );
    }
    openInfoDetailDrawer();
    setDetailTab(tabName || 'overview');
}

async function openServiceDetailDrawer (card, tabName) {
    if (!card) return;
    const service = getServiceCardContext(card);
    state.detailType = 'service';
    state.detailServiceId = service.service_id;
    state.detailNodeId = getActiveNodeRow()
        ? getActiveNodeRow().dataset.nodeId
        : '';
    state.detailServiceContext = service;
    state.editingServiceCard = card;
    $('#detailLiveStatusTab').style.display = '';
    $('#detailLaunchBtn').style.display = 'none';
    $('#detailDeleteBtn').style.display = '';
    $('#detailEditBtn').textContent = 'Edit';
    window.refreshRuntimePatchStatus(service.service_id);

    const liveStatus = state.serviceLiveStatusCache[service.service_id];
    const events =
        state.serviceEventsCache[service.service_id] ||
        (await (async function () {
            renderDetailEvents([], 'Loading service events...');
            const res = await sendRequest({
                'user-action': 'service_event',
                service_id: service.service_id,
            });
            state.serviceEventsCache[service.service_id] =
                res.service_event_info || [];
            return res.service_event_info || [];
        })());
    state.detailServiceEvents = events || [];
    renderServiceDetailOverview(service, events, liveStatus, {
        loading: !liveStatus,
    });
    renderDetailEvents(events, 'No service events found');
    openInfoDetailDrawer();
    setDetailTab(tabName || 'overview');
    if (liveStatus) {
        renderServiceLiveStatus(liveStatus || {});
    } else {
        renderLiveStatusLoading('Preparing runtime status…');
    }
    if (tabName === 'overview' || tabName === 'live-status' || !liveStatus) {
        loadAndRenderServiceLiveStatus(service.service_id, {
            silent: false,
            message: 'Fetching runtime status from the cluster…',
        });
    }
}

//himanshu code
async function fetchNodeEvents (nodeId) {
    if (!nodeId) return;
    renderPanelLoading($('#nodeEventsPanel'), 'Loading node events...');
    const res = await sendRequest({
        'user-action': 'node_event',
        node_id: nodeId,
    });
    state.nodeEventsCache[nodeId] = res.node_event_info || [];
    renderEvents(
        'nodeEventsPanel',
        'nodeEventsStatus',
        res.node_event_info || [],
        getMessage(res, 'No node events'),
    );
}

// ========================================
// CLOSE SERVICE CONFIG
// ========================================

async function fetchServiceEvents (serviceId) {
    if (!serviceId) return;
    renderPanelLoading($('#serviceEventsPanel'), 'Loading service events...');
    const res = await sendRequest({
        'user-action': 'service_event',
        service_id: serviceId,
    });
    state.serviceEventsCache[serviceId] = res.service_event_info || [];
    renderEvents(
        'serviceEventsPanel',
        'serviceEventsStatus',
        res.service_event_info || [],
        getMessage(res, 'No service events'),
    );
}

async function refreshClusterStats () {
    const res = await sendRequest({
        'user-action': 'get_cluster_info',
        cluster_id: clusterId,
    });
    if (!normalizeSuccess(res) || !res.cluster_info) return;
    const c = res.cluster_info[1] || {};
    const statValues = $$('.stats .stat .v');
    if (statValues.length >= 4) {
        statValues[0].textContent = Object.keys(c.node_info || {}).length;
        statValues[1].textContent = c.service_counts || 0;
        statValues[2].innerHTML =
            String(c.total_vcpus || 0) + ' <span class="unit">vCPU</span>';
        statValues[3].innerHTML =
            String(c.total_memory || 0) + ' <span class="unit">GB</span>';
    }
    refreshNodeList(c);
}

function buildServiceCardHtml (service) {
    const serviceConfig = service.service_config || {};
    const isInfra = serviceConfig.service_category === 'Infrastructure';
    const infraMode =
        serviceConfig.infra_mode ||
        (serviceConfig.runtime && serviceConfig.runtime.infra_mode) ||
        '';
    const adoptionStatus =
        (serviceConfig.runtime && serviceConfig.runtime.adoption_status) || '';
    const validationError =
        (serviceConfig.runtime && serviceConfig.runtime.validation_error) || '';
    const runtimeContainer =
        serviceConfig.container_name ||
        (serviceConfig.runtime && serviceConfig.runtime.container_name) ||
        '';
    const serviceName = isInfra
        ? serviceConfig.service_display_name ||
          service.service_name ||
          service.service_id ||
          'service'
        : service.service_name || service.service_id || 'service';
    const letter = serviceName.charAt(0).toUpperCase();
    const exposedHostPort = String(serviceConfig.host_port || '').trim();
    const portLabel = isInfra
        ? serviceConfig.expose_service && exposedHostPort
            ? ':' + exposedHostPort
            : 'internal'
        : ':' + esc(service.service_port || '—');
    const uptimeLabel = isInfra
        ? serviceConfig.expose_service && exposedHostPort
            ? 'host port ' + exposedHostPort
            : 'no host port'
        : service.service_debug || '-';
    const infraRuntimeLine =
        isInfra && infraMode
            ? '<div class="meta">' +
              esc(adoptionStatus || infraMode) +
              (runtimeContainer ? ' · ' + esc(runtimeContainer) : '') +
              '</div>'
            : '';
    const infraValidationLine =
        isInfra && validationError
            ? '<div class="meta">' + esc(validationError) + '</div>'
            : '';
    const iconClass = service.service_type.startsWith('Infra')
        ? 'ico'
        : 'ico-infra';
    const metaVersion = service.service_type.startsWith('Infra')
        ? '3rd Party - v' + (service.service_version || '-')
        : 'v' + service.service_version || '-';
    return [
        '<div class="' + iconClass + '">' + esc(letter) + '</div>',
        '<div class="svc-info">',
        '  <div class="nm">' + esc(serviceName) + '</div>',
        '  <div class="meta">' +
            esc(metaVersion) +
            ' · install <span class="v">' +
            esc(service.service_install || '-') +
            '</span> · <span class="v">' +
            esc(service.service_type || '-') +
            '</span></div>',
        infraRuntimeLine,
        infraValidationLine,
        '</div>',
        '<div class="svc-ports"><span class="port">' +
            portLabel +
            '</span></div>',
        '<div class="svc-status"><span class="pill ' +
            (String(service.deploy_status || '').toUpperCase() === 'DEPLOYED'
                ? 'pill-ok'
                : 'pill-warn') +
            '">' +
            esc(service.deploy_status || 'UNKNOWN') +
            '</span><div class="uptime">' +
            esc(uptimeLabel) +
            '</div></div>',
        '<div class="svc-acts">',
        '  <button title="Deploy" data-action="deploy-service"><svg class="ic ic-sm" viewBox="0 0 24 24"><path d="M1 4v6h6M23 20v-6h-6M20.49 9A9 9 0 005.64 5.64L1 10m22 4l-4.64 4.36A9 9 0 013.51 15"/></svg></button>',
        '  <button title="Config Manager" data-action="service-config-manager"><svg class="ic ic-sm" viewBox="0 0 24 24"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 00.33 1.82l.06.06a2 2 0 01-2.83 2.83l-.06-.06a1.65 1.65 0 00-1.82-.33 1.65 1.65 0 00-1 1.51V21a2 2 0 01-4 0v-.09A1.65 1.65 0 009 19.4a1.65 1.65 0 00-1.82.33l-.06.06a2 2 0 01-2.83-2.83l.06-.06a1.65 1.65 0 00.33-1.82 1.65 1.65 0 00-1.51-1H3a2 2 0 010-4h.09A1.65 1.65 0 004.6 9a1.65 1.65 0 00-.33-1.82l-.06-.06a2 2 0 012.83-2.83l.06.06a1.65 1.65 0 001.82.33H9a1.65 1.65 0 001-1.51V3a2 2 0 014 0v.09a1.65 1.65 0 001 1.51"/></svg></button>',
        '  <button title="Uninstall" data-action="delete-service"><svg class="ic ic-sm" viewBox="0 0 24 24"><path d="M3 6h18M8 6V4a2 2 0 012-2h4a2 2 0 012 2v2m1 0v14a2 2 0 01-2 2H8a2 2 0 01-2-2V6h12z"/></svg></button>',
        '  <button data-action="edit-service" class="svc-edit-btn" title="Edit service" onclick="event.stopPropagation(); window.editService && window.editService(this.closest(\'.svc-card\'));"> <svg class="ic ic-sm" viewBox="0 0 24 24"><path d="M11 4H4a2 2 0 00-2 2v14a2 2 0 002 2h14a2 2 0 002-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 013 3L12 15l-4 1 1-4 9.5-9.5z"/></svg> </button>',
        '</div>',
    ].join('');
}

function normalizeServiceSchemaKey (value) {
    return String(value || '')
        .trim()
        .toLowerCase();
}

function getServiceSchemaCandidates (service, cfg) {
    const seen = {};
    const candidates = [];

    function pushCandidate (value) {
        const raw = String(value || '').trim();
        if (!raw) return;
        const alias = INFRA_SCHEMA_ALIASES[raw] || raw;
        const normalized = normalizeServiceSchemaKey(alias);
        if (!seen[normalized]) {
            seen[normalized] = true;
            candidates.push(alias);
        }
        const withoutInstanceSuffix = alias.replace(/_[A-Za-z]+[0-9]+$/, '');
        const normalizedBase = normalizeServiceSchemaKey(withoutInstanceSuffix);
        if (
            withoutInstanceSuffix &&
            withoutInstanceSuffix !== alias &&
            !seen[normalizedBase]
        ) {
            seen[normalizedBase] = true;
            candidates.push(withoutInstanceSuffix);
        }
    }

    pushCandidate(cfg && cfg.service_type);
    pushCandidate(service && service.service_type);
    pushCandidate(cfg && cfg.service_name);
    pushCandidate(service && service.service_name);
    pushCandidate(cfg && cfg.service_id);
    pushCandidate(service && service.service_id);
    return candidates;
}

async function showServiceSchemaGroupByName (nameOrNames) {
    const groups = $$('.svc-schema-group');
    const fallback = $('#svcInfraConfigFallback');
    const candidates = Array.isArray(nameOrNames) ? nameOrNames : [nameOrNames];
    let matchedGroup = null;
    groups.forEach((group) => {
        group.style.display = 'none';
    });
    if (fallback) fallback.style.display = 'none';
    candidates.some((candidate) => {
        const normalizedCandidate = normalizeServiceSchemaKey(candidate);

        matchedGroup =
            groups.find(
                (group) =>
                    normalizeServiceSchemaKey(group.dataset.serviceSchema) ===
                    normalizedCandidate,
            ) || null;

        return !!matchedGroup;
    });

    // =========================
    // SHOW MATCHED GROUP
    // =========================

    if (matchedGroup) {
        matchedGroup.style.display = 'block';
    }

    return matchedGroup;
}

function getVisibleServiceSchemaGroup () {
    return $('.svc-schema-group[style*="block"]');
}

function renderServiceConfigFallback (svc, matchedGroup) {
    const fallback = $('#svcInfraConfigFallback');
    if (!fallback) return;
    if (matchedGroup) {
        fallback.style.display = 'none';
        return;
    }

    const info = svc || {};
    const serviceType =
        info.serviceType ||
        info.service_type ||
        info.id ||
        info.service_id ||
        '';
    const displayName =
        info.name ||
        info.service_name ||
        info.display_name ||
        info.service_display_name ||
        serviceType ||
        'Service';
    const isInfra = !!info.isInfra || isInfrastructureServiceType(serviceType);
    const activeNode = getActiveNodeRow();
    const nodeId =
        (activeNode && activeNode.dataset.nodeId) ||
        info.node_id ||
        '<node_id>';
    const slug =
        info.containerSlug || getInfraContainerSlug(serviceType, displayName);
    const containerName = isInfra
        ? 'node-' + nodeId + '-' + slug
        : 'managed by service role';
    const version =
        info.version ||
        info.service_version ||
        getSelectedServiceVersion() ||
        'role default';
    const internalPort =
        info.internalPort || info.internal_port || 'internal only';
    const sourceRole =
        info.sourceRole || info.source_role || serviceType || 'service role';

    fallback.innerHTML = [
        '<div class="fallback-title">' +
            esc(
                isInfra
                    ? 'Infrastructure runtime contract'
                    : 'Default service configuration',
            ) +
            '</div>',
        '<div class="fallback-copy">',
        isInfra
            ? 'This card installs the shared dependency runtime on the selected node. External host exposure is optional; app services still connect to the static internal container target after the dependency pre-flight passes.'
            : 'No advanced schema is registered for this service. The installer will use the standard service defaults plus the setup values from the previous step.',
        '</div>',
        '<div class="infra-config-grid">',
        '  <div class="infra-config-kv"><div class="k">Service type</div><div class="v">' +
            esc(serviceType || 'role default') +
            '</div></div>',
        '  <div class="infra-config-kv"><div class="k">Container target</div><div class="v">' +
            esc(containerName) +
            '</div></div>',
        '  <div class="infra-config-kv"><div class="k">Version</div><div class="v">' +
            esc(version) +
            '</div></div>',
        '  <div class="infra-config-kv"><div class="k">Network</div><div class="v">' +
            esc(
                isInfra
                    ? 'internal bridge, no external port'
                    : 'service default',
            ) +
            '</div></div>',
        '  <div class="infra-config-kv"><div class="k">Internal port</div><div class="v">' +
            esc(internalPort) +
            '</div></div>',
        '  <div class="infra-config-kv"><div class="k">Installer role</div><div class="v">' +
            esc(sourceRole) +
            '</div></div>',
        '</div>',
    ].join('');
    fallback.style.display = 'block';
}

function syncInfraExposeControls (group) {
    if (!group) return;
    const exposeField = $('[name="expose_service"]', group);
    const hostPortRow = $('[data-infra-host-port-row]', group);
    const hostPortField = hostPortRow
        ? $('[name="host_port"]', hostPortRow)
        : null;
    if (!exposeField || !hostPortRow || !hostPortField) return;

    const isExposed = !!exposeField.checked;
    hostPortRow.style.display = isExposed ? '' : 'none';
    hostPortField.disabled = !isExposed;
    if (!isExposed) hostPortField.value = '';
}

function applyInfrastructureDrawerDefaults (svc) {
    if (!svc || !svc.isInfra) return;
    if (svc.version) ensureServiceVersionOption(svc.version);
    if ($('#svc-port')) $('#svc-port').value = '';
}

function ensureServiceVersionOption (version) {
    const select = $('#svc-version');
    const normalizedVersion = String(version || '').trim();
    if (!select || !normalizedVersion) return;

    let matched = $$('option', select).find(
        (option) =>
            String(option.value || option.textContent || '')
                .trim()
                .indexOf(normalizedVersion) === 0,
    );
    if (!matched) {
        matched = document.createElement('option');
        matched.value = normalizedVersion;
        matched.textContent = normalizedVersion;
        select.appendChild(matched);
    }
    select.value = matched.value || matched.textContent;
}

function getSelectedServiceVersion () {
    const select = $('#svc-version');
    if (!select) return '';
    const option = select.options[select.selectedIndex];
    const raw = String(
        (option && (option.value || option.textContent)) || select.value || '',
    ).trim();
    const match = raw.match(/^([0-9]+(?:\.[0-9A-Za-z_-]+)*)/);
    return match ? match[1] : raw;
}

function getServiceStaticFieldValues () {
    return {
        service_name: $('#svc-name')
            ? String($('#svc-name').value || '').trim()
            : '',
        service_version: getSelectedServiceVersion(),
        service_port: $('#svc-port')
            ? String($('#svc-port').value || '').trim()
            : '',
        data_directory: $('#svc-data-dir')
            ? String($('#svc-data-dir').value || '').trim()
            : '',
        max_connections: $('#svc-max-conn')
            ? String($('#svc-max-conn').value || '').trim()
            : '',
        shared_buffers: $('#svc-shared-buffers')
            ? String($('#svc-shared-buffers').value || '').trim()
            : '',
    };
}

function fillServiceStaticFields (cfg) {
    const serviceCfg = cfg || {};
    resetServiceStaticFields();
    syncServiceStaticFieldsFromGroup();
    if ($('#svc-name')) $('#svc-name').value = serviceCfg.service_name || '';
    ensureServiceVersionOption(serviceCfg.service_version || '');
    if ($('#svc-data-dir'))
        $('#svc-data-dir').value = serviceCfg.data_directory || '';
    if ($('#svc-port')) $('#svc-port').value = serviceCfg.service_port || '';
    if ($('#svc-max-conn'))
        $('#svc-max-conn').value = serviceCfg.max_connections || '';
    if ($('#svc-shared-buffers'))
        $('#svc-shared-buffers').value = serviceCfg.shared_buffers || '';
}

function resetServiceStaticFields () {
    const defaults = state.serviceStaticDefaults;
    if (!defaults) return;
    if ($('#svc-name')) $('#svc-name').value = defaults.serviceName;
    if ($('#svc-version')) {
        $('#svc-version').innerHTML = defaults.versionOptionsHtml;
        $('#svc-version').value = defaults.serviceVersionValue;
    }
    if ($('#svc-data-dir')) $('#svc-data-dir').value = defaults.dataDirectory;
    if ($('#svc-port')) $('#svc-port').value = defaults.servicePort;
    if ($('#svc-max-conn')) $('#svc-max-conn').value = defaults.maxConnections;
    if ($('#svc-shared-buffers'))
        $('#svc-shared-buffers').value = defaults.sharedBuffers;
}

function wireServiceSetupFieldSync (group) {
    if (!group) return;

    function wireField (selector, syncFn) {
        const field = $(selector, group);
        if (!field || field.dataset.syncWired === '1') return;
        field.dataset.syncWired = '1';
        field.addEventListener('input', syncFn);
        field.addEventListener('change', syncFn);
    }

    wireField('[name="service_version"]', () => {
        const versionField = $('[name="service_version"]', group);
        if (!versionField) return;
        ensureServiceVersionOption(versionField.value || '');
    });
    wireField('[name="service_port"]', () => {
        const field = $('[name="service_port"]', group);
        if ($('#svc-port') && field) $('#svc-port').value = field.value || '';
    });
    wireField('[name="expose_service"]', () => {
        syncInfraExposeControls(group);
    });
    wireField('[name="data_directory"]', () => {
        const field = $('[name="data_directory"]', group);
        if ($('#svc-data-dir') && field)
            $('#svc-data-dir').value = field.value || '';
    });
    wireField('[name="max_connections"]', () => {
        const field = $('[name="max_connections"]', group);
        if ($('#svc-max-conn') && field)
            $('#svc-max-conn').value = field.value || '';
    });
    wireField('[name="shared_buffers"]', () => {
        const field = $('[name="shared_buffers"]', group);
        if ($('#svc-shared-buffers') && field)
            $('#svc-shared-buffers').value = field.value || '';
    });
}

function syncVisibleGroupFieldFromStatic (fieldName, value) {
    const group = getVisibleServiceSchemaGroup();
    const field = group ? $('[name="' + fieldName + '"]', group) : null;
    if (!field) return;
    field.value = value;
}

function syncStaticVersionFieldFromSetup () {
    const group = getVisibleServiceSchemaGroup();
    const versionField = group ? $('[name="service_version"]', group) : null;
    if (!versionField) return;
    versionField.value = getSelectedServiceVersion();
}

function syncServiceStaticFieldsFromGroup () {
    const group = getVisibleServiceSchemaGroup();
    if (!group) return;
    wireServiceSetupFieldSync(group);

    const versionField = $('[name="service_version"]', group);
    const portField = $('[name="service_port"]', group);
    const dataDirectoryField = $('[name="data_directory"]', group);
    const maxConnectionsField = $('[name="max_connections"]', group);
    const sharedBuffersField = $('[name="shared_buffers"]', group);

    if (versionField && $('#svc-version')) {
        if (versionField.tagName === 'SELECT') {
            $('#svc-version').innerHTML = versionField.innerHTML;
        }
        ensureServiceVersionOption(versionField.value || '');
    }
    if (portField && $('#svc-port'))
        $('#svc-port').value = portField.value || $('#svc-port').value;
    if (dataDirectoryField && $('#svc-data-dir'))
        $('#svc-data-dir').value =
            dataDirectoryField.value || $('#svc-data-dir').value;
    if (maxConnectionsField && $('#svc-max-conn'))
        $('#svc-max-conn').value =
            maxConnectionsField.value || $('#svc-max-conn').value;
    if (sharedBuffersField && $('#svc-shared-buffers'))
        $('#svc-shared-buffers').value =
            sharedBuffersField.value || $('#svc-shared-buffers').value;
    syncInfraExposeControls(group);
}

function fillServiceFormFromConfig (cfg) {
    fillServiceStaticFields(cfg);
    const group = getVisibleServiceSchemaGroup();
    if (!group || !cfg) return;
    wireServiceSetupFieldSync(group);
    $$('input, select, textarea', group).forEach((field) => {
        if (!field.name) return;
        if (cfg[field.name] === undefined || cfg[field.name] === null) return;
        if (field.type === 'checkbox') field.checked = !!cfg[field.name];
        else field.value = cfg[field.name];
    });
    syncInfraExposeControls(group);
    syncStaticVersionFieldFromSetup();
}

function setServiceDrawerMode (mode) {
    state.serviceMode = mode;
    const isEdit = mode === 'edit';
    const title = $('#svcDrawerTitle');
    const badge = $('#svcEditBadge');
    if (title)
        title.childNodes[0].nodeValue = isEdit
            ? 'Edit service '
            : 'Configure service ';
    if (badge) badge.style.display = isEdit ? 'inline-block' : 'none';
    currentSvcStep = isEdit ? 2 : 1;
    updateSvcStepper();
}

function updateServiceFooterActions () {
    const isEdit = state.serviceMode === 'edit';
    const isFinal = currentSvcStep === totalSvcSteps;
    const saveBtn = $('#svcSaveBtn');
    const deployBtn = $('#deploySvcBtn');
    const deleteBtn = $('#deleteSvcBtn');
    const cfgBtn = $('#openConfigManagerBtn');
    if (saveBtn)
        saveBtn.style.display = isEdit && isFinal ? 'inline-flex' : 'none';
    if (deployBtn)
        deployBtn.style.display = isEdit && isFinal ? 'inline-flex' : 'none';
    if (deleteBtn)
        deleteBtn.style.display = isEdit && isFinal ? 'inline-flex' : 'none';
    if (cfgBtn)
        cfgBtn.style.display = isEdit && isFinal ? 'inline-flex' : 'none';
}

async function deployService (serviceId, card) {
    const button = card
        ? $('[data-action="deploy-service"]', card)
        : $('#deploySvcBtn');
    await withPending('deploy-service:' + serviceId, async function () {
        setButtonLoading(button, true, 'Deploying...');
        if (card) setBusyState(card, true);
        const res = await sendRequest({
            'user-action': 'deploy_service',
            service_id: serviceId,
        });
        if (!normalizeSuccess(res)) {
            if (res.details && res.details.code === 'MISSING_DEPENDENCIES') {
                showDependencyBlocker(
                    res.details,
                    getMessage(res, 'Deploy blocked'),
                );
                return;
            }
            showToast(getMessage(res, 'Deploy failed'), 'err');
            return;
        }
        if (card) {
            const pill = $('.svc-status .pill', card);
            if (pill) pill.textContent = 'DEPLOYING';
        }
        showToast(getMessage(res, 'Deploy initiated'), 'ok');
        fetchServiceEvents(serviceId);
        await refreshClusterStats();
    }).finally(function () {
        setButtonLoading(button, false);
        if (card) setBusyState(card, false);
    });
}

function showDependencyBlocker (details, fallbackMessage) {
    const missing = (details && details.missing_dependencies) || [];
    const nodeId = (details && details.node_id) || 'selected node';
    state.pendingDependencyDetails = details || {};
    openActionBlockerModal({
        eyebrow: 'Missing dependencies',
        title: 'Deployment blocked',
        message:
            (fallbackMessage || 'Deployment blocked: missing dependencies') +
            '. Deploy the required infrastructure cards on ' +
            nodeId +
            ' before starting this application service.',
        items: missing.map((item, index) => ({
            name: item.display_name || item.service_type || 'Dependency',
            meta:
                (item.service_type || 'infrastructure') +
                ' · ' +
                (item.reason || item.state || 'not ready'),
            actionLabel: 'Install',
            actionIndex: index,
        })),
        emptyText: 'Required infrastructure is not ready.',
        primaryLabel: missing.length ? 'Install first missing' : 'Open catalog',
        secondaryLabel: 'Open catalog',
        onPrimary: () => {
            if (missing.length) {
                startDependencyInstall(missing[0]);
                return;
            }
            closeActionBlockerModal();
            toggleCatalog(true);
        },
        onSecondary: () => {
            closeActionBlockerModal();
            toggleCatalog(true);
        },
        onItemAction: (index) => startDependencyInstall(missing[index]),
    });
}

function closeActionBlockerModal () {
    const modal = $('#actionBlockerModal');
    const backdrop = $('#actionBlockerBack');
    if (modal) modal.classList.remove('open');
    if (backdrop) backdrop.classList.remove('open');
    actionModalHandlers.primary = null;
    actionModalHandlers.secondary = null;
}

function openActionBlockerModal (options) {
    const cfg = options || {};
    const modal = $('#actionBlockerModal');
    const backdrop = $('#actionBlockerBack');
    const list = $('#actionBlockerList');
    const primary = $('#actionBlockerPrimary');
    const secondary = $('#actionBlockerSecondary');
    if (!modal || !backdrop || !list) {
        showToast(cfg.message || cfg.title || 'Action blocked', 'err');
        return;
    }

    if ($('#actionBlockerEyebrow'))
        $('#actionBlockerEyebrow').textContent =
            cfg.eyebrow || 'Action required';
    if ($('#actionBlockerTitle'))
        $('#actionBlockerTitle').textContent = cfg.title || 'Action blocked';
    if ($('#actionBlockerMessage'))
        $('#actionBlockerMessage').textContent =
            cfg.message || 'Resolve the listed items before continuing.';

    const items = cfg.items || [];
    list.innerHTML = items.length
        ? items
            .map((item) => {
                const action = item.actionLabel
                    ? '<button class="mini-action" type="button" data-blocker-item="' +
                        attrEsc(item.actionIndex) +
                        '">' +
                        esc(item.actionLabel) +
                        '</button>'
                    : '';
                return [
                    '<div class="action-modal-item">',
                    '  <div><div class="name">' +
                          esc(item.name || 'Item') +
                          '</div><div class="meta">' +
                          esc(item.meta || '') +
                          '</div></div>',
                    action,
                    '</div>',
                ].join('');
            })
            .join('')
        : '<div class="action-modal-item"><div><div class="name">' +
          esc(cfg.emptyText || 'Nothing to show') +
          '</div></div></div>';

    $$('[data-blocker-item]', list).forEach((button) => {
        button.addEventListener('click', () => {
            if (cfg.onItemAction)
                cfg.onItemAction(Number(button.dataset.blockerItem));
        });
    });

    if (primary) {
        primary.textContent = cfg.primaryLabel || 'Continue';
        primary.style.display = cfg.primaryLabel === null ? 'none' : '';
        actionModalHandlers.primary = cfg.onPrimary || null;
    }
    if (secondary) {
        secondary.textContent = cfg.secondaryLabel || 'Close';
        secondary.style.display = cfg.secondaryLabel === null ? 'none' : '';
        actionModalHandlers.secondary =
            cfg.onSecondary || closeActionBlockerModal;
    }

    backdrop.classList.add('open');
    modal.classList.add('open');
}

async function startDependencyInstall (dependency) {
    if (!dependency) return;
    const details = state.pendingDependencyDetails || {};
    const nodeId = details.node_id || dependency.node_id;
    if (nodeId) {
        const row = $$('.node-row').find(
            (candidate) => candidate.dataset.nodeId === nodeId,
        );
        if (row && !row.classList.contains('active'))
            await loadNodeWorkspace(row);
    }

    const catalogItem = findCatalogItemForServiceType(dependency.service_type);
    const svc = buildCatalogServiceInfo(catalogItem) || {
        id:
            dependency.service_type ||
            dependency.display_name ||
            'Infrastructure',
        serviceType: dependency.service_type || '',
        isInfra: true,
        name:
            dependency.display_name ||
            dependency.service_type ||
            'Infrastructure',
        letter: (dependency.display_name || dependency.service_type || 'I')
            .charAt(0)
            .toUpperCase(),
    };
    closeActionBlockerModal();
    toggleCatalog(false);
    openServiceDrawerAdd(svc);
}

function showNodeDeleteBlocker (details, fallbackMessage) {
    const services = (details && details.services) || [];
    const nodeName =
        (details && (details.node_name || details.node_id)) || 'this node';
    openActionBlockerModal({
        eyebrow: 'Node has services',
        title: 'Node deletion blocked',
        message:
            (fallbackMessage || 'Delete the services first.') +
            ' Remove the mapped services from ' +
            nodeName +
            ' before deleting the node.',
        items: services.map((service) => ({
            name: service.service_name || service.service_id || 'Service',
            meta:
                (service.service_type || 'service') +
                ' · ' +
                (service.deploy_status || 'mapped'),
        })),
        emptyText: 'Services are still mapped to this node.',
        primaryLabel: 'Review services',
        secondaryLabel: 'Close',
        onPrimary: () => {
            closeActionBlockerModal();
            const stack = $('#serviceStack');
            if (stack && stack.scrollIntoView)
                stack.scrollIntoView({ block: 'center' });
        },
        onSecondary: closeActionBlockerModal,
    });
}

async function deleteService (serviceId, nodeId, card, options) {
    const opts = options || {};
    if (!opts.confirmed) {
        const serviceName =
            (card && (card.dataset.serviceName || card.dataset.svcName)) ||
            serviceId ||
            'Service';
        openActionBlockerModal({
            eyebrow: 'Confirm uninstall',
            title: 'Delete service?',
            message:
                'This removes "' +
                serviceName +
                '" from the selected node. Infrastructure dependency cards are only removed when you delete those cards directly.',
            items: [
                {
                    name: serviceName,
                    meta:
                        ((card &&
                            (card.dataset.serviceType ||
                                card.dataset.svcType)) ||
                            'service') +
                        ' · ' +
                        (nodeId || 'selected node'),
                },
            ],
            primaryLabel: 'Delete service',
            secondaryLabel: 'Cancel',
            onPrimary: () => {
                closeActionBlockerModal();
                deleteService(serviceId, nodeId, card, { confirmed: true });
            },
            onSecondary: closeActionBlockerModal,
        });
        return;
    }
    const button = card
        ? $('[data-action="delete-service"]', card)
        : $('#deleteSvcBtn');
    await withPending('delete-service:' + serviceId, async function () {
        setButtonLoading(button, true, 'Deleting...');
        if (card) setBusyState(card, true);
        const res = await sendRequest({
            'user-action': 'delete_service',
            service_id: serviceId,
            node_id: nodeId,
        });
        if (!normalizeSuccess(res)) {
            if (res.details && res.details.code === 'NODE_HAS_SERVICES') {
                showNodeDeleteBlocker(
                    res.details,
                    getMessage(res, 'Delete failed'),
                );
                return;
            }
            showToast(getMessage(res, 'Delete failed'), 'err');
            return;
        }
        if (
            state.detailType === 'service' &&
            state.detailServiceId === serviceId
        )
            closeInfoDetailDrawer();
        if (card) card.remove();
        const active = getActiveNodeRow();
        if (active) loadNodeWorkspace(active);
        await refreshClusterStats();
        showToast(getMessage(res, 'Service deleted'), 'ok');
    }).finally(function () {
        setButtonLoading(button, false);
        if (card) setBusyState(card, false);
    });
}

async function openServiceDrawerEdit (service, card, nodeId) {
    setServiceDrawerMode('edit');
    $('#cfgIco').textContent = (service.service_name || 'S')
        .charAt(0)
        .toUpperCase();
    $('#cfgName').textContent = service.service_name || service.service_id;
    $('#cfgMeta').textContent =
        'service_id ' + service.service_id + ' · node ' + (nodeId || '');
    $('#svcConfigBack').classList.add('open');
    $('#svcConfigDrawer').classList.add('open');
    renderPanelLoading(
        $('#svcInfraConfigFallback'),
        'Loading service configuration...',
    );
    $('#svcInfraConfigFallback').style.display = '';
    setDrawerActionLoading('svcConfigDrawer', true);
    const res = await sendRequest({
        'user-action': 'get_service_info',
        service_id: service.service_id,
    });
    setDrawerActionLoading('svcConfigDrawer', false);
    if (!normalizeSuccess(res)) {
        showToast(getMessage(res, 'Unable to load service config'), 'err');
        return;
    }
    state.editingServiceId = service.service_id;
    state.editingServiceCard = card;
    state.editingServiceConfig = Object.assign({}, res.service_info || {});

    const matchedGroup = await showServiceSchemaGroupByName(
        getServiceSchemaCandidates(service, state.editingServiceConfig),
    );
    fillServiceFormFromConfig(state.editingServiceConfig);
    renderServiceConfigFallback(
        Object.assign({}, state.editingServiceConfig, service, {
            isInfra: isInfrastructureServiceType(
                service.service_type || state.editingServiceConfig.service_type,
            ),
        }),
        matchedGroup,
    );
    syncInfraExposeControls(matchedGroup);
    if ($('#svcInfraConfigFallback'))
        $('#svcInfraConfigFallback').style.display = 'none';
    fetchServiceEvents(service.service_id);
}

function buildServiceUpdatePayload () {
    const base = Object.assign({}, state.editingServiceConfig || {});
    const activeNode = getActiveNodeRow();
    base['user-action'] = 'update_service';
    base.service_id = state.editingServiceId;
    base.node_id = activeNode ? activeNode.dataset.nodeId : '';

    const group = getVisibleServiceSchemaGroup();
    if (group) {
        $$('input, select, textarea', group).forEach((field) => {
            if (!field.name) return;
            base[field.name] =
                field.type === 'checkbox' ? field.checked : field.value;
        });
    }

    Object.assign(base, getServiceStaticFieldValues());

    if (!base.service_name)
        base.service_name =
            state.editingServiceConfig.service_name || state.editingServiceId;
    if (!base.service_version)
        base.service_version = state.editingServiceConfig.service_version || '';
    if (!base.service_install)
        base.service_install =
            state.editingServiceConfig.service_install || 'ANSIBLE';
    if (!base.service_port)
        base.service_port = state.editingServiceConfig.service_port || '';
    if (!base.service_debug)
        base.service_debug = state.editingServiceConfig.service_debug || '';
    if (!base.service_volume)
        base.service_volume = state.editingServiceConfig.service_volume || '';
    return base;
}

async function saveServiceChanges () {
    const saveBtn = $('#svcSaveBtn');
    await withPending(
        'save-service:' + state.editingServiceId,
        async function () {
            setButtonLoading(saveBtn, true, 'Saving...');
            setDrawerActionLoading('svcConfigDrawer', true);
            const payload = buildServiceUpdatePayload();
            const res = await sendRequest(payload);
            if (!normalizeSuccess(res)) {
                showToast(getMessage(res, 'Update failed'), 'err');
                return;
            }
            const storedConfig = Object.assign(
                {},
                state.editingServiceConfig || {},
                payload,
            );
            delete storedConfig['user-action'];
            delete storedConfig.node_id;

            const card = state.editingServiceCard;
            if (card) {
                card.dataset.serviceName =
                    payload.service_name || card.dataset.serviceName;
                card.dataset.svcName =
                    payload.service_name || card.dataset.svcName;
                card.dataset.serviceVersion =
                    payload.service_version || card.dataset.serviceVersion;
                card.dataset.serviceInstall =
                    payload.service_install || card.dataset.serviceInstall;
                card.dataset.servicePort =
                    payload.service_port || card.dataset.servicePort;
                card.dataset.serviceDebug =
                    payload.service_debug || card.dataset.serviceDebug;
                card.dataset.serviceConfig = JSON.stringify(storedConfig);
                const nm = $('.svc-info .nm', card);
                if (nm) nm.textContent = payload.service_name;
                const meta = $('.svc-info .meta', card);
                if (meta)
                    meta.innerHTML =
                        'v' +
                        esc(payload.service_version || '-') +
                        ' · install <span class="v">' +
                        esc(payload.service_install || '-') +
                        '</span> · <span class="v">' +
                        esc(
                            payload.service_type ||
                                card.dataset.serviceType ||
                                '-',
                        ) +
                        '</span>';
                const port = $('.svc-ports .port', card);
                if (port)
                    port.textContent = ':' + (payload.service_port || '-');
                const serviceConfig = storedConfig || {};
                if (
                    (serviceConfig.service_category === 'Infrastructure' ||
                        isInfrastructureServiceType(
                            payload.service_type ||
                                card.dataset.serviceType ||
                                '',
                        )) &&
                    port
                ) {
                    const hostPort = String(
                        serviceConfig.host_port || '',
                    ).trim();
                    port.textContent =
                        serviceConfig.expose_service && hostPort
                            ? ':' + hostPort
                            : 'internal';
                }
                const uptime = $('.svc-status .uptime', card);
                if (uptime) {
                    const hostPort = String(
                        serviceConfig.host_port || '',
                    ).trim();
                    if (
                        serviceConfig.service_category === 'Infrastructure' ||
                        isInfrastructureServiceType(
                            payload.service_type ||
                                card.dataset.serviceType ||
                                '',
                        )
                    ) {
                        uptime.textContent =
                            serviceConfig.expose_service && hostPort
                                ? 'host port ' + hostPort
                                : 'no host port';
                    }
                }
            }

            state.editingServiceConfig = storedConfig;
            showToast(getMessage(res, 'Service updated'), 'ok');
            fetchServiceEvents(state.editingServiceId);
            window.closeSvcConfig();
            const active = getActiveNodeRow();
            if (active) active.click();
        },
    ).finally(function () {
        setDrawerActionLoading('svcConfigDrawer', false);
        setButtonLoading(saveBtn, false);
    });
}

function attachServiceCardEvents (card, service, nodeId) {
    const deployBtn = $('[data-action="deploy-service"]', card);
    const editBtn = $('[data-action="edit-service"]', card);
    const deleteBtn = $('[data-action="delete-service"]', card);
    const configBtn = $('[data-action="service-config-manager"]', card);

    if (deployBtn)
        deployBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            deployService(service.service_id, card);
        });
    if (editBtn)
        editBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            openServiceDrawerEdit(service, card, nodeId);
        });
    if (deleteBtn)
        deleteBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            deleteService(service.service_id, nodeId, card);
        });
    if (configBtn)
        configBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            if (window.openConfigManagerForService)
                window.openConfigManagerForService(card);
        });
    card.addEventListener('click', () => {
        // track service visit
        currentVisit.service_name = service.service_name || '';
        trackVisit();

        if (window.openServiceOverviewDrawer) {
            window.openServiceOverviewDrawer(card);
            return;
        }
        fetchServiceEvents(service.service_id);
    });
}

function renderServicesForNode (nodeId, serviceObj) {
    const stack = $('#serviceStack');
    if (!stack) return;
    stack.innerHTML = '';

    const list = Object.values(serviceObj || {});
    const ct = $('.services-head .ct');
    if (ct) ct.textContent = list.length + ' running';

    if (!list.length) {
        stack.innerHTML =
            '<div class="empty-services">No services installed on this node</div>';
        renderEvents(
            'serviceEventsPanel',
            'serviceEventsStatus',
            [],
            'No service selected',
        );
        return;
    }

    list.forEach((service) => {
        const card = document.createElement('div');
        card.className = 'svc-card running';
        card.dataset.serviceId = service.service_id || '';
        card.dataset.serviceName = service.service_name || '';
        card.dataset.serviceType = service.service_type || '';
        card.dataset.serviceVersion = service.service_version || '';
        card.dataset.servicePort = service.service_port || '';
        card.dataset.serviceInstall = service.service_install || '';
        card.dataset.serviceDebug = service.service_debug || '';
        card.dataset.serviceStatus = service.deploy_status || '';
        card.dataset.serviceConfig = JSON.stringify(
            service.service_config || {},
        );
        card.innerHTML = buildServiceCardHtml(service);
        attachServiceCardEvents(card, service, nodeId);
        stack.appendChild(card);
    });
}

function extractUtilizationMetrics (machineStats) {
    if (!machineStats || machineStats.error) {
        return null;
    }

    const cpuValues = machineStats?.cpu_utilization_data?.data || [];
    const freeMemory = machineStats?.free_memory_data?.data || [];
    const totalMemory = machineStats?.total_memory_data?.data || [];
    const freeDisk = machineStats?.free_disk_data?.data || [];
    const totalDisk = machineStats?.total_disk_data?.data || [];
    const gpuValues = machineStats?.gpu_utilization_data?.data || [];
    const freeGpuMemory = machineStats?.free_gpu_memory_data?.data || [];
    const usedGpuMemory = machineStats?.used_gpu_memory_data?.data || [];

    const cpu = cpuValues.length
        ? Number(cpuValues[cpuValues.length - 1])
        : null;
    let memory = null;

    if (
        freeMemory.length &&
        totalMemory.length &&
        freeMemory.length === totalMemory.length
    ) {
        const free = Number(freeMemory[freeMemory.length - 1]);
        const total = Number(totalMemory[totalMemory.length - 1]);

        if (total > 0) {
            memory = ((total - free) / total) * 100;
        }
    }

    let storage = null;

    if (
        freeDisk.length &&
        totalDisk.length &&
        freeDisk.length === totalDisk.length
    ) {
        const free = Number(freeDisk[freeDisk.length - 1]);
        const total = Number(totalDisk[totalDisk.length - 1]);

        if (total > 0) {
            storage = ((total - free) / total) * 100;
        }
    }

    const gpu = gpuValues.length
        ? Number(gpuValues[gpuValues.length - 1])
        : null;

    let gpuMemory = null;
    if (
        freeGpuMemory.length &&
        usedGpuMemory.length &&
        freeGpuMemory.length === usedGpuMemory.length
    ) {
        const free = Number(freeGpuMemory[freeGpuMemory.length - 1]);
        const used = Number(usedGpuMemory[usedGpuMemory.length - 1]);
        const total = free + used;

        if (total > 0) {
            gpuMemory = (used / total) * 100;
        }
    }

    return {
        cpu,
        memory,
        storage,
        gpu,
        gpuMemory,
    };
}

async function fetchNodeUtilizationData (cluster, node) {
    try {
        const payload = {
            cluster,
            node,
            period: '24h',
            refresh: false,
        };

        const formData = new FormData();
        formData.append('json_data', JSON.stringify(payload));

        const response = await fetch('/PlatformIO/GetNodePerformance/', {
            method: 'POST',
            body: formData,
            headers: {
                'X-CSRFToken': csrfToken,
            },
        });

        const data = await response.json();

        if (!data.success) {
            return null;
        }

        return extractUtilizationMetrics(data.machine_stats);
    } catch {
        return null;
    }
}

function renderMetric (valueId, barId, value, suffix = '%') {
    const valueEl = document.getElementById(valueId);
    const barEl = document.getElementById(barId);

    if (value === null || value === undefined || Number.isNaN(value)) {
        valueEl.textContent = 'NA';
        if (barEl) {
            barEl.style.width = '0%';
        }
        return;
    }

    valueEl.textContent = `${value.toFixed(1)}${suffix}`;

    if (barEl) {
        barEl.style.width = `${Math.min(value, 100)}%`;
    }
}

function renderNodeUtilization (metrics) {
    if (!metrics) {
        renderMetric('cpuVal', 'cpuBar', null);
        renderMetric('memoryVal', 'memoryBar', null);
        renderMetric('storageVal', 'storageBar', null);
        renderMetric('gpuVal', 'gpuBar', null);
        renderMetric('gpuMemoryVal', 'gpuMemoryBar', null);

        return;
    }

    renderMetric('cpuVal', 'cpuBar', metrics.cpu);
    renderMetric('memoryVal', 'memoryBar', metrics.memory);
    renderMetric('storageVal', 'storageBar', metrics.storage);
    renderMetric('gpuVal', 'gpuBar', metrics.gpu);
    renderMetric('gpuMemoryVal', 'gpuMemoryBar', metrics.gpuMemory);
}

async function loadNodeWorkspace (row) {
    const nodeId = row.dataset.nodeId;
    const pendingKey = 'load-node-workspace:' + nodeId;
    if (state.pendingRequests[pendingKey]) {
        setActiveRow(row);
        return withPending(pendingKey, async function () {});
    }
    if (
        $('#infoDetailDrawer') &&
        $('#infoDetailDrawer').classList.contains('open') &&
        state.detailNodeId &&
        state.detailNodeId !== nodeId
    ) {
        closeInfoDetailDrawer();
    }
    setActiveRow(row);

    // track node visit
    currentVisit.node_id = nodeId || '';
    currentVisit.service_name = ''; // reset service when node changes
    trackVisit();

    updateNodeSpecFromRow(row);
    const stack = $('#serviceStack');
    const eventsPanel = $('#nodeEventsPanel');
    if (stack) renderPanelLoading(stack, 'Loading node services...');
    if (eventsPanel) renderPanelLoading(eventsPanel, 'Loading node events...');
    const requestToken = ++state.workspaceLoadToken;
    await withPending(pendingKey, async function () {
        const res = await sendRequest({
            'user-action': 'get_node_info',
            node_id: nodeId,
        });
        if (requestToken !== state.workspaceLoadToken) return;
        if (!normalizeSuccess(res)) {
            showToast(getMessage(res, 'Node load failed'), 'err');
            return;
        }
        state.nodeInfoCache[nodeId] = res;
        renderServicesForNode(nodeId, res.service_info || {});
        fetchNodeEvents(nodeId);

        const nodeName = row.dataset.nodeName;
        const metrics = await fetchNodeUtilizationData(clusterName, nodeName);

        if (requestToken !== state.workspaceLoadToken) {
            return;
        }
        renderNodeUtilization(metrics);
    });
}

function attachNodeRowEvents (row) {
    row.addEventListener('click', () => loadNodeWorkspace(row));
    const editBtn = $('.node-edit-btn', row);
    if (editBtn) {
        editBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            openNodeDrawerEditMode(row);
        });
    }
}

function collectNodeConfigFromForm (nodeIdOverride) {
    const step1Inputs = $$('[data-step-content="1"] .input');
    const step1Selects = $$('[data-step-content="1"] .select');
    const step2Inputs = $$('[data-step-content="2"] .spec-input input');
    const step2Selects = $$('[data-step-content="2"] .select');
    const step4Selects = $$('[data-step-content="4"] .select');
    const step4Checks = $$('[data-step-content="4"] input[type="checkbox"]');
    const step5Checks = $$('[data-step-content="5"] input[type="checkbox"]');
    const step5Selects = $$('[data-step-content="5"] .select');

    const authTypeEl = $('#authType');
    const authType = authTypeEl ? authTypeEl.value : 'encryptionKey';
    const encryptionEl = $('#encryptionKeyField .input');
    const passwordEl = $('#passwordField .input');

    const chips = $$('#portRow .port-chip');
    const ports = chips
        .map(
            (chip) =>
                String(chip.textContent || '')
                    .replace('×', '')
                    .replace('Ã—', '')
                    .trim()
                    .split(' ')[0],
        )
        .filter(Boolean);

    return {
        node_id: nodeIdOverride || state.editingNodeId || '',
        node_name: $('[data-step-content="1"] .field .input').value,
        provider: $('.cloud-card.selected')
            ? $('.cloud-card.selected').dataset.cloud
            : 'aws',
        gpu_status: step2Selects[0] ? step2Selects[0].value : '',
        node_ip: $('#nd-ip') ? $('#nd-ip').value : '',
        auth_type: authType === 'encryptionKey' ? 'EncryptionKey' : 'Password',
        username: $('#nd-username') ? $('#nd-username').value : '',
        password: passwordEl ? passwordEl.value : '',
        encryption_key: encryptionEl ? encryptionEl.value : '',
        node_volume: $('#nd-volume') ? $('#nd-volume').value : '',
        node_monitor_port: 9010,
        access_key: step1Inputs[1] ? step1Inputs[1].value : '',
        secret_key: step1Inputs[2] ? step1Inputs[2].value : '',
        region: step1Selects[0] ? step1Selects[0].value : '',
        availability_zone: step1Selects[1] ? step1Selects[1].value : '',
        vcpu: step2Inputs[0] ? step2Inputs[0].value : '',
        memory: step2Inputs[1] ? step2Inputs[1].value : '',
        storage: step2Inputs[2] ? step2Inputs[2].value : '',
        gpu_type: step2Selects[0] ? step2Selects[0].value : '',
        os_variant: step2Selects[1] ? step2Selects[1].value : '',
        image_source: step2Selects[2] ? step2Selects[2].value : '',
        vpc: step4Selects[0] ? step4Selects[0].value : '',
        subnet: step4Selects[1] ? step4Selects[1].value : '',
        auto_assign_private_ip: step4Checks[0] ? step4Checks[0].checked : false,
        attach_elastic_ip: step4Checks[1] ? step4Checks[1].checked : false,
        dns_name: $('[data-step-content="4"] .field .input')
            ? $('[data-step-content="4"] .field .input').value
            : '',
        ports: ports,
        source_cidr: step5Selects[0] ? step5Selects[0].value : '',
        allow_all_outbound: step5Checks[0] ? step5Checks[0].checked : false,
        restrict_corp_proxy: step5Checks[1] ? step5Checks[1].checked : false,
    };
}

function updateNodeReview () {
    const cfg = collectNodeConfigFromForm(state.editingNodeId || '');
    const providerCard = $('.cloud-card.selected');
    const providerName = providerCard
        ? $('.ico', providerCard).textContent.trim()
        : String(cfg.provider || 'aws').toUpperCase();
    const storageText = cfg.storage ? cfg.storage + ' GB gp3 SSD' : '-';
    const instanceBits = [];
    if (cfg.vcpu) instanceBits.push(cfg.vcpu + ' vCPU');
    if (cfg.memory) instanceBits.push(cfg.memory + ' GB');

    if ($('#rvNodeName')) $('#rvNodeName').textContent = cfg.node_name || '-';
    if ($('#rvProviderAz'))
        $('#rvProviderAz').textContent =
            providerName + ' · ' + (cfg.availability_zone || cfg.region || '-');
    if ($('#rvInstance'))
        $('#rvInstance').textContent = instanceBits.length
            ? 'Custom · ' + instanceBits.join(' · ')
            : '-';
    if ($('#rvStorage')) $('#rvStorage').textContent = storageText;
    if ($('#rvGpu'))
        $('#rvGpu').textContent =
            cfg.gpu_type && cfg.gpu_type !== 'None' ? cfg.gpu_type : 'none';
    if ($('#rvOs')) $('#rvOs').textContent = cfg.os_variant || '-';
    if ($('#rvAuthType')) $('#rvAuthType').textContent = cfg.auth_type || '-';
    if ($('#rvUsername')) $('#rvUsername').textContent = cfg.username || '-';
    if ($('#rvNodeVolume'))
        $('#rvNodeVolume').textContent = cfg.node_volume || '-';
    if ($('#rvVpcSubnet'))
        $('#rvVpcSubnet').textContent =
            [cfg.vpc, cfg.subnet].filter(Boolean).join(' / ') || '-';
    if ($('#rvDns')) $('#rvDns').textContent = cfg.dns_name || '-';
    if ($('#rvPorts'))
        $('#rvPorts').textContent = cfg.ports.length
            ? cfg.ports.join(', ')
            : '-';
}

function fillNodeFormFromConfig (cfg) {
    if (!cfg) return;
    const setVal = (sel, val) => {
        const el = $(sel);
        if (el && val !== undefined && val !== null) el.value = val;
    };
    setVal('[data-step-content="1"] .field .input', cfg.node_name || '');
    $$('.cloud-card').forEach((card) => card.classList.remove('selected'));
    const c = $('.cloud-card[data-cloud="' + (cfg.provider || '') + '"]');
    if (c) c.classList.add('selected');
    if ($('#credentials-section'))
        $('#credentials-section').style.display =
            cfg.provider === 'dc' ? 'none' : 'block';

    const step1Inputs = $$('[data-step-content="1"] .input');
    if (step1Inputs[1]) step1Inputs[1].value = cfg.access_key || '';
    if (step1Inputs[2]) step1Inputs[2].value = cfg.secret_key || '';
    const step1Selects = $$('[data-step-content="1"] .select');
    if (step1Selects[0] && cfg.region) step1Selects[0].value = cfg.region;
    if (step1Selects[1] && cfg.availability_zone)
        step1Selects[1].value = cfg.availability_zone;

    const step2Inputs = $$('[data-step-content="2"] .spec-input input');
    if (step2Inputs[0]) step2Inputs[0].value = cfg.vcpu || '';
    if (step2Inputs[1]) step2Inputs[1].value = cfg.memory || '';
    if (step2Inputs[2]) step2Inputs[2].value = cfg.storage || '';
    const step2Selects = $$('[data-step-content="2"] .select');
    if (step2Selects[0] && (cfg.gpu_type || cfg.gpu_status))
        step2Selects[0].value = cfg.gpu_type || cfg.gpu_status;
    if (step2Selects[1] && cfg.os_variant)
        step2Selects[1].value = cfg.os_variant;
    if (step2Selects[2] && cfg.image_source)
        step2Selects[2].value = cfg.image_source;

    if ($('#authType'))
        $('#authType').value =
            String(cfg.auth_type || '').toLowerCase() === 'password'
                ? 'password'
                : 'encryptionKey';
    setVal('#nd-username', cfg.username || '');
    setVal('#nd-volume', cfg.node_volume || '');
    setVal('#nd-ip', cfg.node_ip || '');
    setVal('#encryptionKeyField .input', cfg.encryption_key || '');
    setVal('#passwordField .input', cfg.password || '');
    $('#authType').dispatchEvent(new Event('change'));
}

let nodeStep = 1;
function setNodeStep (n) {
    nodeStep = n;
    $$('.drawer .stepper .step').forEach((s) => {
        const sn = parseInt(s.dataset.step, 10);
        s.classList.toggle('active', sn === n);
        s.classList.toggle('done', sn < n);
    });
    $$('[data-step-content]').forEach((p) =>
        p.classList.toggle('active', parseInt(p.dataset.stepContent, 10) === n),
    );

    const isFinal = n === 6;
    const isEdit = state.nodeMode === 'edit';
    if (isFinal) updateNodeReview();
    $('#prevNodeStep').style.display = n > 1 ? '' : 'none';
    $('#nextNodeStep').style.display = isFinal ? 'none' : '';
    $('#provisionNode').style.display = isFinal && !isEdit ? '' : 'none';
    if ($('#saveNodeChanges'))
        $('#saveNodeChanges').style.display = isFinal && isEdit ? '' : 'none';
}

function setNodeDrawerMode (mode) {
    state.nodeMode = mode;
    const isEdit = mode === 'edit';
    if ($('#nodeDrawerTitle'))
        $('#nodeDrawerTitle').childNodes[0].nodeValue = isEdit
            ? 'Edit node '
            : 'Provision new node ';
    if ($('#nodeEditBadge'))
        $('#nodeEditBadge').style.display = isEdit ? 'inline-block' : 'none';
    setNodeStep(1);
}

window.closeNodeDrawer = function () {
    $('#newNodeBack').classList.remove('open');
    $('#newNodeDrawer').classList.remove('open');
    if (window.resetNodeDrawerTabs) window.resetNodeDrawerTabs();
    state.nodeMode = 'add';
    state.editingNodeId = '';
    setNodeDrawerMode('add');
};

function openNodeDrawerAddMode () {
    state.editingNodeId = '';
    setNodeDrawerMode('add');
    $('#newNodeBack').classList.add('open');
    $('#newNodeDrawer').classList.add('open');
}

async function openNodeDrawerEditMode (row) {
    setActiveRow(row);
    const nodeId = row.dataset.nodeId;
    $('#newNodeBack').classList.add('open');
    $('#newNodeDrawer').classList.add('open');
    setNodeDrawerMode('edit');
    setDrawerActionLoading('newNodeDrawer', true);
    let info = state.nodeInfoCache[nodeId];
    if (!info) {
        const res = await sendRequest({
            'user-action': 'get_node_info',
            node_id: nodeId,
        });
        if (normalizeSuccess(res)) {
            info = res;
            state.nodeInfoCache[nodeId] = res;
        }
    }
    setDrawerActionLoading('newNodeDrawer', false);
    state.editingNodeId = nodeId;
    setNodeDrawerMode('edit');
    fillNodeFormFromConfig(info || {});
}

async function addNodeFromForm () {
    const button = $('#provisionNode');
    await withPending('add-node', async function () {
        setButtonLoading(button, true, 'Provisioning...');
        setDrawerActionLoading('newNodeDrawer', true);
        const cfg = collectNodeConfigFromForm('');
        const res = await sendRequest({
            'user-action': 'add_node',
            cluster_id: clusterId,
            node_provision_config: JSON.stringify(cfg),
        });
        if (!normalizeSuccess(res)) {
            showToast(getMessage(res, 'Node add failed'), 'err');
            return;
        }
        showToast(getMessage(res, 'Node added'), 'ok');
        const discoverySummary =
            (res.infra_discovery && res.infra_discovery.summary) || {};
        const adopted =
            res.infra_discovery && res.infra_discovery.adopted
                ? res.infra_discovery.adopted.length
                : 0;
        if (adopted || discoverySummary.quarantined) {
            showToast(
                'Node added; kept ' +
                    (discoverySummary.kept || 0) +
                    ', adopted ' +
                    (discoverySummary.adopted || 0) +
                    ', repaired ' +
                    (discoverySummary.repaired || 0) +
                    ', quarantined ' +
                    (discoverySummary.quarantined || 0),
                'ok',
            );
        }
        window.closeNodeDrawer();
        await refreshClusterStats();
        const active = state.activeNodeId
            ? $('.node-row[data-node-id="' + state.activeNodeId + '"]')
            : getActiveNodeRow();
        if (active) loadNodeWorkspace(active);
    }).finally(function () {
        setDrawerActionLoading('newNodeDrawer', false);
        setButtonLoading(button, false);
    });
}

async function discoverInfrastructureForActiveNode () {
    const row = getActiveNodeRow();
    const nodeId = row ? row.dataset.nodeId : '';
    if (!nodeId) {
        showToast('Select a node first', 'err');
        return;
    }
    const btn = $('#discoverInfraBtn');
    setButtonLoading(btn, true, 'Discovering...');
    try {
        const res = await sendRequest({
            'user-action': 'discover_infrastructure',
            node_id: nodeId,
        });
        if (!normalizeSuccess(res)) {
            showToast(
                getMessage(res, 'Infrastructure discovery failed'),
                'err',
            );
            return;
        }
        const summary = (res.details && res.details.summary) || {};
        showToast(
            'Infra reconcile: kept ' +
                (summary.kept || 0) +
                ', adopted ' +
                (summary.adopted || 0) +
                ', repaired ' +
                (summary.repaired || 0) +
                ', quarantined ' +
                (summary.quarantined || 0),
            'ok',
        );
        delete state.nodeInfoCache[nodeId];
        await refreshClusterStats();
        const active = $('.node-row[data-node-id="' + nodeId + '"]') || row;
        if (active) loadNodeWorkspace(active);
    } finally {
        setButtonLoading(btn, false);
    }
}

async function saveNodeChanges () {
    const button = $('#saveNodeChanges');
    await withPending('save-node:' + state.editingNodeId, async function () {
        setButtonLoading(button, true, 'Saving...');
        setDrawerActionLoading('newNodeDrawer', true);
        const cfg = collectNodeConfigFromForm(state.editingNodeId);
        const res = await sendRequest({
            'user-action': 'update_node',
            node_provision_config: JSON.stringify(cfg),
        });
        if (!normalizeSuccess(res)) {
            showToast(getMessage(res, 'Node update failed'), 'err');
            return;
        }
        showToast(getMessage(res, 'Node updated'), 'ok');
        window.closeNodeDrawer();
        await refreshClusterStats();
        const active = state.activeNodeId
            ? $('.node-row[data-node-id="' + state.activeNodeId + '"]')
            : getActiveNodeRow();
        if (active) loadNodeWorkspace(active);
    }).finally(function () {
        setDrawerActionLoading('newNodeDrawer', false);
        setButtonLoading(button, false);
    });
}

async function launchActiveNode () {
    const row = getActiveNodeRow();
    if (!row) return;
    const nodeId = row.dataset.nodeId;
    const info = Object.assign({}, state.nodeInfoCache[nodeId] || {}, {
        node_id: nodeId,
    });
    const button = $('#launchNodeBtn');
    await withPending('launch-node:' + nodeId, async function () {
        setButtonLoading(button, true, 'Launching...');
        const res = await sendRequest({
            'user-action': 'launch_node',
            node_provision_config: JSON.stringify(info),
        });
        if (!normalizeSuccess(res)) {
            showToast(getMessage(res, 'Launch failed'), 'err');
            return;
        }
        showToast(getMessage(res, 'Launch initiated'), 'ok');
        fetchNodeEvents(nodeId);
    }).finally(function () {
        setButtonLoading(button, false);
    });
}

async function deleteActiveNode (options) {
    const opts = options || {};
    const row = opts.nodeId
        ? $$('.node-row').find(
            (candidate) => candidate.dataset.nodeId === opts.nodeId,
        )
        : getActiveNodeRow();
    if (!row) return;
    if (!opts.confirmed) {
        openActionBlockerModal({
            eyebrow: 'Confirm deletion',
            title: 'Delete node?',
            message:
                'This removes node "' +
                (row.dataset.nodeName || row.dataset.nodeId) +
                '" from the cluster. If services are still mapped, deletion will be blocked and the services will be listed.',
            items: [
                {
                    name: row.dataset.nodeName || row.dataset.nodeId || 'Node',
                    meta:
                        (row.dataset.nodeId || 'node') +
                        ' · ' +
                        (row.dataset.nodeIp || 'no runtime IP recorded'),
                },
            ],
            primaryLabel: 'Delete node',
            secondaryLabel: 'Cancel',
            onPrimary: () => {
                closeActionBlockerModal();
                deleteActiveNode({
                    confirmed: true,
                    nodeId: row.dataset.nodeId,
                });
            },
            onSecondary: closeActionBlockerModal,
        });
        return;
    }
    const button = $('#deleteNodeBtn');
    await withPending('delete-node:' + row.dataset.nodeId, async function () {
        setButtonLoading(button, true, 'Deleting...');
        const res = await sendRequest({
            'user-action': 'delete_node',
            node_id: row.dataset.nodeId,
        });
        if (!normalizeSuccess(res)) {
            showToast(getMessage(res, 'Delete failed'), 'err');
            return;
        }
        showToast(getMessage(res, 'Node deleted'), 'ok');
        if (
            state.detailType === 'node' &&
            state.detailNodeId === row.dataset.nodeId
        )
            closeInfoDetailDrawer();
        row.remove();
        await refreshClusterStats();
        const first = $('.node-row');
        if (first) {
            loadNodeWorkspace(first);
        } else {
            // No nodes left! Clear the workspace and detail panel
            state.activeNodeId = '';

            // 1. Clear spec headers and cells
            $('#specNodeName').textContent = 'No Nodes';
            $('#specRegion').textContent = '—';
            $('#specNodeId').textContent = '— · --';
            $('#specVcpu').textContent = '0';
            $('#specMemory').innerHTML = '0 <span class="unit">GB</span>';
            $('#specStorage').innerHTML = '0 <span class="unit">GB SSD</span>';
            if ($('#specGpu')) $('#specGpu').textContent = '—';
            if ($('#specOs')) $('#specOs').textContent = '—';

            // 2. Clear service stack with a clean placeholder
            const stack = $('#serviceStack');
            if (stack) {
                stack.innerHTML = `
                    <div style="padding:40px; text-align:center; color:var(--ink-4);">
                        <svg class="ic ic-lg" viewBox="0 0 24 24" style="margin-bottom:12px; opacity:0.5; stroke:currentColor; stroke-width:2; fill:none; width:48px; height:48px; display:inline-block;">
                            <rect x="2" y="2" width="20" height="8" rx="2" ry="2"></rect>
                            <rect x="2" y="14" width="20" height="8" rx="2" ry="2"></rect>
                            <line x1="6" y1="6" x2="6.01" y2="6"></line>
                            <line x1="6" y1="18" x2="6.01" y2="18"></line>
                        </svg>
                        <div>No nodes in cluster. Provision a node to get started.</div>
                    </div>
                `;
            }

            // 3. Clear events panel
            const eventsPanel = $('#nodeEventsPanel');
            if (eventsPanel) {
                eventsPanel.innerHTML =
                    '<div style="color:var(--ink-4); padding:16px; text-align:center;">No node events available.</div>';
            }
            if ($('#nodeEventsStatus'))
                $('#nodeEventsStatus').textContent = '0 events';

            // 4. Reset utilization charts
            renderNodeUtilization(null);
        }
    }).finally(function () {
        setButtonLoading(button, false);
    });
}

async function deleteClusterFromDetail (options) {
    const opts = options || {};
    if (!opts.confirmed) {
        openActionBlockerModal({
            eyebrow: 'Confirm deletion',
            title: 'Delete cluster?',
            message:
                'This permanently removes "' +
                clusterName +
                '" if it has no active nodes. Clusters with mapped nodes or primary/secondary dependencies will be blocked.',
            items: [
                {
                    name: clusterName,
                    meta: clusterId + ' · this action cannot be undone',
                },
            ],
            primaryLabel: 'Delete cluster',
            secondaryLabel: 'Cancel',
            onPrimary: () => {
                closeActionBlockerModal();
                deleteClusterFromDetail({ confirmed: true });
            },
            onSecondary: closeActionBlockerModal,
        });
        return;
    }

    console.log(
        '[deleteClusterFromDetail] confirmed — sending delete_cluster request',
        clusterId,
    );

    const button = $('#deleteClusterBtn');
    await withPending('delete-cluster:' + clusterId, async function () {
        setButtonLoading(button, true, 'Deleting...');
        const res = await sendRequest(
            { 'user-action': 'delete_cluster', cluster_id: clusterId },
            { url: '/PlatformIO/ClusterView/' },
        );

        console.log('[deleteClusterFromDetail] response:', res);

        if (!normalizeSuccess(res)) {
            const details = res.details || {};
            const nodes = details.nodes || [];

            const items = nodes.length
                ? nodes.map((node) => ({
                    name: node.node_name || node.node_id,
                    meta: `${node.node_id || 'node'} · delete this node first`,
                }))
                : [
                    {
                        name: clusterName,
                        meta:
                              details.code === 'PRIMARY_CLUSTER_HAS_SECONDARIES'
                                  ? 'Primary cluster must be deleted after secondary clusters'
                                  : 'Review cluster dependencies before deleting',
                    },
                ];

            openActionBlockerModal({
                eyebrow: 'Deletion blocked',
                title: 'Cluster deletion blocked',
                message: getMessage(res, 'This cluster cannot be deleted yet.'),
                items,
                primaryLabel: 'Close',
                secondaryLabel: null,
                onPrimary: closeActionBlockerModal,
            });

            return;
        }

        showToast(getMessage(res, 'Cluster deleted'), 'ok');
        setTimeout(function () {
            window.location.href = '/PlatformIO/ClusterView/';
        }, 700);
    }).finally(function () {
        setButtonLoading(button, false);
    });
}

function toggleCatalog (open) {
    const d = $('#catalogDrawer');
    if (!d) return;
    if (open === undefined) open = !d.classList.contains('open');
    d.classList.toggle('open', !!open);
}
window.toggleCatalog = toggleCatalog;

window.closeSvcConfig = function () {
    $('#svcConfigBack').classList.remove('open');
    $('#svcConfigDrawer').classList.remove('open');
    if (window.resetSvcDrawerTabs) window.resetSvcDrawerTabs();
    state.serviceMode = 'add';
    state.editingServiceId = '';
    state.editingServiceCard = null;
    state.editingServiceConfig = {};
    state.pendingSvc = null;
    if ($('#svcInfraConfigFallback'))
        $('#svcInfraConfigFallback').style.display = 'none';
    currentSvcStep = 1;
    updateSvcStepper();
};

const totalSvcSteps = 2;
let currentSvcStep = 1;
function updateSvcStepper () {
    $$('.svc-config-drawer [data-svc-step]').forEach((step) => {
        const sn = parseInt(step.dataset.svcStep, 10);
        step.classList.remove('active', 'done');
        if (sn === currentSvcStep) step.classList.add('active');
        if (sn < currentSvcStep) step.classList.add('done');
    });
    $$('.svc-config-drawer [data-svc-step-content]').forEach((pane) => {
        const pn = parseInt(pane.dataset.svcStepContent, 10);
        pane.classList.toggle('active', pn === currentSvcStep);
        pane.style.display = pn === currentSvcStep ? 'block' : 'none';
    });
    $('#prevSvcStep').style.display = currentSvcStep === 1 ? 'none' : '';
    $('#nextSvcStep').style.display =
        currentSvcStep === totalSvcSteps ? 'none' : '';
    $('#installSvc').style.display =
        currentSvcStep === totalSvcSteps && state.serviceMode === 'add'
            ? ''
            : 'none';
    updateServiceFooterActions();
}

function collectServiceAddPayload (activeNodeId) {
    const payload = {
        'user-action': 'add_service',
        node_id: activeNodeId,
        service_type: (
            state.pendingSvc.serviceType || state.pendingSvc.name
        ).trim(),
    };
    const group = getVisibleServiceSchemaGroup();
    if (group) {
        $$('input, select, textarea', group).forEach((field) => {
            if (!field.name) return;
            payload[field.name] =
                field.type === 'checkbox' ? field.checked : field.value;
        });
    }
    Object.assign(payload, getServiceStaticFieldValues());
    return payload;
}

async function addServiceFromDrawer () {
    const active = getActiveNodeRow();
    if (!active || !state.pendingSvc) return;
    const installBtn = $('#installSvc');
    await withPending(
        'add-service:' +
            active.dataset.nodeId +
            ':' +
            (state.pendingSvc.serviceType || state.pendingSvc.id || 'service'),
        async function () {
            setButtonLoading(installBtn, true, 'Installing...');
            setDrawerActionLoading('svcConfigDrawer', true);
            const payload = collectServiceAddPayload(active.dataset.nodeId);
            const res = await sendRequest(payload);
            if (!normalizeSuccess(res)) {
                showToast(getMessage(res, 'Install failed'), 'err');
                return;
            }
            showToast(getMessage(res, 'Service added'), 'ok');
            window.closeSvcConfig();
            toggleCatalog(false);
            loadNodeWorkspace(active);
            await refreshClusterStats();
        },
    ).finally(function () {
        setDrawerActionLoading('svcConfigDrawer', false);
        setButtonLoading(installBtn, false);
    });
}

function openServiceDrawerAdd (svc) {
    if (!getActiveNodeRow()) {
        showToast('Select a node before installing a service', 'err');
        return;
    }
    state.pendingSvc = svc;
    resetServiceStaticFields();
    applyInfrastructureDrawerDefaults(svc);
    showServiceSchemaGroupByName([svc.name, svc.id, svc.serviceType]).then(
        (matchedGroup) => {
            syncServiceStaticFieldsFromGroup();
            syncStaticVersionFieldFromSetup();
            applyInfrastructureDrawerDefaults(svc);
            renderServiceConfigFallback(svc, matchedGroup);
            syncInfraExposeControls(matchedGroup);
            if ($('#svc-name')) $('#svc-name').value = '';
        },
    );
    $('#cfgIco').textContent =
        svc.letter || (svc.name || 'S').charAt(0).toUpperCase();
    $('#cfgName').textContent = svc.name;
    $('#cfgMeta').textContent =
        'to be installed on ' +
        (getActiveNodeRow() ? getActiveNodeRow().dataset.nodeName : 'node') +
        ' · ansible role ' +
        (svc.sourceRole || svc.id);
    setServiceDrawerMode('add');
    $('#svcConfigBack').classList.add('open');
    $('#svcConfigDrawer').classList.add('open');
}

function applyCatalogFilter () {
    const search = $('#catalogSearch');
    const query = search ? String(search.value || '').toLowerCase() : '';
    const activeChip = $('.cat-chip.active');
    const activeCategory = activeChip ? activeChip.dataset.cat : 'all';
    $$('.catalog-item').forEach((item) => {
        const matchesCategory =
            activeCategory === 'all' || item.dataset.cat === activeCategory;
        const matchesQuery =
            !query ||
            String(item.textContent || '')
                .toLowerCase()
                .includes(query);
        item.style.display = matchesCategory && matchesQuery ? '' : 'none';
    });
}

function wireCatalogInteractions () {
    let draggingSvc = null;
    const stack = $('#serviceStack');

    $$('.cat-chip').forEach((chip) => {
        chip.addEventListener('click', () => {
            $$('.cat-chip').forEach((item) => item.classList.remove('active'));
            chip.classList.add('active');
            applyCatalogFilter();
        });
    });

    if ($('#catalogSearch'))
        $('#catalogSearch').addEventListener('input', applyCatalogFilter);

    $$('.catalog-item').forEach((item) => {
        const getSvcInfo = () => buildCatalogServiceInfo(item);

        item.addEventListener('dragstart', (e) => {
            draggingSvc = getSvcInfo();
            item.classList.add('dragging');
            if (e.dataTransfer) {
                e.dataTransfer.effectAllowed = 'copy';
                e.dataTransfer.setData('text/plain', draggingSvc.id);
            }
        });

        item.addEventListener('dragend', () => {
            item.classList.remove('dragging');
            draggingSvc = null;
            if (stack) stack.classList.remove('drop-target');
        });

        item.addEventListener('click', () =>
            openServiceDrawerAdd(getSvcInfo()),
        );
    });

    if (stack) {
        stack.addEventListener('dragover', (e) => {
            if (!draggingSvc) return;
            e.preventDefault();
            if (e.dataTransfer) e.dataTransfer.dropEffect = 'copy';
            stack.classList.add('drop-target');
        });
        stack.addEventListener('dragleave', (e) => {
            if (e.target === stack) stack.classList.remove('drop-target');
        });
        stack.addEventListener('drop', (e) => {
            e.preventDefault();
            stack.classList.remove('drop-target');
            if (draggingSvc) openServiceDrawerAdd(draggingSvc);
        });
    }

    applyCatalogFilter();
}

function wireBaseControls () {
    function wirePortChipRemovers () {
        $$('#portRow .port-chip .x').forEach((btn) => {
            btn.onclick = function () {
                if (this.parentElement) this.parentElement.remove();
            };
        });
    }

    const cards = $$('.cloud-card');
    const credentialsSection = $('#credentials-section');
    cards.forEach((card) => {
        card.addEventListener('click', () => {
            cards.forEach((c) => c.classList.remove('selected'));
            card.classList.add('selected');
            if (credentialsSection)
                credentialsSection.style.display =
                    card.dataset.cloud === 'dc' ? 'none' : 'block';
        });
    });

    const authType = $('#authType');
    if (authType) {
        authType.addEventListener('change', () => {
            $('#encryptionKeyField').style.display =
                authType.value === 'encryptionKey' ? 'block' : 'none';
            $('#passwordField').style.display =
                authType.value === 'encryptionKey' ? 'none' : 'block';
        });
    }

    const addPortBtn = $('#addPortBtn');
    const portRow = $('#portRow');
    if (addPortBtn && portRow) {
        addPortBtn.addEventListener('click', () => {
            const chip = document.createElement('span');
            chip.className = 'port-chip';
            chip.innerHTML =
                '<input type="number" min="1" max="9999" placeholder="Port" class="port-input"><span class="x">×</span>';
            const input = $('.port-input', chip);
            $('.x', chip).addEventListener('click', () => chip.remove());
            input.addEventListener('keydown', (e) => {
                if (e.key === 'Enter') {
                    e.preventDefault();
                    finish();
                }
            });
            input.addEventListener('blur', finish);
            function finish () {
                const value = String(input.value || '').trim();
                if (!value) {
                    chip.remove();
                    return;
                }
                chip.innerHTML = value + ' map <span class="x">×</span>';
                $('.x', chip).addEventListener('click', () => chip.remove());
            }
            portRow.insertBefore(chip, addPortBtn);
            input.focus();
        });
    }

    if ($('#nodeSearch'))
        $('#nodeSearch').addEventListener('input', applyNodeSearchFilter);
    wirePortChipRemovers();
}

function wireNodeAndServiceActions () {
    $$('.node-row').forEach((row) => attachNodeRowEvents(row));

    $('#newNodeBtn').addEventListener('click', openNodeDrawerAddMode);
    $('#newNodeBtn2').addEventListener('click', openNodeDrawerAddMode);
    $('#newNodeBack').addEventListener('click', window.closeNodeDrawer);
    $('#prevNodeStep').addEventListener('click', () =>
        setNodeStep(Math.max(1, nodeStep - 1)),
    );
    $('#nextNodeStep').addEventListener('click', () =>
        setNodeStep(Math.min(6, nodeStep + 1)),
    );
    $('#provisionNode').addEventListener('click', addNodeFromForm);
    if ($('#saveNodeChanges'))
        $('#saveNodeChanges').addEventListener('click', saveNodeChanges);
    $('#nodeOverviewBtn').addEventListener('click', () => {
        const row = getActiveNodeRow();
        if (row) openNodeDetailDrawer(row, 'overview');
    });
    $('#editActiveNodeBtn').addEventListener('click', () => {
        const row = getActiveNodeRow();
        if (row) openNodeDrawerEditMode(row);
    });
    $('#launchNodeBtn').addEventListener('click', launchActiveNode);
    $('#deleteNodeBtn').addEventListener('click', deleteActiveNode);
    if ($('#deleteClusterBtn'))
        $('#deleteClusterBtn').addEventListener('click', () =>
            deleteClusterFromDetail(),
        );
    if ($('#discoverInfraBtn'))
        $('#discoverInfraBtn').addEventListener(
            'click',
            discoverInfrastructureForActiveNode,
        );
    $('#nodeEventsBtn').addEventListener('click', () => {
        const row = getActiveNodeRow();
        if (row && window.openNodeEventsDrawer) {
            window.openNodeEventsDrawer(row);
            return;
        }
        fetchNodeEvents(state.activeNodeId);
    });
    $('#infoDetailBack').addEventListener('click', closeInfoDetailDrawer);
    $('#detailCloseBtn').addEventListener('click', closeInfoDetailDrawer);
    $('#detailCloseIcon').addEventListener('click', closeInfoDetailDrawer);
    $$('#detailTabs .tab').forEach((tab) => {
        tab.addEventListener('click', async () => {
            const nextTab = tab.dataset.detailTab;
            setDetailTab(nextTab);
            if (state.detailType === 'node' && nextTab === 'events') {
                await fetchNodeEvents(state.detailNodeId);
                renderDetailEvents(
                    state.nodeEventsCache[state.detailNodeId] || [],
                    'No node events found',
                );
            }
            if (state.detailType === 'service') {
                if (nextTab === 'events') {
                    const res = await sendRequest({
                        'user-action': 'service_event',
                        service_id: state.detailServiceId,
                    });
                    state.serviceEventsCache[state.detailServiceId] =
                        res.service_event_info || [];
                    renderDetailEvents(
                        state.serviceEventsCache[state.detailServiceId] || [],
                        'No service events found',
                    );
                }
                if (nextTab === 'live-status') {
                    await loadAndRenderServiceLiveStatus(
                        state.detailServiceId,
                        {
                            silent: false,
                            message: 'Refreshing runtime status…',
                        },
                    );
                }
            }
        });
    });
    if ($('#detailLiveStatusRefreshBtn')) {
        $('#detailLiveStatusRefreshBtn').addEventListener('click', async () => {
            if (!state.detailServiceId) return;
            await loadAndRenderServiceLiveStatus(state.detailServiceId, {
                silent: false,
                message: 'Refreshing runtime status…',
            });
        });
    }
    $('#detailEditBtn').addEventListener('click', () => {
        if (state.detailType === 'node') {
            const row = $(
                '.node-row[data-node-id="' + state.detailNodeId + '"]',
            );
            if (row) window.editNode(row);
            return;
        }
        if (state.detailType === 'service') {
            const card =
                state.editingServiceCard ||
                $(
                    '.svc-card[data-service-id="' +
                        state.detailServiceId +
                        '"]',
                ) ||
                $('.svc-card[data-svc-id="' + state.detailServiceId + '"]');
            if (card) window.editService(card);
        }
    });
    $('#detailDeleteBtn').addEventListener('click', () => {
        if (state.detailType === 'node') {
            deleteActiveNode();
            return;
        }
        if (state.detailType === 'service') {
            const card =
                $(
                    '.svc-card[data-service-id="' +
                        state.detailServiceId +
                        '"]',
                ) ||
                $('.svc-card[data-svc-id="' + state.detailServiceId + '"]');
            deleteService(state.detailServiceId, state.detailNodeId, card);
        }
    });
    $('#detailLaunchBtn').addEventListener('click', () => {
        if (state.detailType === 'node') launchActiveNode();
    });

    $('#catalogBtn').addEventListener('click', () => toggleCatalog(true));
    if ($('#actionBlockerBack'))
        $('#actionBlockerBack').addEventListener(
            'click',
            closeActionBlockerModal,
        );
    if ($('#actionBlockerCloseIcon'))
        $('#actionBlockerCloseIcon').addEventListener(
            'click',
            closeActionBlockerModal,
        );
    if ($('#actionBlockerPrimary'))
        $('#actionBlockerPrimary').addEventListener('click', () => {
            if (actionModalHandlers.primary) {
                actionModalHandlers.primary();
                return;
            }
            closeActionBlockerModal();
        });
    if ($('#actionBlockerSecondary'))
        $('#actionBlockerSecondary').addEventListener('click', () => {
            if (actionModalHandlers.secondary) {
                actionModalHandlers.secondary();
                return;
            }
            closeActionBlockerModal();
        });
    $('#svcConfigBack').addEventListener('click', window.closeSvcConfig);
    $('#nextSvcStep').addEventListener('click', () => {
        currentSvcStep = Math.min(totalSvcSteps, currentSvcStep + 1);
        updateSvcStepper();
    });
    $('#prevSvcStep').addEventListener('click', () => {
        currentSvcStep = Math.max(1, currentSvcStep - 1);
        updateSvcStepper();
    });
    $('#installSvc').addEventListener('click', addServiceFromDrawer);
    if ($('#svc-version'))
        $('#svc-version').addEventListener(
            'change',
            syncStaticVersionFieldFromSetup,
        );
    if ($('#svc-port')) {
        $('#svc-port').addEventListener('input', () =>
            syncVisibleGroupFieldFromStatic(
                'service_port',
                $('#svc-port').value,
            ),
        );
    }
    if ($('#svc-data-dir')) {
        $('#svc-data-dir').addEventListener('input', () =>
            syncVisibleGroupFieldFromStatic(
                'data_directory',
                $('#svc-data-dir').value,
            ),
        );
    }
    if ($('#svc-max-conn')) {
        $('#svc-max-conn').addEventListener('input', () =>
            syncVisibleGroupFieldFromStatic(
                'max_connections',
                $('#svc-max-conn').value,
            ),
        );
    }
    if ($('#svc-shared-buffers')) {
        $('#svc-shared-buffers').addEventListener('input', () =>
            syncVisibleGroupFieldFromStatic(
                'shared_buffers',
                $('#svc-shared-buffers').value,
            ),
        );
    }
    if ($('#deploySvcBtn'))
        $('#deploySvcBtn').addEventListener('click', () =>
            deployService(state.editingServiceId, state.editingServiceCard),
        );
    if ($('#deleteSvcBtn'))
        $('#deleteSvcBtn').addEventListener('click', () => {
            const active = getActiveNodeRow();
            if (active)
                deleteService(
                    state.editingServiceId,
                    active.dataset.nodeId,
                    state.editingServiceCard,
                );
        });
    if ($('#openConfigManagerBtn')) {
        $('#openConfigManagerBtn').addEventListener('click', () => {
            const active = getActiveNodeRow();
            if (!active || !state.editingServiceId) return;
            window.location.href =
                '/PlatformIO/ConfigManager/?cluster_id=' +
                clusterId +
                '&node_id=' +
                active.dataset.nodeId +
                '&service_id=' +
                state.editingServiceId;
        });
    }

    document.addEventListener('keydown', (e) => {
        if (e.key !== 'Escape') return;
        if (
            $('#actionBlockerModal') &&
            $('#actionBlockerModal').classList.contains('open')
        ) {
            closeActionBlockerModal();
            return;
        }
        if ($('#infoDetailDrawer').classList.contains('open')) {
            closeInfoDetailDrawer();
            return;
        }
        if ($('#svcConfigDrawer').classList.contains('open')) {
            window.closeSvcConfig();
            return;
        }
        if ($('#newNodeDrawer').classList.contains('open')) {
            window.closeNodeDrawer();
            return;
        }
        if ($('#catalogDrawer').classList.contains('open'))
            toggleCatalog(false);
    });
    // Provision button — spinner on click
    const provisionBtn = $('#provisionNode');
    if (provisionBtn) {
        provisionBtn.addEventListener('click', () => {
            provisionBtn.classList.add('loading');
            provisionBtn.disabled = true;
        });
    }
}

window.editNode = function (row) {
    if (row) openNodeDrawerEditMode(row);
};

window.openNodeOverviewDrawer = function (row) {
    if (row) openNodeDetailDrawer(row, 'overview');
};

window.openNodeEventsDrawer = function (row) {
    if (row) openNodeDetailDrawer(row, 'events');
};

window.editService = function (card) {
    const active = getActiveNodeRow();
    if (!card || !active) return;
    openServiceDrawerEdit(
        {
            service_id: card.dataset.serviceId,
            service_name: card.dataset.serviceName,
            service_type: card.dataset.serviceType,
            service_version: card.dataset.serviceVersion,
            service_port: card.dataset.servicePort,
            service_install: card.dataset.serviceInstall,
            service_debug: card.dataset.serviceDebug,
        },
        card,
        active.dataset.nodeId,
    );
};
window.openServiceDrawerEditShared = window.editService;

window.openServiceOverviewDrawer = function (card) {
    if (card) openServiceDetailDrawer(card, 'overview');
};

window.openServiceEventsDrawer = function (card) {
    if (card) openServiceDetailDrawer(card, 'events');
};
window.openServiceEventsDrawerShared = window.openServiceEventsDrawer;
window.saveServiceChangesShared = saveServiceChanges;

window.openConfigManagerForService = function (card) {
    const active = getActiveNodeRow();
    const serviceId = card ? card.dataset.serviceId || card.dataset.svcId : '';
    if (!active || !serviceId) return;
    window.location.href =
        '/PlatformIO/ConfigManager/?cluster_id=' +
        clusterId +
        '&node_id=' +
        active.dataset.nodeId +
        '&service_id=' +
        serviceId;
};

document.addEventListener('DOMContentLoaded', () => {
    state.serviceStaticDefaults = {
        serviceName: $('#svc-name') ? $('#svc-name').value : '',
        versionOptionsHtml: $('#svc-version')
            ? $('#svc-version').innerHTML
            : '',
        serviceVersionValue: $('#svc-version') ? $('#svc-version').value : '',
        dataDirectory: $('#svc-data-dir') ? $('#svc-data-dir').value : '',
        servicePort: $('#svc-port') ? $('#svc-port').value : '',
        maxConnections: $('#svc-max-conn') ? $('#svc-max-conn').value : '',
        sharedBuffers: $('#svc-shared-buffers')
            ? $('#svc-shared-buffers').value
            : '',
    };
    wireBaseControls();
    wireCatalogInteractions();
    wireNodeAndServiceActions();
    setNodeDrawerMode('add');
    setNodeStep(1);
    setServiceDrawerMode('add');
    const active = getActiveNodeRow() || $('.node-row');
    if (active) loadNodeWorkspace(active);
});

// ========================================
// UPDATE INSTALL BUTTON LABEL
// ========================================

function updateInstallButtonLabel () {
    const installBtn = document.getElementById('installSvc');

    if (!installBtn) {
        return;
    }

    const activeGroup = document.querySelector(
        '.svc-schema-group[style*="block"]',
    );

    if (!activeGroup) {
        return;
    }

    const installSelect = activeGroup.querySelector(
        'select[name="service_install"]',
    );

    if (!installSelect) {
        return;
    }

    if (installSelect.value === 'MANUAL') {
        installBtn.innerHTML = `
            <svg class="ic" viewBox="0 0 24 24">
                <polygon points="5,3 19,12 5,21"></polygon>
            </svg>

            Install Manual
        `;
    } else {
        installBtn.innerHTML = `
            <svg class="ic" viewBox="0 0 24 24">
                <polygon points="5,3 19,12 5,21"></polygon>
            </svg>

            Install via Ansible
        `;
    }
}

// ========================================
// GLOBAL LISTENER
// ========================================

document.addEventListener('change', function (event) {
    if (event.target.matches('select[name="service_install"]')) {
        updateInstallButtonLabel();
    }
});

window.refreshRuntimePatchStatus = async function (
    expectedServiceId = state.detailServiceId,
) {
    const statusEl = document.getElementById('runtimePatchStatusText');
    const btn = document.getElementById('btnRuntimePatchFooter');
    if (!btn) {
        return;
    }

    const serviceContext = state.detailServiceContext;
    const serviceType = ((serviceContext && serviceContext.service_type) || '')
        .trim()
        .toLowerCase();
    const EXCLUDED_SERVICE_TYPES = [
        'infrarabbitmq',
        'infrapostgresqlcore',
        'infrarediscore',
        'infraairflowpostgresql',
        'infraairflowredis',
        'infraclickhouse',
        'infranifi',
        'inframilvus',
        'infraetcd',
        'inframinio',
        'infranodeexporter',
        'infraprocessexporter',
        'infrakafkaexporter',
        'infradcgmexporter',
        'infraprometheus',
        'infraprometheusans',
        'infraprometheusrag',
        'airflowinit',
    ];
    if (serviceType && EXCLUDED_SERVICE_TYPES.includes(serviceType)) {
        btn.disabled = true;
        btn.style.display = 'none';
        if (statusEl) {
            statusEl.style.display = 'none';
            statusEl.textContent = '';
        }
        return;
    }

    if (!expectedServiceId || expectedServiceId !== state.detailServiceId) {
        btn.disabled = true;
        btn.style.display = 'none';
        if (statusEl) {
            statusEl.style.display = 'none';
            statusEl.textContent = '';
        }
        return;
    }

    btn.style.display = '';
    btn.disabled = false;
    if (statusEl) {
        statusEl.style.display = '';
        statusEl.textContent = 'Checking patch status...';
    }

    const response = await sendRequest({
        'user-action': 'service_runtime_patch_status',
        service_id: expectedServiceId,
    });
    if (expectedServiceId !== state.detailServiceId) {
        return;
    }
    if (!response || response.success !== true) {
        if (statusEl) {
            statusEl.textContent = response?.error || 'Status unavailable';
        }
        return;
    }

    const status = response.status || {};
    const lastStatus = status.last_status || 'never';
    const checkedAt = status.last_checked_at || '-';
    const message = status.last_message || '';
    const environment = status.last_environment || '';
    const envText = environment ? ` [env: ${environment}]` : '';
    const isPatchedSuccess = String(lastStatus).toLowerCase() === 'success';
    if (statusEl) {
        statusEl.textContent = `Runtime patch: ${lastStatus}${envText} (${checkedAt})${message ? ' - ' + message : ''}`;
    }
    btn.disabled = isPatchedSuccess;
};

window.runServiceRuntimePatch = async function () {
    const serviceId = state.detailServiceId;
    if (!serviceId) {
        return;
    }
    setRuntimePatchButtonBusy(true);
    const response = await sendRequest({
        'user-action': 'service_runtime_patch',
        service_id: serviceId,
    });
    setRuntimePatchButtonBusy(false);
    if (!response) {
        showToast('Runtime patch request failed', 'err');
        return;
    }
    if (response.success === 'True' || response.success === true) {
        showToast(response.msg || 'Runtime patch request completed', 'ok');
    } else {
        showToast(response.msg || 'Runtime patch request failed', 'err');
    }
    window.refreshRuntimePatchStatus(serviceId);
};

function setRuntimePatchButtonBusy (isBusy) {
    const btn = document.getElementById('btnRuntimePatchFooter');
    if (!btn) {
        return;
    }
    btn.disabled = isBusy;
    btn.innerHTML = isBusy
        ? '<span class="spinner-border spinner-border-sm me-1"></span>Patching...'
        : 'Patch Observability Runtime';
}
