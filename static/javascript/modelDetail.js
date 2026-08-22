const logs = JSON.parse(document.getElementById('log-data').textContent);
const modelData = JSON.parse(
    document.getElementById('model-data').textContent,
)[0];
//const perf = JSON.parse(document.getElementById('performance-data').textContent);

const STATUS_CLASS = {
    TrainingInProcess: 'pill-info',
    TrainingComplete: 'pill-success',
    TrainingFailed: 'pill-danger',
    Scheduled: 'pill-neutral',
};

document.querySelectorAll('.pill[data-status]').forEach((pill) => {
    const cls = STATUS_CLASS[pill.dataset.status];
    if (cls) pill.classList.add(cls);
});

function formatLabel (key) {
    return key
        .replace(/([A-Z])/g, ' $1')
        .replaceAll('_', ' ')
        .replace(/\b\w/g, (c) => c.toUpperCase());
}

function smartRound (val) {
    if (val === null || val === undefined || val === '') return '--';
    const n = Number(val);
    if (!isFinite(n)) return String(val);
    const abs = Math.abs(n);
    if (abs === 0) return '0';
    if (abs >= 1_000_000) {
        const m = n / 1_000_000;
        return (m % 1 === 0 ? m.toFixed(0) : m.toFixed(1)) + 'M';
    }
    if (abs >= 1_000) {
        const k = n / 1_000;
        return (k % 1 === 0 ? k.toFixed(0) : k.toFixed(1)) + 'K';
    }
    if (n % 1 === 0) return String(n);
    if (abs < 10) return n.toFixed(4);
    return n.toFixed(2);
}

function updateAlgo (tab) {
    const container = document.getElementById('dynamic-kpis');
    if (!container) return;
    container.innerHTML = '';
    const skipFields = ['algoType', 'algoCategory', 'algoId', 'first'];
    Object.entries(tab.dataset).forEach(([key, val]) => {
        if (skipFields.includes(key) || !val) return;
        const kpi = document.createElement('div');
        kpi.className = 'kpi';
        const valEl = document.createElement('div');
        valEl.className = 'v';
        valEl.textContent = smartRound(val);
        const lblEl = document.createElement('div');
        lblEl.className = 'l';
        lblEl.textContent = formatLabel(key);
        kpi.appendChild(valEl);
        kpi.appendChild(lblEl);
        container.appendChild(kpi);
    });
}

function isTimeSeriesAlgo (tab) {
    const cat = (tab.dataset.algoCategory || '').toLowerCase();
    return (
        cat.includes('timeseries') ||
        cat.includes('forecast') ||
        cat.includes('time_series')
    );
}

// ─────────────────────────────────────────────────────────────────────────────
// Score-distribution histogram (rendered from a `graph_data*.json` artifact)
// ─────────────────────────────────────────────────────────────────────────────

function markerColor (c) {
    if (c === 'green') return 'var(--ok)';
    if (c === 'red') return 'var(--err)';
    if (c === 'amber' || c === 'yellow' || c === 'orange') return 'var(--warn)';
    return 'var(--navy)';
}

function renderGraphData (graphData) {
    const {
        title,
        x_label: xLabel,
        y_label: yLabel,
        bins,
        counts,
        markers = [],
    } = graphData || {};

    if (
        !Array.isArray(bins) ||
        !Array.isArray(counts) ||
        !bins.length ||
        !counts.length
    ) {
        return '<div style="padding:30px;text-align:center;width:100%;color:var(--ink-3);">No graph data available</div>';
    }

    const W = 760,
        H = 320,
        PAD_L = 56,
        PAD_B = 40,
        PAD_R = 16,
        PAD_T = 16;
    const plotW = W - PAD_L - PAD_R;
    const plotH = H - PAD_T - PAD_B;

    const binWidth = bins.length > 1 ? bins[1] - bins[0] : 1;
    const minX = bins[0];
    const maxX = bins[bins.length - 1] + binWidth;
    const maxCount = Math.max(...counts, 1);

    const xScale = (v) => PAD_L + ((v - minX) / (maxX - minX || 1)) * plotW;
    const barW = Math.max(1, plotW / bins.length - 1);

    const bars = bins
        .map((b, i) => {
            const x = xScale(b);
            const h = (counts[i] / maxCount) * plotH;
            const y = PAD_T + plotH - h;
            return `<rect x="${x.toFixed(2)}" y="${y.toFixed(2)}" width="${barW.toFixed(2)}" height="${h.toFixed(2)}" class="hist-bar"/>`;
        })
        .join('');

    const gridLines = [0.25, 0.5, 0.75, 1]
        .map((f) => {
            const y = PAD_T + plotH * (1 - f);
            return `<line x1="${PAD_L}" y1="${y}" x2="${W - PAD_R}" y2="${y}" class="hist-grid"/>
                <text x="${PAD_L - 8}" y="${y + 4}" class="hist-axis-lbl" text-anchor="end">${Math.round(maxCount * f)}</text>`;
        })
        .join('');

    const tickCount = 5;
    const xLabels = Array.from({ length: tickCount + 1 }, (_, i) => {
        const v = minX + (maxX - minX) * (i / tickCount);
        const x = xScale(v);
        return `<text x="${x.toFixed(2)}" y="${PAD_T + plotH + 18}" class="hist-axis-lbl" text-anchor="middle">${Math.round(v)}</text>`;
    }).join('');

    const markerLines = markers
        .map((m) => {
            const x = xScale(m.value);
            return `<line x1="${x.toFixed(2)}" y1="${PAD_T}" x2="${x.toFixed(2)}" y2="${PAD_T + plotH}" stroke="${markerColor(m.color)}" stroke-width="1.5" stroke-dasharray="5,4"/>`;
        })
        .join('');

    const legend = markers
        .map(
            (m) => `
        <span class="hist-leg"><span class="hist-leg-dot" style="background:${markerColor(m.color)}"></span>${m.label}</span>
    `,
        )
        .join('');

    return `
<div class="perf-col" style="grid-column: 1 / -1;">
    <div class="perf-col-label">${title ? title.toUpperCase() : 'SCORE DISTRIBUTION'}</div>
    <div class="graph-box" style="height:${H}px;">
        <svg width="100%" height="${H}" viewBox="0 0 ${W} ${H}">
            ${gridLines}
            ${bars}
            ${markerLines}
            <line x1="${PAD_L}" y1="${PAD_T}" x2="${PAD_L}" y2="${PAD_T + plotH}" stroke="var(--line)"/>
            <line x1="${PAD_L}" y1="${PAD_T + plotH}" x2="${W - PAD_R}" y2="${PAD_T + plotH}" stroke="var(--line)"/>
            ${xLabels}
            <text x="${PAD_L + plotW / 2}" y="${H - 2}" font-size="12" fill="var(--ink-3)" text-anchor="middle">${xLabel || ''}</text>
            <text x="14" y="${PAD_T + plotH / 2}" font-size="12" fill="var(--ink-3)" text-anchor="middle" transform="rotate(-90 14,${PAD_T + plotH / 2})">${yLabel || ''}</text>
        </svg>
    </div>
    ${markers.length ? `<div class="hist-legend">${legend}</div>` : ''}
</div>`;
}

function updateOverview (tab) {
    const algoId = tab.dataset.algoId;
    const logEntry = Object.values(logs).find(
        (item) => String(item.algo_id) === String(algoId),
    );
    const artifacts = logEntry?.artifacts || [];

    const metricFile = artifacts.find((x) => x.name?.endsWith('_metrics.json'));
    let metrics = metricFile?.metrics || logEntry?.metrics || {};
    if (typeof metrics === 'string') {
        try {
            metrics = JSON.parse(metrics);
        } catch {
            metrics = {};
        }
    }

    // Score-distribution histogram artifact (graph_data*.json), if one was produced
    // for this algorithm.
    const graphFile = artifacts.find((x) =>
        x.name?.toLowerCase().includes('graph_data'),
    );
    const graphData =
        graphFile &&
        typeof graphFile.graph_data === 'object' &&
        graphFile.graph_data
            ? graphFile.graph_data
            : null;

    const perfBox = document.getElementById('perf-split');
    const metricBox = document.getElementById('metric-container');

    // Dynamic section heading: Classification vs Forecast vs Score distribution
    const sectionHead = document.querySelector(
        '#metrics-section .sect-head-bar h3',
    );
    if (sectionHead) {
        if (!metrics.confusion_matrix && graphData) {
            sectionHead.textContent = 'Score distribution';
        } else {
            sectionHead.textContent = isTimeSeriesAlgo(tab)
                ? 'Forecast performance'
                : 'Classification performance';
        }
    }

    perfBox.innerHTML = '';
    metricBox.innerHTML = '';

    if (!Object.keys(metrics).length) {
        metricBox.innerHTML =
            '<div style="padding:30px;text-align:center;width:100%;color:var(--ink-3);">No performance data available</div>';
    } else {
        const scalarMetrics = Object.entries(metrics).filter(
            ([, v]) => v !== null && typeof v !== 'object',
        );

        if (scalarMetrics.length) {
            scalarMetrics.forEach(([key, value]) => {
                const rounded = smartRound(value);
                metricBox.innerHTML += `
                <div class="kpi">
                    <div class="l">${formatLabel(key.replace(/_/g, ' '))}</div>
                    <div class="v" title="${value}">${rounded}</div>
                </div>`;
            });
        } else {
            metricBox.innerHTML =
                '<div style="padding:30px;text-align:center;width:100%;color:var(--ink-3);">No scalar metrics available</div>';
        }
    }

    // Confusion matrix + ROC (classification) takes priority. If the algorithm
    // doesn't have one but does have a graph_data artifact, render that histogram
    // in the same slot instead.
    const cm = metrics.confusion_matrix;
    if (cm) {
        const tpr = (cm.tp / (cm.tp + cm.fn)).toFixed(2);
        const fpr = (cm.fp / (cm.fp + cm.tn)).toFixed(2);
        perfBox.innerHTML = `
<div class="perf-col">
    <div class="perf-col-label">CONFUSION MATRIX</div>
    <div class="confusion-wrap">
        <div></div>
        <div class="pred-label">PRED · NO CHURN</div>
        <div class="pred-label">PRED · CHURN</div>
        <div class="actual-label">ACTUAL · NO CHURN</div>
        <div class="cm-box tn"><div class="num">${smartRound(cm.tn)}</div><div class="tag">TN</div></div>
        <div class="cm-box fp"><div class="num">${smartRound(cm.fp)}</div><div class="tag">FP</div></div>
        <div class="actual-label">ACTUAL · CHURN</div>
        <div class="cm-box fn"><div class="num">${smartRound(cm.fn)}</div><div class="tag">FN</div></div>
        <div class="cm-box tp"><div class="num">${smartRound(cm.tp)}</div><div class="tag">TP</div></div>
    </div>
</div>
<div class="perf-col">
    <div class="perf-col-label">ROC CURVE · AUC ${metrics.roc !== null ? smartRound(metrics.roc) : '--'}</div>
    <div class="graph-box">
        <svg width="100%" height="320" viewBox="0 0 500 320">
            <text x="230" y="305" font-size="13" fill="var(--ink-3)">False Positive Rate</text>
            <text x="20" y="180" transform="rotate(-90 20,180)" font-size="13" fill="var(--ink-3)">True Positive Rate</text>
            <line x1="70" y1="250" x2="430" y2="250" stroke="var(--line)"/>
            <line x1="70" y1="250" x2="70" y2="50" stroke="var(--line)"/>
            <line x1="70" y1="250" x2="430" y2="50" stroke="var(--line)" stroke-dasharray="6,6"/>
            <path d="M70 250 L70 ${250 - tpr * 200} L${70 + fpr * 360} ${250 - tpr * 200} L430 50 L430 250 Z" fill="rgba(10,58,120,.08)"/>
            <polyline points="70,250 70,${250 - tpr * 200} ${70 + fpr * 360},${250 - tpr * 200} 430,50" fill="none" stroke="var(--navy)" stroke-width="4"/>
        </svg>
    </div>
</div>`;
    } else if (graphData) {
        perfBox.innerHTML = renderGraphData(graphData);
    }

    // Artifacts
    const artifactContainer = document.getElementById('artifact-list');
    artifactContainer.innerHTML = '';

    // Log rendering
    const logFile = artifacts.find((x) => x.log_content);
    const logBox = document.getElementById('training-log-box');
    const lineBox = document.getElementById('log-lines');
    const fullLog = document.getElementById('full-log-link');

    if (logBox) {
        if (logFile?.log_content) {
            const lines = logFile.log_content
                .split('\n')
                .filter((x) => x.trim());
            lineBox.innerText = `${lines.length} lines`;
            logBox.innerHTML = lines
                .map((x) => `<div class="log-line">${x}</div>`)
                .join('');
            fullLog.href = logFile.url;
            fullLog.innerText = `View full log (${lines.length} lines) →`;
        } else {
            lineBox.innerText = '0 lines';
            logBox.innerHTML = 'No logs available';
            fullLog.href = '#';
        }
    }

    // Dynamic artifact count + size
    const countEl = document.getElementById('artifact-count');
    const sizeEl = document.getElementById('artifact-size');
    if (countEl)
        countEl.innerText = `${artifacts.length} file${artifacts.length !== 1 ? 's' : ''}`;
    if (sizeEl) {
        const totalMb = artifacts.reduce(
            (sum, f) => sum + (parseFloat(f.size) || 0),
            0,
        );
        sizeEl.innerText = totalMb > 0 ? `${totalMb.toFixed(1)} MB` : '--';
    }

    if (!artifacts.length) {
        artifactContainer.innerHTML =
            '<div style="text-align:center;color:var(--ink-3);padding:30px;">No artifacts available</div>';
    } else {
        const algoType = tab.dataset.algoType || '';
        artifacts.forEach((file) => {
            const sizeMb = parseFloat(file.size);
            const displaySize = !isNaN(sizeMb)
                ? sizeMb < 0.01
                    ? '<0.01 MB'
                    : sizeMb.toFixed(2) + ' MB'
                : '--';

            let displayName = file.name;
            if (
                algoType &&
                file.name.toLowerCase().startsWith(algoType.toLowerCase() + '_')
            ) {
                displayName = file.name.substring(algoType.length + 1);
            }

            artifactContainer.innerHTML += `
<div class="artifact">
    <div class="ico">${file.type}</div>
    <div class="info">
        <div class="nm" title="${file.name}">${displayName}</div>
        <div class="meta">${file.description || 'No description'}</div>
        <div class="artifact-category">${file.category || '--'}</div>
    </div>
    <div class="size">${displaySize}</div>
    <a href="${file.url}" download target="_blank" class="artifact-dl">↓</a>
</div>`;
        });
    }
}

function renderFeatureImportance (tab) {
    const algoName = tab.dataset.algoType || '--';
    const algoId = tab.dataset.algoId;
    const box = document.getElementById('feature-importance-container');
    box.innerHTML = '';
    const logEntry = Object.values(logs).find((x) => x.algo_id === algoId);
    const featureFile = logEntry?.artifacts?.find((x) =>
        x.name?.toLowerCase().includes('fea_imp'),
    );
    document.getElementById('feature-header').innerText =
        featureFile?.feature_count
            ? `${algoName} · top 10 of ${featureFile.feature_count} features`
            : 'No feature importance available';
    if (!featureFile) {
        box.innerHTML =
            '<div style="color:var(--ink-3);text-align:center;padding:30px;">No feature importance available</div>';
        return;
    }
    const features = featureFile?.top_features || [];
    if (!features.length) {
        box.innerHTML =
            '<div style="color:var(--ink-3);text-align:center;padding:30px;">Feature data empty</div>';
        return;
    }
    const maxValue = Math.max(...features.map((x) => x.Importance));
    const wrap = document.createElement('div');
    wrap.className = 'feature-list';
    features.forEach((item) => {
        const percent = maxValue ? (item.Importance / maxValue) * 100 : 0;
        const displayVal =
            typeof item.Importance === 'number'
                ? item.Importance.toFixed(2)
                : item.Importance;
        wrap.innerHTML += `
<div class="feature-row">
    <div class="feature-name" title="${item.Feature}">${item.Feature}</div>
    <div class="feature-bar-wrap"><div class="feature-bar" style="width:${percent}%"></div></div>
    <div class="feature-value">${displayVal}</div>
</div>`;
    });
    box.appendChild(wrap);
}

function renderHyperParameters (tab) {
    const algoName = tab.dataset.algoType || '--';
    const algoCategory = tab.dataset.algoCategory || '--';
    const algoId = tab.dataset.algoId;
    document.getElementById('hyper-header').innerText =
        `${algoName} · parameters`;
    const box = document.getElementById('hyper-container');
    const logEntry = Object.values(logs).find(
        (x) => String(x.algo_id) === String(algoId),
    );
    box.innerHTML = '';
    if (!logEntry?.algo_config) {
        box.innerHTML =
            '<div style="padding:30px;text-align:center;color:var(--ink-3);">No parameters available</div>';
        return;
    }
    let config;
    try {
        config =
            typeof logEntry.algo_config === 'string'
                ? JSON.parse(logEntry.algo_config)
                : logEntry.algo_config;
    } catch {
        box.innerHTML =
            '<div style="padding:30px;text-align:center;color:var(--ink-3);">Could not parse parameters</div>';
        return;
    }
    let rows = '';
    Object.entries(config).forEach(([k, v]) => {
        rows += `<div class="hyper-item">
            <div class="hyper-key">${formatLabel(k)}</div>
            <div class="hyper-value">${v}</div>
        </div>`;
    });
    box.innerHTML = `
<div class="hyper-card">
    <div class="hyper-top">
        <div><span class="hyper-name">${algoName}</span><span class="hyper-sub">${algoCategory}</span></div>
        <div class="hyper-type">${algoCategory}</div>
    </div>
    <div class="hyper-grid">${rows}</div>
</div>`;
}

function renderTrainingSummary () {
    const box = document.getElementById('training-summary');
    const ds = modelData?.dataSet_type_Json || {};
    const server =
        modelData?.training_server_Json?.training_field_info?.[0] || {};
    const service = server?.service_config || {};
    const sched = modelData?.schedule_info_Json || {};
    box.innerHTML = `
<div class="summary-item">
    <div class="sum-label">DATASET</div>
    <div class="sum-title">${ds.service_name || ds.connection_type || '--'}</div>
    <div class="sum-sub">${ds.dataset_type || '--'}${ds.app_name ? ` · ${ds.app_name}` : ''}</div>
</div>
<hr>
<div class="summary-item">
    <div class="sum-label">TRAINING SERVER</div>
    <div class="sum-title">${server.cluster_name || '--'}</div>
    <div class="sum-sub">${service.v_cpu || '--'} CPU · ${service.max_memory || '--'} GB</div>
</div>
<hr>
<div class="summary-item">
    <div class="sum-label">SCHEDULED AT</div>
    <div class="sum-title">${sched.start_date || '--'}</div>
    <div class="sum-sub">${sched.time || '--'} . ${sched.time_zone || '--'}</div>
</div>`;
}

// Smooth scroll for detail-tab links
document.querySelectorAll('.detail-tabs .tab').forEach((link) => {
    link.addEventListener('click', (e) => {
        e.preventDefault();
        const target = document.querySelector(link.getAttribute('href'));
        if (target)
            target.scrollIntoView({ behavior: 'smooth', block: 'start' });
        document
            .querySelectorAll('.detail-tabs .tab')
            .forEach((t) => t.classList.remove('active'));
        link.classList.add('active');
    });
});

const allTabs = document.querySelectorAll('.algo-tab');

document.addEventListener('click', (e) => {
    const tab = e.target.closest('.algo-tab');
    if (!tab) return;
    allTabs.forEach((t) => t.classList.remove('active'));
    tab.classList.add('active');
    const { algoCategory, algoType, algoId } = tab.dataset;
    if (algoCategory)
        document.getElementById('active-algo-name').innerText = algoCategory;
    if (algoType || algoId)
        document.getElementById('active-algo-meta').innerText =
            `${algoType || '--'} · ${algoId || '--'}`;
    updateAlgo(tab);
    updateOverview(tab);
    renderFeatureImportance(tab);
    renderHyperParameters(tab);
});

if (allTabs.length) {
    const first = allTabs[0];
    first.classList.add('active');
    const { algoCategory, algoType, algoId } = first.dataset;
    if (algoCategory)
        document.getElementById('active-algo-name').innerText = algoCategory;
    if (algoType || algoId)
        document.getElementById('active-algo-meta').innerText =
            `${algoType || '--'} · ${algoId || '--'}`;
    updateAlgo(first);
    updateOverview(first);
    renderFeatureImportance(first);
    renderHyperParameters(first);
    renderTrainingSummary();
}

// ─────────────────────────────────────────────────────────────────────────────
// LIVE METRICS TAB
// ─────────────────────────────────────────────────────────────────────────────

(function () {
    // The model_id is injected by the template as a global const MODEL_ID.
    const modelId =
        typeof window.MODEL_ID !== 'undefined' && window.MODEL_ID
            ? window.MODEL_ID
            : modelData && modelData.model_id
                ? modelData.model_id
                : null;

    let currentWindow = 3600; // seconds — tracks the active range button
    let isLoading = false;

    // ── Fetch ────────────────────────────────────────────────────────────────

    async function loadInferenceMetrics (windowSeconds) {
        if (!modelId) {
            showMetricsError('model_id not available on this page.');
            return;
        }
        if (isLoading) return;
        isLoading = true;

        const refreshBtn = document.getElementById('infer-refresh-btn');
        if (refreshBtn) refreshBtn.disabled = true;

        try {
            const resp = await window.fetch(
                '/PlatformIO/APIv1/InferenceMetrics/',
                {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': getCsrfToken(),
                    },
                    body: JSON.stringify({
                        model_id: modelId,
                        window_seconds: windowSeconds,
                    }),
                },
            );
            const json = await resp.json();
            if (json.status === 'success') {
                renderMetrics(json.data);
            } else {
                const errMsg = json.data?.error || json.msg || 'Unknown error';
                showMetricsError(errMsg);
            }
        } catch (err) {
            showMetricsError('Network error: ' + err.message);
        } finally {
            isLoading = false;
            if (refreshBtn) refreshBtn.disabled = false;
        }
    }

    // ── Render ───────────────────────────────────────────────────────────────

    function renderMetrics (d) {
        renderKPIs(d);
        renderChart(d.timeseries || []);
        renderAlgoBreakdown(d.algo_breakdown || {});

        const sub = document.getElementById('infer-last-updated');
        if (sub) {
            const ts = d.last_request_ts
                ? new Date(d.last_request_ts * 1000).toLocaleTimeString()
                : '--';
            sub.textContent = `Last request: ${ts} · ${windowLabel(currentWindow)} window`;
        }
    }

    function renderKPIs (d) {
        const row = document.getElementById('infer-kpi-row');
        if (!row) return;
        const errColor =
            d.error_rate_pct > 5
                ? 'var(--danger)'
                : d.error_rate_pct > 1
                    ? 'var(--warn)'
                    : 'var(--ok)';
        row.innerHTML = `
<div class="infer-kpi">
  <div class="infer-kpi-v">${d.total_requests.toLocaleString()}</div>
  <div class="infer-kpi-l">Total requests</div>
</div>
<div class="infer-kpi">
  <div class="infer-kpi-v" style="color:${errColor}">${d.error_rate_pct}%</div>
  <div class="infer-kpi-l">Error rate</div>
</div>
<div class="infer-kpi">
  <div class="infer-kpi-v">${d.p50_ms} ms</div>
  <div class="infer-kpi-l">p50 latency</div>
</div>
<div class="infer-kpi">
  <div class="infer-kpi-v">${d.p99_ms} ms</div>
  <div class="infer-kpi-l">p99 latency</div>
</div>
<div class="infer-kpi">
  <div class="infer-kpi-v">${d.avg_ms} ms</div>
  <div class="infer-kpi-l">Avg latency</div>
</div>
<div class="infer-kpi">
  <div class="infer-kpi-v">${d.req_per_min}</div>
  <div class="infer-kpi-l">Req / min</div>
</div>`;
    }

    function renderChart (buckets) {
        const area = document.getElementById('infer-chart-area');
        const totalEl = document.getElementById('infer-chart-total');
        if (!area) return;

        if (!buckets.length) {
            area.innerHTML =
                '<div class="infer-chart-empty">No requests in this window</div>';
            if (totalEl) totalEl.textContent = '';
            return;
        }

        const W = 760,
            H = 120,
            PAD_L = 36,
            PAD_B = 22,
            PAD_R = 8,
            PAD_T = 8;
        const plotW = W - PAD_L - PAD_R;
        const plotH = H - PAD_B - PAD_T;
        const maxCount = Math.max(...buckets.map((b) => b.count), 1);
        const barW = Math.max(2, plotW / buckets.length - 1);
        const total = buckets.reduce((s, b) => s + b.count, 0);
        if (totalEl) totalEl.textContent = `${total.toLocaleString()} requests`;

        // x-axis labels — show at most 8 evenly spaced
        const labelStep = Math.ceil(buckets.length / 8);
        const labels = buckets
            .map((b, i) =>
                i % labelStep === 0
                    ? `<text x="${PAD_L + i * (barW + 1) + barW / 2}" y="${H - 4}" class="infer-axis-lbl">${b.label}</text>`
                    : '',
            )
            .join('');

        // y-axis gridlines
        const gridLines = [0.25, 0.5, 0.75, 1]
            .map((f) => {
                const y = PAD_T + plotH * (1 - f);
                return `<line x1="${PAD_L}" y1="${y}" x2="${W - PAD_R}" y2="${y}" class="infer-grid"/>
                    <text x="${PAD_L - 4}" y="${y + 4}" class="infer-axis-lbl" text-anchor="end">${Math.round(maxCount * f)}</text>`;
            })
            .join('');

        const bars = buckets
            .map((b, i) => {
                const x = PAD_L + i * (barW + 1);
                const bh = (b.count / maxCount) * plotH;
                const y = PAD_T + plotH - bh;
                const errH = (b.errors / maxCount) * plotH;
                const errY = PAD_T + plotH - errH;
                return `<rect x="${x}" y="${y}" width="${barW}" height="${bh}" class="infer-bar-ok"/>
                    ${b.errors ? `<rect x="${x}" y="${errY}" width="${barW}" height="${errH}" class="infer-bar-err"/>` : ''}`;
            })
            .join('');

        area.innerHTML = `
<svg viewBox="0 0 ${W} ${H}" class="infer-chart-svg">
  ${gridLines}
  ${bars}
  ${labels}
  <line x1="${PAD_L}" y1="${PAD_T}" x2="${PAD_L}" y2="${PAD_T + plotH}" class="infer-axis"/>
  <line x1="${PAD_L}" y1="${PAD_T + plotH}" x2="${W - PAD_R}" y2="${PAD_T + plotH}" class="infer-axis"/>
</svg>
<div class="infer-chart-legend">
  <span class="infer-leg ok"></span>Success
  <span class="infer-leg err" style="margin-left:12px;"></span>Error
</div>`;
    }

    function renderAlgoBreakdown (breakdown) {
        const box = document.getElementById('infer-algo-breakdown');
        if (!box) return;
        const algos = Object.entries(breakdown);
        if (!algos.length) {
            box.innerHTML =
                '<div class="infer-chart-empty">No per-algorithm data available</div>';
            return;
        }
        const rows = algos
            .map(([algo, s]) => {
                const errColor =
                    s.errors > 0 ? 'var(--danger)' : 'var(--ink-3)';
                return `<tr>
  <td class="infer-td-algo">${algo}</td>
  <td class="infer-td-num">${s.requests.toLocaleString()}</td>
  <td class="infer-td-num" style="color:${errColor}">${s.errors}</td>
  <td class="infer-td-num">${s.p50_ms} ms</td>
  <td class="infer-td-num">${s.p99_ms} ms</td>
</tr>`;
            })
            .join('');
        box.innerHTML = `
<table class="infer-table">
  <thead>
    <tr>
      <th>Algorithm</th><th>Requests</th><th>Errors</th><th>p50</th><th>p99</th>
    </tr>
  </thead>
  <tbody>${rows}</tbody>
</table>`;
    }

    function showMetricsError (msg) {
        const row = document.getElementById('infer-kpi-row');
        if (row) row.innerHTML = `<div class="infer-error-msg">⚠ ${msg}</div>`;
        const area = document.getElementById('infer-chart-area');
        if (area) area.innerHTML = '';
        const bd = document.getElementById('infer-algo-breakdown');
        if (bd) bd.innerHTML = '';
    }

    // ── Helpers ──────────────────────────────────────────────────────────────

    function windowLabel (s) {
        if (s <= 3600) return '1 hour';
        if (s <= 21600) return '6 hours';
        return '24 hours';
    }

    function getCsrfToken () {
        const el = document.querySelector('[name=csrfmiddlewaretoken]');
        if (el) return el.value;
        const cookie = document.cookie
            .split(';')
            .find((c) => c.trim().startsWith('csrftoken='));
        return cookie ? cookie.split('=')[1].trim() : '';
    }

    // ── Wire up tab click ────────────────────────────────────────────────────

    const liveTab = document.querySelector(
        '.tab[href="#inference-metrics-section"]',
    );
    const allDetailTabs = document.querySelectorAll('.detail-tabs .tab');

    if (liveTab) {
        liveTab.addEventListener('click', function (e) {
            e.preventDefault();
            allDetailTabs.forEach((t) => t.classList.remove('active'));
            this.classList.add('active');

            // Hide overview, show metrics section
            document.getElementById('overview-section')?.style &&
                (document.getElementById('overview-section').style.display =
                    'none');
            document.getElementById('logs-section')?.style &&
                (document.getElementById('logs-section').style.display =
                    'none');
            const sec = document.getElementById('inference-metrics-section');
            if (sec) sec.style.display = '';

            // Auto-load if not yet fetched
            const kpiRow = document.getElementById('infer-kpi-row');
            if (kpiRow && kpiRow.querySelector('.infer-kpi-placeholder')) {
                loadInferenceMetrics(currentWindow);
            }
        });
    }

    // Re-show correct sections when other tabs are clicked
    allDetailTabs.forEach((t) => {
        if (t === liveTab) return;
        t.addEventListener('click', function () {
            const sec = document.getElementById('inference-metrics-section');
            if (sec) sec.style.display = 'none';
            document.getElementById('overview-section')?.style &&
                (document.getElementById('overview-section').style.display =
                    '');
        });
    });

    // ── Range buttons ────────────────────────────────────────────────────────

    document
        .getElementById('infer-range-group')
        ?.addEventListener('click', function (e) {
            const btn = e.target.closest('.range-btn');
            if (!btn) return;
            this.querySelectorAll('.range-btn').forEach((b) =>
                b.classList.remove('active'),
            );
            btn.classList.add('active');
            currentWindow = parseInt(btn.dataset.window, 10);
            loadInferenceMetrics(currentWindow);
        });

    // ── Refresh button ───────────────────────────────────────────────────────

    document
        .getElementById('infer-refresh-btn')
        ?.addEventListener('click', function () {
            loadInferenceMetrics(currentWindow);
        });
})();

// ─────────────────────────────────────────────────────────────────────────────
// LIVE STATUS POLLING (every 1 minute)
// ─────────────────────────────────────────────────────────────────────────────
(function () {
    const modelId =
        typeof window.MODEL_ID !== 'undefined' && window.MODEL_ID
            ? window.MODEL_ID
            : modelData && modelData.model_id
                ? modelData.model_id
                : null;

    let intervalId;

    async function updateLiveStatus () {
        if (!modelId) return;
        try {
            const resp = await window.fetch(
                `/PlatformIO/APIv1/Model/LiveStatus/?model_id=${modelId}`,
            );
            if (resp.ok) {
                const data = await resp.json();

                // Update Stage
                const stageEl = document.getElementById('live-status-stage');
                if (stageEl) {
                    stageEl.textContent = data.stage || 'Unknown';
                    stageEl.style.color = '';
                    if (data.stage === 'Complete')
                        stageEl.style.color = 'var(--ok)';
                    else if (data.stage === 'Failed')
                        stageEl.style.color = 'var(--danger)';
                    else if (data.stage === 'Training')
                        stageEl.style.color = 'var(--warn)';
                }

                // Update Epoch
                const epochEl = document.getElementById('live-status-epoch');
                if (epochEl) {
                    epochEl.textContent =
                        data.epoch !== null && data.epoch !== undefined
                            ? data.epoch
                            : '--';
                }

                // Update Total Epochs
                const totalEpochsEl = document.getElementById(
                    'live-status-total-epochs',
                );
                if (totalEpochsEl) {
                    totalEpochsEl.textContent =
                        data.total_epochs !== null &&
                        data.total_epochs !== undefined
                            ? data.total_epochs
                            : '--';
                }

                // Update Updated At
                const updatedAtEl = document.getElementById(
                    'live-status-updated-at',
                );
                if (updatedAtEl) {
                    if (data.updated_at) {
                        const dateObj = new Date(data.updated_at);
                        updatedAtEl.textContent = `Updated: ${dateObj.toLocaleTimeString()}`;
                    } else {
                        updatedAtEl.textContent = '--';
                    }
                }

                // Update Logs
                const logsBox = document.getElementById('live-status-logs-box');
                if (logsBox) {
                    if (data.logs && data.logs.length > 0) {
                        logsBox.innerHTML = data.logs
                            .map((line) => `<div>${line}</div>`)
                            .join('');
                        logsBox.scrollTop = logsBox.scrollHeight;
                    } else {
                        logsBox.textContent = 'No live logs available';
                    }
                }

                // Stop the browser timer if the training has completed or failed
                if (data.stage === 'Complete' || data.stage === 'Failed') {
                    if (intervalId) {
                        window.clearInterval(intervalId);
                        intervalId = null;
                    }
                }
            }
        } catch (err) {
            console.error('Error fetching live status:', err);
        }
    }

    // Call on load and set 1-minute interval
    if (modelId) {
        updateLiveStatus();
        intervalId = window.setInterval(updateLiveStatus, 60000);
    }
})();
// ─────────────────────────────────────────────────────────────────────────────
