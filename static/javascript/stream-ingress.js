/* global Event, fetch, setTimeout, clearTimeout */
/* eslint camelcase: "off" */
/* =============================================================================
   stream-ingress.js
   All interactivity for /PlatformIO/StreamIngress/ (single-page)
   Sections:
     1. View switcher  — list  ↔  crud wizard
     2. List tabs      — filter rows by type
     3. Bulletin drawer — open / close / tab panes
     4. CRUD stepper   — step navigation, type pickers, rail sync
   ============================================================================= */

(function () {
    'use strict';

    /* ─── helpers ─────────────────────────────────────────────────────────── */
    const $ = (sel, ctx) => (ctx || document).querySelector(sel);
    const $$ = (sel, ctx) =>
        Array.from((ctx || document).querySelectorAll(sel));

    const DF_CATEGORY_MAP = {
        CDR: { label: 'CDR', color: '#4f46e5', bg: '#eef2ff' },
        RIBBON: { label: 'RIBBON', color: '#7c3aed', bg: '#f5f3ff' },
        GROUNDHOG: { label: 'GROUNDHOG', color: '#0891b2', bg: '#ecfeff' },
        NEP: { label: 'NEP', color: '#059669', bg: '#ecfdf5' },
        MNP: { label: 'MNP', color: '#d97706', bg: '#fffbeb' },
        CHURN: { label: 'CHURN', color: '#dc2626', bg: '#fef2f2' },
        ROTATIONAL: { label: 'ROTATIONAL', color: '#9333ea', bg: '#fdf4ff' },
        USERPROFILE: { label: 'USERPROFILE', color: '#0284c7', bg: '#f0f9ff' },
        NETWORKPROFILE: {
            label: 'NETWORKPROFILE',
            color: '#0d9488',
            bg: '#f0fdfa',
        },
        PREPAID: { label: 'PREPAID', color: '#16a34a', bg: '#f0fdf4' },
        POSTPAID: { label: 'POSTPAID', color: '#2563eb', bg: '#eff6ff' },
        RECHARGE: { label: 'RECHARGE', color: '#ea580c', bg: '#fff7ed' },
        BUSINESSPROFILE: { label: 'BUSINESS', color: '#0f766e', bg: '#f0fdfa' },
    };

    window.colorTypeTags = function (root) {
        const scope = root || document;
        scope.querySelectorAll('.df-type-tag-auto').forEach(function (tag) {
            const raw = (tag.dataset.dftype || tag.textContent || '')
                .toUpperCase()
                .replace(/[_\s]/g, '');
            let cat = { label: raw || 'STD', color: '#64748b', bg: '#f8fafc' };
            for (const [key, val] of Object.entries(DF_CATEGORY_MAP)) {
                if (raw.startsWith(key)) {
                    cat = val;
                    break;
                }
            }
            tag.textContent = cat.label;
            tag.style.color = cat.color;
            tag.style.background = cat.bg;
        });
    };

    /* =========================================================================
     SECTION 1 — VIEW SWITCHER
     Toggles between the list view and the CRUD wizard (in-page navigation)
     ========================================================================= */
    const listView = $('#listView');
    const crudView = $('#crudView');

    function resetWizard () {
        // 1. Reset Stepper navigation
        $$('.stepper .step').forEach((s, idx) => {
            s.classList.remove('active', 'done');
            if (idx === 0) s.classList.add('active');
        });
        $$('[data-step-content]').forEach((p) => p.classList.remove('active'));
        const step1Pane = $('[data-step-content="1"]');
        if (step1Pane) step1Pane.classList.add('active');

        // 2. Reset Stream name input
        const streamNameInp = $('#streamName');
        if (streamNameInp) streamNameInp.value = '';

        // 3. Reset hidden input fields
        ['addConnType', 'addAppName', 'addServiceName', 'addDataFlowType', 'addIngestion'].forEach((id) => {
            const el = document.getElementById(id);
            if (el) el.value = '';
        });

        // 4. Reset Step 1 (Source) selections and parameters
        $$('[data-step-content="1"] .type-card').forEach((c) => c.classList.remove('selected'));
        const subPicker = document.getElementById('serviceSubPicker');
        if (subPicker) {
            subPicker.style.display = 'none';
            $$('.sub-type-card', subPicker).forEach((x) => x.classList.remove('selected'));
        }
        const srcParams = document.querySelector('[data-step-content="1"] .src-params');
        if (srcParams) {
            $$('.panel', srcParams).forEach((p) => p.classList.remove('active'));
            $$('input, select, textarea', srcParams).forEach((el) => {
                if (el.tagName === 'SELECT') el.selectedIndex = 0;
                else el.value = '';
            });
        }
        if ($('#nocVendor')) $('#nocVendor').value = 'aviat';

        // Pre-select Service Based as the default without selecting any sub-service
        const srvCard = document.querySelector('[data-step-content="1"] .type-card[data-src="service"]');
        if (srvCard) srvCard.click();
        const subPickerEl = document.getElementById('serviceSubPicker');
        if (subPickerEl) {
            $$('.sub-type-card', subPickerEl).forEach((x) => x.classList.remove('selected'));
        }

        const replayControls = document.getElementById('demoReplayControls');
        if (replayControls) replayControls.style.display = 'none';

        // 5. Reset Step 2 (Destination) selections and drilldown
        $$('[data-step-content="2"] .type-card').forEach((c) => c.classList.remove('selected'));
        const dstParams = document.querySelector('[data-step-content="2"] .dst-params');
        if (dstParams) {
            $$('.panel', dstParams).forEach((p) => p.classList.remove('active'));
        }
        const mockDestUI = $('#mockDestUI');
        const drilldownDestUI = $('#drilldownDestUI');
        if (mockDestUI) mockDestUI.style.display = 'block';
        if (drilldownDestUI) drilldownDestUI.style.display = 'none';

        // Reset Drilldown UI
        const ddSummary = $('#ddSummary');
        if (ddSummary) ddSummary.style.display = 'none';
        const dftSection = $('#dftSection');
        if (dftSection) dftSection.style.display = 'none';
        const dftGrid = $('#dftGrid');
        if (dftGrid) dftGrid.innerHTML = '';
        const ingestionSelect = $('#ingestionSelect');
        if (ingestionSelect) ingestionSelect.value = '';
        const serviceNotSupportedMsg = $('#serviceNotSupportedMsg');
        if (serviceNotSupportedMsg) serviceNotSupportedMsg.style.display = 'none';

        // Reset dynamic service config area (Fin_Data etc.)
        const serviceConfigArea = $('#serviceConfigArea');
        if (serviceConfigArea) {
            serviceConfigArea.style.display = 'none';
            $$('.conn-fields', serviceConfigArea).forEach((p) => (p.style.display = 'none'));
            $$('input, select, textarea', serviceConfigArea).forEach((el) => {
                if (el.tagName === 'SELECT') {
                    if (el.multiple) {
                        Array.from(el.options).forEach((opt) => (opt.selected = false));
                        el.dispatchEvent(new Event('change'));
                    } else {
                        el.selectedIndex = 0;
                    }
                } else {
                    el.value = '';
                }
            });
        }

        // Reset drilldown step states
        $$('#destDrill .dd-step').forEach((st, idx) => {
            st.classList.remove('active', 'selected', 'disabled');
            if (idx === 0) st.classList.add('active');
            else st.classList.add('disabled');
        });

        // 6. Reset Review summary fields
        ['rvStreamName', 'rvSrcType', 'rvSrcDetail', 'rvDestApp', 'rvDestService', 'rvDestIngestion', 'rvPeriodicity', 'rvStartDate', 'rvTimeTz'].forEach((id) => {
            const el = document.getElementById(id);
            if (el) el.textContent = '—';
        });

        // 7. Reset Right Rail topology
        const railSource = $('#railSource');
        if (railSource) railSource.textContent = 'Kafka';
        const railSink = $('#railSink');
        if (railSink) railSink.textContent = 'ClickHouse';
    }

    function showCrud () {
        resetWizard();
        listView.style.display = 'none';
        crudView.style.display = 'block';
        window.scrollTo({ top: 0, behavior: 'smooth' });
    }

    function showList () {
        crudView.style.display = 'none';
        listView.style.display = 'block';
        window.scrollTo({ top: 0, behavior: 'smooth' });
    }

    // "New stream" button on the list page
    const btnNewStream = $('#btnNewStream');
    if (btnNewStream) btnNewStream.addEventListener('click', showCrud);

    // "Back" breadcrumb inside the wizard
    const btnBackToList = $('#btnBackToList');
    if (btnBackToList) btnBackToList.addEventListener('click', showList);

    // "Cancel" on step-1 bottom nav
    const crudCancelBtn = $('#crudCancelBtn');
    if (crudCancelBtn) crudCancelBtn.addEventListener('click', showList);

    /* =========================================================================
     SECTION 2 — LIST TABS
     ========================================================================= */
    const listTabs = $('#listTabs');
    if (listTabs) {
        $$('.tab', listTabs).forEach((tab) => {
            tab.addEventListener('click', () => {
                $$('.tab', listTabs).forEach((t) =>
                    t.classList.remove('active'),
                );
                tab.classList.add('active');

                const filter = tab.dataset.filter;
                $$('.cards-grid .stream-card').forEach((row) => {
                    if (filter === 'all' || !filter) {
                        row.style.display = '';
                    } else {
                        row.style.display = (row.dataset.type === filter) ? '' : 'none';
                    }
                });
            });
        });
    }

    /* =========================================================================
     SECTION 3 — BULLETIN DRAWER
     Open when a table row is clicked; close via backdrop or X button
     Tab panes switch inside the drawer
     ========================================================================= */
    const drawer = $('#drawer');
    const drawerBack = $('#drawerBack');
    const drawerClose = $('#drawerClose');
    /* ─── metrics polling ────────────────────────────────────────────────── */
    let metricsIntervalId = null;
    let metricsInFlight = false;
    let metricsParams = null;
    let metricsGeneration = 0;
    // Runtime observations are intentionally kept in the drawer only.  The
    // backend remains the source of truth; this short ring buffer gives the
    // charts a real live trace without inventing historical data or writing
    // anything to cPlatform state.
    const runtimeSamples = new Map();
    const runtimeLogEntries = new Map();

    /* ─── exception aggregator polling ────────────────────────────────────── */
    let exceptionPollingTimer = null;
    let exceptionPollingPaused = false;
    let currentExceptionsData = [];
    let exceptionFilterQuery = '';

    function startExceptionPolling (dataflowId, dataflowType, intervalMs = 15000) {
        stopExceptionPolling();
        exceptionPollingPaused = false;
        const badge = document.getElementById('exceptionLiveBadge');
        const pauseBtn = document.getElementById('exceptionPauseResumeBtn');
        if (badge) badge.innerHTML = '<span class="live-dot"></span> Live (15s)';
        if (pauseBtn) pauseBtn.textContent = 'Pause';

        fetchStreamExceptions(dataflowId, dataflowType);
        exceptionPollingTimer = setInterval(() => {
            if (!exceptionPollingPaused && activeDrawerStreamId) {
                fetchStreamExceptions(activeDrawerStreamId, activeDrawerDataflowType);
            }
        }, intervalMs);
    }

    function stopExceptionPolling () {
        if (exceptionPollingTimer) {
            clearInterval(exceptionPollingTimer);
            exceptionPollingTimer = null;
        }
    }

    function toggleExceptionPause () {
        exceptionPollingPaused = !exceptionPollingPaused;
        const badge = document.getElementById('exceptionLiveBadge');
        const pauseBtn = document.getElementById('exceptionPauseResumeBtn');
        if (exceptionPollingPaused) {
            if (badge) badge.innerHTML = '<span class="live-dot" style="background:var(--ink-4);"></span> Paused';
            if (pauseBtn) pauseBtn.textContent = 'Resume';
        } else {
            if (badge) badge.innerHTML = '<span class="live-dot"></span> Live (15s)';
            if (pauseBtn) pauseBtn.textContent = 'Pause';
            if (activeDrawerStreamId) {
                fetchStreamExceptions(activeDrawerStreamId, activeDrawerDataflowType);
            }
        }
    }

    function fetchStreamExceptions (dataflowId, dataflowType) {
        if (!dataflowId) return;
        const csrfToken =
            window.csrfToken ||
            document.querySelector('[name="csrfmiddlewaretoken"]')?.value ||
            '';
        const payload = {
            'user-action': 'stream_exceptions',
            dataflow_id: dataflowId,
            dataflow_type: dataflowType || '',
        };

        fetch('/PlatformIO/StreamIngress/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': csrfToken,
            },
            body: JSON.stringify(payload),
        })
            .then((r) => r.json())
            .then((data) => {
                if (data.success) {
                    currentExceptionsData = data.exceptions || [];
                    renderExceptions(currentExceptionsData);
                } else {
                    console.warn('Failed to fetch stream exceptions:', data.message);
                }
            })
            .catch((err) => {
                console.error('Error fetching stream exceptions:', err);
            });
    }

    function escapeHtml (str) {
        if (!str) return '';
        return String(str)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;');
    }

    function renderExceptions (exceptions) {
        const container = document.getElementById('drawerExceptionContainer');
        const totalBadge = document.getElementById('exceptionTotalBadge');
        if (!container) return;

        const totalIncidents = exceptions.length;
        const totalOccurrences = exceptions.reduce((acc, x) => acc + (x.count || 1), 0);

        if (totalBadge) {
            if (totalIncidents === 0) {
                totalBadge.textContent = '0 Incidents';
                totalBadge.classList.remove('has-errors');
            } else {
                totalBadge.textContent = `${totalIncidents} Incident${totalIncidents > 1 ? 's' : ''} (${totalOccurrences}x)`;
                totalBadge.classList.add('has-errors');
            }
        }

        // Apply search filter if active
        let filtered = exceptions;
        if (exceptionFilterQuery.trim()) {
            const q = exceptionFilterQuery.toLowerCase();
            filtered = exceptions.filter((x) =>
                (x.component_name && x.component_name.toLowerCase().includes(q)) ||
                (x.error_type && x.error_type.toLowerCase().includes(q)) ||
                (x.message && x.message.toLowerCase().includes(q)) ||
                (x.source && x.source.toLowerCase().includes(q))
            );
        }

        if (filtered.length === 0) {
            if (exceptions.length > 0) {
                container.innerHTML = `
                    <div class="exception-empty-state">
                        <div class="empty-icon" style="background:var(--bg); color:var(--ink-3);">🔍</div>
                        <h4>No matching exceptions</h4>
                        <p>No exceptions match the query "${escapeHtml(exceptionFilterQuery)}".</p>
                    </div>
                `;
            } else {
                container.innerHTML = `
                    <div class="exception-empty-state">
                        <div class="empty-icon">✓</div>
                        <h4>No Exceptions Detected</h4>
                        <p>Pipeline is operating cleanly. Any processor failures, crashes, or unhandled exceptions will appear here in real time.</p>
                    </div>
                `;
            }
            return;
        }

        container.innerHTML = filtered.map((exc, index) => {
            const isCritical = exc.severity === 'CRITICAL';
            const pillClass = isCritical ? 'exc-pill critical' : 'exc-pill err';
            const occText = exc.count > 1 ? `<span class="exc-pill occ" title="First seen: ${escapeHtml(exc.first_seen)} · Last seen: ${escapeHtml(exc.last_seen)}">${exc.count} occurrences</span>` : '';
            const timeText = exc.last_seen ? `Last seen ${escapeHtml(exc.last_seen)}` : '';
            const cardId = `exc-trace-${index}`;

            return `
                <div class="exception-card ${isCritical ? 'critical' : ''}">
                    <div class="exception-card-head">
                        <div class="exception-tags">
                            <span class="${pillClass}">${exc.severity || 'ERROR'}</span>
                            <span class="exc-pill component">${escapeHtml(exc.component_name || exc.source)}</span>
                            ${occText}
                        </div>
                        <div class="exception-time">${timeText}</div>
                    </div>
                    <h5 class="exception-title">${escapeHtml(exc.error_type || 'Execution Error')}</h5>
                    <div class="exception-msg-snippet">${escapeHtml(exc.message || '')}</div>
                    <div class="exception-actions">
                        <button type="button" class="trace-toggle-btn" data-target="${cardId}">
                            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="9 18 15 12 9 6"></polyline></svg>
                            <span>Show Diagnostic Trace</span>
                        </button>
                    </div>
                    <div class="exception-trace-box" id="${cardId}" style="display:none;">
                        <button type="button" class="copy-trace-btn" data-trace="${encodeURIComponent(exc.stacktrace || exc.message || '')}">Copy Trace</button>
                        <code>${escapeHtml(exc.stacktrace || exc.message || 'No stacktrace available')}</code>
                    </div>
                </div>
            `;
        }).join('');

        // Wire accordion toggles
        container.querySelectorAll('.trace-toggle-btn').forEach((btn) => {
            btn.addEventListener('click', () => {
                const targetId = btn.dataset.target;
                const traceBox = document.getElementById(targetId);
                if (!traceBox) return;
                const isOpen = traceBox.style.display !== 'none';
                traceBox.style.display = isOpen ? 'none' : 'block';
                btn.classList.toggle('open', !isOpen);
                const label = btn.querySelector('span');
                if (label) label.textContent = isOpen ? 'Show Diagnostic Trace' : 'Hide Diagnostic Trace';
            });
        });

        // Wire copy buttons
        container.querySelectorAll('.copy-trace-btn').forEach((btn) => {
            btn.addEventListener('click', (e) => {
                e.stopPropagation();
                const traceContent = decodeURIComponent(btn.dataset.trace || '');
                navigator.clipboard.writeText(traceContent).then(() => {
                    const original = btn.textContent;
                    btn.textContent = 'Copied!';
                    setTimeout(() => { btn.textContent = original; }, 1800);
                });
            });
        });
    }

    function pollMetrics () {
        if (metricsInFlight || !metricsParams) return;
        metricsInFlight = true;
        const { dataflowId, dataflowType } = metricsParams;
        const myGeneration = metricsGeneration;
        fetchDataflowLog(dataflowId, dataflowType, myGeneration).finally(() => {
            metricsInFlight = false;
        });
    }

    function startMetricsPolling (dataflowId, dataflowType, intervalMs = 5000) {
        stopMetricsPolling();
        metricsGeneration++;
        metricsParams = { dataflowId, dataflowType };
        metricsIntervalId = setInterval(pollMetrics, intervalMs);
    }

    function stopMetricsPolling () {
        if (metricsIntervalId) {
            clearInterval(metricsIntervalId);
            metricsIntervalId = null;
        }
        metricsGeneration++;
        metricsParams = null;
    }
    let activeDrawerStreamId = null;
    let activeDrawerStreamName = null;
    let activeDrawerDataflowType = null;
    let activeDrawerDataflow = null;

    function openDrawer (streamId, streamName, dataflowType) {
        activeDrawerStreamId = streamId;
        activeDrawerStreamName = streamName;
        activeDrawerDataflowType = dataflowType;

        let df = null;
        if (window.dataflow_info && Array.isArray(window.dataflow_info)) {
            df = window.dataflow_info.find(
                (d) =>
                    (streamId && d.dataflow_id === streamId) ||
                    (streamName && d.dataflow_name === streamName),
            );
        }
        activeDrawerDataflow = df || {
            dataflow_id: streamId,
            dataflow_name: streamName,
            dataflow_type: dataflowType,
        };

        const nameEl = $('#drawerStreamName');
        const idEl = $('#drawerStreamId');
        if (nameEl && streamName) nameEl.textContent = streamName;
        if (idEl && streamId) idEl.textContent = dataflowType ? `${streamId} · ${dataflowType}` : streamId;

        drawer.classList.add('open');
        drawerBack.classList.add('open');
        document.body.style.overflow = 'hidden';

        if (streamId) {
            startMetricsPolling(streamId, dataflowType, 5000);
            fetchDataflowLog(streamId, dataflowType);

            const activeTab = document.querySelector('.drawer-tabs .tab.active');
            if (activeTab && activeTab.dataset.pane === 'logs') {
                startExceptionPolling(streamId, dataflowType, 15000);
            }
        }
        document.getElementById('metricsLoading').style.display = 'flex';
    }

    function fetchDataflowLog (dataflowId, dataflowType, generation = metricsGeneration) {
        const current = activeDrawerDataflow || {};
        if (current.control_plane_contract) {
            return fetchRuntimeSnapshot(dataflowId, generation);
        }
        const csrfToken =
            window.csrfToken ||
            document.querySelector('[name="csrfmiddlewaretoken"]')?.value ||
            '';
        const payload = {
            'user-action': 'dataflow_log',
            dataflow_id: dataflowId,
            dataflow_type: dataflowType || '',
            request_info: {
                dataflow_id: dataflowId,
                dataflow_type: dataflowType || '',
            },
        };

        return fetch('/PlatformIO/StreamIngress/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': csrfToken,
            },
            body: JSON.stringify(payload),
        })
            .then((r) => r.json())
            .then((data) => {
                document.getElementById('metricsLoading').style.display = 'none';
                if (generation !== metricsGeneration) return;
                if (!data.success) {
                    // eslint-disable-next-line no-console
                    console.error(data.message || 'Failed to fetch metrics');
                    return;
                }
                renderDrawerMetrics(data.metrics);
            })
            .catch((err) => {
                document.getElementById('metricsLoading').style.display = 'none';
                // eslint-disable-next-line no-console
                console.error('Error fetching dataflow logs:', err);
            });
    }

    /* ─── stream history (History tab) ──────────────────────────────────── */
    function isNocStream (dataflowType) {
        return String(dataflowType || '').toLowerCase() === 'nocalarmstream';
    }

    function renderStockHistoryChrome () {
        const title = document.querySelector('[data-pane-content="history"] .section-head-sm');
        if (title) title.childNodes[0].textContent = 'Historical Trend ';
        const labels = document.querySelectorAll('[data-pane-content="history"] .history-chart-label');
        ['Ticks / sec', 'Processed Files / min', 'Row / sec'].forEach((label, index) => {
            if (labels[index]) labels[index].textContent = label;
        });
        const summary = document.getElementById('nocHistorySummary');
        if (summary) summary.style.display = 'none';
        $$('#historyTimeToggle button').forEach((button) => { button.style.display = ''; });
    }

    function renderNocHistory (payload, timeRange) {
        const title = document.querySelector('[data-pane-content="history"] .section-head-sm');
        if (title) title.childNodes[0].textContent = 'NOC alarm history ';
        const labels = document.querySelectorAll('[data-pane-content="history"] .history-chart-label');
        ['Source rows / sec', 'NiFi flow-files / sec', 'Normalized rows / sec'].forEach((label, index) => {
            if (labels[index]) labels[index].textContent = label;
        });
        const buttons = $$('#historyTimeToggle button');
        buttons.forEach((button) => { button.style.display = button.dataset.time === '24h' ? '' : 'none'; });
        const samples = Array.isArray(payload.samples) ? payload.samples : [];
        const series = (key) => samples.map((row) => ({
            time: row.at,
            value: Number(row[key]),
        })).filter((point) => Number.isFinite(point.value));
        const chartArgs = [
            ['historyTicksChart', 'historyTicksChartLine', 'historyTicksChartFill', 'historyTicksHoverLine', 'historyTicksHoverDot', 'historyTicksLegendValue', 'rows/s', series('source_rows_per_second')],
            ['historyFilesChart', 'historyFilesChartLine', 'historyFilesChartFill', 'historyFilesHoverLine', 'historyFilesHoverDot', 'historyFilesLegendValue', 'flow-files/s', series('nifi_flowfiles_per_second')],
            ['historyRowsChart', 'historyRowsChartLine', 'historyRowsChartFill', 'historyRowsHoverLine', 'historyRowsHoverDot', 'historyRowsLegendValue', 'rows/s', series('normalized_per_second')],
        ];
        chartArgs.forEach(([chartId, lineId, fillId, hoverLineId, hoverDotId, legendValueId, unit, values]) => renderSingleSeriesChart({
            chartId, lineId, fillId, hoverLineId, hoverDotId, legendValueId, unit,
            seriesData: values, chartWidth: 480, chartHeight: 80, chartTop: 8, chartBottom: 72,
        }));
        const summary = payload.alarm_summary?.summary || {};
        const tiles = document.getElementById('nocHistorySummaryTiles');
        if (tiles) {
            tiles.innerHTML = [
                ['Normalized', summary.normalized], ['Duplicates', summary.duplicates],
                ['Active', payload.alarm_summary?.active], ['Cleared', payload.alarm_summary?.cleared],
                ['Clusters', summary.clusters], ['Incidents', summary.incidents],
                ['DLQ', summary.dlq],
            ].map(([label, value]) => `<div class="metric-tile"><div class="l">${escapeRuntimeHtml(label)}</div><div class="v">${escapeRuntimeHtml(value ?? '—')}</div><div class="sub">cycle-scoped</div></div>`).join('');
        }
        const latest = samples.length ? samples[samples.length - 1] : {};
        const scope = document.getElementById('nocHistoryScope');
        if (scope) scope.textContent = `cycle ${payload.cycle_id || '—'} · ${samples.length} persisted samples · queue ${latest.nifi_queue ?? '—'} · normalized lag ${latest.kafka_lag ?? '—'} · ${timeRange || '24h'}`;
        const summaryPanel = document.getElementById('nocHistorySummary');
        if (summaryPanel) summaryPanel.style.display = '';
    }

    function fetchNocStreamHistory (dataflowId, timeRange) {
        const runtime = activeDrawerDataflow?.control_plane_runtime || {};
        const cycleId = runtime.cycle_id || '';
        if (!cycleId) {
            const query = new URLSearchParams({ dataflow_id: dataflowId });
            return fetch(`/PlatformIO/APIv1/ControlPlane/StreamRuntime/?${query.toString()}`)
                .then((response) => response.json())
                .then((snapshot) => {
                    if (snapshot?.cycle_id) {
                        activeDrawerDataflow = activeDrawerDataflow || {};
                        activeDrawerDataflow.control_plane_runtime = {
                            ...(activeDrawerDataflow.control_plane_runtime || {}),
                            cycle_id: snapshot.cycle_id,
                        };
                    }
                    return fetchNocStreamHistory(dataflowId, timeRange);
                });
        }
        const histLoading = document.getElementById('historyLoading');
        if (histLoading) histLoading.style.display = 'flex';
        const params = new URLSearchParams({ dataflow_id: dataflowId, cycle_id: cycleId, window: '24h' });
        return fetch(`/PlatformIO/APIv1/ControlPlane/StreamRuntime/History/?${params.toString()}`)
            .then((response) => response.json())
            .then((data) => {
                if (histLoading) histLoading.style.display = 'none';
                if (!data || data.success === false || data.available === false) {
                    const scope = document.getElementById('nocHistoryScope');
                    if (scope) scope.textContent = data?.message || data?.error || 'No persisted NOC samples yet.';
                    return;
                }
                const label = document.getElementById('history-right-label');
                if (label) label.textContent = 'last 24 hrs · NOC';
                renderNocHistory(data, '24h');
            })
            .catch((error) => {
                if (histLoading) histLoading.style.display = 'none';
                const scope = document.getElementById('nocHistoryScope');
                if (scope) scope.textContent = `NOC history unavailable: ${error.message}`;
            });
    }

    function fetchStreamHistory (dataflowId, dataflowType, timeRange) {
        timeRange = timeRange || '24h';
        if (isNocStream(dataflowType) || activeDrawerDataflow?.control_plane_contract) {
            return fetchNocStreamHistory(dataflowId, timeRange);
        }
        renderStockHistoryChrome();
        const csrfToken =
            window.csrfToken ||
            document.querySelector('[name="csrfmiddlewaretoken"]')?.value ||
            '';
        const payload = {
            'user-action': 'stream_history',
            dataflow_id: dataflowId,
            dataflow_type: dataflowType || '',
            time_range: timeRange,
        };

        const histLoading = document.getElementById('historyLoading');
        if (histLoading) histLoading.style.display = 'flex';

        return fetch('/PlatformIO/StreamIngress/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': csrfToken,
            },
            body: JSON.stringify(payload),
        })
            .then((r) => r.json())
            .then((data) => {
                if (histLoading) histLoading.style.display = 'none';
                if (!data || !data.success) {
                    // eslint-disable-next-line no-console
                    console.error(data?.message || 'Failed to fetch stream history');
                    return;
                }

                // Update time-range label
                const labelMap = { '24h': 'last 24 hrs', '7d': 'last 7 days', '15d': 'last 15 days' };
                const labelEl = document.getElementById('history-right-label');
                if (labelEl) labelEl.textContent = labelMap[timeRange] || '';

                const W = 480, H = 80, TOP = 8, BOT = 72;

                // Extract history payload from nested (data.data.history / data.history) or flat structures
                const historyObj =
                    data.data?.history ||
                    data.history ||
                    data.data ||
                    data;

                // 1. Ticks / sec (Source ingress: fyers / ticker / ticks / throughput)
                let ticksSeries = [];
                if (historyObj && typeof historyObj === 'object') {
                    ticksSeries =
                        historyObj.fyers ||
                        historyObj.fyer ||
                        historyObj.source ||
                        historyObj.ticks ||
                        historyObj.ticks_range ||
                        historyObj.throughput ||
                        historyObj.throughput_range ||
                        (dataflowType && historyObj[dataflowType]) ||
                        (dataflowType && historyObj[dataflowType.toLowerCase()]) ||
                        (dataflowType && historyObj[dataflowType.toLowerCase().replace('stream', '')]);
                }
                if (!ticksSeries || !Array.isArray(ticksSeries)) {
                    ticksSeries = data.ticks_range || data.throughput_range || [];
                }

                // 2. Processed Files / min (Transform: NiFi / flowfiles / files)
                let filesSeries = [];
                if (historyObj && typeof historyObj === 'object') {
                    filesSeries =
                        historyObj.nifi ||
                        historyObj.transform ||
                        historyObj.files ||
                        historyObj.files_range ||
                        historyObj.flowfiles ||
                        historyObj.flowfiles_range ||
                        historyObj.processed_files ||
                        historyObj.processed_files_range;
                }
                if (!filesSeries || !Array.isArray(filesSeries)) {
                    filesSeries = data.files_range || data.flowfiles_range || [];
                }

                // 3. Row / sec (Sink: ClickHouse / records / rows / lag)
                let rowsSeries = [];
                if (historyObj && typeof historyObj === 'object') {
                    rowsSeries =
                        historyObj.clickhouse ||
                        historyObj.sink ||
                        historyObj.records ||
                        historyObj.records_range ||
                        historyObj.rows ||
                        historyObj.rows_range ||
                        historyObj.lag ||
                        historyObj.lag_range;
                }
                if (!rowsSeries || !Array.isArray(rowsSeries)) {
                    rowsSeries = data.rows_range || data.records_range || data.lag_range || [];
                }

                // Chart 1 — Ticks / sec
                renderSingleSeriesChart({
                    chartId: 'historyTicksChart',
                    lineId: 'historyTicksChartLine',
                    fillId: 'historyTicksChartFill',
                    hoverLineId: 'historyTicksHoverLine',
                    hoverDotId: 'historyTicksHoverDot',
                    legendValueId: 'historyTicksLegendValue',
                    unit: 'ticks/s',
                    seriesData: ticksSeries,
                    chartWidth: W, chartHeight: H, chartTop: TOP, chartBottom: BOT,
                });

                // Chart 2 — Processed Files / min
                renderSingleSeriesChart({
                    chartId: 'historyFilesChart',
                    lineId: 'historyFilesChartLine',
                    fillId: 'historyFilesChartFill',
                    hoverLineId: 'historyFilesHoverLine',
                    hoverDotId: 'historyFilesHoverDot',
                    legendValueId: 'historyFilesLegendValue',
                    unit: 'files/min',
                    seriesData: filesSeries,
                    chartWidth: W, chartHeight: H, chartTop: TOP, chartBottom: BOT,
                });

                // Chart 3 — Row / sec
                renderSingleSeriesChart({
                    chartId: 'historyRowsChart',
                    lineId: 'historyRowsChartLine',
                    fillId: 'historyRowsChartFill',
                    hoverLineId: 'historyRowsHoverLine',
                    hoverDotId: 'historyRowsHoverDot',
                    legendValueId: 'historyRowsLegendValue',
                    unit: 'row/s',
                    seriesData: rowsSeries,
                    chartWidth: W, chartHeight: H, chartTop: TOP, chartBottom: BOT,
                });
            })
            .catch((err) => {
                if (histLoading) histLoading.style.display = 'none';
                // eslint-disable-next-line no-console
                console.error('Error fetching stream history:', err);
            });
    }

    function escapeRuntimeHtml (value) {
        return String(value === null || value === undefined ? '—' : value)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#039;');
    }

    function runtimeValue (component, key, fallback = 'unavailable') {
        if (!component || component.available === false) return fallback;
        const value = component[key];
        return value === null || value === undefined ? fallback : value;
    }

    function applyRuntimeToDataflow (snapshot) {
        if (!snapshot || !window.dataflow_info) return;
        const runtime = {
            state: snapshot.state,
            cycle_id: snapshot.cycle_id,
            run_id: snapshot.run_id,
            group_id: snapshot.nifi?.group_id,
            last_error: snapshot.last_error,
            updated_at: snapshot.updated_at,
        };
        const df = window.dataflow_info.find((item) => item.dataflow_id === snapshot.dataflow_id);
        if (df) {
            df.control_plane_runtime = {
                ...(df.control_plane_runtime || {}),
                ...runtime,
                group_id: snapshot.nifi?.group_id || df.control_plane_runtime?.group_id,
            };
        }
        if (activeDrawerDataflow && activeDrawerDataflow.dataflow_id === snapshot.dataflow_id) {
            activeDrawerDataflow.control_plane_runtime = {
                ...(activeDrawerDataflow.control_plane_runtime || {}),
                ...runtime,
                group_id: snapshot.nifi?.group_id || activeDrawerDataflow.control_plane_runtime?.group_id,
            };
        }
    }

    function setRuntimeControlState (state) {
        const normalized = String(state || '').toLowerCase();
        const start = $('#drawerStartBtn');
        const pause = $('#drawerPauseBtn');
        const resume = $('#drawerResumeBtn');
        const stop = $('#drawerStopBtn');
        if (!start || !pause || !resume || !stop) return;
        start.disabled = normalized === 'running' || normalized === 'starting';
        pause.disabled = !['running', 'starting'].includes(normalized);
        resume.disabled = !['paused', 'stopped', 'failed', 'registered'].includes(normalized);
        stop.disabled = !['running', 'starting', 'paused'].includes(normalized);
    }

    function runtimeNumber (value) {
        const parsed = Number(value);
        return Number.isFinite(parsed) ? parsed : null;
    }

    function topicWatermarkTotal (kafka, topicKey = 'raw') {
        const partitions = kafka?.topics?.[topicKey]?.partitions;
        if (Array.isArray(partitions)) {
            return partitions.reduce((sum, row) => {
                const high = runtimeNumber(row?.high_watermark);
                return sum + (high === null ? 0 : high);
            }, 0);
        }
        const highWatermarks = kafka?.high_watermarks || {};
        const topicName = topicKey === 'normalized'
            ? (kafka?.topics?.normalized?.name || 'noc.alarm.normalized.v1')
            : (kafka?.topics?.raw?.name || kafka?.topic || 'noc.alarm.raw.v1');
        const watermarks = highWatermarks[topicName] || {};
        return Object.values(watermarks).reduce((sum, value) => sum + (runtimeNumber(value) || 0), 0);
    }

    function normalizerLag (kafka) {
        const group = (kafka?.groups || []).find((item) => ['normalizer', 'correlator'].includes(item?.stage));
        if (!group) return null;
        const rows = (group.offsets || []).map((item) => runtimeNumber(item?.lag));
        // Kafka can expose a lag for only the partitions that are currently
        // producing.  Summing the known partitions keeps the MVP useful while
        // a newly-created group is still catching up on the others.
        const known = rows.filter((value) => value !== null);
        return known.length
            ? known.reduce((sum, value) => sum + value, 0)
            : runtimeNumber(group.lag);
    }

    function processorCumulative (nifi) {
        const stats = nifi?.processor_stats || nifi?.processors?.stats;
        if (stats && runtimeNumber(stats.flow_files_out) !== null) {
            return runtimeNumber(stats.flow_files_out);
        }
        if (runtimeNumber(nifi?.processors?.flow_files_out) !== null) {
            return runtimeNumber(nifi.processors.flow_files_out);
        }
        return null;
    }

    function normalizedRecordCount (postgres) {
        const counts = postgres?.cycle_counts || postgres?.counts || {};
        return runtimeNumber(
            counts.normalized_events ?? postgres?.rows ?? postgres?.normalized_events,
        );
    }

    function appendRuntimeSample (dataflowId, snapshot, topicKey = 'raw') {
        const key = dataflowId || snapshot?.dataflow_id || 'runtime';
        const now = Date.now();
        const state = runtimeSamples.get(key) || { samples: [], previous: null };
        const topicWatermark = topicWatermarkTotal(snapshot?.kafka || {}, topicKey);
        const flowFiles = processorCumulative(snapshot?.nifi || {});
        const records = normalizedRecordCount(snapshot?.postgresql || {});
        const previous = state.previous;
        const elapsed = previous ? Math.max((now - previous.timestamp) / 1000, 0.1) : null;
        const deltaRate = (current, prior) => {
            if (!elapsed || current === null || prior === null) return 0;
            // NiFi's aggregateSnapshot is a rolling observer counter and can
            // reset when its reporting window rolls over.  Treat a reset as a
            // fresh baseline instead of drawing a misleading zero-throughput
            // gap in the live chart.
            const delta = current >= prior ? current - prior : current;
            return Math.max(0, delta) / elapsed;
        };
        const sample = {
            timestamp: now,
            time: new Date(now).toLocaleTimeString(),
            throughput: deltaRate(topicWatermark, previous?.topicWatermark ?? null),
            flowfiles: deltaRate(flowFiles, previous?.flowFiles ?? null),
            records: deltaRate(records, previous?.records ?? null),
        };
        state.samples.push(sample);
        state.samples = state.samples.slice(-120);
        state.previous = { timestamp: now, topicWatermark, flowFiles, records };
        runtimeSamples.set(key, state);
        return { ...sample, history: state.samples };
    }

    function renderLiveLogs (dataflowId, snapshot, sample) {
        // Logs pane is strictly handled by the Exception Aggregator engine (renderExceptions)
    }

    function renderRuntimeSnapshot (snapshot) {
        if (!snapshot) return;
        const status = document.getElementById('drawerStatusText');
        if (status) status.textContent = snapshot.state || 'unknown';
        const source = snapshot.source || {};
        const replay = snapshot.replay || {};
        const simulator = snapshot.simulator || {};
        const kafka = snapshot.kafka || {};
        const nifi = snapshot.nifi || {};
        const postgres = snapshot.postgresql || {};
        const alarmSummary = snapshot.alarm_summary || {};
        const isNoc = isNocStream(activeDrawerDataflowType || activeDrawerDataflow?.dataflow_type)
            || Boolean(activeDrawerDataflow?.control_plane_contract);
        const normalizedTopic = kafka.topics?.normalized?.name || 'noc.alarm.normalized.v1';
        const topic = isNoc
            ? normalizedTopic
            : (kafka.topic || snapshot.topic || 'noc.alarm.raw.v1');
        const eps = replay.events_per_second;
        const lag = normalizerLag(kafka);
        const queued = nifi.queue?.queued_count ?? nifi.queued_flowfiles;
        const cycle = snapshot.cycle_id || 'not started';
        const sample = appendRuntimeSample(
            activeDrawerStreamId || snapshot.dataflow_id,
            snapshot,
            isNoc ? 'normalized' : 'raw',
        );
        const processorCount = nifi.processors?.count ?? (Array.isArray(nifi.processors) ? nifi.processors.length : 0);
        const records = normalizedRecordCount(postgres);
        const incidents = runtimeNumber(postgres.cycle_counts?.incidents ?? postgres.incidents);
        const measuredThroughput = sample.throughput;
        const measuredFlowFiles = sample.flowfiles;
        const measuredRecords = sample.records;

        const sourceName = document.getElementById('source-name');
        const sourceDesc = document.getElementById('source-desc');
        const sourceRate = document.getElementById('source-rate');
        const transformName = document.getElementById('transform-name');
        const transformDesc = document.getElementById('transform-desc');
        const transformRate = document.getElementById('transform-rate');
        const sinkName = document.getElementById('sink-name');
        const sinkDesc = document.getElementById('sink-desc');
        const sinkRate = document.getElementById('sink-rate');
        if (sourceName) sourceName.textContent = source.type || 'source';
        if (sourceDesc) sourceDesc.textContent = source.path || source.remote_path || 'configured source';
        if (sourceRate) sourceRate.textContent = eps ? `${eps} events/s` : 'unavailable';
        if (transformName) transformName.textContent = 'NiFi';
        if (transformDesc) transformDesc.textContent = nifi.available === false ? 'unavailable' : (nifi.flow_name || 'flow state');
        if (transformRate) transformRate.textContent = `${processorCount} processors · ${queued ?? 0} queued`;
        if (sinkName) sinkName.textContent = topic;
        if (sinkDesc) sinkDesc.textContent = kafka.available === false
            ? 'Kafka observer unavailable'
            : (isNoc ? 'normalized topic · PostgreSQL outbox' : 'raw alarm topic');
        if (sinkRate) sinkRate.textContent = lag === null ? 'starting' : `${lag} lag`;

        const currentThroughput = document.getElementById('currentThroughputValue');
        const currentThroughputSub = document.getElementById('currentThroughputSub');
        const currentFlowFiles = document.getElementById('currentFlowFilesValue');
        const currentFlowFilesSub = document.getElementById('currentFlowFilesSub');
        const currentRecords = document.getElementById('currentRecordsValue');
        const currentRecordsSub = document.getElementById('currentRecordsSub');
        if (currentThroughput) currentThroughput.innerHTML = `${formatMetricNumber(measuredThroughput)}<span style="font-size:11px; color:var(--ink-3);"> ${isNoc ? 'normalized events/s' : 'events/s'}</span>`;
        if (currentThroughputSub) currentThroughputSub.textContent = `measured · target ${eps || '—'} · cycle ${cycle}`;
        if (currentFlowFiles) currentFlowFiles.innerHTML = `${formatMetricNumber(measuredFlowFiles)}<span style="font-size:11px; color:var(--ink-3);"> Flow Files/s</span>`;
        if (currentFlowFilesSub) currentFlowFilesSub.textContent = `NiFi queue ${queued ?? 0} · ${processorCount} processors`;
        if (currentRecords) currentRecords.innerHTML = `${formatMetricNumber(measuredRecords)}<span style="font-size:11px; color:var(--ink-3);"> ${isNoc ? 'normalized rows/s' : 'records/s'}</span>`;
        if (currentRecordsSub) currentRecordsSub.textContent = postgres.available === false ? 'PostgreSQL observer unavailable' : `${records ?? 0} normalized · ${incidents ?? 0} incidents`;

        ['throughputLegendValue', 'flowfilesLegendValue', 'recordsLegendValue'].forEach((id) => {
            const element = document.getElementById(id);
            if (element) element.textContent = '(live snapshot)';
        });
        renderSingleSeriesChart({
            chartId: 'throughputChart', lineId: 'throughputChartLine', fillId: 'throughputChartFill',
            hoverLineId: 'throughputHoverLine', hoverDotId: 'throughputHoverDot', legendValueId: 'throughputLegendValue',
            unit: isNoc ? 'normalized events/s' : 'events/s', seriesData: sample.history.map((item) => ({ time: item.time, value: item.throughput })),
        });
        renderSingleSeriesChart({
            chartId: 'flowfilesChart', lineId: 'flowfilesChartLine', fillId: 'flowfilesChartFill',
            hoverLineId: 'flowfilesHoverLine', hoverDotId: 'flowfilesHoverDot', legendValueId: 'flowfilesLegendValue',
            unit: 'Flow Files/s', seriesData: sample.history.map((item) => ({ time: item.time, value: item.flowfiles })),
        });
        renderSingleSeriesChart({
            chartId: 'recordsChart', lineId: 'recordsChartLine', fillId: 'recordsChartFill',
            hoverLineId: 'recordsHoverLine', hoverDotId: 'recordsHoverDot', legendValueId: 'recordsLegendValue',
            unit: isNoc ? 'normalized rows/s' : 'records/s', seriesData: sample.history.map((item) => ({ time: item.time, value: item.records })),
        });

        const chartLabels = document.querySelectorAll('[data-pane-content="live"] .charts-row .section-head-sm');
        (isNoc ? ['Normalized Kafka events', 'NiFi flow-files', 'Normalized rows'] : ['Throughput', 'Flow Files', 'Records']).forEach((label, index) => {
            if (chartLabels[index]) chartLabels[index].childNodes[0].textContent = `${label} `;
        });

        const summary = document.getElementById('runtimeSummary');
        if (summary) {
            const observer = snapshot.observer?.available ? 'live' : 'unavailable';
            summary.innerHTML = [
                `<div><strong>State:</strong> ${escapeRuntimeHtml(snapshot.state)} · <strong>Cycle:</strong> ${escapeRuntimeHtml(cycle)} · <strong>Observer:</strong> ${observer}</div>`,
                `<div><strong>Simulator:</strong> ${escapeRuntimeHtml(isNoc ? `${simulator.kind || 'replay'} · ${simulator.state || 'unknown'}` : 'not applicable')} · <strong>Kafka:</strong> ${escapeRuntimeHtml(kafka.available === false ? 'unavailable' : `${topic} · ${isNoc ? 'correlator lag' : 'normalizer lag'} ${lag ?? 'starting'} · ${isNoc ? 'normalized' : 'raw'} offset ${topicWatermarkTotal(kafka, isNoc ? 'normalized' : 'raw')}`)} · <strong>NiFi:</strong> ${escapeRuntimeHtml(nifi.available === false ? 'unavailable' : `${nifi.flow_name || 'flow'} · queue ${queued ?? 0} · processors ${processorCount}`)}</div>`,
                `<div><strong>PostgreSQL:</strong> ${escapeRuntimeHtml(postgres.available === false ? 'unavailable' : `${records ?? 0} normalized · ${incidents ?? 0} incidents`)} · <strong>DLQ:</strong> ${escapeRuntimeHtml(kafka.topics?.dlq?.retained_messages ?? 0)} · <strong>Prometheus:</strong> ${escapeRuntimeHtml(snapshot.prometheus?.available === false ? 'unavailable' : 'up')}</div>`,
                isNoc && alarmSummary.available !== false && alarmSummary.summary ? `<div><strong>Alarm cycle:</strong> ${escapeRuntimeHtml(`active ${alarmSummary.active ?? 0} · cleared ${alarmSummary.cleared ?? 0} · duplicates ${alarmSummary.summary.duplicates ?? '—'} · clusters ${alarmSummary.summary.clusters ?? 0} · incidents ${alarmSummary.summary.incidents ?? incidents ?? 0}`)}</div>` : '',
                snapshot.last_error ? `<div style="color:var(--err);"><strong>Error:</strong> ${escapeRuntimeHtml(snapshot.last_error)}</div>` : '',
            ].join('');
        }
        const visibility = document.getElementById('componentVisibility');
        if (visibility) {
            const card = (name, component, detail) => {
                const available = component && component.available !== false;
                return `<div style="border:1px solid var(--line); border-radius:6px; padding:8px; background:var(--paper);"><div style="font-weight:600; color:var(--ink);">${name} <span style="color:${available ? 'var(--ok)' : 'var(--err)'};">${available ? '● live' : '● unavailable'}</span></div><div style="margin-top:4px; color:var(--ink-3); word-break:break-word;">${escapeRuntimeHtml(detail)}</div></div>`;
            };
            visibility.innerHTML = [
                ...(isNoc ? [card('Simulator', simulator, `${simulator.kind || 'replay'} · ${simulator.state || 'unknown'} · ${simulator.events_per_second || '—'} events/s`)] : []),
                card('Kafka', kafka, kafka.available === false ? (kafka.error || 'observer unavailable') : `topic ${topic} · lag ${lag ?? '—'} · offsets ${kafka.high_watermarks ? JSON.stringify(kafka.high_watermarks) : '—'}`),
                card('NiFi', nifi, nifi.available === false ? (nifi.error || 'REST unavailable') : `flow ${nifi.flow_name || '—'} · queue ${queued ?? 0} · processors ${processorCount}`),
                card('PostgreSQL', postgres, postgres.available === false ? (postgres.error || 'cycle observer unavailable') : `${records ?? 0} normalized · ${incidents ?? 0} incidents`),
                card('Prometheus', snapshot.prometheus, snapshot.prometheus?.available === false ? (snapshot.prometheus?.error || 'target observer unavailable') : JSON.stringify(snapshot.prometheus.targets || snapshot.prometheus.metrics || {})),
            ].join('');
        }
        renderLiveLogs(activeDrawerStreamId || snapshot.dataflow_id, snapshot, sample);
        setRuntimeControlState(snapshot.state);
        applyRuntimeToDataflow(snapshot);

        if (snapshot.dataflow_id || activeDrawerStreamId) {
            const sid = activeDrawerStreamId || snapshot.dataflow_id;
            const currentTput = (measuredThroughput && measuredThroughput > 0) ? measuredThroughput : (Number(eps) || 0);
            if (typeof streamThroughputMap !== 'undefined') {
                streamThroughputMap.set(sid, currentTput);
                if (typeof updateHeaderThroughputUI === 'function') updateHeaderThroughputUI();
            }
        }

        const refresh = document.getElementById('last-refresh');
        if (refresh) refresh.textContent = `Live · ${new Date().toLocaleTimeString()}`;
    }

    function fetchRuntimeSnapshot (dataflowId, generation = metricsGeneration) {
        return fetch(`/PlatformIO/APIv1/ControlPlane/StreamRuntime/?dataflow_id=${encodeURIComponent(dataflowId)}`, {
            headers: { Accept: 'application/json' },
        })
            .then((response) => response.json())
            .then((snapshot) => {
                const loading = document.getElementById('metricsLoading');
                if (loading) loading.style.display = 'none';
                if (generation !== metricsGeneration) return snapshot;
                if (!snapshot.success) throw new Error(snapshot.message || 'Unable to retrieve stream runtime');
                renderRuntimeSnapshot(snapshot);
                return snapshot;
            })
            .catch((error) => {
                const loading = document.getElementById('metricsLoading');
                if (loading) loading.style.display = 'none';
                const summary = document.getElementById('runtimeSummary');
                if (summary) summary.textContent = `Runtime unavailable: ${error.message}`;
                throw error;
            });
    }

    async function controlRuntime (dataflowId, action) {
        const response = await fetch('/PlatformIO/APIv1/ControlPlane/StreamRuntime/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': window.csrfToken || '',
            },
            body: JSON.stringify({ dataflow_id: dataflowId, action }),
        });
        const result = await response.json();
        if (!response.ok || result.success === false) {
            throw new Error(result.message || `Unable to ${action} stream`);
        }
        if (result.dataflow_id && result.deleted) return result;
        renderRuntimeSnapshot(result);
        applyRuntimeToDataflow(result);
        renderDataflowCards();
        return result;
    }

    function updateText (id, text, themeColor) {
        const el = document.getElementById(id);
        if (!el) return;

        if (el.textContent !== text) {
            el.textContent = text;
        }

        el.style.setProperty('--glow-color', `var(${themeColor})`);
        el.style.setProperty('--glow-border-color', `var(${themeColor})`);

        el.classList.remove('value-glow');
        void el.offsetWidth;
        el.classList.add('value-glow');
    }

    function formatMetricNumber (value, decimals = 2) {
        if (!Number.isFinite(value)) return 'â€”';

        return new Intl.NumberFormat(undefined, {
            maximumFractionDigits: decimals,
        }).format(value);
    }

    function getChartPoints (series) {
        if (!Array.isArray(series)) return [];

        return series
            .map((point, index) => {
                const value = Array.isArray(point)
                    ? Number(point[1])
                    : Number(point && point.value);
                const time = Array.isArray(point)
                    ? point[0]
                    : point && (point.time || point.timestamp || point.label);

                return { time: time || '', value, index };
            })
            .filter((point) => Number.isFinite(point.value));
    }

    function getChartValueMeta (points) {
        const values = points.map((point) => point.value);
        const min = Math.min(...values);
        const max = Math.max(...values);

        return {
            min,
            range: max - min,
            maxIndex: Math.max(points.length - 1, 1),
        };
    }

    function getChartPointPosition (point, meta, chartWidth = 480, chartTop = 8, chartBottom = 72) {
        const ratio = !meta || meta.range === 0
            ? (meta && meta.max === 0 ? 0 : 0.5)
            : (point.value - meta.min) / meta.range;
        const maxIdx = Math.max(meta ? meta.maxIndex : 1, 1);

        return {
            x: (point.index / maxIdx) * chartWidth,
            y: chartBottom - ratio * (chartBottom - chartTop),
        };
    }

    function buildChartLinePath (points, meta, chartWidth = 480, chartTop = 8, chartBottom = 72) {
        if (!points || points.length === 0) return '';
        if (points.length === 1) {
            const pos = getChartPointPosition(points[0], meta, chartWidth, chartTop, chartBottom);
            return `M0.00 ${pos.y.toFixed(2)} L${chartWidth.toFixed(2)} ${pos.y.toFixed(2)}`;
        }
        return points
            .map((value, index) => {
                const position = getChartPointPosition(value, meta, chartWidth, chartTop, chartBottom);
                const command = index === 0 ? 'M' : 'L';

                return `${command}${position.x.toFixed(2)} ${position.y.toFixed(2)}`;
            })
            .join(' ');
    }

    function renderCurrentThroughputLag (throughputPoints) {
        const throughputPoint = throughputPoints[throughputPoints.length - 1];
        const throughputValue = document.getElementById('currentThroughputValue');
        const throughputSub = document.getElementById('currentThroughputSub');

        if (throughputValue) {
            if (throughputPoint) {
                throughputValue.innerHTML =
                    `${formatMetricNumber(throughputPoint.value)}<span style="font-size:11px; color:var(--ink-3);"> ticks/s</span>`;
            } else {
                throughputValue.innerHTML = '—<span style="font-size:11px; color:var(--ink-3);"> ticks/s</span>';
            }
        }

        if (throughputSub) {
            if (throughputPoints.length > 0) {
                const total = throughputPoints.reduce((sum, point) => sum + point.value, 0);

                throughputSub.textContent =
                    `10-min avg: ${formatMetricNumber(total / throughputPoints.length)} ticks/s`;
            } else {
                throughputSub.textContent = 'No throughput data';
            }
        }
    }

    function renderCurrentRecords (clickhouseMetrics) {
        const recordsValue = document.getElementById('currentRecordsValue') || document.getElementById('currentLagValue');
        const recordsSub = document.getElementById('currentRecordsSub') || document.getElementById('currentLagSub');

        if (!clickhouseMetrics) return;

        const rawVal = clickhouseMetrics.trades_rows_inserted_5m ?? clickhouseMetrics.rows_per_sec;
        const val = Number.isFinite(Number(rawVal)) ? Number(rawVal) : 0;

        if (recordsValue) {
            recordsValue.innerHTML = `<span style="color:var(--warn);">${formatMetricNumber(val)}</span><span style="font-size:11px; color:var(--ink-3);"> Row/s</span>`;
        }
        if (recordsSub) {
            recordsSub.textContent = `ClickHouse: growing at ${formatMetricNumber(val)} Row/s`;
        }
    }

    function renderCurrentFlowFiles (nifiMetrics) {
        const ffValue = document.getElementById('currentFlowFilesValue');
        const ffSub = document.getElementById('currentFlowFilesSub');
        if (!nifiMetrics) return;

        const val = nifiMetrics.processed_flow_files_min ?? 0;
        const numVal = Number.isFinite(Number(val)) ? Number(val) : 0;
        if (ffValue) {
            ffValue.innerHTML = `<span style="color:#0284c7;">${formatMetricNumber(numVal)}</span><span style="font-size:11px; color:var(--ink-3);"> Flow Files/min</span>`;
        }
        if (ffSub) {
            ffSub.textContent = `NiFi: ${formatMetricNumber(numVal)} Flow Files/min`;
        }
    }

    function renderSingleSeriesChart ({
        chartId,
        lineId,
        fillId,
        hoverLineId,
        hoverDotId,
        legendValueId,
        unit,
        seriesData,
        chartWidth = 480,
        chartHeight = 80,
        chartTop = 8,
        chartBottom = 72,
    }) {
        const chart = document.getElementById(chartId);
        const line = document.getElementById(lineId);
        const fill = document.getElementById(fillId);
        const hoverLine = document.getElementById(hoverLineId);
        const hoverDot = document.getElementById(hoverDotId);
        const legendValue = document.getElementById(legendValueId);

        if (!chart) return;

        const points = getChartPoints(seriesData);
        const meta = points.length > 0 ? getChartValueMeta(points) : null;

        function getPointPosition (point) {
            return getChartPointPosition(point, meta, chartWidth, chartTop, chartBottom);
        }

        function setLegend (point) {
            if (!legendValue) return;
            if (point && Number.isFinite(point.value)) {
                legendValue.textContent = `${formatMetricNumber(point.value)} ${unit}${point.time ? ` @ ${point.time}` : ''}`;
            } else {
                legendValue.textContent = `0 ${unit}`;
            }
        }

        if (line && fill) {
            if (meta && points.length > 0) {
                const path = buildChartLinePath(points, meta, chartWidth, chartTop, chartBottom);
                line.setAttribute('d', path);
                fill.setAttribute('d', `${path} L${chartWidth} ${chartHeight} L0 ${chartHeight} Z`);
            } else {
                line.setAttribute('d', '');
                fill.setAttribute('d', '');
            }
        }

        setLegend(points.at(-1));

        chart._points = points;
        chart._getPointPos = getPointPosition;
        chart._setLegend = setLegend;

        if (chart.dataset.hoverBound !== 'true') {
            chart.dataset.hoverBound = 'true';
            chart.addEventListener('mousemove', (event) => {
                const curPts = chart._points;
                if (!curPts || curPts.length === 0) return;
                const rect = chart.getBoundingClientRect();
                const ratio = Math.min(Math.max((event.clientX - rect.left) / rect.width, 0), 1);
                const index = Math.round(ratio * Math.max(curPts.length - 1, 0));
                const pt = curPts[index] || curPts.at(-1);
                if (!pt) return;
                const pos = chart._getPointPos(pt);

                if (hoverLine) {
                    hoverLine.setAttribute('x1', pos.x.toFixed(2));
                    hoverLine.setAttribute('x2', pos.x.toFixed(2));
                    hoverLine.classList.add('active');
                }
                if (hoverDot) {
                    hoverDot.setAttribute('cx', pos.x.toFixed(2));
                    hoverDot.setAttribute('cy', pos.y.toFixed(2));
                    hoverDot.classList.add('active');
                }
                chart._setLegend(pt);
            });

            chart.addEventListener('mouseleave', () => {
                if (hoverLine) hoverLine.classList.remove('active');
                if (hoverDot) hoverDot.classList.remove('active');
                const curPts = chart._points;
                if (curPts) chart._setLegend(curPts.at(-1));
            });
        }
    }

    function renderThroughputLagChart (throughputLag) {
        if (!throughputLag) return;

        const throughputRange = throughputLag.throughput_range || [];
        const flowfilesRange = throughputLag.flowfiles_range || throughputLag.processed_files_range || [];
        const recordsRange = throughputLag.records_range || throughputLag.lag_range || [];

        // 1. Throughput Chart (ticks/s)
        renderSingleSeriesChart({
            chartId: 'throughputChart',
            lineId: 'throughputChartLine',
            fillId: 'throughputChartFill',
            hoverLineId: 'throughputHoverLine',
            hoverDotId: 'throughputHoverDot',
            legendValueId: 'throughputLegendValue',
            unit: 'ticks/s',
            seriesData: throughputRange,
        });

        // 2. Flow Files Chart (Flow Files/min)
        renderSingleSeriesChart({
            chartId: 'flowfilesChart',
            lineId: 'flowfilesChartLine',
            fillId: 'flowfilesChartFill',
            hoverLineId: 'flowfilesHoverLine',
            hoverDotId: 'flowfilesHoverDot',
            legendValueId: 'flowfilesLegendValue',
            unit: 'Flow Files/min',
            seriesData: flowfilesRange,
        });

        // 3. Records Chart (Row/s)
        renderSingleSeriesChart({
            chartId: 'recordsChart',
            lineId: 'recordsChartLine',
            fillId: 'recordsChartFill',
            hoverLineId: 'recordsHoverLine',
            hoverDotId: 'recordsHoverDot',
            legendValueId: 'recordsLegendValue',
            unit: 'Row/s',
            seriesData: recordsRange,
        });

        renderCurrentThroughputLag(getChartPoints(throughputRange));
    }

    function renderDrawerMetrics (data) {
        if (!data) return;
        const metrics = data.metrics || data; // handles wrapped or unwrapped
        if (!metrics.entity || !metrics.fyer || !metrics.nifi || !metrics.clickhouse) {
            // eslint-disable-next-line no-console
            console.warn('renderDrawerMetrics: incomplete payload', metrics);
            return;
        }
        const fmt = (v) => (v === null || v === undefined ? '—' : v);

        document.getElementById('last-refresh').textContent = 'Last refreshed just now';
        const statusText = document.getElementById('drawerStatusText');
        if (statusText) {
            statusText.textContent = metrics.status === 'Healthy' ? 'Running' : (metrics.status || 'Running');
        }

        document.getElementById('source-name').textContent = fmt(metrics.entity[0]);
        document.getElementById('source-desc').textContent = fmt(metrics.fyer.desc);
        document.getElementById('source-rate').textContent = fmt(metrics.fyer.ticks_per_sec) + ' ticks/s';

        //        document.getElementById('source-arrow-rate').textContent =fmt(metrics.fyer.execute_process_output_mb_per_sec) + ' Mb/s';
        //        document.getElementById('source-arrow-rate-below').textContent =fmt(metrics.fyer.ticks_per_sec) + ' ticks/s';

        document.getElementById('transform-name').textContent = fmt(metrics.entity[1]);
        document.getElementById('transform-desc').textContent = fmt(metrics.nifi.desc);
        document.getElementById('transform-rate').textContent = fmt(metrics.nifi.processed_flow_files_min) + ' Flow Files';
        //        document.getElementById('transform-arrow-rate').textContent = fmt(metrics.nifi.invoke_http_mb_ps) +  ' Mb/s';
        //        document.getElementById('transform-arrow-rate-below').textContent = fmt(metrics.clickhouse.trades_rows_inserted_5m) +  ' Row/s';

        document.getElementById('sink-name').textContent = fmt(metrics.entity[2]);
        document.getElementById('sink-desc').textContent = fmt(metrics.clickhouse.desc);
        document.getElementById('sink-rate').textContent = fmt(metrics.clickhouse.trades_rows_inserted_5m) + ' Row/s';

        // Source (navy)
        updateText(
            'source-arrow-rate',
            fmt(metrics.fyer.execute_process_output_mb_per_sec) + ' Mb/s',
            '--navy'
        );

        updateText(
            'source-arrow-rate-below',
            fmt(metrics.fyer.ticks_per_sec) + ' ticks/s',
            '--navy'
        );

        // Transform (warm)
        updateText(
            'transform-arrow-rate',
            fmt(metrics.nifi.invoke_http_mb_ps) + ' Mb/s',
            '--warm'
        );

        updateText(
            'transform-arrow-rate-below',
            fmt(metrics.clickhouse.trades_rows_inserted_5m) + ' Row/s',
            '--warm'
        );

        renderThroughputLagChart(metrics.throughput_lag);
        renderCurrentFlowFiles(metrics.nifi);
        renderCurrentRecords(metrics.clickhouse);

        if (activeDrawerStreamId && metrics && typeof extractThroughputFromMetrics === 'function') {
            const tput = extractThroughputFromMetrics(metrics, activeDrawerDataflowType);
            if (typeof streamThroughputMap !== 'undefined') {
                streamThroughputMap.set(activeDrawerStreamId, tput);
                if (typeof updateHeaderThroughputUI === 'function') updateHeaderThroughputUI();
            }
        }
    }
    // eslint-disable-next-line no-unused-vars
    function renderDrawerLogs (data) {
        const container = $('#drawerLogStream');
        if (!container) return;

        if (!data || (typeof data === 'object' && Object.keys(data).length === 0)) {
            container.innerHTML = `
                <div class="log-line">
                    <span class="t">${new Date().toLocaleTimeString()}</span>
                    <span class="lvl lvl-info">INFO</span>
                    <span class="msg">No log entries recorded for this stream yet.</span>
                </div>
            `;
            return;
        }

        let html = '';
        const items = Array.isArray(data) ? data : Object.values(data);
        items.forEach((item) => {
            const status = (item.Status || item.status || 'INFO').toUpperCase();
            let lvlClass = 'lvl-info';
            if (status.includes('ERR') || status.includes('FAIL')) lvlClass = 'lvl-err';
            else if (status.includes('WARN')) lvlClass = 'lvl-warn';
            else if (status.includes('OK') || status.includes('SUCCESS')) lvlClass = 'lvl-ok';

            const timeStr = item.Time || item.Date || '';
            const msgStr = item.Msg || item.msg || item.log_info || (typeof item === 'string' ? item : JSON.stringify(item));

            html += `
                <div class="log-line">
                    <span class="t">${timeStr}</span>
                    <span class="lvl ${lvlClass}">${status}</span>
                    <span class="msg">${msgStr}</span>
                </div>
            `;
        });
        container.innerHTML = html;
    }
    //   function renderDrawerMetrics(metrics) {
    //    const container = $('#drawerLogStream');
    //    if (!container) return;
    //
    //    const fmt = (value, suffix = '') => {
    //        if (value === null || value === undefined) return '—';
    //        return `${value}${suffix}`;
    //    };
    //
    //    const nifi = metrics.nifi || {};
    //    const clickhouse = metrics.clickhouse || {};
    //    const system = metrics.system || {};
    //
    //    let html = `
    //        <div class="metric-section">
    //            <h6>Dataflow</h6>
    //            <div class="metric-row">
    //                <span>Status</span>
    //                <span>${metrics.status || 'Unknown'}</span>
    //            </div>
    //            <div class="metric-row">
    //                <span>Process Group</span>
    //                <span>${metrics.pg_id || '—'}</span>
    //            </div>
    //        </div>
    //
    //        <div class="metric-section">
    //            <h6>NiFi</h6>
    //            <div class="metric-row">
    //                <span>Throughput</span>
    //                <span>${fmt(nifi.throughput_bytes_sec, ' B/s')}</span>
    //            </div>
    //            <div class="metric-row">
    //                <span>Queued Files</span>
    //                <span>${fmt(nifi.queued_files)}</span>
    //            </div>
    //            <div class="metric-row">
    //                <span>ExecuteProcess Rate</span>
    //                <span>${fmt(nifi.execute_process_flowfiles_per_sec, ' flow/s')}</span>
    //            </div>
    //            <div class="metric-row">
    //                <span>InvokeHTTP Rate</span>
    //                <span>${fmt(nifi.invoke_http_flowfiles_sent_per_sec, ' flow/s')}</span>
    //            </div>
    //        </div>
    //
    //        <div class="metric-section">
    //            <h6>ClickHouse</h6>
    //            <div class="metric-row">
    //                <span>Rows/sec</span>
    //                <span>${fmt(clickhouse.rows_per_sec)}</span>
    //            </div>
    //            <div class="metric-row">
    //                <span>Memory</span>
    //                <span>${fmt(clickhouse.memory_mb, ' MB')}</span>
    //            </div>
    //            <div class="metric-row">
    //                <span>OHLCV Rows</span>
    //                <span>${fmt(clickhouse.ohlcv_rows)}</span>
    //            </div>
    //            <div class="metric-row">
    //                <span>Trades Rows</span>
    //                <span>${fmt(clickhouse.trades_rows)}</span>
    //            </div>
    //        </div>
    //
    //        <div class="metric-section">
    //            <h6>System</h6>
    //            <div class="metric-row">
    //                <span>RAM Usage</span>
    //                <span>${fmt(system.ram_usage_pct, '%')}</span>
    //            </div>
    //        </div>
    //    `;
    //
    //    const processors = metrics.processors || {};
    //
    //    html += `
    //        <div class="metric-section">
    //            <h6>Processors</h6>
    //    `;
    //
    //    Object.entries(processors).forEach(([name, proc]) => {
    //        html += `
    //            <div class="processor-card">
    //                <div><strong>${name}</strong></div>
    //
    //                <div class="metric-row">
    //                    <span>In Rate</span>
    //                    <span>${fmt(proc.flowfiles_in_rate)}</span>
    //                </div>
    //
    //                <div class="metric-row">
    //                    <span>Out Rate</span>
    //                    <span>${fmt(proc.flowfiles_out_rate)}</span>
    //                </div>
    //
    //                <div class="metric-row">
    //                    <span>Queued</span>
    //                    <span>${fmt(proc.flowfiles_queued)}</span>
    //                </div>
    //
    //                <div class="metric-row">
    //                    <span>Bytes Written</span>
    //                    <span>${fmt(proc.bytes_written_rate)}</span>
    //                </div>
    //
    //                <hr>
    //            </div>
    //        `;
    //    });
    //
    //    html += `</div>`;
    //
    //    container.innerHTML = html;
    //}
    function closeDrawer () {
        drawer.classList.remove('open');
        drawerBack.classList.remove('open');
        document.body.style.overflow = '';
        stopMetricsPolling();
        stopExceptionPolling();
    }

    if (drawerClose) drawerClose.addEventListener('click', closeDrawer);
    if (drawerBack) drawerBack.addEventListener('click', closeDrawer);

    const drawerCloseFootBtn = $('#drawerCloseFootBtn');
    if (drawerCloseFootBtn) drawerCloseFootBtn.addEventListener('click', closeDrawer);

    const drawerEditBtn = $('#drawerEditBtn');
    if (drawerEditBtn) {
        drawerEditBtn.addEventListener('click', () => {
            const df = activeDrawerDataflow ||
                (window.dataflow_info &&
                    window.dataflow_info.find(
                        (d) =>
                            (activeDrawerStreamId && d.dataflow_id === activeDrawerStreamId) ||
                            (activeDrawerStreamName && d.dataflow_name === activeDrawerStreamName),
                    )) || {
                dataflow_id: activeDrawerStreamId,
                dataflow_name: activeDrawerStreamName,
                dataflow_type: activeDrawerDataflowType,
            };
            closeDrawer();
            if (df && typeof openCrudEdit === 'function') {
                setTimeout(() => openCrudEdit(df), 150);
            }
        });
    }

    const drawerDeleteBtn = $('#drawerDeleteBtn');
    if (drawerDeleteBtn) {
        drawerDeleteBtn.addEventListener('click', () => {
            const id = activeDrawerStreamId || (activeDrawerDataflow && activeDrawerDataflow.dataflow_id);
            const name = activeDrawerStreamName || (activeDrawerDataflow && activeDrawerDataflow.dataflow_name);
            closeDrawer();
            if ((id || name) && typeof openDeleteDialog === 'function') {
                setTimeout(() => openDeleteDialog(id, name), 150);
            }
        });
    }

    const runtimeButtons = {
        drawerStartBtn: 'start',
        drawerPauseBtn: 'pause',
        drawerResumeBtn: 'resume',
        drawerStopBtn: 'stop',
    };
    Object.entries(runtimeButtons).forEach(([id, action]) => {
        const button = document.getElementById(id);
        if (!button) return;
        button.addEventListener('click', async () => {
            const idValue = activeDrawerStreamId || activeDrawerDataflow?.dataflow_id;
            if (!idValue) return;
            button.disabled = true;
            const labelSpan = button.querySelector('span');
            const originalText = labelSpan ? labelSpan.textContent : button.textContent;
            if (labelSpan) {
                labelSpan.textContent = `${action}…`;
            } else {
                button.textContent = `${action}…`;
            }
            try {
                await controlRuntime(idValue, action);
                showToast(`Stream ${action} requested`, 'ok');
                await fetchRuntimeSnapshot(idValue);
            } catch (error) {
                showToast(error.message || `Unable to ${action} stream`, 'err');
            } finally {
                if (labelSpan) {
                    labelSpan.textContent = originalText;
                } else {
                    button.textContent = originalText;
                }
                setRuntimeControlState(activeDrawerDataflow?.control_plane_runtime?.state);
            }
        });
    });

    // Keyboard close (Esc)
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape' && drawer && drawer.classList.contains('open')) {
            closeDrawer();
        }
    });

    // Clicking a stream row opens the drawer
    $$('.row-clickable').forEach((row) => {
        row.addEventListener('click', (e) => {
            // Don't open drawer if a button inside the row was clicked
            if (e.target.closest('button')) return;
            const streamId = row.dataset.streamId || '';
            const dataflowType =
                row.dataset.dataflowType ||
                row.querySelector('.df-type-tag')?.dataset.dftype ||
                '';
            const streamName =
                row
                    .querySelector('.title')
                    ?.childNodes[1]?.textContent?.trim() ||
                row.querySelector('.title')?.textContent?.trim() ||
                row
                    .querySelector('.primary')
                    ?.childNodes[1]?.textContent?.trim() ||
                row.querySelector('.primary')?.textContent?.trim() ||
                '';
            openDrawer(streamId, streamName, dataflowType);
        });
    });

    // "View" / "Resume" / "Start" buttons inside rows also open the drawer
    $$('.row-clickable .btn-ghost').forEach((btn) => {
        btn.addEventListener('click', (e) => {
            e.stopPropagation();
            const row = btn.closest('.row-clickable');
            const streamId = row?.dataset.streamId || '';
            const dataflowType =
                row?.dataset.dataflowType ||
                row?.querySelector('.df-type-tag')?.dataset.dftype ||
                '';
            const streamName =
                row
                    ?.querySelector('.primary')
                    ?.childNodes[1]?.textContent?.trim() ||
                row?.querySelector('.primary')?.textContent?.trim() ||
                '';
            openDrawer(streamId, streamName, dataflowType);
        });
    });

    // Drawer tab pane switching
    $$('.drawer-tabs .tab').forEach((tab) => {
        tab.addEventListener('click', () => {
            $$('.drawer-tabs .tab').forEach((t) =>
                t.classList.remove('active'),
            );
            tab.classList.add('active');

            const pane = tab.dataset.pane;
            $$('.detail-pane.step-pane').forEach((p) =>
                p.classList.remove('active'),
            );
            const target = $(`[data-pane-content="${pane}"]`);
            if (target) target.classList.add('active');

            // When Logs tab is clicked, auto-start exception polling; otherwise stop
            if (pane === 'logs' && activeDrawerStreamId) {
                startExceptionPolling(activeDrawerStreamId, activeDrawerDataflowType, 15000);
            } else {
                stopExceptionPolling();
            }

            // When History tab is clicked, auto-fetch with current time-range
            if (pane === 'history' && activeDrawerStreamId) {
                const activeTimeBtn = document.querySelector('#historyTimeToggle button.active');
                const timeRange = activeTimeBtn ? activeTimeBtn.dataset.time : '24h';
                fetchStreamHistory(activeDrawerStreamId, activeDrawerDataflowType, timeRange);
            }
        });
    });

    // History time-range toggle buttons
    $$('#historyTimeToggle button').forEach((btn) => {
        btn.addEventListener('click', () => {
            $$('#historyTimeToggle button').forEach((b) => b.classList.remove('active'));
            btn.classList.add('active');
            if (activeDrawerStreamId) {
                fetchStreamHistory(activeDrawerStreamId, activeDrawerDataflowType, btn.dataset.time);
            }
        });
    });

    // Exception Aggregator UI Event Listeners
    const exceptionFilterInput = document.getElementById('exceptionFilterInput');
    if (exceptionFilterInput) {
        exceptionFilterInput.addEventListener('input', (e) => {
            exceptionFilterQuery = e.target.value || '';
            renderExceptions(currentExceptionsData);
        });
    }

    const exceptionPauseResumeBtn = document.getElementById('exceptionPauseResumeBtn');
    if (exceptionPauseResumeBtn) {
        exceptionPauseResumeBtn.addEventListener('click', toggleExceptionPause);
    }

    const exceptionManualRefreshBtn = document.getElementById('exceptionManualRefreshBtn');
    if (exceptionManualRefreshBtn) {
        exceptionManualRefreshBtn.addEventListener('click', () => {
            if (activeDrawerStreamId) {
                fetchStreamExceptions(activeDrawerStreamId, activeDrawerDataflowType);
            }
        });
    }

    /* =========================================================================
     SECTION 4 — CRUD WIZARD
     4a. Stepper step navigation
     4b. Continue / Back buttons
     4c. Source / Destination type cards + parameter panels
     4d. Semantic delivery cards
     4e. Window strategy chips
     4f. Right-rail topology + summary sync
     ========================================================================= */

    function showToast (msg, kind) {
        const t = $('#toast');
        if (!t) return;
        $('#toastMsg').textContent = msg;
        t.classList.remove('ok', 'err');
        if (kind) t.classList.add(kind);
        t.classList.add('show');
        clearTimeout(showToast._t);
        showToast._t = setTimeout(() => t.classList.remove('show'), 3000);
    }

    function validateStep1 () {
        const streamNameInput = $('#streamName');
        if (streamNameInput && !streamNameInput.value.trim()) {
            showToast('Please provide a Stream name.', 'err');
            streamNameInput.focus();
            return false;
        }
        return true;
    }

    /* 4a. Stepper click navigation ------------------------------------------- */
    $$('.step').forEach((step) => {
        step.addEventListener('click', () => {
            const n = step.dataset.step;

            const activeStep = $('.step.active');
            if (activeStep && activeStep.dataset.step === '1' && n !== '1') {
                if (!validateStep1()) return;
            }

            $$('.step').forEach((s) => s.classList.remove('active'));
            step.classList.add('active');
            $$('[data-step-content]').forEach((p) =>
                p.classList.remove('active'),
            );
            const pane = $(`[data-step-content="${n}"]`);
            if (pane) pane.classList.add('active');

            // On entering Step 2: fetch filtered clusters/nodes/services by conn_type
            if (parseInt(n) === 2) {
                const connTypeInput = document.getElementById('addConnType');
                const connType = connTypeInput ? connTypeInput.value : '';
                const serviceConfigArea =
                    document.getElementById('serviceConfigArea');

                if (connType === 'Fin_Data') {
                    if (serviceConfigArea)
                        serviceConfigArea.style.display = 'none';

                    fetch('/PlatformIO/APIv1/GetServicesByConnType/', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                            'X-CSRFToken': window.csrfToken || '',
                        },
                        body: JSON.stringify({ conn_type: connType }),
                    })
                        .then((r) => r.json())
                        .then((res) => {
                            if (res.success && res.clusters) {
                                const cInfo = {};
                                res.clusters.forEach((c) => {
                                    cInfo[c.cluster_name] = {
                                        cluster_name: c.cluster_name,
                                        node_info: {},
                                    };
                                    c.nodes.forEach((nd) => {
                                        cInfo[c.cluster_name].node_info[
                                            nd.node_name
                                        ] = {
                                            node_name: nd.node_name,
                                            service_info: {},
                                        };
                                        nd.services.forEach((s) => {
                                            cInfo[c.cluster_name].node_info[
                                                nd.node_name
                                            ].service_info[s.service_name] = s;
                                        });
                                    });
                                });
                                window.cluster_info = cInfo;
                                if (window.buildClustersGlobal)
                                    window.buildClustersGlobal();
                                if (window.bindClickhouseStaticDropdowns)
                                    window.bindClickhouseStaticDropdowns();
                            }
                        })
                        .catch((err) => {
                            // eslint-disable-next-line no-console
                            console.error(
                                'Error fetching services by conn type:',
                                err,
                            );
                        });
                }
            }

            if (parseInt(n) === 3) {
                updateReview();
            }
        });
    });

    function updateReview () {
        // Stream Card
        const sn = document.getElementById('streamName');
        const rvStreamName = document.getElementById('rvStreamName');
        if (rvStreamName) rvStreamName.textContent = (sn && sn.value) || '—';

        // Source Card
        const step1 = document.querySelector('[data-step-content="1"]');
        const srcCard = step1
            ? step1.querySelector('.type-card.selected:not(.sub-type-card)')
            : null;
        const rvSrcType = document.getElementById('rvSrcType');
        if (rvSrcType) {
            const tn = srcCard ? srcCard.querySelector('.tn') : null;
            rvSrcType.textContent = tn ? tn.textContent.trim() : '—';
        }

        const subCard = step1
            ? step1.querySelector('.sub-type-card.selected')
            : null;
        const rvSrcDetail = document.getElementById('rvSrcDetail');
        if (rvSrcDetail) {
            let detail = '—';
            if (subCard) {
                const subTn = subCard.querySelector('.tn');
                detail = subTn ? subTn.textContent.trim() : '—';
            } else if (srcCard && srcCard.dataset.src === 'kafka') {
                const topicInp = document.querySelector(
                    '[data-panel="kafka"] input',
                );
                detail =
                    topicInp && topicInp.value
                        ? `Topic: ${topicInp.value}`
                        : '—';
            } else if (srcCard && srcCard.dataset.src === 'cdc') {
                const dbInp = document.querySelector(
                    '[data-panel="cdc"] input',
                );
                detail = dbInp && dbInp.value ? `DB: ${dbInp.value}` : '—';
            }
            rvSrcDetail.textContent = detail;
        }

        // Destination Card
        const step2 = document.querySelector('[data-step-content="2"]');
        const dstCard = step2
            ? step2.querySelector('.type-card.selected')
            : null;
        const nocReview = isNocStream(document.getElementById('addDataFlowType')?.value)
            || Boolean(srcCard && ['local_path', 'ftp'].includes(srcCard.dataset.src));
        const rvDestApp = document.getElementById('rvDestApp');
        if (rvDestApp) {
            const dstTn = dstCard ? dstCard.querySelector('.tn') : null;
            rvDestApp.textContent = nocReview ? 'Kafka alarm topic' : (dstTn ? dstTn.textContent.trim() : '—');
        }

        const rvDestService = document.getElementById('rvDestService');
        if (rvDestService) {
            const ddSvc = document.getElementById('addServiceName');
            rvDestService.textContent = nocReview ? 'noc.alarm.normalized.v1' : (ddSvc && ddSvc.value ? ddSvc.value : '—');
        }

        const rvDestIngestion = document.getElementById('rvDestIngestion');
        if (rvDestIngestion) {
            const ddIng = document.getElementById('addIngestion');
            rvDestIngestion.textContent = nocReview ? 'AgenticNOC canonical ingress' : (ddIng && ddIng.value ? ddIng.value : '—');
        }


    }

    /* 4b. Continue (primary) / Back (ghost) buttons -------------------------- */
    $$('.step-nav .btn-primary').forEach((btn) => {
        // Exclude the final "Start stream" button
        if (btn.textContent.trim().startsWith('Start')) return;

        btn.addEventListener('click', () => {
            const activeStep = $('.step.active');
            if (!activeStep) return;
            const n = activeStep.dataset.step;

            // Step 1 Validation
            if (n === '1') {
                if (!validateStep1()) return;
            }

            // Skip Step 3 (Schedule) and advance directly from Step 2 to Step 4 (Review)
            if (n === '2') {
                activeStep.classList.add('done');
                const step4 = $('.step[data-step="4"]');
                if (step4) {
                    step4.click();
                    return;
                }
            }

            const next = activeStep.nextElementSibling;
            if (next && next.classList.contains('step')) {
                activeStep.classList.add('done');
                next.click(); // triggers the step click handler above
            }
        });
    });

    $$('.step-nav .btn-ghost').forEach((btn) => {
        const text = btn.textContent.trim();
        if (!text.startsWith('Back') && !btn.querySelector('svg')) return;

        btn.addEventListener('click', () => {
            const activeStep = $('.step.active');
            if (!activeStep) return;
            const n = activeStep.dataset.step;

            // Navigate back directly from Step 4 (Review) to Step 2 (Destination)
            if (n === '4') {
                activeStep.classList.remove('done');
                const step2 = $('.step[data-step="2"]');
                if (step2) {
                    step2.click();
                    return;
                }
            }

            const prev = activeStep.previousElementSibling;
            if (prev && prev.classList.contains('step')) {
                activeStep.classList.remove('done');
                prev.click();
            }
        });
    });

    /* 4c. Type cards + panel switching --------------------------------------- */
    function setActivePanel (container, key) {
        if (!container) return;
        $$('.panel', container).forEach((p) => p.classList.remove('active'));
        if (!key) return;
        const panel = $(`[data-panel="${key}"]`, container);
        if (panel) panel.classList.add('active');
    }

    function updateRail (role, label) {
        const topo = $('#topoPreview');
        if (topo) {
            const nodes = $$('.node', topo);
            if (role === 'source' && nodes[0]) nodes[0].textContent = label;
            if (role === 'sink' && nodes[2]) nodes[2].textContent = label;
        }
        const el = $('#' + (role === 'source' ? 'railSource' : 'railSink'));
        if (el) el.textContent = label;
    }

    function updateDestinationVisibility () {
        const srcCard = $('.type-card.selected[data-src]');
        const sourceType = srcCard?.dataset.src || '';
        const nocSource = sourceType === 'local_path' || sourceType === 'ftp' || sourceType === 'endpoint' || ($('#addDataFlowType')?.value || '').toLowerCase() === 'nocalarmstream';
        const isService = srcCard && srcCard.dataset.src === 'service';
        const subCard = $('.sub-type-card.selected[data-src]');
        const isFinData =
            isService && subCard && subCard.dataset.src === 'Fin_Data';

        const mockDestUI = $('#mockDestUI');
        const drilldownDestUI = $('#drilldownDestUI');
        const nocKafkaDestUI = $('#nocKafkaDestUI');

        if (nocKafkaDestUI) nocKafkaDestUI.style.display = nocSource && !isService ? 'block' : 'none';
        if (nocSource && !isService) updateRail('sink', 'AgenticNOC Kafka pipeline');
        else if (!isFinData) updateRail('sink', 'ClickHouse');

        if (nocSource && !isService) {
            if (mockDestUI) mockDestUI.style.display = 'none';
            if (drilldownDestUI) drilldownDestUI.style.display = 'none';
        } else if (isFinData) {
            if (mockDestUI) mockDestUI.style.display = 'none';
            if (drilldownDestUI) drilldownDestUI.style.display = 'block';
        } else {
            if (mockDestUI) mockDestUI.style.display = 'block';
            if (drilldownDestUI) drilldownDestUI.style.display = 'none';
        }
    }

    $$('.type-card:not(.sub-type-card)').forEach((card) => {
        card.addEventListener('click', () => {
            // Deselect siblings in same picker grid
            $$('.type-card', card.parentElement).forEach((c) =>
                c.classList.remove('selected'),
            );
            card.classList.add('selected');

            const stepPane = card.closest('[data-step-content]');
            const label = card.querySelector('.tn')?.textContent.trim() || '';

            if (card.dataset.src) {
                const subPicker = document.getElementById('serviceSubPicker');
                const isServiceBased = card.dataset.src === 'service';

                if (isServiceBased) {
                    if (subPicker) subPicker.style.display = 'block';
                    setActivePanel(stepPane?.querySelector('.src-params'), '');
                } else {
                    if (subPicker) {
                        subPicker.style.display = 'none';
                        $$('.sub-type-card', subPicker).forEach((x) =>
                            x.classList.remove('selected'),
                        );
                    }
                    setActivePanel(
                        stepPane?.querySelector('.src-params'),
                        card.dataset.src,
                    );
                    if (card.dataset.src === 'endpoint') {
                        if ($('#nifiListenPort') && !$('#nifiListenPort').value) $('#nifiListenPort').value = '9080';
                        if ($('#nifiBasePath') && !$('#nifiBasePath').value) $('#nifiBasePath').value = 'aviat';
                        if ($('#endpointProtocol') && !$('#endpointProtocol').value) $('#endpointProtocol').value = 'http';
                    }
                }
                // Show AgenticNOC stream controls for sources owned by this runtime.
                const replayControls = document.getElementById('demoReplayControls');
                if (replayControls) {
                    replayControls.style.display = ['local_path', 'ftp', 'endpoint'].includes(card.dataset.src) ? 'block' : 'none';
                }

                updateRail('source', label);
                updateDestinationVisibility();
            }
            if (card.dataset.dst) {
                setActivePanel(
                    stepPane?.querySelector('.dst-params'),
                    card.dataset.dst,
                );
                updateRail('sink', label);
                updateDestinationVisibility();
            }
        });
    });

    /* 4d. Semantic delivery cards -------------------------------------------- */
    $$('.semantic-card').forEach((card) => {
        card.addEventListener('click', () => {
            $$('.semantic-card').forEach((c) => c.classList.remove('selected'));
            card.classList.add('selected');
        });
    });

    /* 4e. Window strategy chips and Schedule chips --------------------------- */
    $$('.window-chip').forEach((chip) => {
        chip.addEventListener('click', () => {
            const strip = chip.closest('.window-strip');
            if (strip) {
                $$('.window-chip', strip).forEach((c) =>
                    c.classList.remove('selected'),
                );
                chip.classList.add('selected');
            }
        });
    });

    /* 4f. Edit links in Review step — jump back to that step ----------------- */
    $$('.edit-link').forEach((link, i) => {
        link.addEventListener('click', (e) => {
            e.preventDefault();
            const stepNum = link.dataset.stepTarget || (i + 1).toString();
            const targetStep = $(`[data-step="${stepNum}"]`);
            if (targetStep) targetStep.click();
        });
    });

    /* =========================================================================
     SECTION 5 — CRUD WIZARD LOGIC (Option A Backend Integration)
     ========================================================================= */

    // Custom Multi-Select UI Component
    function initCustomMultiSelect (selectEl, forceRebuild = false) {
        if (!selectEl) return;

        let wrapper;
        if (selectEl.dataset.customized) {
            wrapper = selectEl.nextElementSibling;
            if (wrapper && wrapper.classList.contains('custom-multi-select')) {
                if (forceRebuild) {
                    if (wrapper._buildDropdown) wrapper._buildDropdown();
                    if (wrapper._updateLabel) wrapper._updateLabel();
                }
                return;
            }
        }

        selectEl.dataset.customized = 'true';
        selectEl.style.display = 'none';

        wrapper = document.createElement('div');
        wrapper.className = 'custom-multi-select';

        const trigger = document.createElement('div');
        trigger.className = 'input custom-multi-select-trigger';

        const labelText = document.createElement('span');
        labelText.className = 'custom-multi-select-label';

        const arrow = document.createElement('span');
        arrow.className = 'custom-multi-select-arrow';
        arrow.innerHTML = '▼';

        trigger.appendChild(labelText);
        trigger.appendChild(arrow);

        const dropdown = document.createElement('div');
        dropdown.className = 'custom-multi-select-dropdown';

        wrapper.appendChild(trigger);
        wrapper.appendChild(dropdown);
        selectEl.parentNode.insertBefore(wrapper, selectEl.nextSibling);

        function updateLabel () {
            const selected = Array.from(selectEl.selectedOptions).map(
                (o) => o.textContent || o.value,
            );
            const placeholder = selectEl.dataset.placeholder || 'Select options...';
            if (selected.length === 0) {
                labelText.textContent = placeholder;
                labelText.style.color = 'var(--ink-4, #94a3b8)';
            } else if (selected.length <= 2) {
                labelText.textContent = selected.join(', ');
                labelText.style.color = 'var(--ink-1, #0f172a)';
            } else {
                labelText.textContent = selected.length + ' symbols selected';
                labelText.style.color = 'var(--ink-1, #0f172a)';
            }
        }

        function buildDropdown () {
            dropdown.innerHTML = '';

            // 1. Search Filter Input Box
            const searchContainer = document.createElement('div');
            searchContainer.className = 'custom-multi-select-search-box';

            const searchInput = document.createElement('input');
            searchInput.type = 'text';
            searchInput.className = 'custom-multi-select-search';
            searchInput.placeholder = 'Filter symbols…';

            searchContainer.appendChild(searchInput);
            dropdown.appendChild(searchContainer);

            // 2. Action Header ("Select All" / "Clear All")
            const header = document.createElement('div');
            header.className = 'custom-multi-select-header';

            const selAllLbl = document.createElement('label');
            selAllLbl.className = 'custom-multi-select-action-lbl';

            const selAllChk = document.createElement('input');
            selAllChk.type = 'checkbox';
            const selectableOpts = Array.from(selectEl.options).filter((opt) => !opt.disabled);
            selAllChk.checked = selectableOpts.length > 0 && selectableOpts.every((opt) => opt.selected);

            selAllChk.onchange = function (e) {
                e.stopPropagation();
                const checkNow = selAllChk.checked;
                selectableOpts.forEach((opt) => {
                    opt.selected = checkNow;
                });
                buildDropdown();
                updateLabel();
                selectEl.dispatchEvent(new Event('change'));
            };

            selAllLbl.appendChild(selAllChk);
            selAllLbl.appendChild(document.createTextNode('Select all'));
            header.appendChild(selAllLbl);

            const clearBtn = document.createElement('button');
            clearBtn.type = 'button';
            clearBtn.className = 'custom-multi-select-clear-btn';
            clearBtn.textContent = 'Clear all';
            clearBtn.onclick = function (e) {
                e.stopPropagation();
                Array.from(selectEl.options).forEach((opt) => {
                    opt.selected = false;
                });
                buildDropdown();
                updateLabel();
                selectEl.dispatchEvent(new Event('change'));
            };
            header.appendChild(clearBtn);

            dropdown.appendChild(header);

            // 3. Options Container
            const listContainer = document.createElement('div');
            listContainer.className = 'custom-multi-select-options-list';

            Array.from(selectEl.options).forEach((opt) => {
                if (opt.disabled) return;
                const lbl = document.createElement('label');
                lbl.className = 'checkbox custom-multi-select-option-item';

                const chk = document.createElement('input');
                chk.type = 'checkbox';
                chk.value = opt.value;
                chk.checked = opt.selected;

                chk.onchange = function () {
                    opt.selected = chk.checked;
                    const allChecked = selectableOpts.every((o) => o.selected);
                    selAllChk.checked = allChecked;
                    updateLabel();
                    selectEl.dispatchEvent(new Event('change'));
                };

                lbl.appendChild(chk);
                lbl.appendChild(document.createTextNode(opt.textContent || opt.value));
                listContainer.appendChild(lbl);
            });

            dropdown.appendChild(listContainer);

            // Live filter search implementation
            searchInput.oninput = function () {
                const term = searchInput.value.toLowerCase().trim();
                const items = listContainer.querySelectorAll('.custom-multi-select-option-item');
                items.forEach((item) => {
                    const text = item.textContent.toLowerCase();
                    if (text.includes(term)) {
                        item.style.display = 'flex';
                    } else {
                        item.style.display = 'none';
                    }
                });
            };
        }

        wrapper._buildDropdown = buildDropdown;
        wrapper._updateLabel = updateLabel;

        trigger.onclick = function (e) {
            if (selectEl.disabled) return;
            e.stopPropagation();
            const isOpen = dropdown.style.display === 'block';
            document
                .querySelectorAll('.custom-multi-select-dropdown')
                .forEach((d) => (d.style.display = 'none'));
            document
                .querySelectorAll('.custom-multi-select-arrow')
                .forEach((a) => (a.style.transform = 'none'));
            if (!isOpen) {
                buildDropdown();
                dropdown.style.display = 'block';
                arrow.style.transform = 'rotate(180deg)';
                const searchInp = dropdown.querySelector('.custom-multi-select-search');
                if (searchInp) {
                    setTimeout(() => searchInp.focus(), 50);
                }
            }
        };

        dropdown.onclick = function (e) {
            e.stopPropagation();
        };

        selectEl.addEventListener('change', updateLabel);
        updateLabel();
    }

    document.addEventListener('click', function () {
        document
            .querySelectorAll('.custom-multi-select-dropdown')
            .forEach((d) => (d.style.display = 'none'));
        document
            .querySelectorAll('.custom-multi-select-arrow')
            .forEach((a) => (a.style.transform = 'none'));
    });

    let editModeId = null;

    // Fetch and populate cascading dropdowns & symbols
    async function initStreamWizard () {
        const addSymList = document.getElementById('addSymbolsList');
        if (addSymList) {
            initCustomMultiSelect(addSymList);
        }

        // Fin_Data toggles
        const finSourceType = $('#addSourceType');
        if (finSourceType) {
            finSourceType.addEventListener('change', () => {
                const apiField = $('#apiKeyField');
                const secretField = $('#secretKeyField');
                // The old UI shows both fields for all 5 source types:
                // YFinance, AlphaVantage, Massive, Finnhub, Tradier
                if (apiField) apiField.style.display = '';
                if (secretField) secretField.style.display = '';
            });
        }

        // Sub-picker for Service Based
        $$('.sub-type-card').forEach((card) => {
            card.addEventListener('click', () => {
                $$('.sub-type-card').forEach((c) =>
                    c.classList.remove('selected'),
                );
                card.classList.add('selected');

                // Set the hidden conn_type so step 2 knows what to fetch
                const connTypeInput = document.getElementById('addConnType');
                if (connTypeInput) connTypeInput.value = card.dataset.src || '';

                const stepPane = document.querySelector(
                    '.step-pane.active[data-step-content="1"]',
                );
                if (stepPane) {
                    setActivePanel(
                        stepPane.querySelector('.src-params'),
                        card.dataset.src,
                    );
                }
                if (typeof updateDestinationVisibility === 'function') {
                    updateDestinationVisibility();
                }
            });
        });

        // Ensure destination visibility is correct on load
        if (typeof updateDestinationVisibility === 'function') {
            updateDestinationVisibility();
        }
    }

    /* =========================================================================
     GLOBAL STREAM THROUGHPUT AGGREGATOR
     Calculates dynamic total throughput sum across all active streams every second
     ========================================================================= */
    const streamThroughputMap = new Map(); // dataflow_id -> number (events or ticks/sec)
    let globalThroughputTimer = null;
    let globalMetricsPollTimer = null;
    let isGlobalPollingInFlight = false;

    function formatThroughputRate (val) {
        if (!Number.isFinite(val) || val <= 0) return '0';
        if (val >= 1000000) {
            return (val / 1000000).toFixed(1).replace(/\.0$/, '') + 'm';
        }
        if (val >= 1000) {
            return (val / 1000).toFixed(1).replace(/\.0$/, '') + 'k';
        }
        if (Number.isInteger(val)) {
            return val.toString();
        }
        return val.toFixed(1).replace(/\.0$/, '');
    }

    function extractThroughputFromMetrics (metrics, dataflowType) {
        if (!metrics) return 0;
        // Check throughput_lag range first (most accurate recent point)
        const tputRange = metrics.throughput_lag?.throughput_range;
        if (Array.isArray(tputRange) && tputRange.length > 0) {
            const lastPt = tputRange[tputRange.length - 1];
            const val = Array.isArray(lastPt) ? Number(lastPt[1]) : Number(lastPt?.value);
            if (Number.isFinite(val)) return Math.max(0, val);
        }
        // Check fyer ticks_per_sec or source rate
        if (metrics.fyer && Number.isFinite(Number(metrics.fyer.ticks_per_sec))) {
            return Math.max(0, Number(metrics.fyer.ticks_per_sec));
        }
        if (Number.isFinite(Number(metrics.ticks_per_sec))) {
            return Math.max(0, Number(metrics.ticks_per_sec));
        }
        if (Number.isFinite(Number(metrics.throughput))) {
            return Math.max(0, Number(metrics.throughput));
        }
        return 0;
    }

    function extractThroughputFromSnapshot (snapshot) {
        if (!snapshot) return 0;
        const key = snapshot.dataflow_id || 'runtime';
        const sampleState = runtimeSamples.get(key);
        if (sampleState && sampleState.samples && sampleState.samples.length > 0) {
            const lastSample = sampleState.samples[sampleState.samples.length - 1];
            if (lastSample && Number.isFinite(lastSample.throughput) && lastSample.throughput > 0) {
                return lastSample.throughput;
            }
        }
        if (snapshot.replay && Number.isFinite(Number(snapshot.replay.events_per_second))) {
            const isRunning = String(snapshot.state || '').toLowerCase() === 'running';
            return isRunning ? Number(snapshot.replay.events_per_second) : 0;
        }
        return 0;
    }

    async function pollAllActiveStreamsThroughput () {
        if (isGlobalPollingInFlight || !window.dataflow_info || !Array.isArray(window.dataflow_info)) return;
        isGlobalPollingInFlight = true;

        const activeStreams = window.dataflow_info.filter((df) => {
            const runtimeState = String(df.control_plane_runtime?.state || '').toLowerCase();
            return runtimeState === 'running' || (!runtimeState && (df.dataflow_status || 'enable').toLowerCase() === 'enable');
        });

        // Clean up streams that no longer exist or are inactive
        const activeIds = new Set(activeStreams.map((df) => df.dataflow_id));
        for (const id of streamThroughputMap.keys()) {
            if (!activeIds.has(id)) {
                streamThroughputMap.delete(id);
            }
        }

        const pollPromises = activeStreams.map(async (df) => {
            try {
                const isNoc = isNocStream(df.dataflow_type) || Boolean(df.control_plane_contract);
                if (isNoc) {
                    const res = await fetch(`/PlatformIO/APIv1/ControlPlane/StreamRuntime/?dataflow_id=${encodeURIComponent(df.dataflow_id)}`, {
                        headers: { Accept: 'application/json' },
                    });
                    const snapshot = await res.json();
                    if (snapshot && snapshot.success !== false) {
                        const tput = extractThroughputFromSnapshot(snapshot);
                        streamThroughputMap.set(df.dataflow_id, tput);
                    }
                } else {
                    const csrfToken = window.csrfToken || document.querySelector('[name="csrfmiddlewaretoken"]')?.value || '';
                    const res = await fetch('/PlatformIO/StreamIngress/', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                            'X-CSRFToken': csrfToken,
                        },
                        body: JSON.stringify({
                            'user-action': 'dataflow_log',
                            dataflow_id: df.dataflow_id,
                            dataflow_type: df.dataflow_type || '',
                            request_info: {
                                dataflow_id: df.dataflow_id,
                                dataflow_type: df.dataflow_type || '',
                            },
                        }),
                    });
                    const data = await res.json();
                    if (data && data.success && data.metrics) {
                        const tput = extractThroughputFromMetrics(data.metrics, df.dataflow_type);
                        streamThroughputMap.set(df.dataflow_id, tput);
                    }
                }
            } catch (err) {
                // Ignore transient background fetch errors
            }
        });

        try {
            await Promise.all(pollPromises);
        } finally {
            isGlobalPollingInFlight = false;
        }
    }

    function updateHeaderThroughputUI () {
        const valEl = document.getElementById('headerThroughputValue');
        const subEl = document.getElementById('headerThroughputSub');
        if (!valEl) return;

        let totalTput = 0;
        let activeCount = 0;

        if (window.dataflow_info && Array.isArray(window.dataflow_info)) {
            window.dataflow_info.forEach((df) => {
                const runtimeState = String(df.control_plane_runtime?.state || '').toLowerCase();
                const isRunning = runtimeState === 'running' || (!runtimeState && (df.dataflow_status || 'enable').toLowerCase() === 'enable');
                if (isRunning) {
                    activeCount++;
                    const streamTput = streamThroughputMap.get(df.dataflow_id) || 0;
                    totalTput += streamTput;
                }
            });
        }

        const formatted = formatThroughputRate(totalTput);
        valEl.innerHTML = `${formatted}<span style="font-family:var(--body); font-size:14px; color:var(--ink-3);"> /s</span>`;

        if (subEl) {
            if (activeCount > 0) {
                subEl.innerHTML = `<span style="color:var(--ok);">●</span> Across ${activeCount} active stream${activeCount > 1 ? 's' : ''}`;
            } else {
                subEl.textContent = 'No active streams';
            }
        }
    }

    function initGlobalThroughputTracking () {
        if (!globalThroughputTimer) {
            globalThroughputTimer = setInterval(updateHeaderThroughputUI, 1000);
        }
        if (!globalMetricsPollTimer) {
            globalMetricsPollTimer = setInterval(pollAllActiveStreamsThroughput, 2500);
        }
        updateHeaderThroughputUI();
        pollAllActiveStreamsThroughput().then(updateHeaderThroughputUI);
    }

    // Dynamic rendering of cards
    function renderDataflowCards () {
        const grid = $('.cards-grid');
        if (!grid || !window.dataflow_info) return;

        // The old page shipped a decorative example card.  Once the NOC
        // control-plane is enabled it would look like a real stream, so keep
        // the list strictly backed by registered dataflow rows.
        $$('.stream-card[data-demo-mock="true"]', grid).forEach((c) => c.remove());

        // Clear only cards generated from the current backend snapshot.
        $$('.stream-card[data-backend="true"]', grid).forEach((c) =>
            c.remove(),
        );

        if (window.dataflow_info.length === 0) {
            grid.innerHTML = `
                <div style="grid-column: 1 / -1; padding: var(--s-6); text-align: center; color: var(--ink-3); border: 1px dashed var(--line); border-radius: var(--r-md); background: var(--bg-sunken);">
                    <div style="font-weight: 600; font-size: 14px; margin-bottom: 4px; color: var(--ink-2);">No stream dataflows registered</div>
                    <div style="font-size: 12px;">Click "+ New stream" to create your first stream ingestion dataflow.</div>
                </div>
            `;
        }

        window.dataflow_info.forEach((df) => {
            const row = document.createElement('div');
            row.className = 'stream-card row-clickable';
            row.dataset.streamId = df.dataflow_id;
            row.dataset.dataflowType = df.dataflow_type || '';
            row.dataset.type = 'ingress';
            row.dataset.backend = 'true';

            const runtimeState = String(df.control_plane_runtime?.state || '').toLowerCase();
            const isRunning = runtimeState === 'running' ||
                (!runtimeState && (df.dataflow_status || 'enable').toLowerCase() === 'enable');
            row.dataset.status = isRunning ? 'enable' : 'disable';

            const pillClass = isRunning ? 'pill-ok' : (runtimeState === 'failed' ? 'pill-err' : 'pill-warn');
            const pillText = runtimeState || (isRunning ? 'Running' : 'Stopped');

            row.innerHTML = `
                <div class="card-head">
                  <div class="title">${df.dataflow_name}</div>
                  <div class="tags">
                      <span class="df-type-tag df-type-tag-auto" data-dftype="${df.dataflow_type || ''}">${df.dataflow_type || 'Unknown'}</span>
                      <span class="pill ${pillClass}">${pillText}</span>
                  </div>
                </div>
                <div class="card-flow">
                  <div class="node"><div class="label">SOURCE</div><div class="val">${df.conn_type || 'Unknown'}</div></div>
                  <div class="arr">→</div>
                  <div class="node"><div class="label">TARGET</div><div class="val">${df.ingestion || 'Unknown'}</div></div>
                </div>
                <div class="card-footer-bar">
                  <div class="service-badge" title="Service: ${df.service_name || 'Unassigned'}">
                    <svg class="ic" viewBox="0 0 24 24" style="width:13px; height:13px; color:var(--primary, #0548a8); margin-right:6px; flex-shrink:0;" fill="none" stroke="currentColor" stroke-width="2">
                      <rect x="2" y="2" width="20" height="8" rx="2"/>
                      <rect x="2" y="14" width="20" height="8" rx="2"/>
                      <circle cx="6" cy="6" r="1" fill="currentColor"/>
                      <circle cx="6" cy="18" r="1" fill="currentColor"/>
                    </svg>
                    <span class="svc-label">Service:</span>
                    <span class="svc-name">${df.service_name || 'Unassigned'}</span>
                  </div>
                </div>
            `;
            grid.appendChild(row);

            // Wire up row click to open drawer
            row.addEventListener('click', (e) => {
                if (e.target.closest('button')) return;
                openDrawer(df.dataflow_id, df.dataflow_name, df.dataflow_type);
            });
        });

        // Update counts dynamically
        const allCards = $$('.cards-grid .stream-card');
        const countAll = allCards.length;
        const countStopped = allCards.filter(
            (c) => c.querySelector('.pill-err') || c.dataset.status === 'disable',
        ).length;

        const tabAll = $('.tab[data-filter="all"] .count');
        if (tabAll) tabAll.textContent = countAll;

        const metaV = $('#headerStreamingCount') || $('.meta-strip .meta:first-child .v');
        if (metaV) {
            const activeCount = countAll - countStopped;
            const deltaSpan = metaV.querySelector('.delta');
            metaV.innerHTML =
                `${activeCount} ` + (deltaSpan ? deltaSpan.outerHTML : '');
        }

        window.colorTypeTags();
        initGlobalThroughputTracking();
    }

    function openCrudEdit (df) {
        editModeId = df.dataflow_id;
        showCrud();

        $('#streamName').value = df.dataflow_name || '';

        // Cascading dropdowns
        if (window.prefillDrilldown) {
            window.prefillDrilldown(
                df.app_name,
                df.service_name,
                df.dataflow_type,
                df.ingestion,
            );
        }

        // Connection config
        if (df.conn_type === 'Fin_Data') {
            const srvCard = $('.type-card[data-src="service"]');
            if (srvCard) srvCard.click();
            setTimeout(() => {
                const subCard = $('.sub-type-card[data-src="Fin_Data"]');
                if (subCard) subCard.click();

                $('#addSourceType').value = df.sourceType || '';
                $('#addSourceType').dispatchEvent(new Event('change'));
                $('#apiKey').value = df.ApiKey || '';
                $('#secretKey').value = df.SecretKey || '';

                const rSelect = $('#realSymbolsSelect');
                if (rSelect && df.symbolsList) {
                    Array.from(rSelect.options).forEach((opt) => {
                        opt.selected = df.symbolsList.includes(opt.value);
                    });
                    rSelect.dispatchEvent(new Event('change'));
                }
            }, 100);
        } else if (df.conn_type === 'FTP') {
            const ftpCard = $('.type-card[data-src="ftp"]');
            if (ftpCard) ftpCard.click();
            setTimeout(() => {
                const destCard = $('.type-card[data-dst="ftp"]');
                if (destCard) destCard.click();
                if ($('#ftpUrl')) $('#ftpUrl').value = df.ftpUrl || '';
                if ($('#ftpUsername'))
                    $('#ftpUsername').value = df.ftpUsername || '';
                if ($('#ftpPassword'))
                    $('#ftpPassword').value = df.ftpPassword || '';
                if ($('#ftpRemotePath'))
                    $('#ftpRemotePath').value = df.ftpRemotePath || '';
                if ($('#ftpFileName'))
                    $('#ftpFileName').value = df.ftpFileName || '';
                if ($('#ftpDestPath'))
                    $('#ftpDestPath').value = df.ftpDestPath || '';
            }, 100);
        } else if (df.conn_type === 'LOCAL') {
            const localCard = $('.type-card[data-src="local_path"]');
            if (localCard) localCard.click();
            setTimeout(() => {
                if ($('#localPath')) $('#localPath').value = df.localPath || df.path || '';
                if ($('#localFilePattern')) $('#localFilePattern').value = df.localFilePattern || df.file_pattern || '';
            }, 100);
        } else if (['ENDPOINT', 'HTTP_ENDPOINT', 'SSE'].includes(df.conn_type)) {
            const endpointCard = $('.type-card[data-src="endpoint"]');
            if (endpointCard) endpointCard.click();
            setTimeout(() => {
                if ($('#endpointUrl')) $('#endpointUrl').value = df.endpointUrl || df.endpoint_url || '';
                if ($('#endpointProtocol')) $('#endpointProtocol').value = df.endpointProtocol || df.endpoint_protocol || 'http';
                if ($('#nifiListenPort')) $('#nifiListenPort').value = df.nifiListenPort || df.listen_port || 9080;
                if ($('#nifiBasePath')) $('#nifiBasePath').value = df.nifiBasePath || df.base_path || 'aviat';
            }, 100);
        }

        if ($('#eventsPerSecond')) $('#eventsPerSecond').value = df.events_per_second || df.eps || 100;
        if ($('#replayMode')) {
            $('#replayMode').value = df.replay_mode || (df.continuous_replay === false ? 'one_shot' : 'continuous');
        }
        if ($('#nocVendor')) $('#nocVendor').value = df.vendor || df.alarm_vendor || 'aviat';

        // Scheduling
        if ($('#startDate')) $('#startDate').value = df.start_date || '';
        if ($('#startTime')) $('#startTime').value = df.start_time || '';
        if ($('#timeZone')) $('#timeZone').value = df.time_zone || '';
        if ($('#periodicity')) $('#periodicity').value = df.periodicity || '';

        // Reset step
        $('.step[data-step="1"]').click();
    }

    let deleteTargetId = null;

    function openDeleteDialog (id, name) {
        deleteTargetId = id;
        const dn = document.getElementById('delName');
        const conf = document.getElementById('delConfirm');
        const btn = document.getElementById('delConfirmBtn');
        if (dn) dn.textContent = name || id;
        if (conf) {
            conf.value = '';
            // Remove previous listeners
            if (conf._deleteInputHandler) {
                conf.removeEventListener('input', conf._deleteInputHandler);
            }
            conf._deleteInputHandler = function () {
                btn.disabled = conf.value.trim().toLowerCase() !== 'delete';
            };
            conf.addEventListener('input', conf._deleteInputHandler);
        }
        if (btn) {
            btn.disabled = true;
            btn.innerHTML = 'Delete stream';

            if (btn._deleteClickHandler) {
                btn.removeEventListener('click', btn._deleteClickHandler);
            }
            btn._deleteClickHandler = function () {
                executeDelete(deleteTargetId);
            };
            btn.addEventListener('click', btn._deleteClickHandler);
        }

        const b = document.getElementById('deleteBack');
        if (b) {
            b.classList.add('open');
            setTimeout(() => {
                if (conf) conf.focus();
            }, 200);
        }
    }

    window.closeDialog = function () {
        const b = document.getElementById('deleteBack');
        if (b) b.classList.remove('open');
        deleteTargetId = null;
    };

    function executeDelete (id) {
        const btn = document.getElementById('delConfirmBtn');
        if (btn) {
            btn.disabled = true;
            btn.innerHTML = 'Deleting...';
        }

        const target = (window.dataflow_info || []).find((item) => item.dataflow_id === id);
        if (target && target.control_plane_contract) {
            controlRuntime(id, 'delete')
                .then(() => {
                    window.closeDialog();
                    showToast('Deleted successfully', 'ok');
                    window.dataflow_info = (window.dataflow_info || []).filter((item) => item.dataflow_id !== id);
                    streamThroughputMap.delete(id);
                    renderDataflowCards();
                })
                .catch((error) => {
                    window.closeDialog();
                    showToast(error.message || 'Error deleting stream', 'err');
                });
            return;
        }

        fetch('/PlatformIO/StreamIngress/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken':
                    document.querySelector('[name="csrfmiddlewaretoken"]')
                        ?.value || '',
            },
            body: JSON.stringify({
                'user-action': 'delete',
                dataflow_id: id,
            }),
        })
            .then((res) => res.json())
            .then((res) => {
                window.closeDialog();
                if (res.success || res.status === 'success') {
                    showToast('Deleted successfully', 'ok');
                    streamThroughputMap.delete(id);
                    if (res.dataflow_info) {
                        window.dataflow_info = res.dataflow_info;
                        renderDataflowCards();
                    } else {
                        const card = document.querySelector(
                            `.stream-card[data-stream-id="${id}"]`,
                        );
                        if (card) card.remove();
                    }
                } else {
                    showToast('Error deleting stream', 'err');
                }
            })
            .catch(() => {
                window.closeDialog();
                showToast('Network error deleting stream', 'err');
            });
    }

    // Bind "Start stream" / "Save changes" button
    $$('.step-nav .btn-primary').forEach((btn) => {
        if (btn.textContent.trim().startsWith('Start')) {
            btn.addEventListener('click', () => {
                const originalHtml = btn.innerHTML;
                const loaderText = editModeId ? 'Saving...' : 'Creating...';
                btn.innerHTML = `<svg class="spin-loader" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="height:1em; margin-right:6px; vertical-align:-0.125em;"><circle cx="12" cy="12" r="10" stroke-opacity="0.25"/><path d="M12 2A10 10 0 0 1 22 12" stroke-linecap="round"/></svg>${loaderText}`;
                btn.disabled = true;

                const payload = {
                    dataflow_name: $('#streamName').value,
                    dataflow_status: 'Enable',
                    app_name: $('input[name="app_name"]')?.value || '',
                    service_name: $('#addServiceName')?.value || '',
                    dataflow_type: $('#addDataFlowType')?.value || '',
                    ingestion: $('#addIngestion')?.value || '',
                    start_date: $('#startDate')
                        ? $('#startDate').value
                        : new Date().toISOString().split('T')[0],
                    start_time: $('#startTime')
                        ? $('#startTime').value
                        : new Date().toTimeString().substring(0, 5),
                    time_zone: $('#timeZone') ? $('#timeZone').value : 'UTC',
                    periodicity: $('#periodicity')
                        ? $('#periodicity').value
                        : 'continuous',
                };

                // Check Source Type
                const selectedSrc = $('.type-card.selected[data-src]');
                if (selectedSrc && selectedSrc.dataset.src === 'service') {
                    const subSrc = $('.sub-type-card.selected[data-src]');
                    if (subSrc && subSrc.dataset.src === 'Fin_Data') {
                        payload.conn_type = 'Fin_Data';
                        payload.sourceType = $('#addSourceType')
                            ? $('#addSourceType').value
                            : '';
                        payload.ApiKey = $('#apiKey') ? $('#apiKey').value : ($('input[name="ApiKey"]')?.value || '');
                        payload.SecretKey = $('#secretKey')
                            ? $('#secretKey').value
                            : ($('input[name="SecretKey"]')?.value || '');

                        const tokenEl = $('#fyersAccessToken') || $('textarea[name="access_token"]') || $('input[name="access_token"]');
                        if (tokenEl && tokenEl.value.trim()) {
                            payload.access_token = tokenEl.value.trim();
                        }

                        const rSelect = $('#realSymbolsSelect') || $('#addSymbolsList');
                        if (rSelect) {
                            payload.symbolsList = Array.from(
                                rSelect.selectedOptions,
                            ).map((o) => o.value);
                        }
                    }
                } else if (selectedSrc && selectedSrc.dataset.src === 'ftp') {
                    payload.conn_type = 'FTP';
                    payload.dataflow_type = 'ftpStream';
                    payload.ingestion = 'BackEnd';
                    payload.ftpUrl = $('#ftpUrl') ? $('#ftpUrl').value : '';
                    payload.ftpUsername = $('#ftpUsername')
                        ? $('#ftpUsername').value
                        : '';
                    payload.ftpPassword = $('#ftpPassword')
                        ? $('#ftpPassword').value
                        : '';
                    payload.ftpRemotePath = $('#ftpRemotePath')
                        ? $('#ftpRemotePath').value
                        : '';
                    payload.ftpFileName = $('#ftpFileName')
                        ? $('#ftpFileName').value
                        : '';

                    const destPath = $('#ftpDestPath');
                    if (destPath) payload.ftpDestPath = destPath.value;

                    // Read ClickHouse destination fields if selected
                    const selectedDst = document.querySelector(
                        '.type-card.selected[data-dst]',
                    );
                    if (
                        selectedDst &&
                        selectedDst.dataset.dst === 'clickhouse'
                    ) {
                        payload.ch_cluster = $('#chStaticCluster')
                            ? $('#chStaticCluster').value
                            : '';
                        payload.ch_node = $('#chStaticNode')
                            ? $('#chStaticNode').value
                            : '';
                        payload.ch_service = $('#chStaticService')
                            ? $('#chStaticService').value
                            : '';
                        payload.chDatabase = $('#dynChDb')
                            ? $('#dynChDb').value
                            : 'analytics';
                        payload.chTable = $('#dynChTable')
                            ? $('#dynChTable').value
                            : '';

                        // Fix: The backend validation requires 'service_name', so we map the ClickHouse service to it.
                        payload.service_name = payload.ch_service;
                    }
                } else if (selectedSrc && selectedSrc.dataset.src === 'local_path') {
                    payload.conn_type = 'LOCAL';
                    payload.dataflow_type = 'nocAlarmStream';
                    payload.ingestion = 'BackEnd';
                    payload.localPath = $('#localPath') ? $('#localPath').value : '';
                    payload.localFilePattern = $('#localFilePattern') ? $('#localFilePattern').value : '';
                } else if (selectedSrc && selectedSrc.dataset.src === 'endpoint') {
                    payload.conn_type = 'ENDPOINT';
                    payload.dataflow_type = 'nocAlarmStream';
                    payload.ingestion = 'BackEnd';
                    payload.endpointUrl = $('#endpointUrl') ? $('#endpointUrl').value : '';
                    payload.endpointProtocol = $('#endpointProtocol') ? $('#endpointProtocol').value : 'http';
                    payload.nifiListenPort = $('#nifiListenPort') ? $('#nifiListenPort').value : '9080';
                    payload.nifiBasePath = $('#nifiBasePath') ? $('#nifiBasePath').value : 'aviat';
                }

                const epsInput = $('#eventsPerSecond');
                const epsValue = epsInput && epsInput.value !== '' ? Number(epsInput.value) : 100;
                payload.eps = Number.isFinite(epsValue) ? epsValue : 100;
                const replayMode = $('#replayMode') ? $('#replayMode').value : 'continuous';
                payload.replay_mode = replayMode;
                payload.continuous = replayMode === 'continuous';
                // HTTP-v2 publishes normalized events through AgenticNOC's
                // PostgreSQL outbox. The raw topic is a legacy-flow
                // diagnostic and is not this stream's acceptance signal.
                payload.topic = 'noc.alarm.normalized.v1';
                payload.vendor = $('#nocVendor')?.value || 'aviat';

                // Fallback for Fin_Data fields if present in form (e.g. Service Drilldown flow)
                const finDataPanel = document.querySelector('.conn-fields[data-conn="Fin_Data"]');
                if (finDataPanel && (finDataPanel.style.display !== 'none' || payload.dataflow_type === 'fyersStream')) {
                    if (!payload.conn_type) payload.conn_type = 'Fin_Data';
                    if (!payload.sourceType && $('#addSourceType')) payload.sourceType = $('#addSourceType').value;
                    if (!payload.ApiKey && $('input[name="ApiKey"]')) payload.ApiKey = $('input[name="ApiKey"]').value;
                    if (!payload.SecretKey && $('input[name="SecretKey"]')) payload.SecretKey = $('input[name="SecretKey"]').value;

                    const tokenEl = $('#fyersAccessToken') || $('textarea[name="access_token"]') || $('input[name="access_token"]');
                    if (tokenEl && tokenEl.value.trim()) {
                        payload.access_token = tokenEl.value.trim();
                    }

                    const symListSelect = $('#addSymbolsList') || $('#realSymbolsSelect');
                    if (symListSelect && (!payload.symbolsList || payload.symbolsList.length === 0)) {
                        const selectedOpts = Array.from(symListSelect.selectedOptions).map((o) => o.value).filter(Boolean);
                        if (selectedOpts.length > 0) {
                            payload.symbolsList = selectedOpts;
                        }
                    }
                }

                const requestBody = {
                    'user-action': editModeId ? 'edit' : 'add',
                    json_data: payload,
                };
                if (editModeId) requestBody['dataflow_id'] = editModeId;

                fetch('/PlatformIO/StreamIngress/', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken':
                            document.querySelector(
                                '[name="csrfmiddlewaretoken"]',
                            )?.value || '',
                    },
                    body: JSON.stringify(requestBody),
                })
                    .then((res) => res.json())
                    .then(async (res) => {
                        if (res.success || res.status === 'success') {
                            btn.innerHTML = originalHtml;
                            btn.disabled = false;
                            if (res.dataflow_info) {
                                window.dataflow_info = res.dataflow_info;
                                renderDataflowCards();
                                showList();
                            } else {
                                window.location.reload();
                            }
                            const streamId = res.dataflow_id || editModeId;
                            const target = (window.dataflow_info || []).find((item) => item.dataflow_id === streamId);
                            if (streamId && target && target.control_plane_contract) {
                                try {
                                    await controlRuntime(streamId, 'start');
                                    showToast(editModeId ? 'Saved and restarted' : 'Created and started', 'ok');
                                } catch (error) {
                                    // Registration is retained so the user can
                                    // inspect the exact runtime error and retry.
                                    showToast(`Saved, but start failed: ${error.message}`, 'err');
                                }
                            } else {
                                showToast(editModeId ? 'Saved successfully' : 'Created successfully', 'ok');
                            }
                        } else {
                            showToast(
                                'Error saving dataflow: ' +
                                (res.error_msg ||
                                    res.message ||
                                    'Unknown error'),
                                'err',
                            );
                            btn.innerHTML = originalHtml;
                            btn.disabled = false;
                        }
                    })
                    .catch(() => {
                        showToast('Network error saving stream', 'err');
                        btn.innerHTML = originalHtml;
                        btn.disabled = false;
                    });
            });
        }
    });

    // Initialize when DOM is ready
    document.addEventListener('DOMContentLoaded', () => {
        initStreamWizard();
        window.initDrilldown();

        // Wait for variables to be injected by Django
        setTimeout(() => {
            if (window.dataflow_info) {
                renderDataflowCards();
                initGlobalThroughputTracking();
            }
        }, 500);

        const newBtn = $('#btnNewStream');
        if (newBtn) {
            newBtn.addEventListener('click', () => {
                editModeId = null;
                $('#streamName').value = '';
                if (window.prefillDrilldown) window.prefillDrilldown();
                if ($('#startDate')) $('#startDate').value = '';
                if ($('#startTime')) $('#startTime').value = '';
            });
        }
    });

    window.updateSourceFieldsVisibility = function () {
        const sourceSelect = document.getElementById('addSourceType');
        const apiSecretRow = document.getElementById('apiSecretRow');
        const apiKeyField = document.getElementById('apiKeyField');
        const secretKeyField = document.getElementById('secretKeyField');
        const accessTokenField = document.getElementById('accessTokenField');

        const val = sourceSelect ? (sourceSelect.value || '').toLowerCase() : '';
        const dft = ($('#addDataFlowType')?.value || '').toLowerCase();

        if (val.includes('fyers') || dft.includes('fyers')) {
            if (apiSecretRow) apiSecretRow.style.display = 'none';
            if (apiKeyField) apiKeyField.style.display = 'none';
            if (secretKeyField) secretKeyField.style.display = 'none';
            if (accessTokenField) accessTokenField.style.display = 'block';
        } else {
            if (apiSecretRow) apiSecretRow.style.display = '';
            if (apiKeyField) apiKeyField.style.display = '';
            if (secretKeyField) secretKeyField.style.display = '';
            if (accessTokenField) accessTokenField.style.display = 'none';
        }
    };

    // ====== DESTINATION DRILLDOWN LOGIC ======
    window.initDrilldown = function () {
        const drillContainer = document.getElementById('destDrill');
        if (!drillContainer) return;

        const clusterOpts = document.getElementById('ddClusterOpts');
        const nodeOpts = document.getElementById('ddNodeOpts');
        const svcOpts = document.getElementById('ddSvcOpts');

        const stepCluster = document.querySelector('[data-dd="cluster"]');
        const stepNode = document.querySelector('[data-dd="node"]');
        const stepSvc = document.querySelector('[data-dd="service"]');

        const summary = document.getElementById('ddSummary');
        const sCluster = document.getElementById('ddCrumbCluster');
        const sNode = document.getElementById('ddCrumbNode');
        const sService = document.getElementById('ddCrumbService');

        const inputApp = document.querySelector('input[name="app_name"]');
        const inputSvc = document.getElementById('addServiceName');

        const dftSection = document.getElementById('dftSection');
        const errMsg = document.getElementById('serviceNotSupportedMsg');
        const dftSelect = document.getElementById('dftSelect');
        const inputDft = document.getElementById('addDataFlowType');
        const inputIng = document.getElementById('addIngestion');
        const ingestionSelect = document.getElementById('ingestionSelect');

        if (!window.cluster_info) return;

        if (dftSelect && inputDft) {
            dftSelect.onchange = () => {
                inputDft.value = dftSelect.value;
            };
        }
        if (ingestionSelect && inputIng) {
            ingestionSelect.onchange = () => {
                inputIng.value = ingestionSelect.value;
            };
        }

        function buildClusters () {
            clusterOpts.innerHTML = '';
            Object.values(window.cluster_info).forEach((c) => {
                const btn = document.createElement('button');
                btn.className = 'dd-opt';
                btn.dataset.val = c.cluster_name;

                const nodeInfo = c.node_info || {};
                const nodeCount = Object.keys(nodeInfo).length;

                btn.innerHTML = `${c.cluster_name} <span class="dd-opt-meta">${nodeCount} nodes</span>`;

                btn.onclick = (e) => {
                    if (e) e.preventDefault();
                    inputApp.value = c.cluster_name;

                    clusterOpts
                        .querySelectorAll('.dd-opt')
                        .forEach((b) => b.classList.remove('selected'));
                    btn.classList.add('selected');

                    sCluster.textContent = c.cluster_name;
                    stepCluster.classList.remove('active');
                    stepCluster.classList.add('done');
                    stepNode.classList.remove('disabled', 'done');
                    stepNode.classList.add('active');
                    inputSvc.value = '';
                    stepSvc.classList.remove('active', 'done');
                    stepSvc.classList.add('disabled');
                    svcOpts.innerHTML =
                        '<span style="font-size:12px; color:var(--ink-4); font-style:italic;">Pick a node first.</span>';
                    summary.style.display = 'none';
                    dftSection.style.display = 'none';
                    errMsg.style.display = 'none';

                    const sca = document.getElementById('serviceConfigArea');
                    if (sca) sca.style.display = 'none';

                    buildNodes(c.node_info || {});
                };
                clusterOpts.appendChild(btn);
            });
        }
        window.buildClustersGlobal = buildClusters;

        function buildNodes (nodeInfo) {
            nodeOpts.innerHTML = '';
            const nodes = Object.values(nodeInfo);
            if (nodes.length === 0) {
                nodeOpts.innerHTML =
                    '<span style="font-size:12px; color:var(--ink-4); font-style:italic;">No nodes available.</span>';
                return;
            }
            nodes.forEach((n) => {
                const btn = document.createElement('button');
                btn.className = 'dd-opt';
                btn.dataset.val = n.node_name;
                btn.textContent = n.node_name;

                btn.onclick = (e) => {
                    if (e) e.preventDefault();

                    nodeOpts
                        .querySelectorAll('.dd-opt')
                        .forEach((b) => b.classList.remove('selected'));
                    btn.classList.add('selected');

                    sNode.textContent = n.node_name;
                    stepNode.classList.remove('active');
                    stepNode.classList.add('done');
                    stepSvc.classList.remove('disabled', 'done');
                    stepSvc.classList.add('active');

                    inputSvc.value = '';
                    summary.style.display = 'none';
                    dftSection.style.display = 'none';
                    errMsg.style.display = 'none';

                    const scaNode =
                        document.getElementById('serviceConfigArea');
                    if (scaNode) scaNode.style.display = 'none';

                    buildServices(n.service_info || {});
                };
                nodeOpts.appendChild(btn);
            });
        }

        function buildServices (serviceInfo) {
            svcOpts.innerHTML = '';
            const svcs = Object.values(serviceInfo);
            if (svcs.length === 0) {
                svcOpts.innerHTML =
                    '<span style="font-size:12px; color:var(--ink-4); font-style:italic;">No services on this node.</span>';
                return;
            }

            svcs.forEach((s) => {
                const btn = document.createElement('button');
                btn.className = 'dd-opt';
                btn.dataset.val = s.service_name;
                btn.textContent = s.service_name;

                btn.onclick = (e) => {
                    if (e) e.preventDefault();

                    inputSvc.value = s.service_name;

                    svcOpts
                        .querySelectorAll('.dd-opt')
                        .forEach((b) => b.classList.remove('selected'));
                    btn.classList.add('selected');

                    sService.textContent = s.service_name;
                    stepSvc.classList.remove('active');
                    stepSvc.classList.add('done');

                    summary.style.display = 'block';

                    const activeSubCard = document.querySelector(
                        '.sub-type-card.selected',
                    );
                    const connType = activeSubCard
                        ? activeSubCard.dataset.src
                        : '';

                    // Regular Fin_Data / Dataflow logic
                    const dfTypes =
                        s.dataflow_types ||
                        (typeof window.dataflowConfig !== 'undefined' &&
                            s.service_type
                            ? window.dataflowConfig[s.service_type]
                            : []) ||
                        [];
                    if (dfTypes && dfTypes.length > 0) {
                        dftSection.style.display = 'block';
                        errMsg.style.display = 'none';
                        buildDataflowTypes(dfTypes);
                    } else {
                        dftSection.style.display = 'none';
                        if (
                            connType !== 'Fin_Data' &&
                            connType !== 'churnData'
                        ) {
                            errMsg.style.display = 'block';
                        } else {
                            errMsg.style.display = 'none';
                        }
                        const sca =
                            document.getElementById('serviceConfigArea');
                        if (sca) sca.style.display = 'none';
                    }

                    if (connType === 'Fin_Data' || connType === 'churnData') {
                        fetchConnTypeConfig(connType, s.service_name);
                    }
                };
                svcOpts.appendChild(btn);
            });
        }

        async function fetchConnTypeConfig (connType, serviceName) {
            const csrfToken = window.csrfToken || '';
            try {
                const res = await fetch(
                    '/PlatformIO/APIv1/GetConnTypeConfig/',
                    {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                            'X-CSRFToken': csrfToken,
                        },
                        body: JSON.stringify({
                            conn_type: connType,
                            service_name: serviceName,
                        }),
                    },
                );
                if (res.ok) {
                    const response = await res.json();
                    if (response.success && response.filter_config) {
                        const config = response.filter_config;
                        if (connType === 'Fin_Data') {
                            // API returns { symbols_list: { symbols_list: [...], source_list: [...] } }
                            // so we need to unwrap one level
                            const inner =
                                config.symbols_list &&
                                    typeof config.symbols_list === 'object' &&
                                    !Array.isArray(config.symbols_list)
                                    ? config.symbols_list
                                    : config;
                            const symbols_list = inner.symbols_list || [];
                            const source_list = inner.source_list || [];

                            const sourceSelect =
                                document.getElementById('addSourceType');
                            if (sourceSelect) {
                                sourceSelect.innerHTML =
                                    '<option value="">--------</option>';
                                source_list.forEach((s) => {
                                    const opt =
                                        document.createElement('option');
                                    opt.value = s;
                                    opt.textContent = s;
                                    sourceSelect.appendChild(opt);
                                });
                                sourceSelect.onchange = function () {
                                    if (window.updateSourceFieldsVisibility) window.updateSourceFieldsVisibility();
                                };
                                if (window.updateSourceFieldsVisibility) window.updateSourceFieldsVisibility();
                            }

                            const symbolsSelect =
                                document.getElementById('addSymbolsList');
                            if (symbolsSelect) {
                                symbolsSelect.innerHTML = '';
                                symbols_list.forEach((s) => {
                                    const opt =
                                        document.createElement('option');
                                    opt.value = s;
                                    opt.textContent = s;
                                    symbolsSelect.appendChild(opt);
                                });
                                setTimeout(() => {
                                    initCustomMultiSelect(symbolsSelect);
                                }, 0);
                            }
                        }

                        const serviceConfigArea =
                            document.getElementById('serviceConfigArea');
                        if (serviceConfigArea) {
                            serviceConfigArea.style.display = 'block';
                            const errMsg = document.getElementById(
                                'serviceNotSupportedMsg',
                            );
                            if (errMsg) errMsg.style.display = 'none';
                            document
                                .querySelectorAll(
                                    '#serviceConfigArea .conn-fields',
                                )
                                .forEach((f) => (f.style.display = 'none'));
                            const targetField = document.querySelector(
                                `#serviceConfigArea .conn-fields[data-conn="${connType}"]`,
                            );
                            if (targetField)
                                targetField.style.display = 'block';
                        }
                    }
                }
            } catch (e) {
                // eslint-disable-next-line no-console
                console.error('Failed to fetch connection config:', e);
            }
        }

        function buildDataflowTypes (supportedTypes) {
            const dftGrid = document.getElementById('dftGrid');

            if (!supportedTypes || supportedTypes.length === 0) {
                errMsg.style.display = 'block';
                dftSection.style.display = 'none';
                dftSection.classList.remove('active');
                inputDft.value = '';
                if (dftGrid) dftGrid.innerHTML = '';
                return;
            }

            errMsg.style.display = 'none';
            dftSection.style.display = 'block';
            dftSection.classList.add('active');

            if (dftGrid) {
                dftGrid.innerHTML = '';
                supportedTypes.forEach((type) => {
                    let displayName = type
                        .replace(/_/g, ' ')
                        .replace(/([a-z])([A-Z])/g, '$1 $2')
                        .replace(/([A-Z]+)([A-Z][a-z])/g, '$1 $2')
                        .trim();
                    displayName =
                        displayName.charAt(0).toUpperCase() +
                        displayName.slice(1);

                    const categoryMap = {
                        CDR: { label: 'CDR', color: '#4f46e5', bg: '#eef2ff' },
                        RIBBON: {
                            label: 'RIBBON',
                            color: '#7c3aed',
                            bg: '#f5f3ff',
                        },
                        GROUNDHOG: {
                            label: 'GROUNDHOG',
                            color: '#0891b2',
                            bg: '#ecfeff',
                        },
                        NEP: { label: 'NEP', color: '#059669', bg: '#ecfdf5' },
                        MNP: { label: 'MNP', color: '#d97706', bg: '#fffbeb' },
                        CHURN: {
                            label: 'CHURN',
                            color: '#dc2626',
                            bg: '#fef2f2',
                        },
                        ROTATIONAL: {
                            label: 'ROTATIONAL',
                            color: '#9333ea',
                            bg: '#fdf4ff',
                        },
                        USERPROFILE: {
                            label: 'USERPROFILE',
                            color: '#0284c7',
                            bg: '#f0f9ff',
                        },
                        NETWORKPROFILE: {
                            label: 'NETWORKPROFILE',
                            color: '#0d9488',
                            bg: '#f0fdfa',
                        },
                        PREPAID: {
                            label: 'PREPAID',
                            color: '#16a34a',
                            bg: '#f0fdf4',
                        },
                        POSTPAID: {
                            label: 'POSTPAID',
                            color: '#2563eb',
                            bg: '#eff6ff',
                        },
                        RECHARGE: {
                            label: 'RECHARGE',
                            color: '#ea580c',
                            bg: '#fff7ed',
                        },
                        BUSINESSPROFILE: {
                            label: 'BUSINESS',
                            color: '#0f766e',
                            bg: '#f0fdfa',
                        },
                        GRIDCLASSIFICATION: {
                            label: 'GRID',
                            color: '#6d28d9',
                            bg: '#f5f3ff',
                        },
                        HISTORICALSTOCK: {
                            label: 'HISTORICAL',
                            color: '#b45309',
                            bg: '#fffbeb',
                        },
                        STOCKFUNDAMENTAL: {
                            label: 'FUNDAMENTAL',
                            color: '#0369a1',
                            bg: '#f0f9ff',
                        },
                        TICKERDATA: {
                            label: 'TICKER',
                            color: '#059669',
                            bg: '#ecfdf5',
                        },
                        OPTIONDATA: {
                            label: 'OPTIONS',
                            color: '#7c3aed',
                            bg: '#f5f3ff',
                        },
                        DUMMYSTREAM: {
                            label: 'DUMMY',
                            color: '#db2777',
                            bg: '#fdf2f8',
                        },
                    };

                    const typeUpper = type.toUpperCase().replace(/[_\s]/g, '');
                    let catInfo = {
                        label: 'STANDARD',
                        color: '#64748b',
                        bg: '#f8fafc',
                    };
                    for (const [key, val] of Object.entries(categoryMap)) {
                        if (typeUpper.startsWith(key)) {
                            catInfo = val;
                            break;
                        }
                    }

                    const iconMap = {
                        CDR: '<svg class="ic" viewBox="0 0 24 24" style="width:18px;height:18px;"><path d="M22 16.92v3a2 2 0 01-2.18 2 19.79 19.79 0 01-8.63-3.07A19.5 19.5 0 013.07 9.8a19.79 19.79 0 01-3.07-8.63A2 2 0 012 0h3a2 2 0 012 1.72c.127.96.361 1.903.7 2.81a2 2 0 01-.45 2.11L6.06 7.87a16 16 0 006.07 6.07l1.27-1.27a2 2 0 012.11-.45c.907.339 1.85.573 2.81.7A2 2 0 0122 14.92v2z"/></svg>',
                        RIBBON: '<svg class="ic" viewBox="0 0 24 24" style="width:18px;height:18px;"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/></svg>',
                        GROUNDHOG:
                            '<svg class="ic" viewBox="0 0 24 24" style="width:18px;height:18px;"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>',
                        NEP: '<svg class="ic" viewBox="0 0 24 24" style="width:18px;height:18px;"><path d="M12 2L2 7l10 5 10-5-10-5z"/><path d="M2 17l10 5 10-5M2 12l10 5 10-5"/></svg>',
                        MNP: '<svg class="ic" viewBox="0 0 24 24" style="width:18px;height:18px;"><path d="M16 3h5v5M4 20L21 3"/><path d="M21 16v5h-5M15 15l6 6M4 4l5 5"/></svg>',
                        CHURN: '<svg class="ic" viewBox="0 0 24 24" style="width:18px;height:18px;"><path d="M17 21v-2a4 4 0 00-4-4H5a4 4 0 00-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 00-3-3.87M16 3.13a4 4 0 010 7.75"/></svg>',
                        ROTATIONAL:
                            '<svg class="ic" viewBox="0 0 24 24" style="width:18px;height:18px;"><path d="M1 4v6h6M23 20v-6h-6"/><path d="M20.49 9A9 9 0 005.64 5.64L1 10m22 4l-4.64 4.36A9 9 0 013.51 15"/></svg>',
                        USERPROFILE:
                            '<svg class="ic" viewBox="0 0 24 24" style="width:18px;height:18px;"><path d="M20 21v-2a4 4 0 00-4-4H8a4 4 0 00-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>',
                        NETWORKPROFILE:
                            '<svg class="ic" viewBox="0 0 24 24" style="width:18px;height:18px;"><rect x="2" y="3" width="20" height="14" rx="2"/><path d="M8 21h8M12 17v4"/></svg>',
                        PREPAID:
                            '<svg class="ic" viewBox="0 0 24 24" style="width:18px;height:18px;"><line x1="12" y1="1" x2="12" y2="23"/><path d="M17 5H9.5a3.5 3.5 0 000 7h5a3.5 3.5 0 010 7H6"/></svg>',
                        POSTPAID:
                            '<svg class="ic" viewBox="0 0 24 24" style="width:18px;height:18px;"><rect x="1" y="4" width="22" height="16" rx="2"/><line x1="1" y1="10" x2="23" y2="10"/></svg>',
                        RECHARGE:
                            '<svg class="ic" viewBox="0 0 24 24" style="width:18px;height:18px;"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/></svg>',
                        BUSINESSPROFILE:
                            '<svg class="ic" viewBox="0 0 24 24" style="width:18px;height:18px;"><rect x="2" y="7" width="20" height="14" rx="2"/><path d="M16 7V5a2 2 0 00-2-2h-4a2 2 0 00-2 2v2"/></svg>',
                        GRIDCLASSIFICATION:
                            '<svg class="ic" viewBox="0 0 24 24" style="width:18px;height:18px;"><rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/></svg>',
                        HISTORICALSTOCK:
                            '<svg class="ic" viewBox="0 0 24 24" style="width:18px;height:18px;"><path d="M3 3v18h18M7 16l4-4 4 4 6-6"/></svg>',
                        STOCKFUNDAMENTAL:
                            '<svg class="ic" viewBox="0 0 24 24" style="width:18px;height:18px;"><path d="M18 20V10M12 20V4M6 20v-6"/></svg>',
                        TICKERDATA:
                            '<svg class="ic" viewBox="0 0 24 24" style="width:18px;height:18px;"><path d="M3 3v18h18M7 16l4-4 4 4 6-6"/></svg>',
                        OPTIONDATA:
                            '<svg class="ic" viewBox="0 0 24 24" style="width:18px;height:18px;"><path d="M18 20V10M12 20V4M6 20v-6"/></svg>',
                        DUMMYSTREAM:
                            '<svg class="ic" viewBox="0 0 24 24" style="width:18px;height:18px;"><path d="M9.3 21l-3.3-3.3a5.55 5.55 0 011-8.54L10 6V3M14 3v3l3 3.16a5.55 5.55 0 011 8.54L14.7 21M9 3h6M10 13h4"/></svg>',
                    };

                    let iconSvg =
                        '<svg class="ic" viewBox="0 0 24 24" style="width:18px;height:18px;"><path d="M21 16V8a2 2 0 00-1-1.73l-7-4a2 2 0 00-2 0l-7 4A2 2 0 003 8v8a2 2 0 001 1.73l7 4a2 2 0 002 0l7-4A2 2 0 0021 16z"/></svg>';
                    for (const [key, val] of Object.entries(iconMap)) {
                        if (typeUpper.startsWith(key)) {
                            iconSvg = val;
                            break;
                        }
                    }

                    let desc = 'Dataflow processing pipeline.';
                    const lowerType = type.toLowerCase();
                    if (lowerType.includes('daily'))
                        desc = 'Daily scheduled batch ingestion.';
                    else if (lowerType.includes('monthly'))
                        desc = 'Monthly scheduled batch ingestion.';
                    else if (lowerType.includes('churn'))
                        desc = 'Customer retention data pipeline.';
                    else if (
                        lowerType.includes('stock') ||
                        lowerType.includes('fin')
                    )
                        desc = 'Financial market data pipeline.';
                    else if (lowerType.includes('network'))
                        desc = 'Network profile data ingestion.';
                    else if (lowerType.includes('profile'))
                        desc = 'User profile data pipeline.';
                    else if (lowerType.includes('cdr'))
                        desc = 'Call Detail Record ingestion pipeline.';
                    else if (lowerType.includes('recharge'))
                        desc = 'Recharge data batch pipeline.';
                    else if (
                        lowerType.includes('prepaid') ||
                        lowerType.includes('postpaid')
                    )
                        desc = 'Subscriber data ingestion pipeline.';
                    else if (lowerType.includes('dummy'))
                        desc = 'End-to-end dummy ticker data simulator.';

                    const card = document.createElement('div');
                    card.className = 'dft-card';
                    card.dataset.dft = type;

                    card.innerHTML = `
                        <div class="dft-icon">${iconSvg}</div>
                        <div class="dft-tag dft-tag--colored" style="color:${catInfo.color}; background:${catInfo.bg}; border-radius:4px; padding:2px 7px; font-size:9px; font-weight:600; letter-spacing:0.08em; border:none;">${catInfo.label}</div>
                        <div class="dft-name">${displayName}</div>
                        <div class="dft-desc">${desc}</div>
                    `;

                    card.onclick = () => {
                        dftGrid
                            .querySelectorAll('.dft-card')
                            .forEach((c) => c.classList.remove('selected'));
                        card.classList.add('selected');
                        inputDft.value = type;
                        inputDft.dispatchEvent(new Event('change'));
                        if (window.updateSourceFieldsVisibility) window.updateSourceFieldsVisibility();
                    };

                    dftGrid.appendChild(card);
                });
            }

            if (inputDft.value && dftGrid) {
                const existingCard = dftGrid.querySelector(
                    `.dft-card[data-dft="${inputDft.value}"]`,
                );
                if (existingCard) existingCard.classList.add('selected');
            }
            if (inputIng.value) {
                ingestionSelect.value = inputIng.value;
            }
        }

        window.prefillDrilldown = function (
            appName,
            serviceName,
            dataflowType,
            ingestion,
        ) {
            buildClusters();

            let targetCluster = appName && appName !== 'None' ? appName : null;
            let targetNode = null;

            if (serviceName && window.cluster_info) {
                for (const c of Object.values(window.cluster_info)) {
                    if (c.node_info) {
                        for (const n of Object.values(c.node_info)) {
                            if (n.service_info) {
                                for (const s of Object.values(n.service_info)) {
                                    if (s.service_name === serviceName) {
                                        targetCluster = c.cluster_name;
                                        targetNode = n.node_name;
                                        break;
                                    }
                                }
                            }
                            if (targetNode) break;
                        }
                    }
                    if (targetNode) break;
                }
            }

            if (!targetCluster) {
                inputApp.value = '';
                inputSvc.value = '';
                stepNode.classList.remove('active');
                stepNode.classList.add('disabled');
                stepSvc.classList.remove('active');
                stepSvc.classList.add('disabled');
                nodeOpts.innerHTML =
                    '<span style="font-size:12px; color:var(--ink-4); font-style:italic;">Pick a cluster first.</span>';
                svcOpts.innerHTML =
                    '<span style="font-size:12px; color:var(--ink-4); font-style:italic;">Pick a node first.</span>';
                summary.style.display = 'none';
                dftSection.style.display = 'none';
                errMsg.style.display = 'none';
                return;
            }

            setTimeout(() => {
                const cBtn = clusterOpts.querySelector(
                    `[data-val="${targetCluster}"]`,
                );
                if (cBtn) {
                    cBtn.click();
                    if (targetNode) {
                        const nBtn = nodeOpts.querySelector(
                            `[data-val="${targetNode}"]`,
                        );
                        if (nBtn) {
                            nBtn.click();
                            const sBtn = svcOpts.querySelector(
                                `[data-val="${serviceName}"]`,
                            );
                            if (sBtn) {
                                inputDft.value = dataflowType || '';
                                inputIng.value = ingestion || '';
                                sBtn.click();
                            }
                        }
                    }
                }
            }, 10);
        };

        buildClusters();
    };
})();
window.bindClickhouseStaticDropdowns = function () {
    const selCluster = document.getElementById('chStaticCluster');
    const selNode = document.getElementById('chStaticNode');
    const selService = document.getElementById('chStaticService');
    if (!selCluster || !selNode || !selService) return;

    // Clear existing
    selCluster.innerHTML = '<option value="">Select Cluster...</option>';
    selNode.innerHTML = '<option value="">Select Node...</option>';
    selService.innerHTML = '<option value="">Select Service...</option>';

    if (!window.cluster_info) return;

    // Populate clusters using Object.values
    Object.values(window.cluster_info).forEach((c) => {
        const opt = document.createElement('option');
        opt.value = c.cluster_name;
        opt.textContent = c.cluster_name;
        selCluster.appendChild(opt);
    });

    selCluster.addEventListener('change', () => {
        const clusterName = selCluster.value;
        selNode.innerHTML = '<option value="">Select Node...</option>';
        selService.innerHTML = '<option value="">Select Service...</option>';
        document.getElementById('dynChDb').innerHTML =
            '<option value="">Select Service First...</option>';
        document.getElementById('chTableList').innerHTML = '';

        const cl = Object.values(window.cluster_info).find(
            (c) => c.cluster_name === clusterName,
        );
        if (cl && cl.node_info) {
            Object.values(cl.node_info).forEach((n) => {
                const opt = document.createElement('option');
                opt.value = n.node_name;
                opt.textContent = n.node_name;
                selNode.appendChild(opt);
            });
        }
    });

    selNode.addEventListener('change', () => {
        const clusterName = selCluster.value;
        const nodeName = selNode.value;
        selService.innerHTML = '<option value="">Select Service...</option>';
        document.getElementById('dynChDb').innerHTML =
            '<option value="">Select Service First...</option>';
        document.getElementById('chTableList').innerHTML = '';

        const cl = Object.values(window.cluster_info).find(
            (c) => c.cluster_name === clusterName,
        );
        if (cl && cl.node_info) {
            const nd = Object.values(cl.node_info).find(
                (n) => n.node_name === nodeName,
            );
            if (nd && nd.service_info) {
                Object.values(nd.service_info).forEach((s) => {
                    // Only show ClickHouse services
                    if (s.service_name.toLowerCase().includes('clickhouse')) {
                        const opt = document.createElement('option');
                        opt.value = s.service_name;
                        opt.textContent = s.service_name;
                        selService.appendChild(opt);
                    }
                });
            }
        }
    });

    selService.addEventListener('change', () => {
        const svcName = selService.value;
        if (svcName) {
            if (typeof fetchClickhouseSchemas === 'function') {
                fetchClickhouseSchemas(svcName);
            }
        } else {
            document.getElementById('dynChDb').innerHTML =
                '<option value="">Select Service First...</option>';
            document.getElementById('chTableList').innerHTML = '';
        }
    });
};

async function fetchClickhouseSchemas (serviceName) {
    const dbSelect = document.getElementById('dynChDb');
    if (!dbSelect) return;

    dbSelect.innerHTML = '<option value="">Loading databases...</option>';

    try {
        const response = await fetch('/PlatformIO/APIv1/GetClickhouseSchema/', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ service_name: serviceName }),
        });
        const res = await response.json();

        dbSelect.innerHTML = ''; // clear options
        if (res.success) {
            if (res.results && res.results.length > 0) {
                res.results.forEach((db) => {
                    const opt = document.createElement('option');
                    opt.value = db;
                    opt.textContent = db;
                    dbSelect.appendChild(opt);
                });

                // Automatically fetch tables for the first loaded database
                fetchClickhouseTables(serviceName, res.results[0]);

                // Add event listener to fetch tables when DB changes
                dbSelect.onchange = (e) =>
                    fetchClickhouseTables(serviceName, e.target.value);
            } else {
                dbSelect.innerHTML =
                    '<option value="">No databases found</option>';
            }
        } else {
            // eslint-disable-next-line no-console
            console.error('Failed to load ClickHouse schemas:', res.message);
            dbSelect.innerHTML = `<option value="">Error: ${res.message}</option>`;
        }
    } catch (e) {
        // eslint-disable-next-line no-console
        console.error('Error fetching ClickHouse schemas:', e);
        dbSelect.innerHTML = '<option value="">Network error</option>';
    }
}

async function fetchClickhouseTables (serviceName, dbName) {
    const tableList = document.getElementById('chTableList');
    if (!tableList) return;

    tableList.innerHTML = ''; // clear current options

    try {
        const response = await fetch('/PlatformIO/APIv1/GetClickhouseSchema/', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                service_name: serviceName,
                db_name: dbName,
            }),
        });
        const res = await response.json();

        if (res.success && res.results) {
            res.results.forEach((tbl) => {
                const opt = document.createElement('option');
                opt.value = tbl;
                tableList.appendChild(opt);
            });
        } else {
            // eslint-disable-next-line no-console
            console.error('Failed to load ClickHouse tables:', res.message);
        }
    } catch (e) {
        // eslint-disable-next-line no-console
        console.error('Error fetching ClickHouse tables:', e);
    }
}

document.addEventListener('DOMContentLoaded', () => {
    if (typeof window.bindClickhouseStaticDropdowns === 'function') {
        window.bindClickhouseStaticDropdowns();
    }
});
