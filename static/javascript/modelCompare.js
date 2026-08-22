/* global setTimeout, FormData, fetch, localStorage ,DOMParser, clearTimeout*/
/* eslint-disable no-console */

(function () {
    // ── CSRF ──────────────────────────────────────────────────────────────────────
    function getCookie (name) {
        let cookieValue = null;
        if (document.cookie && document.cookie !== '') {
            const cookies = document.cookie.split(';');
            for (let i = 0; i < cookies.length; i++) {
                const cookie = cookies[i].trim();
                if (cookie.substring(0, name.length + 1) === name + '=') {
                    cookieValue = decodeURIComponent(
                        cookie.substring(name.length + 1),
                    );
                    break;
                }
            }
        }
        return cookieValue;
    }

    const csrftoken = getCookie('csrftoken');
    // ── RELOAD DETAIL PAGE ────────────────────────────────────────────────────────
    async function reloadCompareDetail () {
        const compareId = document.getElementById('currentCompareId')?.value;
        if (!compareId) {
            window.location.reload();
            return;
        }

        const formData = new FormData();
        formData.append('user-action', 'compare_info');
        formData.append('compare_id', compareId);

        try {
            const res = await fetch(window.location.href, {
                method: 'POST',
                headers: { 'X-CSRFToken': csrftoken },
                body: formData,
            });
            if (!res.ok) {
                window.location.reload();
                return;
            }

            const html = await res.text();
            const parser = new DOMParser();
            const doc = parser.parseFromString(html, 'text/html');

            const swap = (sel) => {
                const n = doc.querySelector(sel);
                const o = document.querySelector(sel);
                if (n && o) o.innerHTML = n.innerHTML;
            };

            swap('#slotRow');
            swap('.kpi-matrix');
            swap('.feat-card');
            swap('#graphDistBody');

            // Sync graph data tag and re-render histograms
            const updatedGraphEl = doc.getElementById('graph-dist-data');
            const localGraphEl = document.getElementById('graph-dist-data');
            if (updatedGraphEl && localGraphEl) {
                localGraphEl.textContent = updatedGraphEl.textContent;
            }
            initGraphDist();
        } catch (err) {
            console.error('Reload error:', err);
            window.location.reload();
        }
    }

    // ── THEME ─────────────────────────────────────────────────────────────────────
    (function () {
        try {
            let t = localStorage.getItem('iktara-theme');
            if (t !== 'light' && t !== 'dark') {
                t =
                    window.matchMedia &&
                    window.matchMedia('(prefers-color-scheme: dark)').matches
                        ? 'dark'
                        : 'light';
            }
            document.documentElement.setAttribute('data-theme', t);
        } catch {
            document.documentElement.setAttribute('data-theme', 'light');
        }
    })();

    // ── TOAST ─────────────────────────────────────────────────────────────────────

    function showToast (msg, type = 'success') {
        const toast = document.getElementById('toast');
        const icon = document.getElementById('toastIcon');

        const icons = {
            success: '<polyline points="20 6 9 17 4 12"/>',
            error: '<line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>',
            warn: '<path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/>',
        };

        toast.classList.remove('toast-success', 'toast-error', 'toast-warn');
        toast.classList.add(`toast-${type}`);
        icon.innerHTML = icons[type] || icons.success;
        document.getElementById('toastMsg').textContent = msg;

        toast.style.opacity = '1';
        toast.style.transform = 'translateY(0)';
        toast.style.pointerEvents = 'auto';

        clearTimeout(toast._timer);
        toast._timer = setTimeout(() => {
            toast.style.opacity = '0';
            toast.style.transform = 'translateY(8px)';
            toast.style.pointerEvents = 'none';
        }, 3000);
    }

    // ── METRIC PILLS ──────────────────────────────────────────────────────────────
    document.querySelectorAll('.metric-pill').forEach((pill) => {
        pill.addEventListener('click', () => {
            document
                .querySelectorAll('.metric-pill')
                .forEach((p) => p.classList.remove('active'));
            pill.classList.add('active');
        });
    });

    // ── DRAWER ELEMENTS ───────────────────────────────────────────────────────────
    const compareModal = document.getElementById('compareModal');
    const addSlotBtn = document.getElementById('addSlotBtn');
    const closeCompareModal = document.getElementById('closeCompareModal');
    const closeCompareBtn = document.getElementById('closeCompareBtn');
    const addCompareBtn = document.getElementById('addCompareBtn');
    //const selectModel       = document.getElementById('selectModel');   // may be null
    //const selectAlgo        = document.getElementById('selectAlgo');    // may be null
    const modelSearchInput = document.getElementById('modelSearchInput');
    //const algoPickerList    = document.getElementById('algoPickerList');
    //const selectedSummary   = document.getElementById('selectedSummary');
    //const selectedModelLabel = document.getElementById('selectedModelLabel');
    //const selectedAlgoLabel  = document.getElementById('selectedAlgoLabel');

    let chosenModel = '';
    let chosenAlgo = '';
    let currentStep = 1;

    // ── DRAWER OPEN / CLOSE ───────────────────────────────────────────────────────
    // ── ALGO LIST DATA (from json_script tag, same dict as algo_detail) ────────
    const algoListEl = document.getElementById('algo-list-data');
    const algoData = algoListEl ? JSON.parse(algoListEl.textContent) : {};

    // ── DRAWER ELEMENTS (new) ─────────────────────────────────────────────────────
    const drawerBackBtn = document.getElementById('drawerBackBtn');
    const drawerStep1 = document.getElementById('drawerStep1');
    const drawerStep2 = document.getElementById('drawerStep2');
    const step1Dot = document.getElementById('step1Dot');
    const step2Dot = document.getElementById('step2Dot');
    const algoPickList = document.getElementById('algoPickList');
    const algoContextModel = document.getElementById('algoContextModel');

    // ── DRAWER OPEN / CLOSE ───────────────────────────────────────────────────────
    function openDrawer () {
        if (!compareModal) return;
        compareModal.classList.add('open');
        resetDrawer();
    }

    function closeDrawer () {
        if (!compareModal) return;
        compareModal.classList.remove('open');
    }

    // ── FILTER MODELS (step 1 search) ─────────────────────────────────────────────
    function filterModels (query) {
        const q = query.toLowerCase();
        document
            .querySelectorAll('#modelPickerList .pick-item')
            .forEach((item) => {
                const nm = (item.dataset.modelName || '').toLowerCase();
                item.style.display = nm.includes(q) ? '' : 'none';
            });
    }

    // ── RENDER STEP ───────────────────────────────────────────────────────────────
    function renderStep (step) {
        currentStep = step;

        drawerStep1.style.display = step === 1 ? '' : 'none';
        drawerStep2.style.display = step === 2 ? '' : 'none';

        // Step dots
        [step1Dot, step2Dot].forEach((d, i) => {
            d.classList.remove('active', 'done');
            if (i + 1 < step) d.classList.add('done');
            else if (i + 1 === step) d.classList.add('active');
        });

        // Back button
        if (drawerBackBtn) drawerBackBtn.style.display = step > 1 ? '' : 'none';

        // Add button label
        if (addCompareBtn) {
            addCompareBtn.textContent = step === 2 ? 'Add' : 'Continue →';
        }

        // Step 2: build algo list for chosen model
        if (step === 2) buildAlgoList(chosenModel);
    }

    // ── BUILD ALGO LIST ───────────────────────────────────────────────────────────
    function buildAlgoList (modelName) {
        if (algoContextModel) algoContextModel.textContent = modelName || '—';
        if (!algoPickList) return;
        algoPickList.innerHTML = '';
        chosenAlgo = '';

        // algoData is keyed by model_name, values are arrays of {algo_id, algo_type, ...}
        const algos = algoData[modelName] || [];
        if (!algos.length) {
            algoPickList.innerHTML =
                '<div class="empty-pick">No algorithms found for this model</div>';
            return;
        }

        algos.forEach((algo) => {
            const div = document.createElement('div');
            div.className = 'pick-item';
            div.dataset.algoId = algo.algo_id;
            div.dataset.algoType = algo.algo_type;
            div.innerHTML = `
                <div class="pick-item-content">
                    <div class="pick-item-nm">${algo.algo_type}</div>
                    <div class="pick-item-meta">${algo.algo_id}</div>
                </div>
                <svg class="pick-item-check ic" viewBox="0 0 24 24"><polyline points="20 6 9 17 4 12"/></svg>
            `;
            div.addEventListener('click', () => {
                document
                    .querySelectorAll('#algoPickList .pick-item')
                    .forEach((i) => i.classList.remove('selected'));
                div.classList.add('selected');
                chosenAlgo = algo.algo_id;
            });
            algoPickList.appendChild(div);
        });
    }

    // ── RESET DRAWER ──────────────────────────────────────────────────────────────
    function resetDrawer () {
        chosenModel = '';
        chosenAlgo = '';
        if (modelSearchInput) modelSearchInput.value = '';
        document
            .querySelectorAll('#modelPickerList .pick-item')
            .forEach((i) => i.classList.remove('selected'));
        filterModels('');
        renderStep(1);
    }

    // ── MODEL PICK ITEMS (step 1) ─────────────────────────────────────────────────
    document.querySelectorAll('#modelPickerList .pick-item').forEach((item) => {
        item.addEventListener('click', () => {
            document
                .querySelectorAll('#modelPickerList .pick-item')
                .forEach((i) => i.classList.remove('selected'));
            item.classList.add('selected');
            chosenModel = item.dataset.modelName;
        });
    });

    if (modelSearchInput) {
        modelSearchInput.addEventListener('input', () =>
            filterModels(modelSearchInput.value),
        );
    }

    // ── BACK BUTTON ───────────────────────────────────────────────────────────────
    if (drawerBackBtn) {
        drawerBackBtn.addEventListener('click', () => {
            if (currentStep > 1) renderStep(currentStep - 1);
        });
    }

    if (addSlotBtn) addSlotBtn.addEventListener('click', openDrawer);
    if (closeCompareModal)
        closeCompareModal.addEventListener('click', closeDrawer);
    if (closeCompareBtn) closeCompareBtn.addEventListener('click', closeDrawer);

    if (compareModal) {
        compareModal.addEventListener('click', (e) => {
            if (e.target === compareModal) closeDrawer();
        });
    }

    // ── CONTINUE / ADD BUTTON ─────────────────────────────────────────────────────
    let isSubmitting = false;

    if (addCompareBtn) {
        addCompareBtn.addEventListener('click', async () => {
            if (currentStep === 1) {
                if (!chosenModel) {
                    showToast('Please select a model');
                    return;
                }
                renderStep(2);
                return;
            }

            // Step 2 — submit
            if (isSubmitting) return; // block double-click / double-fire

            const algoId = chosenAlgo;
            const modelName = chosenModel;
            const compareId =
                document.getElementById('currentCompareId')?.value;

            if (!algoId || !modelName || !compareId) {
                showToast('Please select an algorithm');
                return;
            }

            isSubmitting = true;
            addCompareBtn.disabled = true;
            addCompareBtn.textContent = 'Adding…';

            try {
                const formData = new FormData();
                formData.append('user-action', 'get_algo_info');
                formData.append('algo_id', algoId);
                formData.append('model_name', modelName);
                formData.append('model_compare_id', compareId);

                const response = await fetch(window.location.href, {
                    method: 'POST',
                    headers: { 'X-CSRFToken': csrftoken },
                    body: formData,
                });
                const data = await response.json();
                if (response.ok) {
                    closeDrawer();
                    showToast(
                        data.already_exists
                            ? 'Algorithm already exists'
                            : 'Algorithm added successfully',
                    );
                    reloadCompareDetail();
                }
            } catch (err) {
                console.error('Add algo error:', err);
            } finally {
                isSubmitting = false;
                addCompareBtn.disabled = false;
                addCompareBtn.textContent = 'Add';
            }
        });
    }

    // ── REMOVE ALGO ───────────────────────────────────────────────────────────────
    document.addEventListener('click', async (e) => {
        const removeBtn = e.target.closest('.remove-algo-btn');
        if (!removeBtn) return;
        e.stopPropagation();

        const algoId = removeBtn.dataset.algoId;
        const modelCompareId = removeBtn.dataset.modelCompareId;

        try {
            const formData = new FormData();
            formData.append('user-action', 'remove_row');
            formData.append('algo_id', algoId);
            formData.append('model_compare_id', modelCompareId);

            const response = await fetch(window.location.href, {
                method: 'POST',
                headers: { 'X-CSRFToken': csrftoken },
                body: formData,
            });

            const data = await response.json();

            if (response.ok && data.status === 'ok') {
                // Remove slot from DOM with animation
                const slot = removeBtn.closest('.slot');
                if (slot) {
                    slot.style.transition = 'opacity .2s';
                    slot.style.opacity = '0';
                    setTimeout(() => {
                        slot.remove();
                        // After removing slot, refresh the rest of the page components
                        reloadCompareDetail();
                    }, 220);
                } else {
                    // Slot not found, just reload everything
                    reloadCompareDetail();
                }
                showToast(data.message || 'Algorithm removed');
            } else {
                showToast(
                    data.message || 'Unable to remove algorithm',
                    'error',
                );
            }
        } catch (err) {
            console.error('Remove algo error:', err);
        }
    });

    // ── PROMOTE BTN ───────────────────────────────────────────────────────────────
    const promoteBtn = document.getElementById('promoteBtn');
    if (promoteBtn) {
        promoteBtn.addEventListener('click', () =>
            showToast('Model queued for promotion'),
        );
    }

    // ── GRAPH DIST: marker colour helper ─────────────────────────────────────────
    function gdistMarkerColor (c) {
        if (c === 'green') return 'var(--ok)';
        if (c === 'red') return 'var(--err)';
        if (c === 'amber' || c === 'yellow' || c === 'orange')
            return 'var(--warn)';
        return 'var(--navy)';
    }

    // ── GRAPH DIST: render one histogram into a container div ─────────────────────
    function renderGraphDist (container, graphData) {
        if (
            !graphData ||
            !Array.isArray(graphData.bins) ||
            !graphData.bins.length
        ) {
            container.innerHTML =
                '<div style="padding:30px;text-align:center;color:var(--ink-4);font-size:13px;">No graph data available</div>';
            return;
        }

        const {
            bins,
            counts,
            markers = [],
            x_label: xLabel = '',
            y_label: yLabel = '',
        } = graphData;

        const W = 480,
            H = 280,
            PAD_B = 44,
            PAD_R = 16,
            PAD_T = 16;

        const binWidth = bins.length > 1 ? bins[1] - bins[0] : 1;
        const minX = bins[0];
        const maxX = bins[bins.length - 1] + binWidth;
        const maxCount = Math.max(...counts, 1);

        // ── DYNAMIC PAD_L based on widest Y label ──────────────────────────────────
        const yTickValues = [0.25, 0.5, 0.75, 1].map((f) =>
            Math.round(maxCount * f),
        );
        const longestLabel = Math.max(
            ...yTickValues.map((v) => String(v).length),
        );
        // ~7px per character at font-size 10px (monospace), plus 10px gap
        const PAD_L = Math.max(40, longestLabel * 7 + 14);
        // ──────────────────────────────────────────────────────────────────────────

        const plotW = W - PAD_L - PAD_R;
        const plotH = H - PAD_T - PAD_B;

        const xScale = (v) => PAD_L + ((v - minX) / (maxX - minX || 1)) * plotW;
        const barW = Math.max(2, plotW / bins.length - 1);

        const bars = bins
            .map((b, i) => {
                const x = xScale(b);
                const h = (counts[i] / maxCount) * plotH;
                const y = PAD_T + plotH - h;
                return `<rect x="${x.toFixed(1)}" y="${y.toFixed(1)}" width="${barW.toFixed(1)}" height="${h.toFixed(1)}" class="gdist-bar"/>`;
            })
            .join('');

        const gridLines = [0.25, 0.5, 0.75, 1]
            .map((f) => {
                const y = PAD_T + plotH * (1 - f);
                return `<line x1="${PAD_L}" y1="${y.toFixed(1)}" x2="${W - PAD_R}" y2="${y.toFixed(1)}" class="gdist-grid"/>
                    <text x="${(PAD_L - 6).toFixed(1)}" y="${(y + 4).toFixed(1)}" class="gdist-axis-lbl" text-anchor="end">${Math.round(maxCount * f)}</text>`;
            })
            .join('');

        const tickCount = 6;
        const xLabels = Array.from({ length: tickCount + 1 }, (_, i) => {
            const v = minX + (maxX - minX) * (i / tickCount);
            const x = xScale(v);
            return `<text x="${x.toFixed(1)}" y="${(PAD_T + plotH + 16).toFixed(1)}" class="gdist-axis-lbl" text-anchor="middle">${Math.round(v)}</text>`;
        }).join('');

        const markerLines = markers
            .map((m) => {
                const x = xScale(m.value);
                return `<line x1="${x.toFixed(1)}" y1="${PAD_T}" x2="${x.toFixed(1)}" y2="${PAD_T + plotH}" stroke="${gdistMarkerColor(m.color)}" stroke-width="1.5" stroke-dasharray="5,4"/>`;
            })
            .join('');

        // Axis labels
        const xAxisLabel = xLabel
            ? `<text x="${(PAD_L + plotW / 2).toFixed(1)}" y="${(H - 4).toFixed(1)}" font-size="11" fill="var(--ink-3)" text-anchor="middle">${xLabel}</text>`
            : '';
        const yAxisLabel = yLabel
            ? `<text x="13" y="${(PAD_T + plotH / 2).toFixed(1)}" font-size="11" fill="var(--ink-3)" text-anchor="middle" transform="rotate(-90 13,${(PAD_T + plotH / 2).toFixed(1)})">${yLabel}</text>`
            : '';

        const svg = `<svg viewBox="0 0 ${W} ${H}" xmlns="http://www.w3.org/2000/svg" style="width:100%;height:auto;display:block;">
            ${gridLines}
            ${bars}
            ${markerLines}
            <line x1="${PAD_L}" y1="${PAD_T}" x2="${PAD_L}" y2="${PAD_T + plotH}" stroke="var(--line)" stroke-width="1.5"/>
            <line x1="${PAD_L}" y1="${PAD_T + plotH}" x2="${W - PAD_R}" y2="${PAD_T + plotH}" stroke="var(--line)" stroke-width="1.5"/>
            ${xLabels}
            ${xAxisLabel}
            ${yAxisLabel}
        </svg>`;

        // Legend
        const legend = markers.length
            ? `<div class="graph-dist-legend">${markers
                .map(
                    (m) =>
                        `<span class="graph-dist-leg-item">
                        <span class="graph-dist-leg-dot" style="background:${gdistMarkerColor(m.color)}"></span>
                        ${m.label}
                    </span>`,
                )
                .join('')}</div>`
            : '';

        container.innerHTML = svg + legend;
    }

    // ── GRAPH DIST: initial render from json_script data ─────────────────────────
    function initGraphDist () {
        const el = document.getElementById('graph-dist-data');
        if (!el) return;

        let rows;
        try {
            rows = JSON.parse(el.textContent);
        } catch {
            return;
        }
        if (!Array.isArray(rows)) return;

        rows.forEach((row, i) => {
            const wrap = document.getElementById(`graphSvg_${i + 1}`);
            if (wrap && row.graph_data && Object.keys(row.graph_data).length) {
                renderGraphDist(wrap, row.graph_data);
            }
        });
    }

    initGraphDist();
})();
