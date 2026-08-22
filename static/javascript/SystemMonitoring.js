/* ════════════════════════════════════════════════════════════════════
   Performance monitoring — demo data and rendering
   ════════════════════════════════════════════════════════════════════
   The backend scrapes Prometheus exporters at /metrics on every node and
   every service. For this static demo we synthesise plausible time-series
   so the UI behaves as it would with live data.
   ════════════════════════════════════════════════════════════════════ */

/* global , SESSION_INFO, document, setTimeout, setInterval, clearInterval, FormData, fetch */
const $ = (s, r) => (r || document).querySelector(s);
const $$ = (s, r) => Array.from((r || document).querySelectorAll(s));
const csrftoken =
    document.querySelector('[name=csrfmiddlewaretoken]')?.value || '';

// ─── Topology: clusters → nodes → services ──────────────────────────
// (Reuses the same shape as the data-flow drilldown for consistency)

// ─── State ──────────────────────────────────────────────────────────
// const defaultNode = Object.keys(MACHINE_STATS || {})[0] || null;

const state = {
    cluster: '',
    period: '24h',
    clusters: [],
    clusterNodes: {},
    machineStats: {},
    lastValidMetrics: {},
    serviceStats: {},
    lastValidServiceStats: {},
    focused: 'cpu',
    autoRefresh: true,
    autoRefreshInterval: 10000,
    isLoading: false,
    loadingNode: null,
    loadingService: null,
    selection: {
        kind: 'node',
        cluster: SESSION_INFO?.cluster_name || '',
        node: SESSION_INFO?.node_name || '',
        service: null,
        serviceType: null,
    },
};

// ─── Time series synthesis ──────────────────────────────────────────
// Deterministic pseudo-random so the same target produces the same data
// every time the page renders (looks plausible across refreshes).
function seededRand (seed) {
    let s = seed % 2147483647;
    if (s <= 0) s += 2147483646;
    return () => {
        s = (s * 16807) % 2147483647;
        return (s - 1) / 2147483646;
    };
}

function rangeBuckets (range) {
    // Number of data points + bucket size (in seconds) per range.
    // Real Prometheus would aggregate by step; we approximate.
    return {
        '1h': { n: 60, step: 60 }, // 1 min
        '6h': { n: 72, step: 300 }, // 5 min
        '24h': { n: 96, step: 900 }, // 15 min
        '7d': { n: 84, step: 7200 }, // 2 hr
        '1M': { n: 90, step: 28800 }, // 8 hr
        '3M': { n: 90, step: 86400 }, // 1 day
    }[range];
}

// Node metric profiles — different metrics have different shapes
function nodeMetrics (cluster, nodeId) {
    const nodeData = state.machineStats[nodeId];
    const cacheKey = `${cluster}|${nodeId}`;
    const lastValidMetrics = state.lastValidMetrics[cacheKey] || {};

    if (!nodeData) {
        return {
            cpu: buildSeries(lastValidMetrics?.cpuData || []),
            memory: buildSeries(lastValidMetrics?.memoryUsage || []),
            memoryTotal: null,
            storage: buildSeries(lastValidMetrics?.diskUsage || []),
            storageTotal: null,
            gpuUtilization: buildSeries(lastValidMetrics?.gpuData || []),
            gpuMemory: buildSeries(lastValidMetrics?.gpuMemoryUsage || []),
            gpuMemoryTotal: null,
        };
    }

    // const labels = nodeData.labels || [];
    const cpuValues = nodeData.cpu_utilization_data?.data || [];
    const freeMemory = nodeData.free_memory_data?.data || [];
    const totalMemory = nodeData.total_memory_data?.data || [];
    const freeDisk = nodeData.free_disk_data?.data || [];
    const totalDisk = nodeData.total_disk_data?.data || [];
    const gpuValues = nodeData.gpu_utilization_data?.data || [];
    const freeGpuMemory = nodeData.free_gpu_memory_data?.data || [];
    const usedGpuMemory = nodeData.used_gpu_memory_data?.data || [];

    function buildSeries (values) {
        const { step } = rangeBuckets(state.period);
        return values.map((value, index) => ({
            t: (values.length - index) * step,
            v: Number(value || 0),
        }));
    }

    // memory usage %
    const hasValidMemoryData =
        freeMemory.length > 0 &&
        totalMemory.length > 0 &&
        freeMemory.length === totalMemory.length;

    const memoryUsage = hasValidMemoryData
        ? freeMemory.map((free, index) => {
            const total = totalMemory[index] || 1;
            return ((total - free) / total) * 100;
        })
        : lastValidMetrics?.memoryUsage || [];

    if (hasValidMemoryData) {
        state.lastValidMetrics[cacheKey] = {
            ...state.lastValidMetrics[cacheKey],
            memoryUsage,
            memoryTotal: totalMemory.at(-1),
        };
    }

    const memoryTotalValue = hasValidMemoryData
        ? totalMemory.at(-1)
        : lastValidMetrics?.memoryTotal || null;

    // disk usage %
    const hasValidDiskData =
        freeDisk.length > 0 &&
        totalDisk.length > 0 &&
        freeDisk.length === totalDisk.length;

    const diskUsage = hasValidDiskData
        ? freeDisk.map((free, index) => {
            const total = totalDisk[index] || 1;
            return ((total - free) / total) * 100;
        })
        : lastValidMetrics?.diskUsage || [];

    if (hasValidDiskData) {
        state.lastValidMetrics[cacheKey] = {
            ...state.lastValidMetrics[cacheKey],
            diskUsage,
            storageTotal: totalDisk.at(-1),
        };
    }

    const storageTotalValue = hasValidDiskData
        ? totalDisk.at(-1)
        : lastValidMetrics?.storageTotal || null;

    const cpuData =
        cpuValues.length > 0 ? cpuValues : lastValidMetrics?.cpuData || [];

    if (cpuValues.length > 0) {
        state.lastValidMetrics[cacheKey] = {
            ...state.lastValidMetrics[cacheKey],
            cpuData,
        };
    }

    const gpuData =
        gpuValues.length > 0 ? gpuValues : lastValidMetrics?.gpuData || [];

    if (gpuValues.length > 0) {
        state.lastValidMetrics[cacheKey] = {
            ...state.lastValidMetrics[cacheKey],
            gpuData,
        };
    }

    const hasValidGpuMemoryData =
        freeGpuMemory.length > 0 &&
        usedGpuMemory.length > 0 &&
        freeGpuMemory.length === usedGpuMemory.length;

    const gpuMemoryUsage = hasValidGpuMemoryData
        ? freeGpuMemory.map((free, index) => {
            const used = usedGpuMemory[index] || 0;
            const total = free + used;
            return total > 0 ? (used / total) * 100 : 0;
        })
        : lastValidMetrics?.gpuMemoryUsage || [];

    if (hasValidGpuMemoryData) {
        state.lastValidMetrics[cacheKey] = {
            ...state.lastValidMetrics[cacheKey],
            gpuMemoryUsage,
            gpuMemoryTotal: freeGpuMemory.at(-1) + usedGpuMemory.at(-1),
        };
    }

    const gpuMemoryTotalValue = hasValidGpuMemoryData
        ? freeGpuMemory.at(-1) + usedGpuMemory.at(-1)
        : lastValidMetrics?.gpuMemoryTotal || null;

    return {
        cpu: buildSeries(cpuData),
        memory: buildSeries(memoryUsage),
        memoryTotal: memoryTotalValue,
        storage: buildSeries(diskUsage),
        storageTotal: storageTotalValue,
        gpuUtilization: buildSeries(gpuData),
        gpuMemory: buildSeries(gpuMemoryUsage),
        gpuMemoryTotal: gpuMemoryTotalValue,
    };
}

// ─── SVG helpers for drawing charts ─────────────────────────────────
function pathFromSeries (series, w, h, yMax) {
    // series is [{t, v}] with t descending; map t=0 to x=w (right side)
    if (!series.length) return '';
    const maxT = series[0].t; // oldest point
    const xFor = (t) => w - (t / maxT) * w;
    const yFor = (v) => h - (v / yMax) * h;
    let d = `M${xFor(series[0].t).toFixed(2)},${yFor(series[0].v).toFixed(2)}`;
    for (let i = 1; i < series.length; i++) {
        d += ` L${xFor(series[i].t).toFixed(2)},${yFor(series[i].v).toFixed(2)}`;
    }
    return d;
}

function areaFromSeries (series, w, h, yMax) {
    const linePath = pathFromSeries(series, w, h, yMax);
    if (!linePath) return '';
    return `${linePath} L${w},${h} L0,${h} Z`;
}

function renderSparkline (series, opts = {}) {
    const w = 200,
        h = 34;
    const yMax = opts.max ?? Math.max(100, ...series.map((p) => p.v));
    const color = opts.color ?? 'var(--navy)';
    return `<svg viewBox="0 0 ${w} ${h}" preserveAspectRatio="none">
    <path d="${areaFromSeries(series, w, h, yMax)}" fill="${color}" opacity="0.08"/>
    <path d="${pathFromSeries(series, w, h, yMax)}" stroke="${color}" stroke-width="1.5" fill="none"/>
  </svg>`;
}

function renderChart (series, opts = {}) {
    if (!series || !series.length) {
        return `
            <div class="empty-chart">
                ${state.loadingService ? 'Loading monitoring data...' : 'No monitoring data available'}
            </div>
        `;
    }

    // Big chart with axes, grid lines, threshold lines
    const w = 900,
        h = 240;
    const padL = 44,
        padR = 12,
        padT = 16,
        padB = 24;
    const cw = w - padL - padR,
        ch = h - padT - padB;
    const yMax = opts.max ?? 100;
    const color = opts.color ?? 'var(--navy)';
    const unit = opts.unit ?? '%';
    const fmt = opts.fmt ?? ((v) => v.toFixed(0));

    // Y-axis ticks
    const ticks = 5;
    let yAxis = '';
    for (let i = 0; i <= ticks; i++) {
        const y = padT + (ch * i) / ticks;
        const val = yMax * (1 - i / ticks);
        yAxis += `<line x1="${padL}" y1="${y.toFixed(1)}" x2="${w - padR}" y2="${y.toFixed(1)}" stroke="var(--line)" stroke-width="0.5" stroke-dasharray="${i === ticks ? '0' : '2 3'}"/>`;
        yAxis += `<text x="${padL - 6}" y="${y.toFixed(1) + 3}" font-size="10" font-family="var(--mono)" fill="var(--ink-4)" text-anchor="end">${fmt(val)}${i === 0 ? unit : ''}</text>`;
    }

    // X-axis ticks — show 5 labels evenly spaced
    let xAxis = '';
    const xTicks = 5;
    for (let i = 0; i <= xTicks; i++) {
        const x = padL + (cw * i) / xTicks;
        const secondsAgo = series[0].t * (1 - i / xTicks);
        const label = formatXAxisTime(secondsAgo);
        xAxis += `<text x="${x.toFixed(1)}" y="${h - 6}" font-size="10" font-family="var(--mono)" fill="var(--ink-4)" text-anchor="middle">${label}</text>`;
    }

    // Threshold lines
    let thresh = '';
    if (opts.warnAt !== undefined) {
        const y = padT + ch * (1 - opts.warnAt / yMax);
        thresh += `<line x1="${padL}" y1="${y}" x2="${w - padR}" y2="${y}" stroke="var(--warn)" stroke-width="1" stroke-dasharray="4 4" opacity="0.5"/>`;
        thresh += `<text x="${w - padR - 4}" y="${y - 3}" font-size="9" font-family="var(--mono)" fill="var(--warn)" text-anchor="end">warn ${opts.warnAt}${unit}</text>`;
    }
    if (opts.errAt !== undefined) {
        const y = padT + ch * (1 - opts.errAt / yMax);
        thresh += `<line x1="${padL}" y1="${y}" x2="${w - padR}" y2="${y}" stroke="var(--err)" stroke-width="1" stroke-dasharray="4 4" opacity="0.5"/>`;
        thresh += `<text x="${w - padR - 4}" y="${y - 3}" font-size="9" font-family="var(--mono)" fill="var(--err)" text-anchor="end">crit ${opts.errAt}${unit}</text>`;
    }

    // The series line + area
    const linePath = pathFromSeries(series, cw, ch, yMax);
    const areaPath = areaFromSeries(series, cw, ch, yMax);
    const seriesG = `<g transform="translate(${padL},${padT})">
    <path d="${areaPath}" fill="${color}" opacity="0.12"/>
    <path d="${linePath}" stroke="${color}" stroke-width="2" fill="none" stroke-linecap="round" stroke-linejoin="round"/>
  </g>`;

    // Data points group for hover tooltip (invisible but clickable)
    const points = series
        .map((p) => {
            const maxT = series[0].t;
            const x = padL + cw * (1 - p.t / maxT);
            const y = padT + ch * (1 - p.v / yMax);
            return `<circle cx="${x.toFixed(1)}" cy="${y.toFixed(1)}" r="3" fill="transparent" data-v="${p.v.toFixed(2)}" data-t="${p.t}" data-unit="${unit}" class="tip-pt"/>`;
        })
        .join('');

    return `<svg viewBox="0 0 ${w} ${h}" preserveAspectRatio="none">
    ${yAxis}
    ${xAxis}
    ${thresh}
    ${seriesG}
    ${points}
  </svg>`;
}

function formatXAxisTime (secondsAgo) {
    const dt = new Date(Date.now() - secondsAgo * 1000);

    if (state.period === '1h' || state.period === '6h') {
        return dt.toLocaleTimeString([], {
            hour: '2-digit',
            minute: '2-digit',
        });
    } else if (state.period === '24h') {
        return dt.toLocaleTimeString([], {
            day: 'numeric',
            hour: '2-digit',
            minute: '2-digit',
        });
    } else if (
        state.period === '7d' ||
        state.period === '1M' ||
        state.period === '3M'
    ) {
        return dt.toLocaleDateString([], {
            day: 'numeric',
            month: 'short',
            hour: '2-digit',
            minute: '2-digit',
        });
    }

    return '';
}

function formatCounterLabel (label) {
    const [dayMonth, hour] = label.split(':');
    const day = dayMonth.split('-')[0];
    const h = Number(hour);
    const suffix = h >= 12 ? 'PM' : 'AM';
    const hh = (((h + 11) % 12) + 1).toString().padStart(2, '0');
    return `${day}, ${hh}:00 ${suffix}`;
}

//function formatTimeAgo (secondsAgo) {
//    if (secondsAgo < 60) return Math.round(secondsAgo) + 's';
//    if (secondsAgo < 3600) return Math.round(secondsAgo/60) + 'm';
//    if (secondsAgo < 86400) return (secondsAgo/3600).toFixed(1) + 'h';
//    return (secondsAgo/86400).toFixed(1) + 'd';
//}

function thresholdStatus (value, warn, err) {
    if (value >= err) return 'err';
    if (value >= warn) return 'warn';
    return 'ok';
}

function showToast (message) {
    const toast = document.createElement('div');
    toast.className = 'monitor-toast';
    toast.innerText = message;
    document.body.appendChild(toast);
    setTimeout(() => {
        toast.remove();
    }, 3000);
}

// Throttling method to limit 1 fetch request within specific time
const canFetchData = (() => {
    let lastKey = null;
    let lastFetchTime = 0;

    return (cluster, node, service, period) => {
        const now = Date.now();
        const key = `${cluster}|${node}|${service}|${period}`;

        if (key !== lastKey) {
            lastKey = key;
            lastFetchTime = now;
            return true;
        }

        if (now - lastFetchTime >= state.autoRefreshInterval) {
            lastFetchTime = now;
            return true;
        }

        return false;
    };
})();

// fetch function
async function fetchNodeMonitoringData (
    cluster,
    node,
    period,
    forceRefresh = false,
) {
    if (state.isLoading) {
        return;
    }

    // avoid duplicate fetch
    const dataAlreadyLoaded = !!state.machineStats?.[node];
    const isSameNode =
        dataAlreadyLoaded &&
        state.selection.cluster === cluster &&
        state.selection.node === node &&
        state.period === period;

    if (isSameNode && !canFetchData(cluster, node, null, period)) {
        return;
    }

    state.isLoading = true;

    try {
        // update current selection
        state.selection = { kind: 'node', cluster, node, service: null };
        state.cluster = cluster;
        state.period = period;
        if (!state.autoRefresh && !forceRefresh) {
            setAutoRefresh(true);
        }

        if (!isSameNode) {
            state.loadingNode = node;
            render();
        }
        highlightTreeSelection();

        // request payload
        const payload = {
            cluster: cluster,
            node: node,
            period: period,
            refresh: forceRefresh,
        };

        // form data
        const formData = new FormData();
        formData.append('json_data', JSON.stringify(payload));

        // backend request
        const response = await fetch('/PlatformIO/GetNodePerformance/', {
            method: 'POST',
            body: formData,
            headers: {
                'X-CSRFToken': csrftoken,
            },
        });

        // response parse
        const data = await response.json();

        // backend error
        if (!data.success) {
            state.isLoading = false;
            state.loadingNode = null;
            setAutoRefresh(false);

            if (!forceRefresh && !isSameNode) {
                state.machineStats[node] = {
                    error: true,
                    nodeInfo: {
                        nodeName: node,
                    },
                };
                render();
            }

            showToast(data.error || 'Failed to fetch monitoring data');
            return;
        }

        // update monitoring data
        state.machineStats[node] = data.machine_stats;
        console.log('data.machine_stats == ', data.machine_stats);
        state.isLoading = false;
        state.loadingNode = null;
        // re-render tree with latest data
        updateTreeNodeData(node);
        // render UI
        render();
    } catch {
        state.isLoading = false;
        state.loadingNode = null;
        setAutoRefresh(false);

        if (!forceRefresh && !isSameNode) {
            state.machineStats[node] = {
                error: true,
                nodeInfo: {
                    nodeName: node,
                },
            };
            render();
        }

        showToast('Failed to fetch monitoring data');
    }
}

async function fetchServiceMonitoringData (
    cluster,
    node,
    service,
    serviceType,
    ipAddress,
    period,
    forceRefresh = false,
) {
    if (state.isLoading) {
        return;
    }

    // avoid duplicate fetch
    const dataAlreadyLoaded = !!state.serviceStats?.[service];
    const isSameService =
        dataAlreadyLoaded &&
        state.selection.cluster === cluster &&
        state.selection.node === node &&
        state.selection.service === service &&
        state.period === period;

    if (isSameService && !canFetchData(cluster, node, service, period)) {
        return;
    }

    state.isLoading = true;

    try {
        state.selection = {
            kind: 'service',
            cluster,
            node,
            service,
            serviceType,
        };
        state.cluster = cluster;
        state.period = period;
        if (!state.autoRefresh && !forceRefresh) {
            setAutoRefresh(true);
        }

        if (!isSameService) {
            state.loadingService = service;
            render();
        }
        highlightTreeSelection();

        const formData = new FormData();
        const payload = {
            cluster: cluster,
            node: node,
            service: service,
            ipAddress: ipAddress,
            period: period,
            refresh: forceRefresh,
        };

        formData.append('json_data', JSON.stringify(payload));

        const response = await fetch('/PlatformIO/GetServicePerformance/', {
            method: 'POST',
            body: formData,
            headers: {
                'X-CSRFToken': csrftoken,
            },
        });

        const data = await response.json();
        console.log('SERVICE API RESPONSE', data);

        if (!data.success) {
            state.isLoading = false;
            state.loadingService = null;
            setAutoRefresh(false);
            showToast(data.error || 'Failed to fetch monitoring data');
            if (!forceRefresh && !isSameService) {
                state.serviceStats[service] = {
                    error: true,
                    serviceInfo: {
                        serviceName: service,
                    },
                };
                render();
            }
            return;
        }

        state.serviceStats[service] = data;
        state.isLoading = false;
        state.loadingService = null;
        render();
    } catch (err) {
        state.isLoading = false;
        state.loadingService = null;
        setAutoRefresh(false);
        if (!forceRefresh && !isSameService) {
            state.serviceStats[service] = {
                error: true,
                serviceInfo: {
                    serviceName: service,
                },
            };
            render();
        }
        showToast('Failed to fetch monitoring data');
    }
}

// ─── Tree Node update ─────────────────────────────────────────────────
function updateTreeNodeData (nodeName) {
    const machineNode = state.machineStats[nodeName];
    if (!machineNode) {
        return;
    }

    // -----------------------------------
    // CPU update
    // -----------------------------------
    const nodeEl = document.getElementById(`tree-node-${nodeName}`);
    if (nodeEl) {
        const cpuData =
            (machineNode?.cpu_utilization_data?.data || []).length > 0
                ? machineNode.cpu_utilization_data.data
                : state.lastValidMetrics?.cpuData || [];
        const latestCPU = cpuData.length
            ? Number(cpuData[cpuData.length - 1]).toFixed(0)
            : '--';
        const loadEl = nodeEl.querySelector('.nload');
        if (loadEl) {
            loadEl.innerText = `${latestCPU}%`;
        }
    }
}

// fetch monitoring tree strucutre
async function fetchMonitoringTree () {
    const response = await fetch('/PlatformIO/GetMonitoringTree/');
    const data = await response.json();

    if (!data.success) {
        return;
    }

    state.clusterNodes = data.cluster_tree;
    state.clusters = Object.keys(data.cluster_tree);
    renderTree();
}

// ─── Tree rendering ─────────────────────────────────────────────────
function renderTree () {
    const list = $('#treeList');
    list.innerHTML = '';

    state.clusters.forEach((clusterName) => {
        const group = document.createElement('div');
        group.className = 'tree-group';
        group.dataset.cluster = clusterName;

        // current selected cluster expanded
        // if (clusterName !== state.cluster) {
        //     group.classList.add('collapsed');
        // }

        // only current cluster nodes render
        const nodes = state.clusterNodes[clusterName] || {};

        group.innerHTML = `
      <div class="group-head">
        <svg class="caret ic"
             viewBox="0 0 24 24"
             fill="none"
             stroke="currentColor"
             stroke-width="2">

          <polyline points="6 9 12 15 18 9"/>
        </svg>

        <span>${clusterName}</span>

        <span class="group-meta">
          ${Object.keys(nodes).length} nodes
        </span>
      </div>

      <div class="group-children"></div>
    `;

        const children = group.querySelector('.group-children');
        Object.keys(nodes).forEach((nodeName) => {
            const nodeEl = document.createElement('div');
            nodeEl.className = 'tree-node';
            nodeEl.id = `tree-node-${nodeName}`;
            nodeEl.dataset.cluster = clusterName;
            nodeEl.dataset.node = nodeName;
            nodeEl.innerHTML = `
          <span class="svc-toggle" title="Show services">
            <svg class="ic"
                 viewBox="0 0 24 24"
                 fill="none"
                 stroke="currentColor"
                 stroke-width="2">
              <polyline points="9 6 15 12 9 18"/>
            </svg>
          </span>
          <span class="nstatus ok"></span>
          <span class="nname">
            ${nodeName}
          </span>

          <span class="nload">
            --
          </span>
        `;

            children.appendChild(nodeEl);

            const svcWrap = document.createElement('div');
            svcWrap.className = 'tree-services';
            svcWrap.id = `tree-services-${nodeName}`;
            // svcWrap.style.display = 'none';

            const services = nodes[nodeName] || [];
            services.forEach((service) => {
                const svcEl = document.createElement('div');
                svcEl.className = 'tree-svc';

                svcEl.dataset.cluster = clusterName;
                svcEl.dataset.node = nodeName;
                svcEl.dataset.service = service.serviceName;
                svcEl.dataset.serviceType = service.serviceType;

                svcEl.innerHTML = `
                    <svg class="ico" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="2" y="3" width="20" height="14" rx="2"/><path d="M8 21h8M12 17v4"/></svg>
                    <span class="svc-name">${service.serviceName}</span>
                    <span class="svc-dot">${service.serviceType}</span>
                `;
                svcWrap.appendChild(svcEl);
            });

            children.appendChild(svcWrap);
            const toggle = nodeEl.querySelector('.svc-toggle');
            toggle.classList.add('expanded');
        });
        list.appendChild(group);
    });

    // Wire tree interactions
    $$('#treeList .group-head').forEach((g) => {
        g.onclick = () => {
            const parent = g.parentElement;
            parent.classList.toggle('collapsed');
        };
    });

    $$('#treeList .tree-node').forEach((n) => {
        n.onclick = (e) => {
            if (e.target.closest('.svc-toggle')) return; // handled below
            fetchNodeMonitoringData(
                n.dataset.cluster,
                n.dataset.node,
                state.period,
            );
        };
        const toggle = n.querySelector('.svc-toggle');
        toggle.onclick = (e) => {
            e.stopPropagation();
            toggle.classList.toggle('expanded');
            const svcWrap = n.nextElementSibling;
            if (svcWrap && svcWrap.classList.contains('tree-services')) {
                svcWrap.style.display =
                    svcWrap.style.display === 'none' ? '' : 'none';
            }
        };
    });

    $$('#treeList .tree-svc').forEach((s) => {
        s.onclick = async () => {
            const nodeInfo = state.machineStats[s.dataset.node]?.nodeInfo || {};
            console.log('nodeInfo---------', nodeInfo);

            await fetchServiceMonitoringData(
                s.dataset.cluster,
                s.dataset.node,
                s.dataset.service,
                s.dataset.serviceType,
                nodeInfo.ip_address,
                state.period,
            );
        };
    });

    highlightTreeSelection();
}

function highlightTreeSelection () {
    $$('#treeList .tree-node').forEach((n) => n.classList.remove('active'));
    $$('#treeList .tree-svc').forEach((s) => s.classList.remove('active'));
    const sel = state.selection;
    if (!sel.cluster) return;
    if (sel.kind === 'node') {
        const el = $(
            `#treeList .tree-node[data-cluster="${sel.cluster}"][data-node="${sel.node}"]`,
        );
        if (el) el.classList.add('active');
    } else if (sel.kind === 'service') {
        const el = $(
            `#treeList .tree-svc[data-cluster="${sel.cluster}"][data-node="${sel.node}"][data-service="${sel.service}"]`,
        );
        if (el) {
            el.classList.add('active');
            // Auto-expand the services group
            const parentNode =
                el.closest('.tree-services').previousElementSibling;
            if (parentNode) {
                const toggle = parentNode.querySelector('.svc-toggle');
                if (toggle && !toggle.classList.contains('expanded')) {
                    toggle.classList.add('expanded');
                    el.closest('.tree-services').style.display = '';
                }
            }
        }
    }
}

// ─── Detail panel rendering ─────────────────────────────────────────
function render () {
    const sel = state.selection;
    if (!sel.cluster || !sel.node) {
        renderEmpty();
        return;
    }
    if (sel.kind === 'service') {
        if (sel.serviceType?.includes('Infra')) renderInfraService();
        else renderService();
    } else renderNode();
    highlightTreeSelection();
    wireMetricCardClicks();
    wireChartHover();
    wireCounterCharts();
}

function renderEmpty () {
    $('#detailPanel').innerHTML = `
    <div class="empty-state">
      <div class="ill"><svg class="ic" viewBox="0 0 24 24"><path d="M3 12h4l3-9 4 18 3-9h4"/></svg></div>
      <h3>Pick a target to start monitoring</h3>
      <p>Click a node in the tree to see CPU, memory and storage metrics. Expand a node to see its services and view application-level counters.</p>
    </div>
  `;
}

function getLatestValue (series) {
    if (!series || !series.length) {
        return 0;
    }
    return series[series.length - 1]?.v || 0;
}

function renderNode () {
    const sel = state.selection;
    const node = state.machineStats[sel.node];

    const isLoading = state.loadingNode === sel.node;
    const hasError = node?.error === true;

    if (!node && !state.isLoading) {
        renderEmpty();
        return;
    }
    const nodeInfo = node?.nodeInfo || {};
    const M = nodeMetrics(sel.cluster, sel.node);

    // Latest values
    const cpuNow = getLatestValue(M.cpu);
    const memNow = getLatestValue(M.memory);
    const diskNow = getLatestValue(M.storage);
    const gpuNow = getLatestValue(M.gpuUtilization);
    const gpuMemoryNow = getLatestValue(M.gpuMemory);

    const hasCpuData = M.cpu.length > 0;
    const hasMemoryData = M.memory.length > 0;
    const hasStorageData = M.storage.length > 0;
    const hasGpuData = M.gpuUtilization.length > 0;
    const hasGpuMemoryData = M.gpuMemory.length > 0;

    // Thresholds
    const cpuStatus = thresholdStatus(cpuNow, 70, 85);
    const memStatus = thresholdStatus(memNow, 75, 90);
    const diskStatus = thresholdStatus(diskNow, 75, 90);
    const gpuStatus = thresholdStatus(gpuNow, 70, 85);
    const gpuMemoryStatus = thresholdStatus(gpuMemoryNow, 75, 90);

    // Node health check
    let healthClass = '';
    let healthLabel = '';
    if (!isLoading && !hasError && cpuStatus && memStatus) {
        if (cpuStatus !== 'ok' && memStatus !== 'ok') {
            healthClass = 'err';
            healthLabel = 'Degraded';
        } else if (cpuStatus !== 'ok' || memStatus !== 'ok') {
            healthClass = 'warn';
            healthLabel = 'Warning';
        } else {
            healthClass = 'ok';
            healthLabel = 'Healthy';
        }
    }

    // Mock breakdown data based on focused metric
    const breakdownHTML = isLoading || hasError ? '' : nodeBreakdown(node);

    // Pick the focused metric for the big chart
    const focusedChart = FocusedCharts(M, isLoading, hasError);

    $('#detailPanel').innerHTML = `
    <div class="sel-band">
      <div class="identity">
        <div class="sel-icon">
          <svg class="ic" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><rect x="2" y="3" width="20" height="6" rx="1"/><rect x="2" y="15" width="20" height="6" rx="1"/><line x1="6" y1="6" x2="6.01" y2="6"/><line x1="6" y1="18" x2="6.01" y2="18"/></svg>
        </div>
        <div class="id-text">
          <div class="hier">${sel.cluster} / </div>
          <div class="name">${nodeInfo.nodeName || sel.node}</div>
          <div class="meta">${nodeInfo.ip_address} · Port ${nodeInfo.node_port} · GPU ${nodeInfo.gpu_status}</div>
        </div>
      </div>
      ${healthLabel ? `<span class="sel-pill ${healthClass}">${healthLabel}</span>` : ''}

    </div>

    <div class="metric-cards">
      ${metricCard('cpu', 'CPU', hasCpuData ? cpuNow : 'NA', '%', cpuStatus, M.cpu, hasCpuData ? rangeSummary(M.cpu) : 'No data available', isLoading, hasError)}
      ${metricCard('memory', 'CPU Memory', hasMemoryData ? memNow : 'NA', '%', memStatus, M.memory, hasMemoryData ? rangeSummary(M.memory) : 'No data available', isLoading, hasError)}
      ${metricCard('storage', 'Storage', hasStorageData ? diskNow : 'NA', '%', diskStatus, M.storage, hasStorageData ? rangeSummary(M.storage) : 'No data available', isLoading, hasError)}
      ${metricCard('gpuUtilization', 'GPU', hasGpuData ? gpuNow : 'NA', '%', gpuStatus, M.gpuUtilization, hasGpuData ? rangeSummary(M.gpuUtilization) : 'No data available', isLoading, hasError)}
      ${metricCard('gpuMemory', 'GPU Memory', hasGpuMemoryData ? gpuMemoryNow : 'NA', '%', gpuMemoryStatus, M.gpuMemory, hasGpuMemoryData ? rangeSummary(M.gpuMemory) : 'No data available', isLoading, hasError)}
    </div>

    ${focusedChart}

    ${breakdownHTML}
  `;
}

function metricCard (
    key,
    label,
    value,
    unit,
    status,
    series,
    sub,
    isLoading,
    hasError,
) {
    const active = state.focused === key ? 'active' : '';
    const valClass = status === 'ok' ? '' : status;
    return `
        <div class="metric-card ${active}" data-focus="${key}">
            <div class="mc-label">
                <svg class="ic" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">${metricIcon(key)}</svg>
                ${label}
            </div>
            <div class="mc-value ${valClass}">
                ${
    isLoading
        ? `
            <div class="card-loading">
                <span class="spinner"></span>
                <span>Loading...</span>
            </div>
          `
        : hasError
            ? 'NA'
            : value === 'NA'
                ? 'NA'
                : `${Number(value || 0).toFixed(1)}<span class="unit">${unit}</span>`
}
            </div>
            <div class="mc-sub">
                <div class="mc-sub-left">
                ${isLoading || hasError ? '--' : sub}
    </div>
            <div class="mc-thresh">${status === 'warn' ? '<span class="warn-dot">▲</span> WARN' : status === 'err' ? '<span class="err-dot">▲</span> CRIT' : ''}</div>
            </div>

            <div class="mc-spark">${
    isLoading || hasError
        ? ''
        : renderSparkline(series, {
            color:
                              status === 'ok'
                                  ? 'var(--navy)'
                                  : status === 'warn'
                                      ? 'var(--warn)'
                                      : 'var(--err)',
        })
}
            </div>
        </div>
    `;
}

function metricIcon (key) {
    return (
        {
            cpu: '<rect x="4" y="4" width="16" height="16" rx="2"/><rect x="9" y="9" width="6" height="6"/><line x1="9" y1="1" x2="9" y2="4"/><line x1="15" y1="1" x2="15" y2="4"/><line x1="9" y1="20" x2="9" y2="23"/><line x1="15" y1="20" x2="15" y2="23"/><line x1="20" y1="9" x2="23" y2="9"/><line x1="20" y1="14" x2="23" y2="14"/><line x1="1" y1="9" x2="4" y2="9"/><line x1="1" y1="14" x2="4" y2="14"/>',
            memory: '<rect x="2" y="6" width="20" height="12" rx="1"/><line x1="6" y1="10" x2="6" y2="14"/><line x1="10" y1="10" x2="10" y2="14"/><line x1="14" y1="10" x2="14" y2="14"/><line x1="18" y1="10" x2="18" y2="14"/>',
            storage:
                '<ellipse cx="12" cy="5" rx="9" ry="3"/><path d="M3 5v14a9 3 0 0018 0V5"/><path d="M3 12a9 3 0 0018 0"/>',
            gpuUtilization:
                '<rect x="4" y="4" width="16" height="16" rx="2"/><path d="M8 8h8v8H8z"/><line x1="12" y1="1" x2="12" y2="4"/><line x1="12" y1="20" x2="12" y2="23"/>',
            gpuMemory:
                '<rect x="2" y="6" width="20" height="12" rx="1"/><line x1="6" y1="10" x2="6" y2="14"/><line x1="10" y1="10" x2="10" y2="14"/><line x1="14" y1="10" x2="14" y2="14"/><line x1="18" y1="10" x2="18" y2="14"/>',

            request: '<path d="M3 12h4l3-9 4 18 3-9h4"/>',
            error: '<circle cx="12" cy="12" r="9"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/>',
            latency: '<path d="M12 6v6l4 2"/><circle cx="12" cy="12" r="9"/>',
        }[key] || ''
    );
}

function rangeSummary (series) {
    if (!series?.length) {
        return 'No data available';
    }

    const vals = series.map((p) => p.v);
    const max = Math.max(...vals);
    const avg = vals.reduce((s, v) => s + v, 0) / vals.length;
    return `avg ${avg.toFixed(0)}<br>max ${max.toFixed(0)}`;
}

function FocusedCharts (M, isLoading, hasError) {
    const focus = state.focused;
    const total = M[`${focus}Total`];

    let series, title, color, warnAt, errAt, max, unit;
    if (focus === 'cpu') {
        series = M.cpu;
        title = 'CPU <em>utilization</em>';
        color = 'var(--navy)';
        warnAt = 70;
        errAt = 85;
        max = Math.max(100, ...series.map((p) => p.v));
        unit = '%';
    } else if (focus === 'memory') {
        series = M.memory;
        title = 'CPU Memory <em>utilization</em>';
        color = 'var(--navy)';
        warnAt = 75;
        errAt = 90;
        max = Math.max(100, ...series.map((p) => p.v));
        unit = '%';
    } else if (focus === 'storage') {
        series = M.storage;
        title = 'Storage <em>utilization</em>';
        color = 'var(--navy)';
        warnAt = 75;
        errAt = 90;
        max = Math.max(100, ...series.map((p) => p.v));
        unit = '%';
    } else if (focus === 'gpuUtilization') {
        series = M.gpuUtilization;
        title = 'GPU <em>utilization</em>';
        color = 'var(--navy)';
        warnAt = 70;
        errAt = 85;
        max = Math.max(100, ...series.map((p) => p.v));
        unit = '%';
    } else if (focus === 'gpuMemory') {
        series = M.gpuMemory;
        title = 'GPU Memory <em>utilization</em>';
        color = 'var(--navy)';
        warnAt = 70;
        errAt = 85;
        max = Math.max(100, ...series.map((p) => p.v));
        unit = '%';
    } else if (focus === 'request') {
        series = M.request;
        title = 'Request <em>rate</em>';
        color = 'var(--navy)';
        warnAt = 450;
        errAt = 500;
        max = Math.max(500, ...series.map((p) => p.v));
        unit = ' req/s';
    } else if (focus === 'error') {
        series = M.error;
        title = 'Error <em>rate</em>';
        color = 'var(--err)';
        warnAt = 2;
        errAt = 5;
        max = Math.max(10, ...series.map((p) => p.v));
        unit = '%';
    } else if (focus === 'latency') {
        series = M.latency;
        title = 'P95 <em>latency</em>';
        color = 'var(--warn)';
        warnAt = 80;
        errAt = 95;
        unit = ' ms';
        max = Math.max(100, ...series.map((p) => p.v));
    } else {
        series = M.cpu;
        title = 'CPU';
        color = 'var(--navy)';
        warnAt = 70;
        errAt = 85;
        max = Math.max(100, ...series.map((p) => p.v));
        unit = '%';
    }

    const vals = series.map((p) => p.v);
    const cur = vals[vals.length - 1],
        avg = vals.reduce((s, v) => s + v, 0) / vals.length,
        mx = Math.max(...vals);

    const chartSVG = renderChart(series, { max, color, unit, warnAt, errAt });
    // Splice the TX overlay into the chart SVG just before closing
    let chartFinal = chartSVG;
    if (isLoading) {
        chartFinal = `
            <div class="chart-loading"
                style="display:flex;justify-content:center;align-items:center;height:100%;">
                <div class="spinner"></div>
                <div>Loading chart data...</div>
            </div>
        `;
    } else if (hasError) {
        chartFinal = `
            <div class="chart-loading"
                style="display:flex;justify-content:center;align-items:center;height:100%;">
                <div>No chart data available</div>
            </div>
        `;
    }

    return `
    <div class="chart-section">
      <div class="chart-head">
        <div class="ch-title">${title}</div>
        <div class="ch-stats">
          ${Number.isFinite(total) ? `<div class="s"><span class="l">Total</span><span class="v">${total.toFixed(1)}GB</span></div>` : ''}
          <div class="s"><span class="l">Current</span><span class="v">${isLoading || hasError ? '--' : `${cur.toFixed(1)}${unit}`}</span></div>
          <div class="s"><span class="l">Avg (${state.period})</span><span class="v">${isLoading || hasError ? '--' : `${avg.toFixed(1)}${unit}`}</span></div>
          <div class="s"><span class="l">Max</span><span class="v">${isLoading || hasError ? '--' : `${mx.toFixed(1)}${unit}`}</span></div>
        </div>
      </div>
        <div class="chart-wrap">
            ${chartFinal}
            <div class="chart-tip" id="chartTip"></div>
        </div>
    </div>
  `;
}

function nodeBreakdown (node) {
    const focus = state.focused;
    if (focus === 'cpu' || focus === 'memory') {
        // Top processes
        const procs = topProcesses(node, focus);
        return `
      <div class="breakdown">
        <div class="breakdown-head">
          <span class="b-title">Top processes by ${focus}</span>
          <span class="b-sub">${procs.length}</span>
        </div>
        <table class="b-table">
          <thead>
            <tr>
              <th style="width:60px;">Instance</th>
              <th>Process</th>
              <th>User</th>
              <th class="r">CPU %</th>
              <th class="r">Memory</th>
              <th class="r">RSS</th>
            </tr>
          </thead>
          <tbody>
            ${procs
        .map(
            (p) => `
                  <tr>
                    <td class="pid">${p.instance}</td>
                    <td><span class="nm">${p.cmd}</span></td>
                    <td class="mono">${p.user}</td>
                    <td class="r">${focus === 'cpu' ? `<span class="usage-bar"><span class="fill${p.cpu > 50 ? ' warn' : ''}" style="width:${Math.min(100, p.cpu)}%"></span></span>` : ''}${p.cpu.toFixed(1)}</td>
                    <td class="r">${focus === 'memory' ? `<span class="usage-bar"><span class="fill${p.mem > 40 ? ' warn' : ''}" style="width:${Math.min(100, p.mem / 50)}%"></span></span>` : ''}${p.mem.toFixed(1)} MB</td>
                    <td class="r">${p.rss}</td>
                  </tr>
                `,
        )
        .join('')}
          </tbody>
        </table>
      </div>
    `;
    }
    if (focus === 'storage') {
        // Mounted volumes
        const vols = mountedVolumes(node);
        return `
      <div class="breakdown">
        <div class="breakdown-head">
          <span class="b-title">Mounted volumes</span>
          <span class="b-sub">${vols.length} volumes · total ${vols.reduce((s, v) => s + v.size, 0)} GB</span>
        </div>
        <table class="b-table">
          <thead>
            <tr>
              <th>Mount point</th>
              <th>Device</th>
              <th>Filesystem</th>
              <th class="r">Used</th>
              <th class="r">Free</th>
              <th class="r">Usage</th>
            </tr>
          </thead>
          <tbody>
            ${vols
        .map((v) => {
            const pct = v.usage;
            const cls = pct > 90 ? 'err' : pct > 75 ? 'warn' : '';
            return `
            <tr>
              <td><span class="nm mono">${v.mount}</span></td>
              <td class="mono">${v.device}</td>
              <td class="mono">${v.fs}</td>
              <td class="r">${v.used} GB</td>
              <td class="r">${(v.size - v.used).toFixed(1)} GB</td>
              <td class="r">
                <span class="usage-bar"><span class="fill ${cls}" style="width:${pct}%"></span></span>
                ${pct.toFixed(1)}%
              </td>
            </tr>
          `;
        })
        .join('')}
          </tbody>
        </table>
      </div>
    `;
    }

    return '';
}

function topProcesses (node, sortBy) {
    // const nodeName = node?.nodeInfo?.nodeName || 'NODE';
    const processes =
        (node?.top_processes || []).length > 0
            ? node.top_processes
            : state.lastValidMetrics?.topProcesses || [];

    if ((node?.top_processes || []).length > 0) {
        state.lastValidMetrics = {
            ...state.lastValidMetrics,
            topProcesses: node.top_processes,
        };
    }

    const procs = processes.map((p) => ({
        instance: p.instance,
        cmd: p.process_name,
        user: '-',
        cpu: p.cpu_usage || 0,
        mem: p.memory_usage || 0,
        rss: '-',
    }));

    procs.sort(
        (a, b) =>
            b[sortBy === 'cpu' ? 'cpu' : 'mem'] -
            a[sortBy === 'cpu' ? 'cpu' : 'mem'],
    );

    return procs.slice(0, 8);
}

function mountedVolumes (node) {
    const volumes =
        (node?.volume_mounts || []).length > 0
            ? node.volume_mounts
            : state.lastValidMetrics?.volumeMounts || [];

    if ((node?.volume_mounts || []).length > 0) {
        state.lastValidMetrics = {
            ...state.lastValidMetrics,
            volumeMounts: node.volume_mounts,
        };
    }

    return volumes.map((v) => ({
        mount: v.mountpoint,
        device: v.device,
        fs: v.filesystem,
        size: v.total_storage,
        used: v.used_storage,
        usage: v.usage_percent,
    }));
}

// ─── Service rendering ──────────────────────────────────────────────
function renderService () {
    const sel = state.selection;
    const cacheKey = `${sel.cluster}|${sel.node}|${sel.service}`;
    const isLoading = state.loadingService === sel.service;
    const node = state.machineStats[sel.node];

    if (!node) {
        renderEmpty();
        return;
    }

    const nodeInfo = node?.nodeInfo || {};

    const serviceData =
        state.serviceStats[sel.service] ||
        state.lastValidServiceStats[cacheKey] ||
        {};

    const hasError = serviceData?.error === true;
    const serviceInfo = serviceData.serviceInfo || {};
    const svc = { type: serviceInfo.serviceType || '', error: false };

    const M = serviceMetrics(sel.cluster, sel.node, sel.service);

    if (
        !['cpu', 'memory', 'request', 'error', 'latency'].includes(
            state.focused,
        )
    ) {
        state.focused = 'cpu';
    }

    const cpuNow = getLatestValue(M.cpu);
    const memNow = getLatestValue(M.memory);
    const reqNow = getLatestValue(M.request);
    const errNow = getLatestValue(M.error);
    const latencyNow = getLatestValue(M.latency);

    // latency adjustable
    let latencyNowSec = latencyNow;
    let latencyUnit = ' ms';
    if (latencyNow && latencyNow > 499) {
        latencyNowSec = latencyNow / 1000;
        latencyUnit = ' s';
    }

    const cpuStatus = thresholdStatus(cpuNow, 70, 85);
    const memStatus = thresholdStatus(memNow, 75, 90);
    const reqStatus = thresholdStatus(reqNow, 450, 500);
    const errStatus = thresholdStatus(errNow, 2, 5);
    const latencyStatus = thresholdStatus(latencyNow, 80, 95);

    const focusedChart = FocusedCharts(M, isLoading, hasError);
    const specific = renderDynamicServiceCharts(
        serviceData.serviceStats?.counterData || {},
    );

    // Service health check
    let healthClass = '';
    let healthLabel = '';
    if (!isLoading && !hasError && errStatus && latencyStatus) {
        if (errStatus !== 'ok' && latencyStatus !== 'ok') {
            healthClass = 'err';
            healthLabel = 'Degraded';
        } else if (errStatus !== 'ok' || latencyStatus !== 'ok') {
            healthClass = 'warn';
            healthLabel = 'Warning';
        } else {
            healthClass = 'ok';
            healthLabel = 'Healthy';
        }
    }

    $('#detailPanel').innerHTML = `
        <div class="sel-band">
            <div class="identity">
                <div class="sel-icon svc">
                    <svg class="ic" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8">
                        <circle cx="12" cy="12" r="3"/>
                        <path d="M19.4 15a1.65 1.65 0 00.33 1.82l.06.06a2 2 0 01-2.83 2.83l-.06-.06a1.65 1.65 0 00-1.82-.33 1.65 1.65 0 00-1 1.51V21a2 2 0 01-4 0v-.09A1.65 1.65 0 009 19.4a1.65 1.65 0 00-1.82.33l-.06.06a2 2 0 01-2.83-2.83l.06-.06a1.65 1.65 0 00.33-1.82 1.65 1.65 0 00-1.51-1H3a2 2 0 010-4h.09A1.65 1.65 0 004.6 9a1.65 1.65 0 00-.33-1.82l-.06-.06a2 2 0 012.83-2.83l.06.06a1.65 1.65 0 001.82.33H9a1.65 1.65 0 001-1.51V3a2 2 0 014 0v.09a1.65 1.65 0 001 1.51 1.65 1.65 0 001.82-.33l.06-.06a2 2 0 012.83 2.83l-.06.06a1.65 1.65 0 00-.33 1.82V9a1.65 1.65 0 001.51 1H21a2 2 0 010 4h-.09a1.65 1.65 0 00-1.51 1z"/>
                    </svg>
                </div>

                <div class="id-text">
                    <div class="hier">${sel.cluster} / ${nodeInfo.nodeName || sel.node} /</div>
                    <div class="name">${sel.service}</div>
                    <div class="meta">${nodeInfo.ip_address || 'NA'} · Port ${serviceInfo.servicePort || 'NA'} · Service ${serviceInfo.serviceType || 'NA'}</div>
                </div>
            </div>
            ${healthLabel ? `<span class="sel-pill ${healthClass}">${healthLabel}</span>` : ''}
        </div>

        <div class="metric-cards">
            ${metricCard('cpu', 'CPU', M.cpu.length ? cpuNow : 'NA', '%', cpuStatus, M.cpu, M.cpu.length ? rangeSummary(M.cpu) : 'No data available', isLoading, hasError)}
            ${metricCard('memory', 'CPU Memory', M.memory.length ? memNow : 'NA', '%', memStatus, M.memory, M.memory.length ? rangeSummary(M.memory) : 'No data available', isLoading, hasError)}
            ${metricCard('request', 'Request Rate', M.request.length ? reqNow : 'NA', ' req/s', reqStatus, M.request, M.request.length ? rangeSummary(M.request) : 'No data available', isLoading, hasError)}
            ${metricCard('error', 'Error Rate', M.error.length ? errNow : 'NA', '%', errStatus, M.error, M.error.length ? rangeSummary(M.error) : 'No data available', isLoading, hasError)}
            ${metricCard('latency', 'P95 Latency', M.latency.length ? latencyNowSec : 'NA', latencyUnit, latencyStatus, M.latency, M.latency.length ? rangeSummary(M.latency) : 'No data available', isLoading, hasError)}
        </div>

        ${focusedChart}

        <div class="svc-section-head">
            <h4>
                ${svc.type.charAt(0).toUpperCase() + svc.type.slice(1)}
                -specific <em>counters</em>
            </h4>

            <span class="h-sub">
                scraped from ${svc.type}_exporter
            </span>
        </div>

        ${specific}
    `;
}

function renderInfraService () {
    const sel = state.selection;
    const cacheKey = `${sel.cluster}|${sel.node}|${sel.service}`;

    const node = state.machineStats[sel.node];
    if (!node) {
        renderEmpty();
        return;
    }

    const nodeInfo = node?.nodeInfo || {};
    const serviceData =
        state.serviceStats[sel.service] ||
        state.lastValidServiceStats[cacheKey] ||
        {};

    const serviceInfo = serviceData.serviceInfo || {};
    const isLoading = state.loadingService === sel.service;
    const hasError = serviceData?.error === true;

    const M = infraServiceMetrics(sel.cluster, sel.node, sel.service);

    const cpuNow = getLatestValue(M.cpu);
    const memNow = getLatestValue(M.memory);
    const cpuStatus = thresholdStatus(cpuNow, 70, 85);
    const memStatus = thresholdStatus(memNow, 75, 90);
    const focusedChart = FocusedCharts(M, isLoading, hasError);

    // Service health check
    let healthClass = '';
    let healthLabel = '';
    if (!isLoading && !hasError && cpuStatus && memStatus) {
        if (cpuStatus !== 'ok' && memStatus !== 'ok') {
            healthClass = 'err';
            healthLabel = 'Degraded';
        } else if (cpuStatus !== 'ok' || memStatus !== 'ok') {
            healthClass = 'warn';
            healthLabel = 'Warning';
        } else {
            healthClass = 'ok';
            healthLabel = 'Healthy';
        }
    }

    $('#detailPanel').innerHTML = `
        <div class="sel-band">
            <div class="identity">
                <div class="sel-icon svc">
                    <svg class="ic" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 00.33 1.82l.06.06a2 2 0 01-2.83 2.83l-.06-.06a1.65 1.65 0 00-1.82-.33 1.65 1.65 0 00-1 1.51V21a2 2 0 01-4 0v-.09A1.65 1.65 0 009 19.4a1.65 1.65 0 00-1.82.33l-.06.06a2 2 0 01-2.83-2.83l.06-.06a1.65 1.65 0 00.33-1.82 1.65 1.65 0 00-1.51-1H3a2 2 0 010-4h.09A1.65 1.65 0 004.6 9a1.65 1.65 0 00-.33-1.82l-.06-.06a2 2 0 012.83-2.83l.06.06a1.65 1.65 0 001.82.33H9a1.65 1.65 0 001-1.51V3a2 2 0 014 0v.09a1.65 1.65 0 001 1.51 1.65 1.65 0 001.82-.33l.06-.06a2 2 0 012.83 2.83l-.06.06a1.65 1.65 0 00-.33 1.82V9a1.65 1.65 0 001.51 1H21a2 2 0 010 4h-.09a1.65 1.65 0 00-1.51 1z"/></svg>
                </div>

                <div class="id-text">
                    <div class="hier">${sel.cluster} / ${nodeInfo.nodeName || sel.node} /</div>
                    <div class="name">${sel.service}</div>
                    <div class="meta">${nodeInfo.ip_address || 'NA'} · Port ${serviceInfo.servicePort || 'NA'} · Service ${serviceInfo.serviceType || 'NA'}</div>
                </div>
            </div>

            ${healthLabel ? `<span class="sel-pill ${healthClass}">${healthLabel}</span>` : ''}
        </div>

        <div class="metric-cards">
            ${metricCard('cpu', 'CPU', M.cpu.length ? cpuNow : 'NA', '%', cpuStatus, M.cpu, M.cpu.length ? rangeSummary(M.cpu) : 'No data available', isLoading, hasError)}
            ${metricCard('memory', 'CPU Memory', M.memory.length ? memNow : 'NA', '%', memStatus, M.memory, M.memory.length ? rangeSummary(M.memory) : 'No data available', isLoading, hasError)}
        </div>

        ${focusedChart}
    `;
}

function serviceMetrics (cluster, nodeId, serviceId) {
    const cacheKey = `${cluster}|${nodeId}|${serviceId}`;

    const serviceData =
        state.serviceStats[serviceId] ||
        state.lastValidServiceStats[cacheKey] ||
        {};

    const stats = serviceData.serviceStats?.stats || {};
    const lastValid = state.lastValidServiceStats[cacheKey] || {};

    const cpuValues = stats.cpu_utilization_data?.data || [];
    const usedMemory = stats.used_memory_data?.data || [];
    const totalMemory = stats.total_memory_data?.data || [];
    const requestValues = stats.request_rate?.data || [];
    const errorValues = stats.error_rate?.data || [];
    const latencyValues = stats.p95_latency?.data || [];

    function buildSeries (values) {
        const { step } = rangeBuckets(state.period);

        return values.map((value, index) => ({
            t: (values.length - index) * step,
            v: Number(value || 0),
        }));
    }

    if (cpuValues.length) {
        state.lastValidServiceStats[cacheKey] = {
            ...state.lastValidServiceStats[cacheKey],
            cpuValues,
        };
    }

    const memoryUsage =
        usedMemory.length && totalMemory.length
            ? usedMemory.map((used, index) => {
                const total = totalMemory[index] || 1;
                return (used / total) * 100;
            })
            : lastValid.memoryUsage || [];

    if (memoryUsage.length) {
        state.lastValidServiceStats[cacheKey] = {
            ...state.lastValidServiceStats[cacheKey],
            memoryUsage,
            memoryTotal: totalMemory.at(-1),
        };
    }

    if (requestValues.length) {
        state.lastValidServiceStats[cacheKey] = {
            ...state.lastValidServiceStats[cacheKey],
            requestValues,
        };
    }

    if (errorValues.length) {
        state.lastValidServiceStats[cacheKey] = {
            ...state.lastValidServiceStats[cacheKey],
            errorValues,
        };
    }

    if (latencyValues.length) {
        state.lastValidServiceStats[cacheKey] = {
            ...state.lastValidServiceStats[cacheKey],
            latencyValues,
        };
    }

    const requestSeries = requestValues.length
        ? requestValues
        : lastValid.requestValues || [];
    const errorSeries = errorValues.length
        ? errorValues
        : lastValid.errorValues || [];
    const latencySeries = latencyValues.length
        ? latencyValues
        : lastValid.latencyValues || [];

    return {
        cpu: buildSeries(
            cpuValues.length ? cpuValues : lastValid.cpuValues || [],
        ),
        memory: buildSeries(memoryUsage),
        memoryTotal: totalMemory.at(-1) || lastValid.memoryTotal,
        request: buildSeries(requestSeries),
        error: buildSeries(errorSeries),
        latency: buildSeries(latencySeries),
    };
}

function infraServiceMetrics (cluster, nodeId, serviceId) {
    const cacheKey = `${cluster}|${nodeId}|${serviceId}`;

    const serviceData =
        state.serviceStats[serviceId] ||
        state.lastValidServiceStats[cacheKey] ||
        {};

    const stats = serviceData.serviceStats?.stats || {};
    const lastValid = state.lastValidServiceStats[cacheKey] || {};

    const cpuValues = stats.cpu_utilization_data?.data || [];
    const usedMemory = stats.used_memory_data?.data || [];
    const totalMemory = stats.total_memory_data?.data || [];

    function buildSeries (values) {
        const { step } = rangeBuckets(state.period);

        return values.map((value, index) => ({
            t: (values.length - index) * step,
            v: Number(value || 0),
        }));
    }

    const memoryUsage =
        usedMemory.length && totalMemory.length
            ? usedMemory.map((used, index) => {
                const total = totalMemory[index] || 1;
                return (used / total) * 100;
            })
            : lastValid.memoryUsage || [];

    if (cpuValues.length) {
        state.lastValidServiceStats[cacheKey] = {
            ...state.lastValidServiceStats[cacheKey],
            cpuValues,
        };
    }

    if (memoryUsage.length) {
        state.lastValidServiceStats[cacheKey] = {
            ...state.lastValidServiceStats[cacheKey],
            memoryUsage,
            memoryTotal: totalMemory.at(-1),
        };
    }

    return {
        cpu: buildSeries(
            cpuValues.length ? cpuValues : lastValid.cpuValues || [],
        ),
        memory: buildSeries(memoryUsage),
        memoryTotal: totalMemory.at(-1) || lastValid.memoryTotal,
    };
}

function renderDynamicServiceCharts (rawData) {
    if (!rawData || !rawData.labels) {
        return `
            <div class="empty-chart">
                ${
    state.loadingService
        ? 'Loading service specific data...'
        : 'No service specific data available'
}
            </div>
        `;
    }

    const labels = rawData.labels || [];
    const grouped = {};

    Object.entries(rawData).forEach(([key, value]) => {
        if (key === 'labels') {
            return;
        }

        const displayName = value.display_name || 'Unknown';
        if (!grouped[displayName]) {
            grouped[displayName] = [];
        }

        grouped[displayName].push({ name: key, data: value.data || [] });
    });

    const entries = Object.entries(grouped);

    if (!state.expandedCounter && entries.length) {
        state.expandedCounter = entries[0][0];
    }

    let html = '';

    entries.forEach(([displayName, seriesList], index) => {
        const expanded = state.expandedCounter === displayName;
        let maxY = 1;

        seriesList.forEach((series) => {
            (series.data || []).forEach((v) => {
                maxY = Math.max(maxY, Number(v || 0));
            });
        });

        const avg = seriesList.length
            ? seriesList[0].data.reduce((s, v) => s + Number(v || 0), 0) /
              Math.max(1, seriesList[0].data.length)
            : 0;

        const current = seriesList.length
            ? Number(seriesList[0].data.at(-1) || 0)
            : 0;

        html += `
                <div class="chart-section" style="margin-top:24px;">
                    <div class="chart-head svc-counter-head"
                         data-counter="${displayName}"
                         style="cursor:pointer;">

                        <div class="ch-title">
                            ${expanded ? '▼' : '▶'}
                            ${displayName}
                        </div>

                        ${
    expanded
        ? `
            <div class="ch-stats">
                <div class="s">
                    <span class="l">Current</span>
                    <span class="v">${current.toFixed(0)}</span>
                </div>

                <div class="s">
                    <span class="l">Avg (${state.period})</span>
                    <span class="v">${avg.toFixed(0)}</span>
                </div>

                <div class="s">
                    <span class="l">Max</span>
                    <span class="v">${maxY.toFixed(0)}</span>
                </div>
            </div>
        `
        : ''
}
                    </div>

                    ${
    expanded
        ? `
            <div class="dynamic-legend">
                ${seriesList
        .map(
            (s, idx) => `
                    <span class="legend-item">
                        <span class="legend-dot legend-${idx}"></span>
                        ${s.name}
                    </span>
                `,
        )
        .join('')}
            </div>

            <div class="chart-wrap">
                ${renderMultiLineChart(labels, seriesList)}
                <div class="chart-tip"></div>
            </div>
        `
        : ''
}
                </div>
            `;
    });

    return html;
}

function renderMultiLineChart (labels, seriesList) {
    const colors = [
        'var(--navy)',
        '#91cc75',
        '#fac858',
        '#ee6666',
        '#73c0de',
        '#3ba272',
    ];

    const w = 900;
    const h = 240;

    const padL = 44;
    const padR = 12;
    const padT = 16;
    const padB = 24;

    const cw = w - padL - padR;
    const ch = h - padT - padB;

    let maxY = 1;

    seriesList.forEach((series) => {
        (series.data || []).forEach((v) => {
            maxY = Math.max(maxY, Number(v || 0));
        });
    });

    maxY = Math.ceil(maxY);

    // Y Axis
    const ticks = 5;
    let yAxis = '';

    for (let i = 0; i <= ticks; i++) {
        const y = padT + (ch * i) / ticks;
        const val = maxY * (1 - i / ticks);

        yAxis += `
            <line
                x1="${padL}"
                y1="${y.toFixed(1)}"
                x2="${w - padR}"
                y2="${y.toFixed(1)}"
                stroke="var(--line)"
                stroke-width="0.5"
                stroke-dasharray="${i === ticks ? '0' : '2 3'}"
            />

            <text
                x="${padL - 6}"
                y="${y + 3}"
                font-size="10"
                font-family="var(--mono)"
                fill="var(--ink-4)"
                text-anchor="end">
                ${Math.round(val)}
            </text>
        `;
    }

    // X Axis (backend labels directly)
    let xAxis = '';
    const xTicks = Math.min(5, labels.length - 1);
    for (let i = 0; i <= xTicks; i++) {
        const index = Math.round(((labels.length - 1) * i) / xTicks);

        const x = padL + (cw * i) / xTicks;

        xAxis += `
            <text
                x="${x.toFixed(1)}"
                y="${h - 6}"
                font-size="10"
                font-family="var(--mono)"
                fill="var(--ink-4)"
                text-anchor="middle">
                ${formatCounterLabel(labels[index])}
            </text>
        `;
    }

    let areas = '';
    let lines = '';
    let points = '';

    seriesList.forEach((series, idx) => {
        const values = series.data || [];
        const size = Math.min(labels.length, values.length);

        if (!values.length) {
            return;
        }

        const chartSeries = [];

        for (let i = 0; i < size; i++) {
            chartSeries.push({ v: Number(values[i] || 0) });
        }

        let linePath = '';
        let areaPath = `M0,${ch}`;

        chartSeries.forEach((point, i) => {
            const x = (cw * i) / Math.max(1, chartSeries.length - 1);
            const y = ch * (1 - point.v / maxY);
            linePath += i === 0 ? `M${x},${y}` : ` L${x},${y}`;
            areaPath += ` L${x},${y}`;

            points += `
                <circle
                    cx="${(padL + x).toFixed(1)}"
                    cy="${(padT + y).toFixed(1)}"
                    r="3"
                    fill="transparent"
                    data-v="${point.v.toFixed(2)}"
                    data-label="${labels[i]}"
                    data-index="${i}"
                    data-series="${idx}"
                    data-name="${series.name}"
                    data-unit=""
                    class="tip-pt"
                />
            `;
        });

        areaPath += ` L${cw},${ch} Z`;

        areas += `
            <g transform="translate(${padL},${padT})">
                <path
                    d="${areaPath}"
                    fill="${colors[idx % colors.length]}"
                    opacity="0.08"
                />
            </g>
        `;

        lines += `
            <g transform="translate(${padL},${padT})">
                <path
                    d="${linePath}"
                    stroke="${colors[idx % colors.length]}"
                    stroke-width="2"
                    stroke-opacity=".9"
                    fill="none"
                    stroke-linecap="round"
                    stroke-linejoin="round"
                />
            </g>
        `;
    });

    return `
        <svg
            viewBox="0 0 ${w} ${h}"
            preserveAspectRatio="none">
            ${yAxis}
            ${xAxis}
            ${areas}
            ${lines}
            ${points}
        </svg>
    `;
}

// ─── Interactions ───────────────────────────────────────────────────
function wireMetricCardClicks () {
    $$('#detailPanel .metric-card').forEach((c) => {
        c.onclick = () => {
            state.focused = c.dataset.focus;
            render();
        };
    });
}

function wireCounterCharts () {
    $$('#detailPanel .svc-counter-head').forEach((h) => {
        h.onclick = () => {
            state.expandedCounter = h.dataset.counter;
            render();
        };
    });
}

function wireChartHover () {
    const wraps = $$('#detailPanel .chart-wrap');
    wraps.forEach((wrap) => {
        const tip = wrap.querySelector('.chart-tip');
        const pts = $$('.tip-pt', wrap);
        pts.forEach((pt) => {
            pt.addEventListener('mouseenter', () => {
                const rect = wrap.getBoundingClientRect();
                const svg = wrap.querySelector('svg');
                const vb = svg.viewBox.baseVal;
                const xRatio = rect.width / vb.width;
                const yRatio = rect.height / vb.height;
                const cx = parseFloat(pt.getAttribute('cx'));
                const cy = parseFloat(pt.getAttribute('cy'));

                const idx = pt.dataset.index;
                if (idx !== undefined) {
                    const index = Number(idx);

                    const allPts = [
                        ...wrap.querySelectorAll(
                            `.tip-pt[data-index="${index}"]`,
                        ),
                    ];

                    let html = `<div class="t">${formatCounterLabel(pt.dataset.label)}</div>`;

                    allPts.forEach((p) => {
                        html += `<div>${p.dataset.name} : ${Number(p.dataset.v).toFixed(0)}</div>`;
                    });

                    tip.innerHTML = html;
                } else {
                    const v = parseFloat(pt.dataset.v);
                    const t = parseFloat(pt.dataset.t);
                    const unit = pt.dataset.unit || '';
                    tip.innerHTML = `<div class="t">${formatXAxisTime(t)}</div>${v.toFixed(2)}${unit}`;
                }

                tip.classList.add('show');
                const tipWidth = tip.offsetWidth;
                const tipHeight = tip.offsetHeight;
                let left = cx * xRatio - tipWidth / 2;
                if (left < 8) left = 8;
                if (left + tipWidth > rect.width - 8)
                    left = rect.width - tipWidth - 8;
                let top = cy * yRatio - tipHeight - 12;
                if (top < 8) top = cy * yRatio + 12;
                tip.style.left = left + 'px';
                tip.style.top = top + 'px';
            });
            pt.addEventListener('mouseleave', () =>
                tip.classList.remove('show'),
            );
        });
    });
}

// Time range buttons
$$('#rangeGroup .range-btn').forEach((b) => {
    b.onclick = () => {
        $$('#rangeGroup .range-btn').forEach((x) =>
            x.classList.remove('active'),
        );
        b.classList.add('active');
        const newPeriod = b.dataset.range;
        state.period = newPeriod;

        const sel = state.selection;
        if (!sel.cluster || !sel.node) {
            return;
        }

        if (sel.kind === 'node') {
            fetchNodeMonitoringData(sel.cluster, sel.node, state.period);
        } else if (sel.kind === 'service') {
            const nodeInfo = state.machineStats[sel.node]?.nodeInfo || {};
            fetchServiceMonitoringData(
                sel.cluster,
                sel.node,
                sel.service,
                sel.serviceType,
                nodeInfo.ip_address,
                state.period,
            );
        }
    };
});

// Auto-refresh toggle (visual only in this demo — no real polling)
let refreshTimer = null;
function setAutoRefresh (on) {
    state.autoRefresh = on;
    const btn = $('#refreshToggle');
    btn.classList.toggle('on', on);
    btn.innerHTML = on
        ? `<svg class="ic" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M1 4v6h6M23 20v-6h-6"/><path d="M20.49 9A9 9 0 005.64 5.64L1 10m22 4l-4.64 4.36A9 9 0 013.51 15"/></svg> Auto-refresh · ${state.autoRefreshInterval / 1000}s`
        : '<svg class="ic" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="5 3 19 12 5 21 5 3"/></svg> Paused';
    if (refreshTimer) {
        clearInterval(refreshTimer);
        refreshTimer = null;
    }
    if (on) {
        refreshTimer = setInterval(() => {
            const sel = state.selection;
            if (!sel.cluster || !sel.node) {
                return;
            }

            if (sel.kind === 'node') {
                fetchNodeMonitoringData(
                    sel.cluster,
                    sel.node,
                    state.period,
                    true,
                );
            } else if (sel.kind === 'service') {
                const nodeInfo = state.machineStats[sel.node]?.nodeInfo || {};
                fetchServiceMonitoringData(
                    sel.cluster,
                    sel.node,
                    sel.service,
                    sel.serviceType,
                    nodeInfo.ip_address,
                    state.period,
                    true,
                );
            }
        }, state.autoRefreshInterval);
    }
}
$('#refreshToggle').onclick = () => setAutoRefresh(!state.autoRefresh);

// ─── Init ────────────────────────────────────────────────────────────
//renderTree();
fetchMonitoringTree().then(() => {
    const clusterName = state.selection.cluster || state.clusters[0];
    const nodeName =
        state.selection.node ||
        Object.keys(state.clusterNodes[clusterName] || {})[0];
    if (clusterName && nodeName) {
        fetchNodeMonitoringData(clusterName, nodeName, state.period);
    }
});
setAutoRefresh(state.autoRefresh);
