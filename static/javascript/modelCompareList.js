/* global setTimeout, fetch, FormData , clearTimeout,  localStorage, requestAnimationFrame*/

// ── CSRF ──────────────────────────────────────────────────────────────────────
(function () {
    // Only run on the list page, not the detail page
    if (document.getElementById('currentCompareId')) return;

    function getCookie (name) {
        let val = null;
        if (document.cookie && document.cookie !== '') {
            document.cookie.split(';').forEach((c) => {
                const t = c.trim();
                if (t.startsWith(name + '='))
                    val = decodeURIComponent(t.slice(name.length + 1));
            });
        }
        return val;
    }
    const csrftoken = getCookie('csrftoken');

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
    const toastEl = document.getElementById('toast');
    const toastMsg = document.getElementById('toastMsg');
    let toastTimer;

    function showToast (msg, type = 'ok') {
        if (!toastEl || !toastMsg) return;
        toastMsg.textContent = msg;
        toastEl.dataset.type = type;
        toastEl.classList.add('show');
        clearTimeout(toastTimer);
        toastTimer = setTimeout(() => toastEl.classList.remove('show'), 2800);
    }

    // ── ALGO LIST DATA ────────────────────────────────────────────────────────────
    const algoListEl = document.getElementById('algo-list-data');
    const algoList = algoListEl ? JSON.parse(algoListEl.textContent) : {};

    // ── DRAWER STATE ──────────────────────────────────────────────────────────────
    let currentStep = 1;
    let chosenModel = '';
    let chosenAlgo = '';

    const drawer = document.getElementById('addDrawer');
    const backdrop = document.getElementById('drawerBackdrop');
    const drawerClose = document.getElementById('drawerClose');
    const drawerCancelBtn = document.getElementById('drawerCancelBtn');
    const drawerNextBtn = document.getElementById('drawerNextBtn');
    const drawerBackBtn = document.getElementById('drawerBackBtn');

    const step1Dot = document.getElementById('step1Dot');
    const step2Dot = document.getElementById('step2Dot');
    const step3Dot = document.getElementById('step3Dot');

    const drawerStep1 = document.getElementById('drawerStep1');
    const drawerStep2 = document.getElementById('drawerStep2');
    const drawerStep3 = document.getElementById('drawerStep3');
    const reviewSummary = document.getElementById('reviewSummary');

    const compareNameInput = document.getElementById('compareNameInput');
    const modelSearchInput = document.getElementById('modelSearchInput');
    const algoPickList = document.getElementById('algoPickList');
    const algoContextModel = document.getElementById('algoContextModel');

    const reviewName = document.getElementById('reviewName');
    const reviewModel = document.getElementById('reviewModel');
    const reviewAlgo = document.getElementById('reviewAlgo');

    // ── OPEN / CLOSE ──────────────────────────────────────────────────────────────
    function openDrawer () {
        resetDrawer();
        drawer.classList.add('open');
        backdrop.classList.add('open');
        setTimeout(() => compareNameInput && compareNameInput.focus(), 280);
    }

    function closeDrawer () {
        drawer.classList.remove('open');
        backdrop.classList.remove('open');
    }

    function resetDrawer () {
        currentStep = 1;
        chosenModel = '';
        chosenAlgo = '';
        if (compareNameInput) compareNameInput.value = '';
        if (modelSearchInput) modelSearchInput.value = '';
        document
            .querySelectorAll('#modelPickList .pick-item')
            .forEach((i) => i.classList.remove('selected'));
        filterModels('');
        renderStep(1);
    }

    // ── STEP RENDERING ────────────────────────────────────────────────────────────
    function renderStep (step) {
        currentStep = step;

        // Show/hide sections
        drawerStep1.style.display = step === 1 ? '' : 'none';
        drawerStep2.style.display = step === 2 ? '' : 'none';
        drawerStep3.style.display = step === 3 ? '' : 'none';
        reviewSummary.style.display = step === 3 ? '' : 'none';

        // Step dots
        [step1Dot, step2Dot, step3Dot].forEach((d, i) => {
            d.classList.remove('active', 'done');
            if (i + 1 < step) d.classList.add('done');
            else if (i + 1 === step) d.classList.add('active');
        });

        // Back button
        drawerBackBtn.style.display = step > 1 ? '' : 'none';

        // Next button label
        if (step === 3) {
            drawerNextBtn.textContent = 'Add compare';
        } else {
            drawerNextBtn.textContent = 'Continue →';
        }

        // Step 3: populate algo list + review
        if (step === 3) {
            buildAlgoList(chosenModel);
            if (reviewName)
                reviewName.textContent = compareNameInput
                    ? compareNameInput.value.trim()
                    : '—';
            if (reviewModel) reviewModel.textContent = chosenModel || '—';
            if (reviewAlgo) reviewAlgo.textContent = chosenAlgo || '—';
        }
    }

    // ── MODEL FILTER ──────────────────────────────────────────────────────────────
    function filterModels (q) {
        const lq = q.toLowerCase();
        document
            .querySelectorAll('#modelPickList .pick-item')
            .forEach((item) => {
                const nm = item.dataset.modelName.toLowerCase();
                item.style.display = nm.includes(lq) ? '' : 'none';
            });
    }

    if (modelSearchInput) {
        modelSearchInput.addEventListener('input', () =>
            filterModels(modelSearchInput.value),
        );
    }

    // ── MODEL PICK ITEMS ──────────────────────────────────────────────────────────
    document.querySelectorAll('#modelPickList .pick-item').forEach((item) => {
        item.addEventListener('click', () => {
            document
                .querySelectorAll('#modelPickList .pick-item')
                .forEach((i) => i.classList.remove('selected'));
            item.classList.add('selected');
            chosenModel = item.dataset.modelName;
            chosenAlgo = ''; // reset algo when model changes
        });
    });

    // ── BUILD ALGO LIST ───────────────────────────────────────────────────────────
    function buildAlgoList (modelName) {
        if (algoContextModel) algoContextModel.textContent = modelName || '—';
        algoPickList.innerHTML = '';
        chosenAlgo = '';

        const algos = algoList[modelName] || [];
        if (!algos.length) {
            algoPickList.innerHTML =
                '<div class="empty-pick">No algorithms found for this model</div>';
            return;
        }

        algos.forEach((algo) => {
            const div = document.createElement('div');
            div.className = 'pick-item';
            div.dataset.algoName = algo;
            div.innerHTML = `
                <div class="pick-item-info">
                    <div class="pick-item-nm">${algo}</div>
                    <div class="pick-item-meta">${modelName}</div>
                </div>
                <svg class="pick-item-check ic" viewBox="0 0 24 24"><polyline points="20 6 9 17 4 12"/></svg>
            `;
            div.addEventListener('click', () => {
                document
                    .querySelectorAll('#algoPickList .pick-item')
                    .forEach((i) => i.classList.remove('selected'));
                div.classList.add('selected');
                chosenAlgo = algo;
                if (reviewAlgo) reviewAlgo.textContent = algo;
            });
            algoPickList.appendChild(div);
        });
    }

    // ── NEXT / BACK ───────────────────────────────────────────────────────────────
    drawerNextBtn.addEventListener('click', async () => {
        if (currentStep === 1) {
            const name = compareNameInput ? compareNameInput.value.trim() : '';
            if (!name) {
                showToast('Please enter a compare name');
                return;
            }
            renderStep(2);
        } else if (currentStep === 2) {
            if (!chosenModel) {
                showToast('Please select a model');
                return;
            }
            renderStep(3);
        } else if (currentStep === 3) {
            if (!chosenAlgo) {
                showToast('Please select an algorithm');
                return;
            }
            await submitCompare();
        }
    });

    if (drawerBackBtn) {
        drawerBackBtn.addEventListener('click', () => {
            if (currentStep > 1) renderStep(currentStep - 1);
        });
    }

    // ── SUBMIT ────────────────────────────────────────────────────────────────────
    async function submitCompare () {
        const name = compareNameInput ? compareNameInput.value.trim() : '';
        if (!name || !chosenModel || !chosenAlgo) {
            showToast('Please complete all fields');
            return;
        }

        drawerNextBtn.disabled = true;
        drawerNextBtn.textContent = 'Adding…';

        try {
            const fd = new FormData();
            fd.append('user-action', 'add');
            fd.append('model_compare_name', name);
            fd.append('model_name', chosenModel);
            fd.append('algo_id', chosenAlgo);

            const res = await fetch(window.location.href, {
                method: 'POST',
                headers: { 'X-CSRFToken': csrftoken },
                body: fd,
            });

            if (res.ok) {
                const data = await res.json();
                closeDrawer();
                showToast('Model compare added successfully.', 'ok');
                injectNewCard(data.compare);
            } else {
                const data = await res.json().catch(() => ({}));
                showToast(data.message || 'Something went wrong.', 'err');
            }
        } catch {
            showToast('Network error. Please try again.');
        } finally {
            drawerNextBtn.disabled = false;
            drawerNextBtn.textContent = 'Add compare';
        }
    }

    // ── OPEN TRIGGERS ─────────────────────────────────────────────────────────────
    const addBtnHeader = document.getElementById('addCompareBtn');
    const addBtnEmpty = document.getElementById('emptyAddBtn');

    if (addBtnHeader) addBtnHeader.addEventListener('click', openDrawer);
    if (addBtnEmpty) addBtnEmpty.addEventListener('click', openDrawer);

    drawerClose.addEventListener('click', closeDrawer);
    drawerCancelBtn.addEventListener('click', closeDrawer);
    backdrop.addEventListener('click', closeDrawer);

    // ── DELETE CARD ───────────────────────────────────────────────────────────────
    // ── DELETE MODAL ──────────────────────────────────────────────────────────────
    const compareActionBackdrop = document.getElementById(
        'compareActionBackdrop',
    );
    const compareActionModal = document.getElementById('compareActionModal');
    const compareActionClose = document.getElementById('compareActionClose');
    const compareActionCancel = document.getElementById('compareActionCancel');
    const compareActionConfirm = document.getElementById(
        'compareActionConfirm',
    );
    const compareActionTitle = document.getElementById('compareActionTitle');
    const compareActionMessage = document.getElementById(
        'compareActionMessage',
    );
    const compareActionList = document.getElementById('compareActionList');

    let pendingDeleteId = null;
    let pendingDeleteCard = null;

    function openDeleteModal (modelId, card) {
        const compareName = card.querySelector('.compare-card-nm')
            ? card.querySelector('.compare-card-nm').textContent.trim()
            : 'this compare';
        pendingDeleteId = modelId;
        pendingDeleteCard = card;
        compareActionTitle.textContent = 'Delete compare?';
        compareActionMessage.textContent = `This will permanently delete "${compareName}". This action cannot be undone.`;
        compareActionList.innerHTML = `
            <div class="action-modal-item">
                <div class="name">${compareName}</div>
                <div class="meta">Model compare · will be removed</div>
            </div>`;
        compareActionBackdrop.classList.add('open');
        compareActionModal.classList.add('open');
    }

    function closeDeleteModal () {
        compareActionBackdrop.classList.remove('open');
        compareActionModal.classList.remove('open');
        pendingDeleteId = null;
        pendingDeleteCard = null;
    }

    compareActionClose.addEventListener('click', closeDeleteModal);
    compareActionCancel.addEventListener('click', closeDeleteModal);
    compareActionBackdrop.addEventListener('click', closeDeleteModal);

    compareActionConfirm.addEventListener('click', async () => {
        if (!pendingDeleteId || !pendingDeleteCard) return;
        const modelId = pendingDeleteId;
        const card = pendingDeleteCard;
        closeDeleteModal();

        try {
            const fd = new FormData();
            fd.append('user-action', 'delete');
            fd.append('model_id', modelId);

            const res = await fetch(window.location.href, {
                method: 'POST',
                headers: { 'X-CSRFToken': csrftoken },
                body: fd,
            });

            if (res.ok) {
                card.style.transition = 'opacity .2s, transform .2s';
                card.style.opacity = '0';
                card.style.transform = 'scale(0.96)';
                setTimeout(() => card.remove(), 220);
                showToast('Model Compare deleted successfully.');
            } else {
                showToast('Something went wrong. Please try again.', 'err');
            }
        } catch {
            showToast('Something went wrong. Please try again.', 'err');
        }
    });

    // ── DELETE CARD (click handler — now opens modal instead of direct delete) ────
    document.addEventListener('click', (e) => {
        const btn = e.target.closest('.remove-compare-btn');
        if (!btn) return;
        e.preventDefault();
        e.stopPropagation();
        const card = btn.closest('.compare-card');
        if (!card) return;
        openDeleteModal(btn.dataset.modelId, card);
    });

    // ── OPEN COMPARE CARD ─────────────────────────────────────────────────────────
    document.addEventListener('click', (e) => {
        // Don't trigger if clicking the delete (×) button
        if (e.target.closest('.remove-compare-btn')) return;

        // Don't trigger on any button that isn't specifically the open button
        if (
            e.target.closest('button') &&
            !e.target.closest('.compare-card-open-btn')
        )
            return;

        const card = e.target.closest('.compare-card[data-compare-id]');
        if (!card) return;

        const compareId = card.dataset.compareId;
        if (!compareId) return;

        window.location.href = `${window.location.pathname}?compare_id=${compareId}`;
    });

    function injectNewCard (compare) {
        // Hide empty state if visible
        const emptyState = document.getElementById('emptyState');
        if (emptyState) emptyState.style.display = 'none';

        // Create or find grid
        let grid = document.getElementById('compareGrid');
        if (!grid) {
            grid = document.createElement('div');
            grid.className = 'compare-grid';
            grid.id = 'compareGrid';
            document.querySelector('.content').appendChild(grid);
        }

        const card = document.createElement('div');
        card.className = 'compare-card';
        card.dataset.modelId = compare.model_compare_id;
        card.dataset.compareId = compare.model_compare_id;
        card.innerHTML = `
            <div class="compare-card-top">
                <div class="compare-card-badges">
                    <span class="compare-card-badge">Model Compare</span>
                </div>
            </div>
            <div class="compare-card-actions">
                <button class="compare-card-delete-btn remove-compare-btn" data-model-id="${compare.model_compare_id}" title="Delete">
                    <svg class="ic" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                        <path d="M3 6h18M8 6V4a2 2 0 012-2h4a2 2 0 012 2v2m1 0v14a2 2 0 01-2 2H8a2 2 0 01-2-2V6h12z"/>
                    </svg>
                </button>
            </div>
            <div class="compare-card-nm">${compare.model_compare_name}</div>
            <div class="compare-card-meta">
                <div class="compare-card-meta-item">
                    <span class="compare-card-meta-lbl">Created</span>
                    <span class="compare-card-meta-val">${compare.created_date ? new Date(compare.created_date).toISOString().slice(0, 10) : '—'}</span>
                </div>
                <div class="compare-card-meta-item">
                    <span class="compare-card-meta-lbl">Algorithms</span>
                    <span class="compare-card-meta-val">${compare.row_count}</span>
                </div>
            </div>
            <button class="compare-card-open-btn" data-compare-id="${compare.model_compare_id}">
                Open compare
                <svg class="ic" viewBox="0 0 24 24"><path d="M5 12h14M12 5l7 7-7 7"/></svg>
            </button>
        `;

        // Animate in
        card.style.opacity = '0';
        card.style.transform = 'scale(0.96)';
        grid.append(card);
        requestAnimationFrame(() =>
            requestAnimationFrame(() => {
                card.style.transition = 'opacity 0.22s, transform 0.22s';
                card.style.opacity = '1';
                card.style.transform = 'scale(1)';
            }),
        );

        // Update stat chip
        const totalChip = document.querySelector('.stat-chip-val');
        if (totalChip)
            totalChip.textContent = parseInt(totalChip.textContent || '0') + 1;
    }
})();
