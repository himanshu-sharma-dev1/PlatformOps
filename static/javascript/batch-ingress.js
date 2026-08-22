/* global fetch, FormData, setTimeout, setInterval, clearTimeout, Event, window, document */

(function () {
    'use strict';

    // ---- Native helpers (no DForm dependency) ----

    // Custom Multi-Select UI Component
    function initCustomMultiSelect (selectEl) {
        if (!selectEl || selectEl.dataset.customized) return;
        selectEl.dataset.customized = 'true';
        selectEl.style.display = 'none'; // Hide native select

        const wrapper = document.createElement('div');
        wrapper.className = 'custom-multi-select';
        wrapper.style.cssText =
            'position:relative; width:100%; font-family:var(--sans);';

        const trigger = document.createElement('div');
        trigger.className = 'input';
        trigger.style.cssText =
            'display:flex; justify-content:space-between; align-items:center; cursor:pointer; min-height:38px; padding:0 12px; border:1px solid var(--ink-5); border-radius:4px; background:#dad8d8;';

        const labelText = document.createElement('span');
        labelText.style.cssText =
            'overflow:hidden; text-overflow:ellipsis; white-space:nowrap; font-size:13px; color:var(--ink-2);';

        const arrow = document.createElement('span');
        arrow.innerHTML = '▼';
        arrow.style.cssText =
            'font-size:10px; color:var(--ink-4); margin-left:8px;';

        trigger.appendChild(labelText);
        trigger.appendChild(arrow);

        const dropdown = document.createElement('div');
        dropdown.className = 'custom-multi-select-dropdown';
        dropdown.style.cssText =
            'display:none; position:absolute; top:100%; left:0; right:0; background:#fff; border:1px solid var(--ink-5); border-radius:4px; box-shadow:0 4px 12px rgba(0,0,0,0.1); z-index:100; max-height:200px; overflow-y:auto; padding:8px; margin-top:4px;';

        wrapper.appendChild(trigger);
        wrapper.appendChild(dropdown);

        selectEl.parentNode.insertBefore(wrapper, selectEl.nextSibling);

        function updateLabel () {
            const selected = Array.from(selectEl.selectedOptions).map(
                (o) => o.textContent,
            );
            if (selected.length === 0) {
                labelText.textContent = 'Select options...';
                labelText.style.color = 'var(--ink-4)';
            } else if (selected.length <= 2) {
                labelText.textContent = selected.join(', ');
                labelText.style.color = 'var(--ink-3)';
            } else {
                labelText.textContent = selected.length + ' options selected';
                labelText.style.color = 'var(--ink-3)';
            }
        }

        function buildDropdown () {
            dropdown.innerHTML = '';

            // Defaults to shown unless explicitly set to "false".
            const showSelectAll = selectEl.dataset.showSelectAll !== 'false';
            const showClearAll = selectEl.dataset.showClearAll !== 'false';

            if (showSelectAll || showClearAll) {
                const header = document.createElement('div');
                header.style.cssText =
                    'display:flex; justify-content:space-between; padding-bottom:6px; margin-bottom:6px; border-bottom:1px solid var(--ink-5);';

                if (showSelectAll) {
                    const selAllLbl = document.createElement('label');
                    selAllLbl.style.cssText =
                        'display:flex; align-items:center; cursor:pointer; font-size:12px; font-weight:600; color:#2563eb;';

                    const selAllChk = document.createElement('input');
                    selAllChk.type = 'checkbox';
                    const selectableOpts = Array.from(
                        selectEl.options,
                    ).filter((opt) => !opt.disabled);
                    selAllChk.checked =
                        selectableOpts.length > 0 &&
                        selectableOpts.every((opt) => opt.selected);
                    selAllChk.style.marginRight = '6px';

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
                }

                if (showClearAll) {
                    const clearBtn = document.createElement('button');
                    clearBtn.type = 'button';
                    clearBtn.textContent = 'Clear all';
                    clearBtn.style.cssText =
                        'background:none; border:none; color:var(--ink-4); font-size:12px; font-weight:600; cursor:pointer; padding:0;';
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
                }

                dropdown.appendChild(header);
            }

            Array.from(selectEl.options).forEach((opt) => {
                if (opt.disabled) return;
                const lbl = document.createElement('label');
                lbl.className = 'checkbox';
                lbl.style.cssText =
                    'display:flex; align-items:center; margin-bottom:6px; cursor:pointer; font-size:13px; color:var(--ink-2);';

                const chk = document.createElement('input');
                chk.type = 'checkbox';
                chk.value = opt.value;
                chk.checked = opt.selected;
                chk.style.marginRight = '8px';

                chk.onchange = function () {
                    opt.selected = chk.checked;
                    updateLabel();
                    selectEl.dispatchEvent(new Event('change'));
                };

                lbl.appendChild(chk);
                lbl.appendChild(document.createTextNode(opt.textContent));
                dropdown.appendChild(lbl);
            });
        }

        trigger.onclick = function (e) {
            if (selectEl.disabled) return;
            e.stopPropagation();
            const isOpen = dropdown.style.display === 'block';
            document
                .querySelectorAll('.custom-multi-select-dropdown')
                .forEach((d) => (d.style.display = 'none'));
            if (!isOpen) {
                buildDropdown(); // rebuild to catch any dynamic option changes
                dropdown.style.display = 'block';
            }
        };

        function syncDisabledVisual () {
            const isDisabled = selectEl.disabled;
            trigger.style.opacity = isDisabled ? '0.6' : '1';
            trigger.style.cursor = isDisabled ? 'not-allowed' : 'pointer';
        }
        syncDisabledVisual();
        // Exposed so callers can re-sync visuals after toggling selectEl.disabled
        wrapper.syncDisabledVisual = syncDisabledVisual;

        dropdown.onclick = function (e) {
            e.stopPropagation();
        };

        // Listen for external changes to the select (e.g. edit mode pre-fill)
        selectEl.addEventListener('change', updateLabel);

        // Initial setup
        updateLabel();
    }

    // Close dropdowns when clicking outside
    document.addEventListener('click', function () {
        document
            .querySelectorAll('.custom-multi-select-dropdown')
            .forEach((d) => (d.style.display = 'none'));
    });

    // Toggles conditional connection-type field groups
    function toggleConnFields (connType) {
        document.querySelectorAll('.conn-fields').forEach(function (el) {
            const types = (el.dataset.conn || '').split(',');
            el.style.display = types.indexOf(connType) !== -1 ? '' : 'none';
        });
    }

    document.addEventListener('DOMContentLoaded', function () {
        let activeDataflow = null;
        let deleteTarget = null;
        let menuTarget = null;
        let currentStep = 1;

        function updateDataflowCounts () {
            let total = 0;
            let active = 0;
            if (window.dataflow_info) {
                total = window.dataflow_info.length;
                active = window.dataflow_info.filter((df) => {
                    const st = (df.dataflow_status || 'enable').toLowerCase();
                    return st !== 'disable' && st !== 'disabled';
                }).length;
            }

            // Update the "All dataflows" tab count
            const allTabCount = document.querySelector(
                '#dfTabsContainer .tab[data-filter="all"] .count',
            );
            if (allTabCount) {
                allTabCount.textContent = total;
            }

            // Update the "Active dataflows" tile count
            const activeTileLabel = Array.from(
                document.querySelectorAll('.s-tile .l'),
            ).find((el) => el.textContent.trim() === 'Active dataflows');
            if (activeTileLabel) {
                const activeTileValue = activeTileLabel.nextElementSibling;
                if (
                    activeTileValue &&
                    activeTileValue.classList.contains('v')
                ) {
                    activeTileValue.textContent = active;
                }
            }
        }

        // Fetch symbol lists and churn config to dynamically update window.schema
        async function fetchSymbolsAndChurnConfig () {
            try {
                const res = await fetch('/opCop/GetSymbolsConfig/');
                if (res.ok) {
                    const response = await res.json();
                    const symbols_list =
                        response['filter_config']['symbols_list'] || [];
                    const source_list =
                        response['filter_config']['source_list'] || [];

                    const symbolsField = window.schema['ConnectionConfig'][
                        'row_Schema'
                    ].find((field) => field.f_name === 'symbolsList');
                    if (symbolsField) symbolsField.v_options = symbols_list;

                    const sourceField = window.schema['ConnectionConfig'][
                        'row_Schema'
                    ].find((field) => field.f_name === 'sourceType');
                    if (sourceField) sourceField.v_options = source_list;

                    const sourceSelect =
                        document.getElementById('addSourceType');
                    if (sourceSelect) {
                        sourceSelect.innerHTML =
                            '<option value="">--------</option>';
                        source_list.forEach((s) => {
                            const opt = document.createElement('option');
                            opt.value = s;
                            opt.textContent = s;
                            sourceSelect.appendChild(opt);
                        });
                    }

                    const symbolsSelect =
                        document.getElementById('addSymbolsList');
                    if (symbolsSelect) {
                        symbolsSelect.innerHTML = '';
                        symbols_list.forEach((s) => {
                            const opt = document.createElement('option');
                            opt.value = s;
                            opt.textContent = s;
                            symbolsSelect.appendChild(opt);
                        });

                        // Wait a tick for DOM to settle, then initialize custom multi-select
                        setTimeout(() => {
                            initCustomMultiSelect(symbolsSelect);
                        }, 0);
                    }
                }
            } catch (e) {

                // Error loading symbols config
            }

            try {
                const csrfToken =
                    document.querySelector('[name="csrfmiddlewaretoken"]')
                        ?.value || '';

                const res = await fetch(
                    '/cPlatformApp/APIv1/Common/GetChurnConfig/',
                    {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                            'X-CSRFToken': csrfToken,
                        },
                        body: JSON.stringify({ service_name: 'AirtelChurn' }),
                    },
                );

                if (res.ok) {
                    const response = await res.json();
                    const circles_list = Array.isArray(
                        response?.filter_config?.circles_list,
                    )
                        ? response.filter_config.circles_list
                        : Array.isArray(response?.circles_list)
                            ? response.circles_list
                            : [];

                    const circlesField =
                        window.schema?.ConnectionConfig?.row_Schema?.find(
                            (field) => field.f_name === 'CirclesList',
                        );
                    if (circlesField) circlesField.v_options = circles_list;

                    const circlesSelect =
                        document.getElementById('addCirclesList');
                    if (circlesSelect) {
                        circlesSelect.innerHTML = '';
                        circles_list.forEach((c) => {
                            const opt = document.createElement('option');
                            opt.value = c;
                            opt.textContent = c;
                            circlesSelect.appendChild(opt);
                        });
                        setTimeout(() => {
                            initCustomMultiSelect(circlesSelect);
                        }, 0);
                    }

                    // Populate statusCircle dropdown for Data Status View
                    const statusCircleSelect =
                        document.getElementById('statusCircle');
                    if (statusCircleSelect) {
                        statusCircleSelect.innerHTML =
                            '<option value="" disabled selected>Select Circle</option>';
                        circles_list.forEach((c) => {
                            const opt = document.createElement('option');
                            opt.value = c;
                            opt.textContent = c;
                            statusCircleSelect.appendChild(opt);
                        });
                    }
                }

                // Populate statusDataflowType dropdown using window.dataflowConfig
                const statusDataflowSelect =
                    document.getElementById('statusDataflowType');
                if (statusDataflowSelect && window.dataflowConfig) {
                    statusDataflowSelect.innerHTML =
                        '<option value="" disabled selected>Select Dataflow</option>';
                    const airtelChurnDataflows =
                        window.dataflowConfig['AirtelChurn'] || [];
                    airtelChurnDataflows.forEach((type) => {
                        const opt = document.createElement('option');
                        opt.value = type;
                        opt.textContent = type;
                        statusDataflowSelect.appendChild(opt);
                    });
                }
            } catch (e) {

                // Error loading churn config
            }
        }

        // Call fetching logic removed to prevent eager loading.
        // fetchSymbolsAndChurnConfig();

        // Format records numbers in dataflow cards
        document.querySelectorAll('.df-card .df-stat .v.mono').forEach((el) => {
            const raw = el.textContent.trim();
            if (raw !== '-' && raw !== '') {
                const parsed = parseInt(raw.replace(/,/g, ''), 10);
                if (!isNaN(parsed)) {
                    el.textContent = formatRecordCount(parsed);
                }
            }
        });

        function showToast (msg, kind) {
            const t = document.getElementById('toast');
            if (!t) return;
            document.getElementById('toastMsg').textContent = msg;
            t.classList.remove('ok', 'err');
            if (kind) t.classList.add(kind);
            t.classList.add('show');
            clearTimeout(showToast._t);
            showToast._t = setTimeout(() => t.classList.remove('show'), 2400);
        }

        function openDrawer (which) {
            if (which === 'detail') {
                const back = document.getElementById('detailBack');
                const dr = document.getElementById('detailDrawer');
                if (back) back.classList.add('open');
                if (dr) dr.classList.add('open');
            } else if (which === 'add') {
                const back = document.getElementById('addBack');
                const dr = document.getElementById('addDrawer');
                if (back) back.classList.add('open');
                if (dr) dr.classList.add('open');
            }
        }

        function closeDrawer (which) {
            if (which === 'detail') {
                const back = document.getElementById('detailBack');
                const dr = document.getElementById('detailDrawer');
                if (back) back.classList.remove('open');
                if (dr) dr.classList.remove('open');

                // Reset status pane data
                const resultArea = document.getElementById(
                    'statusPaneResultArea',
                );
                if (resultArea) resultArea.style.display = 'none';

                // Return to overview tab
                switchTab('overview');
            } else if (which === 'add') {
                const back = document.getElementById('addBack');
                const dr = document.getElementById('addDrawer');
                if (back) back.classList.remove('open');
                if (dr) dr.classList.remove('open');
                resetStepper();
            }
        }
        window.closeDrawer = closeDrawer;

        function switchTab (name) {
            document.querySelectorAll('.drawer-tabs .tab').forEach((t) => {
                t.classList.toggle('active', t.dataset.pane === name);
            });
            document.querySelectorAll('[data-pane-content]').forEach((p) => {
                p.classList.toggle('active', p.dataset.paneContent === name);
            });
        }

        // No DForm relocation needed — form fields are hardcoded in the template

        function openAddDrawer (mode, df) {
            const title = document.getElementById('addTitle');
            const saveBtn = document.getElementById('saveDataflow');
            const connSel = document.getElementById('addConnType');

            // ConnectionType toggling is now handled by .type-card click listener.

            // Wire SourceType cascading (ApiKey/SecretKey)
            const sourceSel = document.getElementById('addSourceType');
            if (sourceSel) {
                sourceSel.onchange = function () {
                    const st = sourceSel.value;
                    const apiField = document.getElementById('apiKeyField');
                    const secretField =
                        document.getElementById('secretKeyField');
                    if (apiField)
                        apiField.style.display = [
                            'AlphaVantage',
                            'Massive',
                            'Finnhub',
                        ].includes(st)
                            ? ''
                            : 'none';
                    if (secretField)
                        secretField.style.display = [
                            'AlphaVantage',
                            'Massive',
                        ].includes(st)
                            ? ''
                            : 'none';
                };
            }

            // Wire add-file-row button
            const addFileBtn = document.getElementById('addFileRowBtn');
            if (addFileBtn) {
                addFileBtn.onclick = function () {
                    const container = document.getElementById('fileConfigRows');
                    const row = document.createElement('div');
                    row.className = 'file-row';
                    row.style.cssText =
                        'display:flex; gap:var(--s-2); margin-bottom:var(--s-2);';
                    row.innerHTML =
                        '<div class="field" style="flex:1;"><label>Remote Path <span style="color:var(--err, #ef4444);">*</span></label><input class="input" type="text" name="remote_path[]" placeholder="/path/to/dir/" style="font-family:var(--mono); font-size:12px;"></div>' +
                        '<div class="field" style="flex:1;"><label>File Name <span style="color:var(--err, #ef4444);">*</span></label><input class="input" type="text" name="file_name[]" placeholder="*.csv" style="font-family:var(--mono); font-size:12px;"></div>' +
                        '<div class="field" style="flex:1;"><label>Role <span style="color:var(--err, #ef4444);">*</span></label><select multiple class="select" name="role[]" style="height:38px;"><option value="System_Admin">System_Admin</option><option value="Operational">Operational</option><option value="Management">Management</option></select></div>' +
                        '<button type="button" class="btn btn-ghost btn-sm" onclick="this.closest(\'.file-row\').remove()">Close ✕</button>';
                    container.appendChild(row);

                    // Initialize custom multi-select on the newly appended role field
                    setTimeout(() => {
                        const roleSelect = row.querySelector(
                            'select[name="role[]"]',
                        );
                        if (roleSelect) initCustomMultiSelect(roleSelect);
                    }, 0);
                };
            }

            if (mode === 'edit' && df) {
                const dfObj = window.dataflow_info.find(function (d) {
                    return d.dataflow_id === df.id;
                });
                if (title)
                    title.textContent =
                        'Edit ' + (dfObj ? dfObj.dataflow_name : df.name);
                if (saveBtn) saveBtn.textContent = 'Save changes';

                // Pre-fill form fields from dfObj
                if (dfObj) {
                    const setVal = function (name, val) {
                        const el = document.querySelector(
                            '#addDrawer [name="' + name + '"]',
                        );
                        if (el) el.value = val || '';
                    };
                    setVal('dataflow_name', dfObj.dataflow_name);
                    setVal('dataflow_status', dfObj.dataflow_status);
                    setVal('app_name', dfObj.app_name);
                    setVal('ingestion', dfObj.ingestion);
                    setVal('start_date', dfObj.start_date);
                    setVal('start_time', dfObj.start_time);
                    setVal('time_zone', dfObj.time_zone);
                    setVal('periodicity', dfObj.periodicity);
                    // Mark schedule fields as prefilled so initScheduleUI won't reset them
                    const _sd = document.getElementById('schedDate');
                    const _st = document.getElementById('schedTime');
                    const _tz =
                        document.getElementById('schedTz') ||
                        document.querySelector(
                            '#scheduleTimeFields select[name="time_zone"]',
                        );
                    if (_sd && dfObj.start_date) _sd.dataset.prefilled = '1';
                    if (_st && dfObj.start_time) _st.dataset.prefilled = '1';
                    if (_tz && dfObj.time_zone) _tz.dataset.prefilled = '1';
                    setVal('conn_type', dfObj.conn_type);

                    // Removed prefillDrilldown from here
                    if (connSel) {
                        connSel.value = dfObj.conn_type || '';
                    }
                    if (dfObj.conn_type) {
                        const serviceBasedTypes = ['Fin_Data', 'churnData'];
                        if (serviceBasedTypes.includes(dfObj.conn_type)) {
                            // Click the Service Based parent card first to reveal sub-picker
                            const parentCard =
                                document.getElementById('serviceBasedCard');
                            if (parentCard) parentCard.click();
                            // Then click the matching sub-type-card
                            setTimeout(() => {
                                const subCard = document.querySelector(
                                    '.sub-type-card[data-src="' +
                                        dfObj.conn_type +
                                        '"]',
                                );
                                if (subCard) subCard.click();
                            }, 50);
                        } else {
                            // Standard connection types (S3, FTP, etc.)
                            const allCards = document.querySelectorAll(
                                '#srcTypePicker > .type-card',
                            );
                            let matched = false;
                            allCards.forEach((c) => {
                                const ds = c.dataset.src || '';
                                if (ds.split(',').includes(dfObj.conn_type)) {
                                    c.click();
                                    matched = true;
                                }
                            });
                            if (!matched) {
                                const defCard = document.querySelector(
                                    '.type-card[data-src="S3"]',
                                );
                                if (defCard) defCard.click();
                            }
                        }
                    } else {
                        const defCard = document.querySelector(
                            '.type-card[data-src="S3"]',
                        );
                        if (defCard) defCard.click();
                    }

                    // Fill connection-specific fields
                    setVal('url', dfObj.url);
                    setVal('user_name', dfObj.user_name);
                    setVal('password', dfObj.password);
                    setVal('BucketName', dfObj.BucketName);
                    setVal('AwsAccessKeyId', dfObj.AwsAccessKeyId);
                    setVal('AwsSecretAccessKey', dfObj.AwsSecretAccessKey);
                    setVal('depth', dfObj.depth);
                    setVal('description', dfObj.description);

                    setVal('sourceType', dfObj.sourceType);
                    const sourceSelect =
                        document.getElementById('addSourceType');
                    if (sourceSelect && dfObj.sourceType)
                        sourceSelect.dataset.prefill = dfObj.sourceType;

                    setVal('ApiKey', dfObj.ApiKey);
                    setVal('SecretKey', dfObj.SecretKey);
                    setVal('startDate', dfObj.startDate);
                    setVal('endDate', dfObj.endDate);
                    setVal('interval', dfObj.interval);

                    // CirclesList multi-select (schema: f_type = multi_select)
                    const circlesSelect =
                        document.getElementById('addCirclesList');
                    if (circlesSelect && dfObj.CirclesList) {
                        const circleVals = Array.isArray(dfObj.CirclesList)
                            ? dfObj.CirclesList
                            : [dfObj.CirclesList];
                        circlesSelect.dataset.prefill =
                            JSON.stringify(circleVals);
                    }

                    // Multi-select for symbolsList
                    const symbolsSelect = document.querySelector(
                        '#addDrawer [name="symbolsList"]',
                    );
                    if (
                        symbolsSelect &&
                        dfObj.symbolsList &&
                        Array.isArray(dfObj.symbolsList)
                    ) {
                        symbolsSelect.dataset.prefill = JSON.stringify(
                            dfObj.symbolsList,
                        );
                        Array.from(symbolsSelect.options).forEach((opt) => {
                            opt.selected = dfObj.symbolsList.includes(
                                opt.value,
                            );
                        });
                        // Trigger custom change manually to update UI
                        symbolsSelect.dispatchEvent(new Event('change'));
                    }

                    // Trigger cascade for Fin_Data Source Type
                    if (sourceSel) {
                        sourceSel.onchange && sourceSel.onchange();
                    }

                    // Populate file configuration rows
                    const container = document.getElementById('fileConfigRows');
                    if (container) {
                        container.innerHTML = '';
                        const fileList = dfObj.file_config || [];
                        if (fileList.length === 0) {
                            const row = document.createElement('div');
                            row.className = 'file-row';
                            row.style.cssText =
                                'display:flex; gap:var(--s-2); margin-bottom:var(--s-2); align-items:flex-end;';
                            row.innerHTML =
                                '<div class="field" style="flex:1;"><label>Remote Path <span style="color:var(--err, #ef4444);">*</span></label><input class="input" type="text" name="remote_path[]" placeholder="/path/to/dir/" style="font-family:var(--mono); font-size:12px;"></div>' +
                                '<div class="field" style="flex:1;"><label>File Name <span style="color:var(--err, #ef4444);">*</span></label><input class="input" type="text" name="file_name[]" placeholder="*.csv" style="font-family:var(--mono); font-size:12px;"></div>' +
                                '<div class="field" style="flex:1;"><label>Role <span style="color:var(--err, #ef4444);">*</span></label><select multiple class="select" name="role[]" style="height:38px;"><option value="System_Admin">System_Admin</option><option value="Operational">Operational</option><option value="Management">Management</option></select></div>' +
                                '<button type="button" class="btn btn-ghost btn-sm" onclick="this.closest(\'.file-row\').remove()">✕</button>';
                            container.appendChild(row);

                            setTimeout(() => {
                                const roleSelect = row.querySelector(
                                    'select[name="role[]"]',
                                );
                                if (roleSelect)
                                    initCustomMultiSelect(roleSelect);
                            }, 0);
                        } else {
                            fileList.forEach(function (fileItem) {
                                const row = document.createElement('div');
                                row.className = 'file-row';
                                row.style.cssText =
                                    'display:flex; gap:var(--s-2); margin-bottom:var(--s-2); align-items:flex-end;';
                                row.innerHTML =
                                    '<div class="field" style="flex:1;"><label>Remote Path <span style="color:var(--err, #ef4444);">*</span></label><input class="input" type="text" name="remote_path[]" placeholder="/path/to/dir/" style="font-family:var(--mono); font-size:12px;" value="' +
                                    (fileItem.remote_path || '') +
                                    '"></div>' +
                                    '<div class="field" style="flex:1;"><label>File Name <span style="color:var(--err, #ef4444);">*</span></label><input class="input" type="text" name="file_name[]" placeholder="*.csv" style="font-family:var(--mono); font-size:12px;" value="' +
                                    (fileItem.file_name || '') +
                                    '"></div>' +
                                    '<div class="field" style="flex:1;"><label>Role <span style="color:var(--err, #ef4444);">*</span></label><select multiple class="select" name="role[]" style="height:38px;"><option value="System_Admin">System_Admin</option><option value="Operational">Operational</option><option value="Management">Management</option></select></div>' +
                                    '<button type="button" class="btn btn-ghost btn-sm" onclick="this.closest(\'.file-row\').remove()">✕</button>';

                                // Pre-select roles if they exist
                                const roleSelect = row.querySelector(
                                    'select[name="role[]"]',
                                );
                                if (
                                    roleSelect &&
                                    fileItem.role &&
                                    Array.isArray(fileItem.role)
                                ) {
                                    Array.from(roleSelect.options).forEach(
                                        (opt) => {
                                            opt.selected =
                                                fileItem.role.includes(
                                                    opt.value,
                                                );
                                        },
                                    );
                                }

                                container.appendChild(row);

                                setTimeout(() => {
                                    if (roleSelect) {
                                        initCustomMultiSelect(roleSelect);
                                        roleSelect.dispatchEvent(
                                            new Event('change'),
                                        );
                                    }
                                }, 0);
                            });
                        }
                    }
                }
                // Ensure connection type is visually selected so UI unhides correct panels
                if (dfObj.conn_type) {
                    const ctCard = document.querySelector(
                        `.type-card[data-src="${dfObj.conn_type}"]`,
                    );
                    if (ctCard) ctCard.click();
                }

                // Pre-fill Drilldown with a slight delay so DOM updates from click can propagate
                if (window.prefillDrilldown) {
                    setTimeout(() => {
                        window.prefillDrilldown(
                            dfObj.app_name,
                            dfObj.service_name,
                            dfObj.dataflow_type,
                            dfObj.ingestion,
                        );
                    }, 50);
                }
            } else {
                if (title) title.textContent = 'New dataflow';
                if (saveBtn) saveBtn.textContent = 'Create dataflow';
                // Reset all form fields
                const form = document.getElementById('create_new_dataflow');
                if (form) {
                    form.querySelectorAll(
                        'input:not([type=hidden]), select, textarea',
                    ).forEach(function (el) {
                        if (el.type === 'checkbox' || el.type === 'radio')
                            el.checked = false;
                        else el.value = '';
                    });
                    // Restore hidden defaults
                    const statusEl = form.querySelector(
                        '[name="dataflow_status"]',
                    );
                    if (statusEl) statusEl.value = 'Enable';
                    // Clear prefilled markers so initScheduleUI applies defaults
                    ['schedDate', 'schedTime', 'schedTz'].forEach((id) => {
                        const el = document.getElementById(id);
                        if (el) delete el.dataset.prefilled;
                    });
                }
                toggleConnFields(''); // hide all conn fields

                // Reset service sub-picker
                const subPicker = document.getElementById('serviceSubPicker');
                if (subPicker) {
                    subPicker.style.display = 'none';
                    subPicker
                        .querySelectorAll('.sub-type-card')
                        .forEach((x) => x.classList.remove('selected'));
                }
                // Deselect all type cards
                document
                    .querySelectorAll('#srcTypePicker .type-card')
                    .forEach((c) => c.classList.remove('selected'));

                // Reset file list to one empty row
                const container = document.getElementById('fileConfigRows');
                if (container) {
                    container.innerHTML = '';
                    const row = document.createElement('div');
                    row.className = 'file-row';
                    row.style.cssText =
                        'display:flex; gap:var(--s-2); margin-bottom:var(--s-2);';
                    row.innerHTML =
                        '<div class="field" style="flex:1;"><label>Remote Path <span style="color:var(--err, #ef4444);">*</span></label><input class="input" type="text" name="remote_path[]" placeholder="/path/to/dir/" style="font-family:var(--mono); font-size:12px;"></div>' +
                        '<div class="field" style="flex:1;"><label>File Name <span style="color:var(--err, #ef4444);">*</span></label><input class="input" type="text" name="file_name[]" placeholder="*.csv" style="font-family:var(--mono); font-size:12px;"></div>' +
                        '<div class="field" style="flex:1;"><label>Role <span style="color:var(--err, #ef4444);">*</span></label><select multiple class="select" name="role[]" style="height:38px;"><option value="System_Admin">System_Admin</option><option value="Operational">Operational</option><option value="Management">Management</option></select></div>' +
                        '<button type="button" style="justify-content:center"class="btn btn-ghost btn-sm" onclick="this.closest(\'.file-row\').remove()">Close ✕</button>';
                    container.appendChild(row);

                    setTimeout(() => {
                        const roleSelect = row.querySelector(
                            'select[name="role[]"]',
                        );
                        if (roleSelect) initCustomMultiSelect(roleSelect);
                    }, 0);
                }
                if (window.prefillDrilldown) window.prefillDrilldown();
            }
            resetStepper();
            if (window.initScheduleUI) window.initScheduleUI();

            const drawerForm = document.getElementById('create_new_dataflow');
            if (drawerForm) {
                const editableFields = [
                    'dataflow_name',
                    'description',
                    'remote_path[]',
                    'file_name[]',
                    'role[]',
                    'start_date',
                    'start_time',
                    'time_zone',
                    'periodicity',
                    'dataflow_status',
                ];
                const allInputs = drawerForm.querySelectorAll(
                    'input:not([type=hidden]), select, textarea',
                );
                const allTypeCards = document.querySelectorAll(
                    '#addDrawer .type-card, #addDrawer .sub-type-card, #destDrill, #dftGrid',
                );

                if (mode === 'edit') {
                    allInputs.forEach((el) => {
                        if (el.name && !editableFields.includes(el.name)) {
                            el.disabled = true;
                        }
                    });
                    allTypeCards.forEach((c) => {
                        c.style.pointerEvents = 'none';
                        c.style.opacity = '0.6';
                    });
                } else {
                    allInputs.forEach((el) => (el.disabled = false));
                    allTypeCards.forEach((c) => {
                        c.style.pointerEvents = 'auto';
                        c.style.opacity = '1';
                    });
                }
            }

            openDrawer('add');
        }

        function closeDialog (type) {
            if (type === 'rerun') {
                const b = document.getElementById('rerunBack');
                if (b) b.classList.remove('open');
                window.rerunTarget = null;
            } else {
                const b = document.getElementById('deleteBack');
                if (b) b.classList.remove('open');
                deleteTarget = null;
            }
        }
        window.closeDialog = closeDialog;

        function openRerunDialog (df) {
            window.rerunTarget = df;
            const rt = document.getElementById('rerunNameTarget');
            const dInp = document.getElementById('rerunDateInput');
            if (rt) rt.textContent = df.name;
            if (dInp) {
                const today = new Date();
                const yyyy = today.getFullYear();
                const mm = String(today.getMonth() + 1).padStart(2, '0');
                const dd = String(today.getDate()).padStart(2, '0');
                dInp.value = `${yyyy}-${mm}-${dd}`;
            }

            const b = document.getElementById('rerunBack');
            if (b) {
                b.classList.add('open');
                setTimeout(() => {
                    if (dInp) dInp.focus();
                }, 200);
            }
        }

        function openDeleteDialog (df) {
            deleteTarget = df;
            const dn = document.getElementById('delName');
            const dt = document.getElementById('delNameTarget');
            const conf = document.getElementById('delConfirm');
            const btn = document.getElementById('delConfirmBtn');
            if (dn) dn.textContent = df.name;
            if (dt) dt.textContent = df.name;
            if (conf) conf.value = '';
            if (btn) {
                btn.disabled = true;
                btn.innerHTML = 'Delete dataflow';
            }

            // Use the visible delNameTarget text as the canonical name for comparison.
            // This guards against stale data-name attributes on cards differing from
            // what the dialog actually displays to the user.
            const canonicalName = (dt ? dt.textContent : df.name).trim();

            // Enable the delete button only when the typed name matches exactly
            if (conf && btn) {
                // Remove any previously attached listener to avoid stacking
                if (conf._deleteInputHandler) {
                    conf.removeEventListener('input', conf._deleteInputHandler);
                }
                conf._deleteInputHandler = function () {
                    btn.disabled = conf.value.trim() !== canonicalName;
                };
                conf.addEventListener('input', conf._deleteInputHandler);
            }

            const b = document.getElementById('deleteBack');
            if (b) {
                b.classList.add('open');
                setTimeout(() => {
                    if (conf) conf.focus();
                }, 200);
            }
        }

        // Load logs and run history from Django backend for specific dataflow
        function loadLogsForDataflow (dfId, dfType) {
            const logStream = document.getElementById('logStream');
            const runsList = document.querySelector(
                '.step-pane[data-pane-content="runs"] .runs-list',
            );

            if (logStream)
                logStream.innerHTML =
                    '<div class="log-line"><span class="msg">Loading logs…</span></div>';
            if (runsList)
                runsList.innerHTML =
                    '<div class="run-row">Loading run history…</div>';

            const csrfTokenInput = document.querySelector(
                '[name="csrfmiddlewaretoken"]',
            );
            const csrfToken = csrfTokenInput ? csrfTokenInput.value : '';

            const formData = new FormData();
            formData.append('user-action', 'dataflow_log');
            formData.append('dataflow_id', dfId);
            formData.append('dataflow_type', dfType);

            fetch('/PlatformIO/BatchIngress/', {
                method: 'POST',
                headers: {
                    'X-CSRFToken': csrfToken,
                },
                body: formData,
            })
                .then((res) => {
                    if (res.ok) return res.json();
                    throw new Error('Failed to fetch logs');
                })
                .then((res) => {
                    // Populate Logs Pane
                    if (logStream) {
                        logStream.innerHTML = '';
                        const logsObj = res.logs || {};
                        const logKeys = Object.keys(logsObj);

                        const drawerLogsBadge =
                            document.getElementById('drawerLogsCount');
                        if (drawerLogsBadge)
                            drawerLogsBadge.textContent = logKeys.length;

                        if (logKeys.length === 0) {
                            logStream.innerHTML =
                                '<div class="log-line"><span class="msg">No log activities recorded.</span></div>';
                        } else {
                            logKeys.forEach((k) => {
                                const log = logsObj[k];
                                const line = document.createElement('div');
                                line.className = 'log-line';

                                const tSpan = document.createElement('span');
                                tSpan.className = 't';
                                tSpan.textContent = `${log.Time || ''} ${log.Date || ''}`;

                                const rawStatus = (
                                    log.Status || 'INFO'
                                ).toUpperCase();
                                const statusClass =
                                    rawStatus === 'SUCCESS' ||
                                    rawStatus === 'OK'
                                        ? 'OK'
                                        : rawStatus.includes('FAIL') ||
                                            rawStatus === 'ERR'
                                            ? 'ERR'
                                            : rawStatus === 'WARN'
                                                ? 'WARN'
                                                : rawStatus;

                                const lvlSpan = document.createElement('span');
                                lvlSpan.className = `lvl ${statusClass}`;
                                lvlSpan.textContent =
                                    statusClass === 'OK'
                                        ? 'Success'
                                        : statusClass === 'ERR'
                                            ? 'Error'
                                            : statusClass === 'WARN'
                                                ? 'Warning'
                                                : statusClass === 'INFO'
                                                    ? 'Info'
                                                    : statusClass;

                                const msgSpan = document.createElement('span');
                                msgSpan.className = 'msg';

                                let msgText = log.Msg || '';
                                if (
                                    res.log_keys &&
                                    res.log_keys.length > 0 &&
                                    log.log_info
                                ) {
                                    const paramsArr = [];
                                    res.log_keys.forEach((key) => {
                                        if (log.log_info[key] !== undefined) {
                                            let v = log.log_info[key];
                                            if (typeof v === 'object')
                                                v = JSON.stringify(v);
                                            paramsArr.push(
                                                `<span class="k">${key}</span>=<span class="v">${v}</span>`,
                                            );
                                        }
                                    });
                                    if (paramsArr.length > 0) {
                                        msgText +=
                                            ' · ' + paramsArr.join(' · ');
                                    }
                                }

                                msgSpan.innerHTML = msgText;

                                line.appendChild(tSpan);
                                line.appendChild(lvlSpan);
                                line.appendChild(msgSpan);
                                logStream.appendChild(line);
                            });
                        }
                    }

                    // Populate Runs History Pane and Overview 7d Stats
                    if (runsList) {
                        runsList.innerHTML = '';
                        const logsObj = res.logs || {};
                        const logKeys = Object.keys(logsObj);

                        let totalRuns = 0;
                        let successRuns = 0;
                        let totalRecords = 0;

                        if (logKeys.length === 0) {
                            runsList.innerHTML =
                                '<div class="run-row">No runs recorded.</div>';
                        } else {
                            logKeys.forEach((k) => {
                                const log = logsObj[k];
                                const row = document.createElement('div');
                                row.className = 'run-row';

                                const statusColor =
                                    log.Status === 'Success' ||
                                    log.Status === 'OK' ||
                                    log.Status === 'INFO'
                                        ? 'ok'
                                        : 'err';

                                totalRuns++;
                                if (statusColor === 'ok') successRuns++;

                                let recCount = '-';
                                if (log.log_info) {
                                    recCount =
                                        log.log_info['Total Records'] ||
                                        log.log_info['total_records'] ||
                                        log.log_info['Total Dev'] ||
                                        '-';
                                    if (
                                        recCount !== '-' &&
                                        !isNaN(parseInt(recCount))
                                    ) {
                                        totalRecords += parseInt(recCount);
                                    }
                                }

                                const duration =
                                    log.Duration ||
                                    log.duration ||
                                    (log.log_info
                                        ? log.log_info['Ingested Time']
                                        : null) ||
                                    '-';
                                const runId = log.log_id || 'Run #' + k;

                                row.innerHTML = `
                                <div class="dot-sm ${statusColor}"></div>
                                <div><strong>${runId}</strong> &nbsp;<span style="color:var(--ink-4); font-family:var(--mono); font-size:11px;">${log.Time || ''} ${log.Date || ''}</span></div>
                                <div class="dur">${duration}</div>
                                <div class="n">${recCount} rec</div>
                            `;
                                runsList.appendChild(row);
                            });
                        }

                        // Update 7d stats in Overview pane
                        const statRuns = document.getElementById('stat7dRuns');
                        const statSuccess =
                            document.getElementById('stat7dSuccess');
                        const statRecords =
                            document.getElementById('stat7dRecords');

                        if (statRuns) statRuns.textContent = totalRuns;
                        if (statSuccess) {
                            statSuccess.textContent =
                                totalRuns > 0
                                    ? Math.round(
                                        (successRuns / totalRuns) * 100,
                                    ) + '%'
                                    : '—';
                        }
                        if (statRecords) {
                            statRecords.textContent =
                                totalRecords > 0
                                    ? totalRecords.toLocaleString()
                                    : '—';
                        }

                        // Update Recent Activity in Overview pane
                        const recentActivityList = document.getElementById(
                            'detailRecentActivity',
                        );
                        if (recentActivityList) {
                            recentActivityList.innerHTML = '';
                            if (logKeys.length === 0) {
                                recentActivityList.innerHTML =
                                    '<div class="run-row"><span class="msg" style="color:var(--ink-4);">No recent activity.</span></div>';
                            } else {
                                // show top 3 most recent
                                const recentKeys = [...logKeys].slice(0, 3);
                                recentKeys.forEach((k) => {
                                    const log = logsObj[k];
                                    const row = document.createElement('div');
                                    row.className = 'run-row';

                                    const statusColor =
                                        log.Status === 'Success' ||
                                        log.Status === 'OK' ||
                                        log.Status === 'INFO'
                                            ? 'ok'
                                            : 'err';
                                    const duration =
                                        log.Duration ||
                                        log.duration ||
                                        (log.log_info
                                            ? log.log_info['Ingested Time']
                                            : null) ||
                                        '-';

                                    let recCount = '-';
                                    if (log.log_info) {
                                        recCount =
                                            log.log_info['Total Records'] ||
                                            log.log_info['total_records'] ||
                                            log.log_info['Total Dev'] ||
                                            '-';
                                    }

                                    row.innerHTML = `
                                    <div class="dot-sm ${statusColor}"></div>
                                    <div>${log.Time || ''} ${log.Date || ''}</div>
                                    <div class="dur">${duration}</div>
                                    <div class="n">${recCount} rec</div>
                                    `;
                                    recentActivityList.appendChild(row);
                                });
                            }
                        }
                    }
                })
                .catch((err) => {
                    if (logStream)
                        logStream.innerHTML = `<div class="log-line"><span class="msg text-danger">Error: ${err.message}</span></div>`;
                    if (runsList)
                        runsList.innerHTML = `<div class="run-row text-danger">Error loading history: ${err.message}</div>`;
                });
        }

        function openDetail (row, tabName) {
            activeDataflow = row;
            const title = document.getElementById('detailTitle');
            const idSpan = document.getElementById('detailId');
            if (title) title.textContent = row.name;
            if (idSpan) idSpan.textContent = row.id;

            const pill = row.el.querySelector('.pill, .pill-mini');
            if (pill) {
                const newPill = pill.cloneNode(true);
                newPill.id = 'detailStatus';
                const oldPill = document.getElementById('detailStatus');
                if (oldPill) oldPill.replaceWith(newPill);
            }

            // Fetch dynamic backend details
            const dfObj = window.dataflow_info.find(
                (d) => d.dataflow_id === row.id,
            );
            const overviewGrid = document.querySelector(
                '.detail-pane[data-pane-content="overview"] .detail-grid',
            );
            if (overviewGrid && dfObj) {
                let sourceStr = `${dfObj.conn_type || 'NA'}`;
                if (dfObj.bucket_name)
                    sourceStr += ` · s3://${dfObj.bucket_name}/${dfObj.folder_name || ''}`;
                else if (dfObj.path) sourceStr += ` · ${dfObj.path}`;
                else if (dfObj.host)
                    sourceStr += ` · ${dfObj.host}:${dfObj.port || ''}`;

                const destStr = `${dfObj.dataflow_type || 'NA'} · ${dfObj.service_name || 'NA'}`;

                overviewGrid.innerHTML = `
                    <dt>Source</dt><dd>${sourceStr}</dd>
                    <dt>Destination</dt><dd>${destStr}</dd>
                    <dt>Schedule</dt><dd>${dfObj.periodicity || 'NA'} at ${dfObj.start_time || 'NA'} (${dfObj.time_zone || 'NA'})</dd>
                    <dt>Application</dt><dd>${dfObj.app_name || 'NA'}</dd>
                    <dt>Created Date</dt><dd>${dfObj.start_date || 'NA'}</dd>
                    <dt>Description</dt><dd>${dfObj.description || 'NA'}</dd>
                `;
            }

            // Populate schedule details
            const scheduleGrid = document.querySelector(
                '.detail-pane[data-pane-content="schedule"] .detail-grid',
            );
            if (scheduleGrid && dfObj) {
                scheduleGrid.innerHTML = `
                    <dt>Frequency</dt><dd>${dfObj.periodicity || 'NA'}</dd>
                    <dt>Start Date</dt><dd>${dfObj.start_date || 'NA'}</dd>
                    <dt>Start Time</dt><dd>${dfObj.start_time || 'NA'}</dd>
                    <dt>Timezone</dt><dd>${dfObj.time_zone || 'NA'}</dd>
                `;
            }

            // Fetch and load logs & run history asynchronously
            loadLogsForDataflow(row.id, dfObj ? dfObj.dataflow_type : '');

            switchTab(tabName || 'overview');
            openDrawer('detail');
        }

        function setStep (n) {
            currentStep = n;
            document.querySelectorAll('.stepper .step').forEach((s) => {
                const sn = parseInt(s.dataset.step, 10);
                s.classList.toggle('active', sn === n);
                s.classList.toggle('done', sn < n);
            });
            document.querySelectorAll('[data-step-content]').forEach((p) => {
                p.classList.toggle(
                    'active',
                    parseInt(p.dataset.stepContent, 10) === n,
                );
            });
            const prev = document.getElementById('prevStep');
            const nxt = document.getElementById('nextStep');
            const save = document.getElementById('saveDataflow');
            if (prev) prev.style.display = n > 1 ? '' : 'none';
            if (nxt) nxt.style.display = n < 4 ? '' : 'none';
            if (save) save.style.display = n === 4 ? '' : 'none';

            if (n === 2) {
                const connTypeInput =
                    document.querySelector('[name="conn_type"]') ||
                    document.getElementById('addConnType');
                const connType = (connTypeInput && connTypeInput.value) || '';
                const serviceConfigArea =
                    document.getElementById('serviceConfigArea');
                const fileConfigWrapper =
                    document.getElementById('fileConfigWrapper');

                if (connType === 'Fin_Data' || connType === 'churnData') {
                    if (serviceConfigArea) {
                        serviceConfigArea.style.display = 'none'; // Keep hidden initially
                    }

                    const csrfToken =
                        document.querySelector('[name="csrfmiddlewaretoken"]')
                            ?.value || '';
                    fetch('/PlatformIO/APIv1/GetServicesByConnType/', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                            'X-CSRFToken': csrfToken,
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
                                    c.nodes.forEach((n) => {
                                        cInfo[c.cluster_name].node_info[
                                            n.node_name
                                        ] = {
                                            node_name: n.node_name,
                                            service_info: {},
                                        };
                                        n.services.forEach((s) => {
                                            cInfo[c.cluster_name].node_info[
                                                n.node_name
                                            ].service_info[s.service_name] = s;
                                        });
                                    });
                                });
                                window.cluster_info = cInfo;
                                if (window.buildClustersGlobal) {
                                    window.buildClustersGlobal();
                                }
                            }
                        })
                        .catch((err) =>
                            console.error('Error fetching services:', err),
                        );
                } else {
                    if (serviceConfigArea) {
                        document
                            .querySelectorAll('#serviceConfigArea .conn-fields')
                            .forEach((f) => (f.style.display = 'none'));
                    }
                }
            }

            if (n === 4) {
                // ── Dataflow card ──────────────────────────────────────────
                const nameInput = document.querySelector(
                    '[name="dataflow_name"]',
                );
                const dfTypeInput = document.querySelector(
                    '[name="dataflow_type"]',
                );
                const descInput =
                    document.querySelector('[name="description"]') ||
                    document.getElementById('addDesc');

                const rvName = document.getElementById('rvName');
                const rvType = document.getElementById('rvType');
                const rvDesc = document.getElementById('rvDesc');

                if (rvName)
                    rvName.textContent = (nameInput && nameInput.value) || '—';
                if (rvType)
                    rvType.textContent =
                        (dfTypeInput && dfTypeInput.value) || 'Batch Ingress';
                if (rvDesc) {
                    const dv = (descInput && descInput.value) || '';
                    rvDesc.textContent = dv || '(no description)';
                    rvDesc.style.fontStyle = dv ? 'normal' : 'italic';
                    rvDesc.style.color = dv ? '' : 'var(--ink-4)';
                }

                // ── Source card ───────────────────────────────────────────
                const connTypeInput =
                    document.querySelector('[name="conn_type"]') ||
                    document.getElementById('addConnType');
                const connType = (connTypeInput && connTypeInput.value) || '';

                const rvConnType = document.getElementById('rvConnType');
                const rvSrcDetail = document.getElementById('rvSrcDetail');
                const rvSrcDetailLabel =
                    document.getElementById('rvSrcDetailLabel');
                const rvSrcExtra1 = document.getElementById('rvSrcExtra1');
                const rvSrcExtra1Lbl =
                    document.getElementById('rvSrcExtra1Label');

                if (rvConnType) rvConnType.textContent = connType || '—';

                // Hide extras by default then reveal as needed
                if (rvSrcExtra1) rvSrcExtra1.style.display = 'none';
                if (rvSrcExtra1Lbl) rvSrcExtra1Lbl.style.display = 'none';

                if (connType === 'S3') {
                    if (rvSrcDetailLabel)
                        rvSrcDetailLabel.textContent = 'Bucket';
                    const bucket = document.querySelector(
                        '[name="BucketName"]',
                    );
                    if (rvSrcDetail)
                        rvSrcDetail.textContent =
                            (bucket && bucket.value) || '—';
                } else if (connType === 'FTP' || connType === 'SFTP') {
                    if (rvSrcDetailLabel) rvSrcDetailLabel.textContent = 'URL';
                    const url = document.querySelector('[name="url"]');
                    if (rvSrcDetail)
                        rvSrcDetail.textContent = (url && url.value) || '—';
                    if (rvSrcExtra1Lbl) {
                        rvSrcExtra1Lbl.textContent = 'User';
                        rvSrcExtra1Lbl.style.display = '';
                    }
                    const user = document.querySelector('[name="user_name"]');
                    if (rvSrcExtra1) {
                        rvSrcExtra1.textContent = (user && user.value) || '—';
                        rvSrcExtra1.style.display = '';
                    }
                } else if (connType === 'WEB_SCRAP') {
                    if (rvSrcDetailLabel)
                        rvSrcDetailLabel.textContent = 'Depth';
                    const depth = document.querySelector('[name="depth"]');
                    if (rvSrcDetail)
                        rvSrcDetail.textContent = (depth && depth.value) || '0';
                } else if (connType === 'Fin_Data') {
                    if (rvSrcDetailLabel)
                        rvSrcDetailLabel.textContent = 'Source type';
                    const srcType = document.querySelector(
                        '[name="sourceType"]',
                    );
                    if (rvSrcDetail)
                        rvSrcDetail.textContent =
                            (srcType && srcType.value) || '—';
                    const symSel = document.querySelector(
                        '[name="symbolsList"]',
                    );
                    if (symSel) {
                        const syms = Array.from(symSel.selectedOptions)
                            .map((o) => o.textContent)
                            .slice(0, 4);
                        if (rvSrcExtra1Lbl) {
                            rvSrcExtra1Lbl.textContent = 'Symbols';
                            rvSrcExtra1Lbl.style.display = '';
                        }
                        if (rvSrcExtra1) {
                            rvSrcExtra1.textContent = syms.length
                                ? syms.join(', ') +
                                  (symSel.selectedOptions.length > 4
                                      ? ' …'
                                      : '')
                                : '—';
                            rvSrcExtra1.style.display = '';
                        }
                    }
                } else if (connType === 'churnData') {
                    if (rvSrcDetailLabel)
                        rvSrcDetailLabel.textContent = 'Circles';
                    const circleSel = document.querySelector(
                        '[name="CirclesList"]',
                    );
                    if (rvSrcDetail) {
                        const vals = circleSel
                            ? Array.from(circleSel.selectedOptions).map(
                                (o) => o.textContent,
                            )
                            : [];
                        rvSrcDetail.textContent = vals.length
                            ? vals.join(', ')
                            : '—';
                    }
                } else if (connType === 'hdfs') {
                    if (rvSrcDetailLabel)
                        rvSrcDetailLabel.textContent = 'Namenode URI';
                    const nn = document.querySelector('[name="hdfs_namenode"]');
                    if (rvSrcDetail)
                        rvSrcDetail.textContent = (nn && nn.value) || '—';
                    if (rvSrcExtra1Lbl) {
                        rvSrcExtra1Lbl.textContent = 'Path';
                        rvSrcExtra1Lbl.style.display = '';
                    }
                    const hp = document.querySelector('[name="hdfs_path"]');
                    if (rvSrcExtra1) {
                        rvSrcExtra1.textContent = (hp && hp.value) || '—';
                        rvSrcExtra1.style.display = '';
                    }
                } else if (connType === 'HTTP_API') {
                    if (rvSrcDetailLabel)
                        rvSrcDetailLabel.textContent = 'Endpoint';
                    const ep = document.querySelector('[name="http_endpoint"]');
                    if (rvSrcDetail)
                        rvSrcDetail.textContent = (ep && ep.value) || '—';
                    if (rvSrcExtra1Lbl) {
                        rvSrcExtra1Lbl.textContent = 'Auth';
                        rvSrcExtra1Lbl.style.display = '';
                    }
                    const authType = document.querySelector(
                        '[name="http_auth_type"]',
                    );
                    if (rvSrcExtra1) {
                        rvSrcExtra1.textContent =
                            (authType && authType.value) || '—';
                        rvSrcExtra1.style.display = '';
                    }
                } else if (connType === 'Google_Drive') {
                    if (rvSrcDetailLabel)
                        rvSrcDetailLabel.textContent = 'Drive folder';
                    if (rvSrcDetail)
                        rvSrcDetail.textContent = '(via service account)';
                } else if (connType === 'LOCAL') {
                    if (rvSrcDetailLabel)
                        rvSrcDetailLabel.textContent = 'Local storage';
                    if (rvSrcDetail)
                        rvSrcDetail.textContent = 'Local file system';
                } else {
                    if (rvSrcDetailLabel)
                        rvSrcDetailLabel.textContent = 'Details';
                    if (rvSrcDetail)
                        rvSrcDetail.textContent = connType ? connType : '—';
                }

                // ── Destination card ──────────────────────────────────────
                const appInput = document.querySelector('[name="app_name"]');
                const serviceInput =
                    document.querySelector('[name="service_name"]') ||
                    document.getElementById('addServiceName');
                const ingestionSel = document.getElementById('ingestionSelect');

                const rvApp = document.getElementById('rvApp');
                const rvService = document.getElementById('rvService');
                const rvIngestion = document.getElementById('rvIngestion');

                if (rvApp)
                    rvApp.textContent = (appInput && appInput.value) || '—';
                if (rvService)
                    rvService.textContent =
                        (serviceInput && serviceInput.value) || '—';
                if (rvIngestion)
                    rvIngestion.textContent =
                        (ingestionSel && ingestionSel.value) || '—';

                // ── Schedule card ─────────────────────────────────────────
                const periodicityInput =
                    document.querySelector('[name="periodicity"]') ||
                    document.getElementById('periodicityInput');
                const startDateInput = document.getElementById('schedDate');
                const startTimeInput = document.getElementById('schedTime');
                const tzInput = document.getElementById('schedTz');

                const rvPeriodicity = document.getElementById('rvPeriodicity');
                const rvStartDate = document.getElementById('rvStartDate');
                const rvTimeTz = document.getElementById('rvTimeTz');

                if (rvPeriodicity) {
                    const pv =
                        (periodicityInput && periodicityInput.value) || '';
                    const labelMap = {
                        HOURLY: 'Hourly',
                        DAILY: 'Daily',
                        WEEKLY: 'Weekly',
                        MONTHLY: 'Monthly',
                        ONCE: 'On-demand only',
                    };
                    rvPeriodicity.textContent = labelMap[pv] || pv || '—';
                }
                if (rvStartDate)
                    rvStartDate.textContent =
                        (startDateInput && startDateInput.value) || '—';
                if (rvTimeTz) {
                    const tv = (startTimeInput && startTimeInput.value) || '';
                    const tzv = (tzInput && tzInput.value) || '';
                    rvTimeTz.textContent =
                        tv && tzv ? `${tv}  ·  ${tzv}` : tv || tzv || '—';
                }
            }
        }

        function resetStepper () {
            setStep(1);
        }

        document.body.addEventListener('click', function (e) {
            if (window.CloseOnClickOut) {
                window.CloseOnClickOut(e);
            }
            const target = e.target;
            const menu = document.getElementById('rowMenu');

            if (target.id === 'newBtn' || target.closest('#newBtn')) {
                openAddDrawer('add', null);
                return;
            }

            if (target.closest('#toggleDataflows')) {
                document
                    .getElementById('toggleDataflows')
                    .classList.add('active');
                if (document.getElementById('toggleBulletin'))
                    document
                        .getElementById('toggleBulletin')
                        .classList.remove('active');
                if (document.getElementById('toggleLogs'))
                    document
                        .getElementById('toggleLogs')
                        .classList.remove('active');
                if (document.getElementById('toggleStatus'))
                    document
                        .getElementById('toggleStatus')
                        .classList.remove('active');
                const vdf = document.getElementById('view-dataflows');
                const vb = document.getElementById('view-bulletin');
                const vl = document.getElementById('view-logs');
                const vs = document.getElementById('view-status');
                if (vdf) vdf.classList.add('active');
                if (vb) vb.classList.remove('active');
                if (vl) vl.classList.remove('active');
                if (vs) vs.classList.remove('active');
                document.body.classList.remove('bulletin-mode', 'logs-mode');
                return;
            }
            if (target.closest('#toggleBulletin')) {
                document
                    .getElementById('toggleBulletin')
                    .classList.add('active');
                if (document.getElementById('toggleDataflows'))
                    document
                        .getElementById('toggleDataflows')
                        .classList.remove('active');
                if (document.getElementById('toggleLogs'))
                    document
                        .getElementById('toggleLogs')
                        .classList.remove('active');
                if (document.getElementById('toggleStatus'))
                    document
                        .getElementById('toggleStatus')
                        .classList.remove('active');
                const vdf = document.getElementById('view-dataflows');
                const vb = document.getElementById('view-bulletin');
                const vl = document.getElementById('view-logs');
                const vs = document.getElementById('view-status');
                if (vb) vb.classList.add('active');
                if (vdf) vdf.classList.remove('active');
                if (vl) vl.classList.remove('active');
                if (vs) vs.classList.remove('active');
                document.body.classList.remove('logs-mode');
                document.body.classList.add('bulletin-mode');
                loadBulletinBoard();
                return;
            }
            if (target.closest('#toggleLogs')) {
                if (document.getElementById('toggleLogs'))
                    document
                        .getElementById('toggleLogs')
                        .classList.add('active');
                if (document.getElementById('toggleDataflows'))
                    document
                        .getElementById('toggleDataflows')
                        .classList.remove('active');
                if (document.getElementById('toggleBulletin'))
                    document
                        .getElementById('toggleBulletin')
                        .classList.remove('active');
                if (document.getElementById('toggleStatus'))
                    document
                        .getElementById('toggleStatus')
                        .classList.remove('active');
                const vdf = document.getElementById('view-dataflows');
                const vb = document.getElementById('view-bulletin');
                const vl = document.getElementById('view-logs');
                const vs = document.getElementById('view-status');
                if (vl) vl.classList.add('active');
                if (vb) vb.classList.remove('active');
                if (vdf) vdf.classList.remove('active');
                if (vs) vs.classList.remove('active');
                document.body.classList.remove('bulletin-mode');
                document.body.classList.add('logs-mode');
                loadAllLogs();
                return;
            }
            if (target.closest('#toggleStatus')) {
                if (document.getElementById('toggleStatus'))
                    document
                        .getElementById('toggleStatus')
                        .classList.add('active');
                if (document.getElementById('toggleDataflows'))
                    document
                        .getElementById('toggleDataflows')
                        .classList.remove('active');
                if (document.getElementById('toggleBulletin'))
                    document
                        .getElementById('toggleBulletin')
                        .classList.remove('active');
                if (document.getElementById('toggleLogs'))
                    document
                        .getElementById('toggleLogs')
                        .classList.remove('active');
                const vdf = document.getElementById('view-dataflows');
                const vb = document.getElementById('view-bulletin');
                const vl = document.getElementById('view-logs');
                const vs = document.getElementById('view-status');
                if (vs) vs.classList.add('active');
                if (vl) vl.classList.remove('active');
                if (vb) vb.classList.remove('active');
                if (vdf) vdf.classList.remove('active');
                document.body.classList.remove('bulletin-mode', 'logs-mode');
                return;
            }

            if (
                menu &&
                menu.classList.contains('open') &&
                !target.closest('#rowMenu') &&
                !target.closest('.more')
            ) {
                menu.classList.remove('open');
            }

            const detailTab = target.closest('.drawer-tabs .tab');
            if (detailTab) {
                switchTab(detailTab.dataset.pane);
                return;
            }

            if (target.id === 'detailBack') return closeDrawer('detail');
            if (target.id === 'addBack') return closeDrawer('add');
            if (target.id === 'deleteBack') return closeDialog();
            if (
                target.closest('.drawer-head .icon-btn') ||
                target.textContent === 'Close' ||
                target.textContent === 'Cancel'
            ) {
                const dr =
                    target.closest('.drawer') ||
                    (target.textContent === 'Close'
                        ? document.getElementById('detailDrawer')
                        : null) ||
                    (target.textContent === 'Cancel'
                        ? document.getElementById('addDrawer')
                        : null);
                if (dr && dr.id === 'addDrawer') return closeDrawer('add');
                if (dr && dr.id === 'detailDrawer')
                    return closeDrawer('detail');
            }

            if (target.closest('#rowMenu button')) {
                const btn = target.closest('#rowMenu button');
                const act = btn.dataset.act;
                if (menu) menu.classList.remove('open');
                if (!menuTarget) return;

                if (act === 'view') openDetail(menuTarget, 'overview');
                else if (act === 'logs') openDetail(menuTarget, 'logs');
                else if (act === 'run') {
                    openDetail(menuTarget, 'rerun');
                } else if (act === 'pause') {
                    showToast(`Paused schedule for ${menuTarget.name}`);
                } else if (act === 'edit') openAddDrawer('edit', menuTarget);
                else if (act === 'duplicate')
                    showToast(`Created copy of ${menuTarget.name}`, 'ok');
                else if (act === 'delete') openDeleteDialog(menuTarget);
                return;
            }

            const actionBtn = target.closest(
                '.action-btn, .more, .quick .btn, .df-menu-btn',
            );
            if (actionBtn) {
                const act =
                    actionBtn.dataset.act ||
                    actionBtn.textContent.trim().toLowerCase();
                const rowEl = actionBtn.closest('tr, .df-card');
                if (!rowEl) return;

                const df = {
                    id: rowEl.dataset.id,
                    name: rowEl.dataset.name,
                    status: rowEl.dataset.status,
                    el: rowEl,
                };

                if (act === 'menu' || actionBtn.classList.contains('more')) {
                    menuTarget = df;
                    const r = actionBtn.getBoundingClientRect();
                    if (menu) {
                        menu.style.top = r.bottom + window.scrollY + 4 + 'px';
                        menu.style.left = r.right + window.scrollX - 180 + 'px';
                        menu.classList.add('open');
                    }
                } else if (act === 'logs') {
                    openDetail(df, 'logs');
                } else if (act === 'retry') {
                    showToast(`Retrying ${df.name}…`);
                } else if (act === 'run') {
                    openDetail(df, 'rerun');
                } else if (act === 'enable') {
                    const pill = rowEl.querySelector('.pill, .pill-mini');
                    if (pill) {
                        pill.className = 'pill pill-ok';
                        pill.textContent = 'Enabled';
                    }
                    showToast(`${df.name} enabled`, 'ok');
                }
                return;
            }

            const container = target.closest('#dataflowsTbody, #dataflowsGrid');
            if (container && target.closest('tr, .df-card')) {
                const rowEl = target.closest('tr, .df-card');
                const df = {
                    id: rowEl.dataset.id,
                    name: rowEl.dataset.name,
                    status: rowEl.dataset.status,
                    el: rowEl,
                };
                openDetail(df, 'overview');
                return;
            }

            if (target.id === 'nextStep') {
                if (currentStep === 1) {
                    const dfName = document
                        .querySelector('input[name="dataflow_name"]')
                        .value.trim();
                    const connType =
                        document.getElementById('addConnType').value;
                    if (!dfName) {
                        showToast('Dataflow name is required', 'err');
                        return;
                    }
                    if (!connType) {
                        showToast('Please select a source type', 'err');
                        return;
                    }
                }
                return setStep(Math.min(4, currentStep + 1));
            }
            if (target.id === 'prevStep')
                return setStep(Math.max(1, currentStep - 1));

            // Review card "Edit" pencil buttons — jump back to a step
            const rvEditBtn = target.closest('.rv-edit-btn');
            if (rvEditBtn) {
                const gotoStep = parseInt(rvEditBtn.dataset.gotoStep, 10);
                if (gotoStep >= 1 && gotoStep <= 4) setStep(gotoStep);
                return;
            }

            // Native form submit (no DForm dependency)
            if (target.id === 'saveDataflow') {
                const userActionInp = document.getElementById('userAction');
                const isEdit = document
                    .getElementById('addTitle')
                    .textContent.includes('Edit');
                const userAction = isEdit ? 'edit' : 'add';
                if (userActionInp) {
                    userActionInp.value = userAction;
                }

                const mainForm = document.getElementById('create_new_dataflow');
                if (mainForm) {
                    // Basic HTML5 validation
                    const invalidEl = mainForm.querySelector(':invalid');
                    if (invalidEl) {
                        const stepPane = invalidEl.closest('.step-pane, [data-step]');
                        if (stepPane && stepPane.dataset && stepPane.dataset.step) {
                            setStep(parseInt(stepPane.dataset.step, 10));
                        }
                        setTimeout(() => {
                            if (typeof invalidEl.reportValidity === 'function') {
                                invalidEl.reportValidity();
                            }
                            if (typeof invalidEl.focus === 'function') {
                                invalidEl.focus();
                            }
                        }, 50);
                        return;
                    }

                    // Re-enable everything momentarily to ensure FormData captures disabled fields
                    const editableFields = [
                        'dataflow_name',
                        'description',
                        'remote_path[]',
                        'file_name[]',
                        'role[]',
                        'start_date',
                        'start_time',
                        'time_zone',
                        'periodicity',
                        'dataflow_status',
                    ];
                    mainForm
                        .querySelectorAll(
                            'input:not([type=hidden]), select, textarea',
                        )
                        .forEach((el) => (el.disabled = false));

                    // Gather the form data into a JSON object
                    const formData = new FormData(mainForm);

                    // Re-disable if in edit mode so UI remains consistent
                    if (userAction === 'edit') {
                        mainForm
                            .querySelectorAll(
                                'input:not([type=hidden]), select, textarea',
                            )
                            .forEach((el) => {
                                if (
                                    el.name &&
                                    !editableFields.includes(el.name)
                                )
                                    el.disabled = true;
                            });
                        // Re-lock CirclesList if it was prefilled (locked in edit mode)
                        const circlesSelectLock =
                            document.getElementById('addCirclesList');
                        if (
                            circlesSelectLock &&
                            circlesSelectLock.dataset.prefill
                        ) {
                            circlesSelectLock.disabled = true;
                            const wrapEl = circlesSelectLock.nextElementSibling;
                            if (wrapEl && wrapEl.syncDisabledVisual)
                                wrapEl.syncDisabledVisual();
                        }
                    }
                    const jsonPayload = {};

                    // Standard fields
                    jsonPayload.dataflow_name = formData.get('dataflow_name');
                    jsonPayload.dataflow_status =
                        formData.get('dataflow_status') || 'Enable';
                    jsonPayload.app_name = formData.get('app_name') || '';
                    jsonPayload.service_name = formData.get('service_name');
                    jsonPayload.dataflow_type =
                        formData.get('dataflow_type') ||
                        document.getElementById('addDataFlowType')?.value ||
                        '';
                    jsonPayload.ingestion =
                        formData.get('ingestion') ||
                        document.getElementById('addIngestion')?.value ||
                        '';
                    jsonPayload.conn_type =
                        formData.get('conn_type') ||
                        document.getElementById('addConnType')?.value ||
                        '';
                    if (jsonPayload.conn_type === 'FTP,SFTP') {
                        jsonPayload.conn_type = 'FTP';
                    }
                    jsonPayload.start_date = formData.get('start_date');
                    jsonPayload.start_time = formData.get('start_time');
                    jsonPayload.time_zone = formData.get('time_zone');
                    jsonPayload.periodicity = formData.get('periodicity');

                    // Connection-specific fields based on conn_type
                    const connType = jsonPayload.conn_type;
                    if (connType === 'FTP' || connType === 'SFTP') {
                        jsonPayload.url = formData.get('url');
                        jsonPayload.user_name = formData.get('user_name');
                        jsonPayload.password = formData.get('password');
                    } else if (connType === 'S3') {
                        jsonPayload.BucketName = formData.get('BucketName');
                        jsonPayload.AwsAccessKeyId =
                            formData.get('AwsAccessKeyId');
                        jsonPayload.AwsSecretAccessKey =
                            formData.get('AwsSecretAccessKey');
                    } else if (connType === 'WEB_SCRAP') {
                        jsonPayload.depth = formData.get('depth');
                    } else if (connType === 'Fin_Data') {
                        jsonPayload.sourceType = formData.get('sourceType');
                        jsonPayload.ApiKey = formData.get('ApiKey');
                        jsonPayload.SecretKey = formData.get('SecretKey');
                        jsonPayload.startDate = formData.get('startDate');
                        jsonPayload.endDate = formData.get('endDate');
                        jsonPayload.interval = formData.get('interval');
                        jsonPayload.description = formData.get('description');

                        const symbolsSelect = mainForm.querySelector(
                            'select[name="symbolsList"]',
                        );
                        if (symbolsSelect) {
                            jsonPayload.symbolsList = Array.from(
                                symbolsSelect.selectedOptions,
                            ).map((opt) => opt.value);
                        } else {
                            jsonPayload.symbolsList = [];
                        }
                    } else if (connType === 'churnData') {
                        // Read directly from DOM element so it works even when the field is disabled
                        const circlesEl =
                            document.getElementById('addCirclesList');
                        jsonPayload.CirclesList = circlesEl
                            ? Array.from(circlesEl.selectedOptions).map(
                                (opt) => opt.value,
                            )
                            : [];
                    }

                    // File config (dynamic rows)
                    const fileConfig = [];
                    const fileRows = mainForm.querySelectorAll(
                        '#fileConfigRows .file-row',
                    );
                    fileRows.forEach((row) => {
                        const remotePathVal = row.querySelector(
                            'input[name="remote_path[]"]',
                        ).value;
                        const fileNameVal = row.querySelector(
                            'input[name="file_name[]"]',
                        ).value;
                        const roleSelect = row.querySelector(
                            'select[name="role[]"]',
                        );
                        const roleVals = roleSelect
                            ? Array.from(roleSelect.selectedOptions).map(
                                (opt) => opt.value,
                            )
                            : [];
                        fileConfig.push({
                            remote_path: remotePathVal,
                            file_name: fileNameVal,
                            role: roleVals,
                        });
                    });
                    jsonPayload.file_config = fileConfig;

                    // Set json_data hidden field value
                    const jsonDataInp = document.getElementById('json_data');
                    const serializedPayload = JSON.stringify(jsonPayload);
                    if (jsonDataInp) {
                        jsonDataInp.value = serializedPayload;
                    }

                    const originalSaveHtml = target.innerHTML;
                    const loaderText =
                        userAction === 'edit' ? 'Saving...' : 'Creating...';
                    target.innerHTML = `<svg class="spin-loader" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="height:1em; margin-right:6px; vertical-align:-0.125em;"><circle cx="12" cy="12" r="10" stroke-opacity="0.25"/><path d="M12 2A10 10 0 0 1 22 12" stroke-linecap="round"/></svg>${loaderText}`;
                    target.disabled = true;

                    if (typeof window.sendRequest === 'function') {
                        window
                            .sendRequest(
                                {
                                    'user-action': userAction,
                                    request_info: jsonPayload,
                                },
                                {
                                    reloadOnSuccess: false,
                                    showAlert: false,
                                    errorMessage: 'Unable to save dataflow.',
                                },
                            )
                            .then(function (resp) {
                                target.innerHTML = originalSaveHtml;
                                target.disabled = false;
                                if (!resp || !resp.success) {
                                    showToast(
                                        (resp && resp.message) ||
                                            'Unable to save dataflow.',
                                        'err',
                                    );
                                    return;
                                }
                                showToast(
                                    (resp && resp.message) || 'Dataflow saved.',
                                    'ok',
                                );
                                closeDrawer('add');

                                // Mock the UI update for SPA feel, delayed slightly for smooth drawer closing
                                setTimeout(() => {
                                    const tbody =
                                        document.getElementById(
                                            'dataflowsTbody',
                                        );
                                    const grid =
                                        document.getElementById(
                                            'dataflowsGrid',
                                        );

                                    if (userAction === 'edit') {
                                        // ── Patch the in-memory dataflow_info entry ──────────────────────
                                        // Determine which dataflow was being edited via the hidden dataflow_id input
                                        const dfIdInput =
                                            mainForm.querySelector(
                                                '[name="dataflow_id"]',
                                            ) ||
                                            mainForm.querySelector(
                                                '[name="id"]',
                                            );
                                        // Fallback: use the id that was active when Edit was opened
                                        const editedId =
                                            (dfIdInput && dfIdInput.value) ||
                                            (activeDataflow &&
                                                activeDataflow.id);

                                        if (editedId && window.dataflow_info) {
                                            const idx =
                                                window.dataflow_info.findIndex(
                                                    (d) =>
                                                        d.dataflow_id ===
                                                        editedId,
                                                );
                                            if (idx !== -1) {
                                                // Merge all submitted fields into the cached object
                                                Object.assign(
                                                    window.dataflow_info[idx],
                                                    {
                                                        dataflow_name:
                                                            jsonPayload.dataflow_name ||
                                                            window
                                                                .dataflow_info[
                                                                    idx
                                                                ].dataflow_name,
                                                        dataflow_status:
                                                            jsonPayload.dataflow_status ||
                                                            window
                                                                .dataflow_info[
                                                                    idx
                                                                ].dataflow_status,
                                                        periodicity:
                                                            jsonPayload.periodicity ||
                                                            window
                                                                .dataflow_info[
                                                                    idx
                                                                ].periodicity,
                                                        start_time:
                                                            jsonPayload.start_time ||
                                                            window
                                                                .dataflow_info[
                                                                    idx
                                                                ].start_time,
                                                        start_date:
                                                            jsonPayload.start_date ||
                                                            window
                                                                .dataflow_info[
                                                                    idx
                                                                ].start_date,
                                                        time_zone:
                                                            jsonPayload.time_zone ||
                                                            window
                                                                .dataflow_info[
                                                                    idx
                                                                ].time_zone,
                                                        description:
                                                            jsonPayload.description !==
                                                            undefined
                                                                ? jsonPayload.description
                                                                : window
                                                                    .dataflow_info[
                                                                        idx
                                                                    ].description,
                                                        CirclesList:
                                                            jsonPayload.CirclesList !==
                                                            undefined
                                                                ? jsonPayload.CirclesList
                                                                : window
                                                                    .dataflow_info[
                                                                        idx
                                                                    ].CirclesList,
                                                        file_config:
                                                            jsonPayload.file_config ||
                                                            window
                                                                .dataflow_info[
                                                                    idx
                                                                ].file_config,
                                                    },
                                                );
                                            }

                                            // ── Update the card DOM data attributes ──────────────────────
                                            const cardEl =
                                                document.querySelector(
                                                    `.df-card[data-id="${editedId}"]`,
                                                );
                                            const rowEl =
                                                document.querySelector(
                                                    `tr[data-id="${editedId}"]`,
                                                );
                                            const newStatusVal = (
                                                jsonPayload.dataflow_status ||
                                                (window.dataflow_info[idx]
                                                    ? window.dataflow_info[idx]
                                                        .dataflow_status
                                                    : 'enable')
                                            ).toLowerCase();
                                            const newStatusText =
                                                newStatusVal === 'disable'
                                                    ? 'Disabled'
                                                    : 'Active';
                                            const newStatusClass =
                                                newStatusVal === 'disable'
                                                    ? 'pill-muted'
                                                    : 'pill-ok';

                                            if (cardEl) {
                                                if (jsonPayload.dataflow_name) {
                                                    cardEl.dataset.name =
                                                        jsonPayload.dataflow_name;
                                                    const nameEl =
                                                        cardEl.querySelector(
                                                            '.df-name',
                                                        );
                                                    if (nameEl)
                                                        nameEl.textContent =
                                                            jsonPayload.dataflow_name;
                                                }
                                                cardEl.dataset.status =
                                                    newStatusVal;
                                                const cardPill =
                                                    cardEl.querySelector(
                                                        '.pill-mini, .pill',
                                                    );
                                                if (cardPill) {
                                                    cardPill.textContent =
                                                        newStatusText;
                                                    cardPill.classList.remove(
                                                        'pill-ok',
                                                        'pill-err',
                                                        'pill-muted',
                                                    );
                                                    cardPill.classList.add(
                                                        newStatusClass,
                                                    );
                                                }
                                            }

                                            if (rowEl) {
                                                if (jsonPayload.dataflow_name) {
                                                    rowEl.dataset.name =
                                                        jsonPayload.dataflow_name;
                                                    const rowNameEl =
                                                        rowEl.querySelector(
                                                            '.primary',
                                                        );
                                                    if (rowNameEl)
                                                        rowNameEl.textContent =
                                                            jsonPayload.dataflow_name;
                                                }
                                                rowEl.dataset.status =
                                                    newStatusVal;
                                                const rowPill =
                                                    rowEl.querySelector(
                                                        '.pill-mini, .pill',
                                                    );
                                                if (rowPill) {
                                                    rowPill.textContent =
                                                        newStatusText;
                                                    rowPill.classList.remove(
                                                        'pill-ok',
                                                        'pill-err',
                                                        'pill-muted',
                                                    );
                                                    rowPill.classList.add(
                                                        newStatusClass,
                                                    );
                                                }
                                            }

                                            // Update schedule text on the card if visible
                                            if (
                                                cardEl &&
                                                jsonPayload.periodicity
                                            ) {
                                                const schedEls =
                                                    cardEl.querySelectorAll(
                                                        '.df-stat .v',
                                                    );
                                                schedEls.forEach((el) => {
                                                    const label =
                                                        el.previousElementSibling;
                                                    if (
                                                        label &&
                                                        label.textContent
                                                            .trim()
                                                            .toLowerCase() ===
                                                            'schedule'
                                                    ) {
                                                        el.textContent =
                                                            jsonPayload.periodicity;
                                                    }
                                                });
                                                // Also update the df-id line if it shows schedule
                                                const dfIdEl =
                                                    cardEl.querySelector(
                                                        '.df-id',
                                                    );
                                                if (
                                                    dfIdEl &&
                                                    dfIdEl.textContent.includes(
                                                        '·',
                                                    )
                                                ) {
                                                    const parts =
                                                        dfIdEl.textContent.split(
                                                            '·',
                                                        );
                                                    dfIdEl.textContent =
                                                        parts[0].trim() +
                                                        ' · ' +
                                                        jsonPayload.periodicity;
                                                }
                                            }

                                            // Also update activeDataflow ref so further interactions use fresh name
                                            if (
                                                activeDataflow &&
                                                activeDataflow.id ===
                                                    editedId &&
                                                jsonPayload.dataflow_name
                                            ) {
                                                activeDataflow.name =
                                                    jsonPayload.dataflow_name;
                                            }
                                        }
                                    } else if (userAction === 'add') {
                                        // Use the real ID returned from the backend if available, fallback to dummy
                                        const tempId =
                                            resp.dataflow_id ||
                                            'df_' +
                                                Math.floor(
                                                    Math.random() * 100000,
                                                );

                                        // Push the newly created object to window.dataflow_info so the Overview panel can dynamically load it!
                                        window.dataflow_info.push(
                                            Object.assign({}, jsonPayload, {
                                                dataflow_id: tempId,
                                                start_date: new Date()
                                                    .toISOString()
                                                    .split('T')[0], // mock today's date
                                            }),
                                        );
                                        const statusVal = (
                                            jsonPayload.dataflow_status ||
                                            'enable'
                                        ).toLowerCase();
                                        const scheduleText =
                                            jsonPayload.periodicity || 'DAILY';
                                        const statusText =
                                            statusVal === 'disable'
                                                ? 'Disabled'
                                                : 'Active';
                                        const statusClass =
                                            statusVal === 'disable'
                                                ? 'pill-muted'
                                                : 'pill-ok';

                                        if (tbody) {
                                            const tr =
                                                document.createElement('tr');
                                            tr.dataset.id = tempId;
                                            tr.dataset.name =
                                                jsonPayload.dataflow_name;
                                            tr.dataset.status = statusVal;

                                            tr.innerHTML = `
                                        <td>
                                          <div class="primary">${jsonPayload.dataflow_name}</div>
                                          <div class="id">${tempId} · ${scheduleText}</div>
                                        </td>
                                        <td>
                                          <div class="flow-ico">
                                            <span class="src">${jsonPayload.conn_type || 'Unknown'}</span><span class="arr">→</span><span class="dst">${jsonPayload.dataflow_type || 'Unknown'}</span>
                                          </div>
                                        </td>
                                        <td>Never run</td>
                                        <td>
                                          <span class="pill pill-ok">Active</span>
                                        </td>
                                        <td class="right num">-</td>
                                        <td>
                                          <div class="spark">
                                            <div class="b ok" style="height:100%"></div>
                                          </div>
                                        </td>
                                        <td class="row-actions-cell">
                                          <div class="row-acts">
                                            <div class="quick">
                                              <button class="btn btn-ghost btn-sm action-btn" data-act="logs">Logs</button>
                                            </div>
                                          </div>
                                        </td>
                                    `;
                                            tbody.appendChild(tr);

                                            const emptyRow =
                                                tbody.querySelector('.empty');
                                            if (emptyRow)
                                                emptyRow.closest('tr').remove();
                                        }

                                        if (grid) {
                                            const article =
                                                document.createElement(
                                                    'article',
                                                );
                                            article.className = 'df-card';
                                            article.dataset.status = statusVal;
                                            article.dataset.id = tempId;
                                            article.dataset.name =
                                                jsonPayload.dataflow_name;
                                            article.dataset.srcType =
                                                jsonPayload.conn_type || '';
                                            article.dataset.flowtype =
                                                jsonPayload.dataflow_type || '';

                                            article.innerHTML = `
                                        <div class="df-top">
                                          <div class="df-title">
                                            <div class="df-name">${jsonPayload.dataflow_name}</div>
                                          </div>
                                          <div class="df-status-area df-status-area--inline">
                                            <span class="pill-mini ${statusClass}">${statusText}</span>
                                            <span class="df-type-tag df-type-tag--auto" data-dftype="${jsonPayload.dataflow_type || ''}">${jsonPayload.dataflow_type || 'Unknown'}</span>
                                          </div>
                                        </div>
                                        <div class="df-flow">
                                          <div class="ep"><span class="ep-label">Source</span>${jsonPayload.conn_type || 'Unknown'}</div>
                                          <span class="arr">→</span>
                                          <div class="ep"><span class="ep-label">Target</span>${jsonPayload.dataflow_type || 'Unknown'}</div>
                                        </div>
                                        <div class="df-stats">
                                          <div class="df-stat">
                                            <div class="l">Last run</div>
                                            <div class="v">Never run</div>
                                          </div>
                                          <div class="df-stat">
                                            <div class="l">Records</div>
                                            <div class="v mono">-</div>
                                          </div>
                                          <div class="df-stat">
                                            <div class="l">Schedule</div>
                                            <div class="v">${scheduleText}</div>
                                          </div>
                                        </div>
                                        <div class="df-foot">
                                          <div class="spark">
                                          </div>
                                        </div>
                                    `;
                                            window.colorTypeTags(article);
                                            grid.appendChild(article);

                                            const emptyCard =
                                                grid.querySelector('.empty');
                                            if (emptyCard) emptyCard.remove();
                                        }
                                    }
                                    if (
                                        typeof window.refreshDashboards ===
                                        'function'
                                    )
                                        window.refreshDashboards();
                                    updateDataflowCounts();
                                }, 300);
                            });
                        return;
                    }

                    mainForm.submit();
                }
                return;
            }
            if (
                target.id === 'newBtn' ||
                (target.closest('.btn-primary') &&
                    target.textContent.includes('New dataflow'))
            ) {
                openAddDrawer('new');
                return;
            }

            const stepHead = target.closest('.stepper .step');
            if (stepHead) {
                const targetStep = parseInt(stepHead.dataset.step, 10);
                if (targetStep > currentStep) {
                    if (currentStep === 1) {
                        const dfName = document
                            .querySelector('input[name="dataflow_name"]')
                            .value.trim();
                        const connType =
                            document.getElementById('addConnType').value;
                        if (!dfName) {
                            showToast('Dataflow name is required', 'err');
                            return;
                        }
                        if (!connType) {
                            showToast('Please select a source type', 'err');
                            return;
                        }
                    }
                    // Prevent skipping steps completely
                    if (targetStep > currentStep + 1) return;
                }
                return setStep(targetStep);
            }

            if (target.id === 'detailEditBtn') {
                if (!activeDataflow) return;
                closeDrawer('detail');
                setTimeout(() => openAddDrawer('edit', activeDataflow), 200);
            }
            if (target.id === 'detailDeleteBtn') {
                if (!activeDataflow) return;
                closeDrawer('detail');
                setTimeout(() => openDeleteDialog(activeDataflow), 200);
            }
            if (target.id === 'detailRunBtn') {
                if (!activeDataflow) return;
                closeDrawer('detail');
                setTimeout(() => openRerunDialog(activeDataflow), 200);
            }

            // ── Sub-type-card click (inside service sub-picker) ──
            const subTypeCard = target.closest('.sub-type-card');
            if (subTypeCard) {
                const subPicker = subTypeCard.closest('.service-sub-picker');
                if (subPicker) {
                    subPicker
                        .querySelectorAll('.sub-type-card')
                        .forEach((x) => x.classList.remove('selected'));
                    subTypeCard.classList.add('selected');

                    const val = subTypeCard.dataset.src || '';
                    const addConnType = document.getElementById('addConnType');
                    if (addConnType) addConnType.value = val;

                    // Show matching conn-fields panel
                    document
                        .querySelectorAll('.conn-fields.panel')
                        .forEach((f) => {
                            const connList = (f.dataset.conn || '').split(',');
                            f.style.display = connList.includes(val)
                                ? 'block'
                                : 'none';
                        });
                }
                return;
            }

            // ── Regular type-card click (including parent Service Based card) ──
            const typeCard = target.closest('.type-card');
            if (typeCard) {
                const grp = typeCard.closest('.type-picker');
                if (grp) {
                    grp.querySelectorAll('.type-card').forEach((x) =>
                        x.classList.remove('selected'),
                    );
                    typeCard.classList.add('selected');

                    const subPicker =
                        document.getElementById('serviceSubPicker');
                    const isServiceBased =
                        typeCard.dataset.src === 'service_based';

                    if (grp.id === 'srcTypePicker') {
                        if (isServiceBased) {
                            // Show sub-picker, don't set conn_type yet, hide all conn panels
                            if (subPicker) subPicker.style.display = '';
                            const addConnType =
                                document.getElementById('addConnType');
                            if (addConnType) addConnType.value = '';
                            document
                                .querySelectorAll('.conn-fields.panel')
                                .forEach((f) => {
                                    f.style.display = 'none';
                                });
                        } else {
                            // Regular card: hide sub-picker, reset sub-selections
                            if (subPicker) {
                                subPicker.style.display = 'none';
                                subPicker
                                    .querySelectorAll('.sub-type-card')
                                    .forEach((x) =>
                                        x.classList.remove('selected'),
                                    );
                            }

                            const val = typeCard.dataset.src || '';
                            const addConnType =
                                document.getElementById('addConnType');
                            if (addConnType) {
                                addConnType.value = val;
                            }

                            document
                                .querySelectorAll('.conn-fields.panel')
                                .forEach((f) => {
                                    const connList = (
                                        f.dataset.conn || ''
                                    ).split(',');
                                    const valList = val.split(',');
                                    const match = valList.some((v) =>
                                        connList.includes(v),
                                    );
                                    if (match && val !== '') {
                                        f.style.display = 'block';
                                    } else {
                                        f.style.display = 'none';
                                    }
                                });
                        }
                    }
                }
                return;
            }
            const preset = target.closest('.preset-row .preset');
            if (preset) {
                const pr = preset.closest('.preset-row');
                if (pr) {
                    pr.querySelectorAll('.preset').forEach((x) =>
                        x.classList.remove('selected'),
                    );
                    preset.classList.add('selected');
                }
                return;
            }
            const logLvl = target.closest('.log-level-pick button');
            if (logLvl) {
                const p = logLvl.parentNode;
                if (p) {
                    p.querySelectorAll('button').forEach((x) =>
                        x.classList.remove('active'),
                    );
                    logLvl.classList.add('active');
                    const lvl = logLvl.textContent.trim();
                    document
                        .querySelectorAll('#logStream .log-line')
                        .forEach((l) => {
                            if (lvl === 'ALL') {
                                l.style.display = '';
                                return;
                            }
                            const haslvl = l.querySelector('.lvl.' + lvl);
                            l.style.display = haslvl ? '' : 'none';
                        });
                }
                return;
            }

            if (target.id === 'delConfirmBtn') {
                if (!deleteTarget) return;

                const currentTarget = deleteTarget; // CACHE IT!
                showToast(`Deleting dataflow "${currentTarget.name}"...`);

                //const originalHtml = target.innerHTML;
                target.innerHTML =
                    '<svg class="spin-loader" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="height:1em; margin-right:6px; vertical-align:-0.125em;"><circle cx="12" cy="12" r="10" stroke-opacity="0.25"/><path d="M12 2A10 10 0 0 1 22 12" stroke-linecap="round"/></svg>Deleting...';
                target.disabled = true;

                const payload = {
                    'user-action': 'delete',
                    dataflow_id: currentTarget.id,
                };
                if (typeof window.sendRequest === 'function') {
                    window
                        .sendRequest(payload, {
                            reloadOnSuccess: false,
                            showAlert: false,
                        })
                        .then(function (resp) {
                            closeDialog();
                            if (!resp || !resp.success) {
                                showToast(
                                    (resp && resp.message) ||
                                        'Unable to delete dataflow.',
                                    'err',
                                );
                                return;
                            }
                            showToast(
                                (resp && resp.message) || 'Dataflow deleted.',
                                'ok',
                            );

                            // Remove from global array so bulletin board heatmap & anomalies don't show it
                            if (window.dataflow_info) {
                                const dfIdx = window.dataflow_info.findIndex(
                                    (d) => d.dataflow_id === currentTarget.id,
                                );
                                if (dfIdx !== -1)
                                    window.dataflow_info.splice(dfIdx, 1);
                            }

                            const rowEl =
                                currentTarget.el ||
                                document.querySelector(
                                    `tr[data-id="${currentTarget.id}"]`,
                                );
                            const cardEl = document.querySelector(
                                `.df-card[data-id="${currentTarget.id}"]`,
                            );

                            if (rowEl) {
                                rowEl.style.transition =
                                    'opacity 0.3s ease, transform 0.3s ease';
                                rowEl.style.opacity = '0';
                                rowEl.style.transform = 'scale(0.95)';
                                setTimeout(() => rowEl.remove(), 300);
                            }

                            if (cardEl) {
                                cardEl.style.transition =
                                    'opacity 0.3s ease, transform 0.3s ease';
                                cardEl.style.opacity = '0';
                                cardEl.style.transform = 'scale(0.95)';
                                setTimeout(() => cardEl.remove(), 300);
                            }

                            if (
                                activeDataflow &&
                                activeDataflow.id === currentTarget.id
                            ) {
                                closeDrawer('detail');
                            }

                            setTimeout(() => {
                                if (
                                    typeof window.refreshDashboards ===
                                    'function'
                                )
                                    window.refreshDashboards();
                                updateDataflowCounts();
                            }, 350);
                        });
                }
            }

            if (target.id === 'rerunConfirmBtn') {
                if (!window.rerunTarget) return;

                const currentTarget = window.rerunTarget;
                const dInp = document.getElementById('rerunDateInput');
                if (!dInp || !dInp.value) {
                    showToast('Please select a date for rerun.', 'err');
                    return;
                }
                const selectedDate = dInp.value;

                showToast(`Starting dataflow "${currentTarget.name}"...`, 'ok');

                const originalHtml = target.innerHTML;
                target.innerHTML =
                    '<svg class="spin-loader" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="height:1em; margin-right:6px; vertical-align:-0.125em;"><circle cx="12" cy="12" r="10" stroke-opacity="0.25"/><path d="M12 2A10 10 0 0 1 22 12" stroke-linecap="round"/></svg>Running...';
                target.disabled = true;

                const rowEl =
                    currentTarget.el ||
                    document.querySelector(`tr[data-id="${currentTarget.id}"]`);
                const cardEl = document.querySelector(
                    `.df-card[data-id="${currentTarget.id}"]`,
                );

                // Mark both the row pill and the card pill as Running
                const statusPill = rowEl
                    ? rowEl.querySelector('.pill, .pill-mini')
                    : null;
                const cardPill = cardEl
                    ? cardEl.querySelector('.pill, .pill-mini')
                    : null;
                let oldPillClass = '';
                if (statusPill) {
                    oldPillClass = statusPill.className;
                    statusPill.className = 'pill pill-info';
                    statusPill.textContent = 'Running';
                }
                if (cardPill) {
                    cardPill.className =
                        cardPill.className
                            .replace(/pill-(ok|err|muted|warn)/g, '')
                            .trim() + ' pill-info';
                    cardPill.textContent = 'Running';
                }
                // ← This is the key fix: mark data-status so _getRunningCards() finds this card
                if (cardEl) cardEl.dataset.status = 'running';

                if (typeof window.sendRequest === 'function') {
                    window
                        .sendRequest(
                            {
                                'user-action': 'rerun',
                                dataflow_id: currentTarget.id,
                                start_date: selectedDate,
                            },
                            { reloadOnSuccess: false, showAlert: false },
                        )
                        .then(function (resp) {
                            closeDialog('rerun');
                            target.innerHTML = originalHtml;
                            target.disabled = false;

                            if (!resp || !resp.success) {
                                showToast(
                                    (resp && resp.message) ||
                                        'Unable to rerun dataflow.',
                                    'err',
                                );
                                if (statusPill) {
                                    statusPill.className = oldPillClass;
                                    statusPill.textContent =
                                        oldPillClass.includes('ok')
                                            ? 'Active'
                                            : 'Disabled';
                                }
                                return;
                            }
                            showToast(
                                (resp && resp.message) || 'Rerun requested.',
                                'ok',
                            );
                        });
                }
                return;
            }

            // Range button selector for heatmap
            const rangeBtn = target.closest('#heatmapRangePick button');
            if (rangeBtn) {
                document
                    .querySelectorAll('#heatmapRangePick button')
                    .forEach((b) => b.classList.remove('active'));
                rangeBtn.classList.add('active');
                const days = parseInt(rangeBtn.dataset.range, 10);
                if (window.lastSummaryData) {
                    renderHeatmap(
                        window.lastSummaryData,
                        days,
                        window.lastBulletinData,
                    );
                    initHeatmapSearch();
                }
                return;
            }

            // Click a cell → open detail drawer logs
            const cell = target.closest('.heatmap-table td.cell');
            if (cell && cell.dataset.tip) {
                if (
                    cell.classList.contains('skip') ||
                    cell.classList.contains('future')
                )
                    return;
                const name = cell.dataset.tip.split('|')[0];
                const matchingDf = window.dataflow_info.find(
                    (d) => d.dataflow_name === name,
                );
                if (matchingDf) {
                    const fakeRow = {
                        id: matchingDf.dataflow_id,
                        name: matchingDf.dataflow_name,
                        status: cell.classList.contains('fail') ? 'err' : 'ok',
                        el: {
                            querySelector: () => document.createElement('span'),
                        },
                    };
                    openDetail(fakeRow, 'logs');
                    document
                        .getElementById('toggleDataflows')
                        .classList.add('active');
                    document
                        .getElementById('toggleBulletin')
                        .classList.remove('active');
                    const vdf = document.getElementById('view-dataflows');
                    const vb = document.getElementById('view-bulletin');
                    if (vdf) vdf.classList.add('active');
                    if (vb) vb.classList.remove('active');
                    document.body.classList.remove('bulletin-mode');
                }
                return;
            }

            // Click a name in the heatmap → open detail overview
            const heatmapName = target.closest('.heatmap-table .name-cell .nm');
            if (heatmapName) {
                const id = heatmapName.dataset.id;
                const matchingDf = window.dataflow_info.find(
                    (d) => d.dataflow_id === id,
                );
                if (matchingDf) {
                    const fakeRow = {
                        id: matchingDf.dataflow_id,
                        name: matchingDf.dataflow_name,
                        status: 'ok',
                        el: {
                            querySelector: () => document.createElement('span'),
                        },
                    };
                    openDetail(fakeRow, 'overview');
                    document
                        .getElementById('toggleDataflows')
                        .classList.add('active');
                    document
                        .getElementById('toggleBulletin')
                        .classList.remove('active');
                    const vdf = document.getElementById('view-dataflows');
                    const vb = document.getElementById('view-bulletin');
                    if (vdf) vdf.classList.add('active');
                    if (vb) vb.classList.remove('active');
                    document.body.classList.remove('bulletin-mode');
                }
                return;
            }

            // Click an anomaly item → open detail logs
            const anomalyItem = target.closest('.anomaly');
            if (anomalyItem) {
                const id = anomalyItem.dataset.id;
                const matchingDf = window.dataflow_info.find(
                    (d) => d.dataflow_id === id,
                );
                if (matchingDf) {
                    const fakeRow = {
                        id: matchingDf.dataflow_id,
                        name: matchingDf.dataflow_name,
                        status: 'err',
                        el: {
                            querySelector: () => document.createElement('span'),
                        },
                    };
                    openDetail(fakeRow, 'logs');
                    document
                        .getElementById('toggleDataflows')
                        .classList.add('active');
                    document
                        .getElementById('toggleBulletin')
                        .classList.remove('active');
                    const vdf = document.getElementById('view-dataflows');
                    const vb = document.getElementById('view-bulletin');
                    if (vdf) vdf.classList.add('active');
                    if (vb) vb.classList.remove('active');
                    document.body.classList.remove('bulletin-mode');
                }
                return;
            }
        });

        document.body.addEventListener('input', function (e) {
            const target = e.target;
            if (target.id === 'delConfirm') {
                const btn = document.getElementById('delConfirmBtn');
                // Use the visible delNameTarget text as the canonical name to match
                // against, so both listeners agree on what string the user must type.
                const dt = document.getElementById('delNameTarget');
                const canonicalName = dt
                    ? dt.textContent.trim()
                    : deleteTarget
                        ? deleteTarget.name.trim()
                        : '';
                if (btn) btn.disabled = target.value.trim() !== canonicalName;
            }
            if (target.id === 'logFilter') {
                const q = target.value.toLowerCase();
                document
                    .querySelectorAll('#logStream .log-line')
                    .forEach((l) => {
                        l.style.display =
                            !q || l.textContent.toLowerCase().includes(q)
                                ? ''
                                : 'none';
                    });
            }
        });

        document.addEventListener('keydown', function (e) {
            if (e.key === 'Escape') {
                const delBack = document.getElementById('deleteBack');
                const addBack = document.getElementById('addBack');
                const detBack = document.getElementById('detailBack');
                const menu = document.getElementById('rowMenu');

                if (delBack && delBack.classList.contains('open'))
                    return closeDialog();
                if (addBack && addBack.classList.contains('open'))
                    return closeDrawer('add');
                if (detBack && detBack.classList.contains('open'))
                    return closeDrawer('detail');
                if (menu && menu.classList.contains('open'))
                    return menu.classList.remove('open');
            }
        });

        // --- Heatmap & Bulletin board system ---
        window.lastSummaryData = null;

        function formatDateToDMY (d) {
            const day = String(d.getDate()).padStart(2, '0');
            const month = String(d.getMonth() + 1).padStart(2, '0');
            const year = d.getFullYear();
            return `${day}/${month}/${year}`;
        }

        function parseRecordCount (val) {
            if (!val) return 0;
            const s = String(val).trim().toUpperCase();
            if (s === '-' || s === '') return 0;
            const m = s.match(/^(\d+(?:\.\d+)?)\s*([KMB]?)$/);
            if (m) {
                const num = parseFloat(m[1]);
                const unit = m[2];
                if (unit === 'K') return num * 1000;
                if (unit === 'M') return num * 1000000;
                if (unit === 'B') return num * 1000000000;
                return num;
            }
            const parsed = parseFloat(s.replace(/,/g, ''));
            return isNaN(parsed) ? 0 : parsed;
        }

        function formatRecordCount (num) {
            if (num >= 1000000000) return (num / 1000000000).toFixed(1) + 'B';
            if (num >= 1000000) return (num / 1000000).toFixed(1) + 'M';
            if (num >= 1000) return (num / 1000).toFixed(1) + 'K';
            return num.toString();
        }

        function renderTileSparks (containerId, dataArray) {
            const container = document.getElementById(containerId);
            if (!container || !dataArray || dataArray.length === 0) return;
            container.innerHTML = '';
            const maxVal = Math.max(...dataArray) || 1;
            dataArray.forEach((val, i) => {
                const bar = document.createElement('div');
                bar.className = 'b';
                const height = Math.max((val / maxVal) * 100, 5);
                bar.style.height = height + '%';
                if (i === dataArray.length - 1) bar.classList.add('hi');
                container.appendChild(bar);
            });
        }

        function initHeatmapSearch () {
            const searchInput = document.getElementById('heatmapSearch');

            if (!searchInput) {
                console.warn('❌ Heatmap search input not found!');
                return;
            }

            // Remove any existing listeners to prevent duplicates
            const newInput = searchInput.cloneNode(true);
            searchInput.parentNode.replaceChild(newInput, searchInput);

            newInput.addEventListener('input', function () {
                const term = this.value.toLowerCase();
                const tbody = document.getElementById('heatmapBody');

                if (!tbody) {
                    console.warn('❌ Heatmap tbody not found!');
                    return;
                }

                const rows = tbody.querySelectorAll('tr');

                let visibleCount = 0;
                rows.forEach((row, index) => {
                    if (index === 0) return; // Skip the header row

                    const rowText = row.innerText.toLowerCase();
                    const matches = rowText.includes(term);
                    row.style.display = matches ? '' : 'none';

                    if (matches) {
                        visibleCount++;
                    }
                });
            });
        }

        function renderHeatmap (summaryReport, rangeDays, bulletinReport) {
            const dates = [];
            for (let i = rangeDays - 1; i >= 0; i--) {
                const d = new Date();
                d.setDate(d.getDate() - i);
                dates.push(d);
            }

            const label = document.getElementById('heatmapRangeLabel');
            if (label && dates.length > 0) {
                const startStr = dates[0].toLocaleDateString('en-US', {
                    month: 'short',
                    day: '2-digit',
                });
                const endStr = dates[dates.length - 1].toLocaleDateString(
                    'en-US',
                    { month: 'short', day: '2-digit', year: 'numeric' },
                );
                label.textContent = `${window.dataflow_info.length} dataflows · ${startStr} – ${endStr}`;
            }

            const tbody = document.getElementById('heatmapBody');
            if (!tbody) return;
            tbody.innerHTML = '';

            const headRow = document.createElement('tr');
            headRow.innerHTML = '<th class="name-col">Dataflow</th>';

            const daysOfWeek = [
                'Sun',
                'Mon',
                'Tue',
                'Wed',
                'Thu',
                'Fri',
                'Sat',
            ];
            dates.forEach((d) => {
                const isToday =
                    formatDateToDMY(d) === formatDateToDMY(new Date());
                const isWeekend = d.getDay() === 0 || d.getDay() === 6;

                let thClass = 'day';
                if (isToday) thClass += ' today';
                if (isWeekend) thClass += ' weekend';

                const th = document.createElement('th');
                th.className = thClass;
                th.innerHTML = `<span class="dow">${daysOfWeek[d.getDay()]}</span><span class="dom">${String(d.getDate()).padStart(2, '0')}</span>`;
                headRow.appendChild(th);
            });
            tbody.appendChild(headRow);

            window.dataflow_info.forEach((df) => {
                const tr = document.createElement('tr');

                const nameCell = document.createElement('td');
                nameCell.className = 'name-cell';

                const cadLabel =
                    df.periodicity === 'DAILY'
                        ? 'DLY'
                        : df.periodicity === 'WEEKLY'
                            ? 'WKL'
                            : 'ON-DEMAND';
                nameCell.innerHTML = `<span class="nm" data-id="${df.dataflow_id}">${df.dataflow_name}</span><div class="meta"><span class="cad">${cadLabel}</span>${df.dataflow_id}</div>`;
                tr.appendChild(nameCell);

                dates.forEach((d) => {
                    const dateStr = formatDateToDMY(d);

                    const dayData = summaryReport.Summary_info
                        ? summaryReport.Summary_info.find(
                            (s) => s.Date === dateStr,
                        )
                        : null;
                    const status = dayData
                        ? dayData[df.dataflow_name]
                        : 'Not_Runned';

                    const cell = document.createElement('td');
                    cell.className = 'cell';

                    const isToday =
                        formatDateToDMY(d) === formatDateToDMY(new Date());
                    if (isToday) {
                        cell.classList.add('today-col');
                    }

                    if (status === 'Success' || status === 'Failure') {
                        const recs =
                            dayData &&
                            dayData[`${df.dataflow_name}_records`] !== undefined
                                ? dayData[`${df.dataflow_name}_records`]
                                : 0;

                        const volNum = parseRecordCount(
                            recs === '-' ? '0' : String(recs),
                        );
                        let okClass = 'ok-3';
                        if (volNum > 100000000) okClass = 'ok-4';
                        else if (volNum < 100000) okClass = 'ok-1';
                        else if (volNum < 1000000) okClass = 'ok-2';

                        cell.classList.add(okClass);
                        cell.style.position = 'relative';

                        const span = document.createElement('span');
                        // Format with K, M, B for readability
                        const parsedRecs = parseInt(
                            String(recs).replace(/,/g, ''),
                            10,
                        );
                        span.textContent = isNaN(parsedRecs)
                            ? recs
                            : formatRecordCount(parsedRecs);
                        cell.appendChild(span);

                        if (status === 'Failure') {
                            const dot = document.createElement('span');
                            dot.style.position = 'absolute';
                            dot.style.top = '2px';
                            dot.style.right = '2px';
                            dot.style.width = '6px';
                            dot.style.height = '6px';
                            dot.style.backgroundColor = 'var(--err)';
                            dot.style.borderRadius = '50%';
                            cell.appendChild(dot);
                            cell.dataset.tip = `${df.dataflow_name}|${dateStr}|${span.textContent}|Warning: Partial/Failed run`;
                        } else {
                            cell.dataset.tip = `${df.dataflow_name}|${dateStr}|${span.textContent}`;
                        }
                    } else {
                        cell.classList.add('skip');
                        cell.dataset.tip = `${df.dataflow_name}|${dateStr}|Not scheduled this day`;
                    }

                    tr.appendChild(cell);
                });

                tbody.appendChild(tr);
            });
        }

        async function checkDataStatus () {
            if (!activeDataflow) return;

            const dfObj = window.dataflow_info.find(
                (d) => d.dataflow_id === activeDataflow.id,
            );
            if (!dfObj) return;

            const startDate =
                (document.getElementById('statusPaneStartDate') || {}).value ||
                '';
            const endDate =
                (document.getElementById('statusPaneEndDate') || {}).value ||
                '';

            // Extract circle from CirclesList if present (optional for non-telecom flows)
            let circle = '';
            if (dfObj.CirclesList && dfObj.CirclesList.length > 0) {
                circle = Array.isArray(dfObj.CirclesList)
                    ? dfObj.CirclesList[0]
                    : dfObj.CirclesList;
            }

            const dataflowType = (dfObj.dataflow_type || '').trim();

            if (!startDate || !endDate) {
                alert('Please select both Start Date and End Date.');
                return;
            }
            if (startDate > endDate) {
                alert('Start Date must be on or before End Date.');
                return;
            }

            const resultArea = document.getElementById('statusPaneResultArea');
            const loadingState = document.getElementById('statusPaneLoading');

            if (resultArea) resultArea.style.display = 'none';
            if (loadingState) {
                loadingState.style.display = 'block';
                loadingState.textContent = 'Querying ClickHouse cluster…';
            }

            const csrfToken =
                (document.querySelector('[name="csrfmiddlewaretoken"]') || {})
                    .value || '';

            let data = null;
            try {
                const res = await fetch('/PlatformIO/BatchIngress/', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': csrfToken,
                    },
                    body: JSON.stringify({
                        'user-action': 'get_data_status',
                        dataflow_id: activeDataflow.id,
                        circle: circle || '',
                        dataflow_type: dataflowType,
                        start_date: startDate,
                        end_date: endDate,
                    }),
                });
                if (res.ok) {
                    data = await res.json();
                } else {
                    throw new Error(`HTTP ${res.status}`);
                }
            } catch (err) {
                if (loadingState)
                    loadingState.textContent = `Error: ${err.message}`;
                return;
            }

            if (loadingState) loadingState.style.display = 'none';

            if (!data || (data.status && data.status === 'Error')) {
                if (loadingState) {
                    loadingState.style.display = 'block';
                    loadingState.textContent = `Error: ${(data && data.message) || 'Unknown error'}`;
                }
                return;
            }

            const apiDataArr = data.data || [];
            const apiMap = {};
            apiDataArr.forEach(function (item) {
                const d = (
                    item.date ||
                    item.Date ||
                    item['Time Period'] ||
                    item['Time Period/Date'] ||
                    ''
                )
                    .toLowerCase()
                    .trim();
                const c = parseInt(
                    item.count || item.Count || item['Record Count'] || 0,
                    10,
                );
                if (d) apiMap[d] = c;
            });

            // ---------------- Pluggable Calendar Strategy Pattern ----------------
            let calendarStrategyName = (data && data.calendar_strategy) || '';
            if (!calendarStrategyName) {
                if ((dataflowType || '').toLowerCase().includes('monthly') || (data && data.unit === 'monthly')) {
                    calendarStrategyName = 'MonthlyCalendar';
                } else if (
                    (dataflowType || '').toLowerCase().includes('stock') ||
                    (dfObj.app_name || '').toLowerCase().includes('optioncopilot') ||
                    (dfObj.service_name || '').toLowerCase().includes('optioncopilot')
                ) {
                    calendarStrategyName = 'TradingCalendar';
                } else {
                    calendarStrategyName = 'ContinuousCalendar';
                }
            }

            const CalendarStrategies = {
                ContinuousCalendar: {
                    name: 'ContinuousCalendar',
                    isMonthly: false,
                    isOffDay: function (d) { return false; },
                    getOffDayLabel: function (d) { return ''; },
                    unitLabel: 'days',
                    unitLabelCap: 'Days',
                },
                TradingCalendar: {
                    name: 'TradingCalendar',
                    isMonthly: false,
                    isOffDay: function (d) {
                        const day = (d instanceof Date) ? d.getUTCDay() : new Date(d + 'T00:00:00Z').getUTCDay();
                        return day === 0 || day === 6; // Sunday = 0, Saturday = 6
                    },
                    getOffDayLabel: function (d) {
                        const day = (d instanceof Date) ? d.getUTCDay() : new Date(d + 'T00:00:00Z').getUTCDay();
                        return day === 0 ? 'Sunday (Market Closed)' : 'Saturday (Market Closed)';
                    },
                    unitLabel: 'trading days',
                    unitLabelCap: 'Trading Days',
                },
                MonthlyCalendar: {
                    name: 'MonthlyCalendar',
                    isMonthly: true,
                    isOffDay: function (d) { return false; },
                    getOffDayLabel: function (d) { return ''; },
                    unitLabel: 'months',
                    unitLabelCap: 'Months',
                }
            };

            const strategy = CalendarStrategies[calendarStrategyName] || CalendarStrategies.ContinuousCalendar;
            const isMonthly = strategy.isMonthly;
            const isTradingCalendar = strategy.name === 'TradingCalendar';

            const allDates = [];
            const cur = new Date(startDate + 'T00:00:00Z');
            const end = new Date(endDate + 'T00:00:00Z');

            const monthNamesShort = [
                'jan',
                'feb',
                'mar',
                'apr',
                'may',
                'jun',
                'jul',
                'aug',
                'sep',
                'oct',
                'nov',
                'dec',
            ];

            if (isMonthly) {
                let currentMonth = cur.getUTCMonth();
                let currentYear = cur.getUTCFullYear();
                const endMonth = end.getUTCMonth();
                const endYear = end.getUTCFullYear();

                while (
                    currentYear < endYear ||
                    (currentYear === endYear && currentMonth <= endMonth)
                ) {
                    const yy = currentYear.toString().slice(-2);
                    const mmm = monthNamesShort[currentMonth];
                    allDates.push(`${mmm}_${yy}`);

                    currentMonth++;
                    if (currentMonth > 11) {
                        currentMonth = 0;
                        currentYear++;
                    }
                }
            } else {
                while (cur <= end) {
                    allDates.push(cur.toISOString().slice(0, 10));
                    cur.setUTCDate(cur.getUTCDate() + 1);
                }
            }

            // Calculate Metrics based on CalendarStrategy
            const totalUnits = allDates.length;
            const unitLabel = strategy.unitLabel;
            const unitLabelCap = strategy.unitLabelCap;

            let presentUnits = 0;
            let missingUnitsArr = [];
            let offMarketUnits = 0;
            let expectedUnits = totalUnits;

            if (isTradingCalendar) {
                const tradingDays = allDates.filter(function (d) { return !strategy.isOffDay(d); });
                const offMarketDays = allDates.filter(function (d) { return strategy.isOffDay(d); });
                expectedUnits = tradingDays.length;
                offMarketUnits = offMarketDays.length;

                presentUnits = allDates.filter(function (d) {
                    return apiMap[d] !== undefined && apiMap[d] > 0;
                }).length;

                missingUnitsArr = tradingDays.filter(function (d) {
                    return apiMap[d] === undefined || apiMap[d] === 0;
                });
            } else {
                presentUnits = allDates.filter(function (d) {
                    return apiMap[d] !== undefined && apiMap[d] > 0;
                }).length;

                missingUnitsArr = allDates.filter(function (d) {
                    return apiMap[d] === undefined || apiMap[d] === 0;
                });
            }

            const missingUnitsCount = missingUnitsArr.length;

            const summaryBanner = document.getElementById(
                'statusSummaryBanner',
            );
            if (summaryBanner) {
                summaryBanner.style.alignItems = 'center';

                let bannerHtml = `
                    <div style="display:flex; flex-direction:column; gap:2px; padding-right:24px; border-right:1px solid var(--line);">
                        <span style="font-size:10px; text-transform:uppercase; color:var(--ink-3); font-weight:600; letter-spacing:0.5px;">Date Range</span>
                        <span style="font-size:14px; font-weight:700; color:var(--ink-1);">${totalUnits} ${isMonthly ? 'months' : 'days'}</span>
                    </div>
                `;

                if (isTradingCalendar) {
                    bannerHtml += `
                        <div style="display:flex; flex-direction:column; gap:2px; padding-right:24px; border-right:1px solid var(--line);">
                            <span style="font-size:10px; text-transform:uppercase; color:var(--ink-3); font-weight:600; letter-spacing:0.5px;">Expected Trading Days</span>
                            <span style="font-size:14px; font-weight:700; color:var(--ink-1);">${expectedUnits}</span>
                        </div>
                        <div style="display:flex; flex-direction:column; gap:2px; padding-right:24px; border-right:1px solid var(--line);">
                            <span style="font-size:10px; text-transform:uppercase; color:var(--ink-3); font-weight:600; letter-spacing:0.5px;">Ingested Days</span>
                            <span style="font-size:14px; font-weight:700; color:#5fa97e;">${presentUnits}</span>
                        </div>
                        <div style="display:flex; flex-direction:column; gap:2px; padding-right:24px; border-right:1px solid var(--line);">
                            <span style="font-size:10px; text-transform:uppercase; color:var(--ink-3); font-weight:600; letter-spacing:0.5px;">Missing Trading Days</span>
                            <span style="font-size:14px; font-weight:700; color:var(--err, #ef4444);" title="${missingUnitsArr.join(', ')}">${missingUnitsCount}</span>
                        </div>
                        <div style="display:flex; flex-direction:column; gap:2px; padding-right:24px;">
                            <span style="font-size:10px; text-transform:uppercase; color:var(--ink-3); font-weight:600; letter-spacing:0.5px;">Market Closed</span>
                            <span style="font-size:14px; font-weight:700; color:var(--ink-3);">${offMarketUnits} days</span>
                        </div>
                        <div style="margin-left:auto; display:flex; gap:14px; align-items:center; font-size:12px;">
                            <div style="display:flex; align-items:center; gap:6px;">
                                <span style="width:12px; height:12px; background:#5fa97e; border-radius:2px;"></span>
                                <span style="font-weight:500;">Ingested</span>
                            </div>
                            <div style="display:flex; align-items:center; gap:6px;">
                                <span style="width:12px; height:12px; background:var(--err-bg, #fca5a5); border:1px solid var(--err, #ef4444); border-radius:2px;"></span>
                                <span style="font-weight:500;">Missing</span>
                            </div>
                            <div style="display:flex; align-items:center; gap:6px;">
                                <span style="width:12px; height:12px; background:#f3f4f6; border:1px dashed #d1d5db; border-radius:2px;"></span>
                                <span style="font-weight:500; color:var(--ink-3);">Market Closed</span>
                            </div>
                        </div>
                    `;
                } else {
                    bannerHtml += `
                        <div style="display:flex; flex-direction:column; gap:2px; padding-right:24px; border-right:1px solid var(--line);">
                            <span style="font-size:10px; text-transform:uppercase; color:var(--ink-3); font-weight:600; letter-spacing:0.5px;">${unitLabelCap} Present</span>
                            <span style="font-size:14px; font-weight:700; color:#5fa97e;">${presentUnits}</span>
                        </div>
                        <div style="display:flex; flex-direction:column; gap:2px; padding-right:24px; border-right:1px solid var(--line);">
                            <span style="font-size:10px; text-transform:uppercase; color:var(--ink-3); font-weight:600; letter-spacing:0.5px;">Missing Data</span>
                            <span style="font-size:14px; font-weight:700; color:var(--err, #ef4444);" title="${missingUnitsArr.join(', ')}">${missingUnitsCount} ${unitLabel}</span>
                        </div>
                        ${circle ? `
                            <div style="display:flex; flex-direction:column; gap:2px; padding-right:24px;">
                                <span style="font-size:10px; text-transform:uppercase; color:var(--ink-3); font-weight:600; letter-spacing:0.5px;">Circle</span>
                                <span style="font-size:14px; font-weight:700; color:var(--ink-1);">${circle}</span>
                            </div>
                        ` : ''}
                        <div style="margin-left:auto; display:flex; gap:16px; align-items:center;">
                            <div style="display:flex; align-items:center; gap:6px;">
                                <span style="width:12px; height:12px; background:#5fa97e; border-radius:2px;"></span>
                                <span style="font-weight:500;">Data Present</span>
                            </div>
                            <div style="display:flex; align-items:center; gap:6px;">
                                <span style="width:12px; height:12px; background:var(--err-bg, #fca5a5); border:1px solid var(--err, #ef4444); border-radius:2px;"></span>
                                <span style="font-weight:500;">Missing Data</span>
                            </div>
                        </div>
                    `;
                }

                summaryBanner.innerHTML = bannerHtml;
            }

            const maxCount = Math.max(1, ...Object.values(apiMap).map(Number));
            const tbody = document.getElementById('statusCalendarBody');

            if (isMonthly) {
                // Replace the calendar table with a Monthly Grid
                const scrollContainer = tbody
                    ? tbody.closest('.heatmap-scroll')
                    : resultArea.querySelector('.heatmap-scroll');
                if (scrollContainer) {
                    scrollContainer.innerHTML = '';

                    const gridContainer = document.createElement('div');
                    gridContainer.style.display = 'grid';
                    gridContainer.style.gridTemplateColumns =
                        'repeat(auto-fill, minmax(120px, 1fr))';
                    gridContainer.style.gap = '12px';
                    gridContainer.style.padding = '8px 0';

                    allDates.forEach((mKey) => {
                        const count =
                            apiMap[mKey] !== undefined ? apiMap[mKey] : 0;
                        const hasData = apiMap[mKey] !== undefined && apiMap[mKey] > 0;

                        // Parse mmm_yy back to a nice name, e.g., "apr_26" -> "Apr 2026"
                        const [mmm, yy] = mKey.split('_');
                        const monthDisplayName =
                            mmm.charAt(0).toUpperCase() +
                            mmm.slice(1) +
                            ' 20' +
                            yy;

                        const tile = document.createElement('div');
                        tile.title = `${monthDisplayName}: ${count.toLocaleString()} records`;
                        tile.style.borderRadius = '6px';
                        tile.style.display = 'flex';
                        tile.style.flexDirection = 'column';
                        tile.style.alignItems = 'center';
                        tile.style.justifyContent = 'center';
                        tile.style.padding = '16px';
                        tile.style.boxSizing = 'border-box';
                        tile.style.minHeight = '80px';

                        const nameSpan = document.createElement('span');
                        nameSpan.textContent = monthDisplayName;
                        nameSpan.style.fontSize = '12px';
                        nameSpan.style.fontWeight = '600';
                        nameSpan.style.marginBottom = '4px';
                        nameSpan.style.opacity = '0.8';
                        tile.appendChild(nameSpan);

                        const countSpan = document.createElement('span');
                        countSpan.style.fontWeight = '700';
                        countSpan.style.fontSize = '18px';

                        let displayCount = '';
                        if (hasData) {
                            if (count >= 1000000) {
                                displayCount =
                                    (count / 1000000).toFixed(1) + 'M';
                            } else if (count >= 1000) {
                                displayCount = (count / 1000).toFixed(1) + 'K';
                            } else {
                                displayCount = count.toString();
                            }
                        } else {
                            displayCount = '-';
                        }
                        countSpan.textContent = displayCount;
                        tile.appendChild(countSpan);

                        if (!hasData) {
                            tile.style.backgroundColor =
                                'var(--err-bg, #fca5a5)';
                            tile.style.border = '1px solid var(--err, #ef4444)';
                            tile.style.color = 'var(--ink-1, #333)';
                            countSpan.style.color = 'var(--ink-1, #333)';
                        } else {
                            const intensity = 0.4 + 0.6 * (count / maxCount);
                            tile.style.backgroundColor = `rgba(95, 169, 126, ${intensity})`;
                            tile.style.border = '1px solid #5fa97e';
                            tile.style.color = 'var(--ink-1, #1f2937)';
                            countSpan.style.color = '#ffffff';
                            countSpan.style.textShadow =
                                '0 1px 2px rgba(0,0,0,0.35)';
                        }

                        gridContainer.appendChild(tile);
                    });

                    scrollContainer.appendChild(gridContainer);
                }
            } else {
                // Ensure table structure exists if we toggled back from monthly
                const scrollContainer = tbody
                    ? tbody.closest('.heatmap-scroll')
                    : resultArea.querySelector('.heatmap-scroll');
                if (
                    scrollContainer &&
                    !scrollContainer.querySelector('table')
                ) {
                    scrollContainer.innerHTML = `
                       <table class="heatmap-table" style="width:100%; border-collapse:separate; border-spacing:4px; text-align:center; table-layout:fixed;">
                         <thead>
                           <tr>
                             <th style="width:14%; font-size:11px; padding:4px; color:var(--ink-3);">Sun</th>
                             <th style="width:14%; font-size:11px; padding:4px; color:var(--ink-3);">Mon</th>
                             <th style="width:14%; font-size:11px; padding:4px; color:var(--ink-3);">Tue</th>
                             <th style="width:14%; font-size:11px; padding:4px; color:var(--ink-3);">Wed</th>
                             <th style="width:14%; font-size:11px; padding:4px; color:var(--ink-3);">Thu</th>
                             <th style="width:14%; font-size:11px; padding:4px; color:var(--ink-3);">Fri</th>
                             <th style="width:14%; font-size:11px; padding:4px; color:var(--ink-3);">Sat</th>
                           </tr>
                         </thead>
                         <tbody id="statusCalendarBody">
                         </tbody>
                       </table>
                    `;
                }
                const newTbody = document.getElementById('statusCalendarBody');
                if (newTbody) newTbody.innerHTML = '';

                // Group dates by YYYY-MM
                const months = {};
                allDates.forEach((d) => {
                    const monthKey = d.slice(0, 7); // "YYYY-MM"
                    if (!months[monthKey]) months[monthKey] = [];
                    months[monthKey].push(d);
                });

                const monthNames = [
                    'January',
                    'February',
                    'March',
                    'April',
                    'May',
                    'June',
                    'July',
                    'August',
                    'September',
                    'October',
                    'November',
                    'December',
                ];

                Object.keys(months).forEach((monthKey, idx) => {
                    const daysInMonth = months[monthKey];

                    // Add Month Header Row
                    const [year, monthNum] = monthKey.split('-');
                    const monthName = monthNames[parseInt(monthNum, 10) - 1];

                    const headerTr = document.createElement('tr');
                    const headerTd = document.createElement('td');
                    headerTd.colSpan = 7;
                    headerTd.style.textAlign = 'left';
                    headerTd.style.padding = '16px 4px 8px 4px';
                    headerTd.style.fontWeight = 'bold';
                    headerTd.style.fontSize = '14px';
                    headerTd.style.color = 'var(--ink-2, #4b5563)';
                    if (idx > 0) {
                        headerTd.style.borderTop =
                            '1px solid var(--line, #e5e7eb)';
                    }
                    headerTd.textContent = `${monthName} ${year}`;
                    headerTr.appendChild(headerTd);
                    newTbody.appendChild(headerTr);

                    let currentTr = document.createElement('tr');

                    // Pad initial empty days for this month
                    const firstDate = new Date(daysInMonth[0] + 'T00:00:00Z');
                    const firstDayOfWeek = firstDate.getUTCDay();
                    for (let i = 0; i < firstDayOfWeek; i++) {
                        const td = document.createElement('td');
                        currentTr.appendChild(td);
                    }

                    daysInMonth.forEach((d) => {
                        const count = apiMap[d] !== undefined ? apiMap[d] : 0;
                        const hasData = apiMap[d] !== undefined && apiMap[d] > 0;

                        const dateObj = new Date(d + 'T00:00:00Z');
                        const dayOfWeek = dateObj.getUTCDay();
                        const isOffDay = strategy.isOffDay(dateObj);

                        if (dayOfWeek === 0 && currentTr.children.length > 0) {
                            newTbody.appendChild(currentTr);
                            currentTr = document.createElement('tr');
                        }

                        const td = document.createElement('td');

                        const cell = document.createElement('div');
                        cell.style.aspectRatio = '1 / 1';
                        cell.style.width = '100%';
                        cell.style.position = 'relative'; // for absolute date
                        cell.style.borderRadius = '4px';
                        cell.style.display = 'flex';
                        cell.style.flexDirection = 'column';
                        cell.style.alignItems = 'center';
                        cell.style.justifyContent = 'center';
                        cell.style.boxSizing = 'border-box';
                        cell.style.padding = '4px';

                        // The Date Number (Top Left)
                        const dateNum = document.createElement('span');
                        dateNum.textContent = dateObj.getUTCDate();
                        dateNum.style.position = 'absolute';
                        dateNum.style.top = '4px';
                        dateNum.style.left = '6px';
                        dateNum.style.fontSize = '10px';
                        dateNum.style.fontWeight = '500';
                        dateNum.style.opacity = '0.8';
                        cell.appendChild(dateNum);

                        // The Count
                        const countSpan = document.createElement('span');
                        countSpan.style.fontWeight = '600';
                        countSpan.style.fontSize = '13px';

                        let displayCount = '';
                        if (hasData) {
                            if (count >= 1000000) {
                                displayCount =
                                    (count / 1000000).toFixed(1) + 'M';
                            } else if (count >= 1000) {
                                displayCount = (count / 1000).toFixed(1) + 'K';
                            } else {
                                displayCount = count.toString();
                            }
                        } else {
                            displayCount = '-';
                        }
                        countSpan.textContent = displayCount;
                        cell.appendChild(countSpan);

                        if (isOffDay && !hasData) {
                            // Neutral Gray Tile for Market Closed / Weekends
                            cell.title = `${d} (${strategy.getOffDayLabel(dateObj)}): 0 records`;
                            cell.style.backgroundColor = 'var(--bg-subtle, #f3f4f6)';
                            cell.style.border = '1px dashed var(--line, #d1d5db)';
                            cell.style.color = 'var(--ink-3, #9ca3af)';
                            countSpan.style.color = 'var(--ink-3, #9ca3af)';
                        } else if (!hasData) {
                            // Red Tile for Missing Ingestion
                            cell.title = `${d}: Missing Data (0 records)`;
                            cell.style.backgroundColor =
                                'var(--err-bg, #fca5a5)';
                            cell.style.border = '1px solid var(--err, #ef4444)';
                            cell.style.color = 'var(--ink-1, #333)';
                            countSpan.style.color = 'var(--ink-1, #333)';
                        } else {
                            // Green Tile for Ingested Data
                            const intensity = 0.4 + 0.6 * (count / maxCount);
                            cell.title = `${d}: ${count.toLocaleString()} records`;
                            cell.style.backgroundColor = `rgba(95, 169, 126, ${intensity})`; // matches #5fa97e
                            cell.style.border = '1px solid #5fa97e';
                            cell.style.color = 'var(--ink-1, #1f2937)'; // Date color
                            countSpan.style.color = '#ffffff'; // Count color
                            countSpan.style.textShadow =
                                '0 1px 2px rgba(0,0,0,0.35)'; // Keep white text readable on light green
                        }
                        td.appendChild(cell);
                        currentTr.appendChild(td);
                    });

                    // Pad trailing empty days for this month
                    const lastDate = new Date(
                        daysInMonth[daysInMonth.length - 1] + 'T00:00:00Z',
                    );
                    const lastDayOfWeek = lastDate.getUTCDay();
                    for (let i = lastDayOfWeek + 1; i <= 6; i++) {
                        const td = document.createElement('td');
                        currentTr.appendChild(td);
                    }
                    if (currentTr.children.length > 0) {
                        newTbody.appendChild(currentTr);
                    }
                });
            }

            if (resultArea) resultArea.style.display = 'block';
        }

        const checkStatusBtn = document.getElementById('statusPaneCheckBtn');
        if (checkStatusBtn) {
            checkStatusBtn.addEventListener('click', function () {
                checkStatusBtn.disabled = true;
                checkStatusBtn.textContent = 'Checking…';
                checkDataStatus().finally(function () {
                    checkStatusBtn.disabled = false;
                    checkStatusBtn.innerHTML = 'Check Status';
                });
            });
        }

        async function loadBulletinBoard () {
            const csrfTokenInput = document.querySelector(
                '[name="csrfmiddlewaretoken"]',
            );
            const csrfToken = csrfTokenInput ? csrfTokenInput.value : '';

            const heatmapBody = document.getElementById('heatmapBody');
            if (heatmapBody) {
                heatmapBody.innerHTML =
                    '<tr><td colspan="15" style="text-align:center; padding:var(--s-6); color:var(--ink-3); background:var(--bg-card);">Loading bulletin dashboard…</td></tr>';
            }

            const formData = new FormData();
            formData.append('user-action', 'bulletin_board');

            let bulletinData = {};
            try {
                const res = await fetch('/PlatformIO/BatchIngress/', {
                    method: 'POST',
                    headers: { 'X-CSRFToken': csrfToken },
                    body: formData,
                });
                if (res.ok) {
                    bulletinData = await res.json();
                    window.lastBulletinData = bulletinData;
                }
            } catch (e) {

                // Error loading bulletin_board
            }

            const summaryFormData = new FormData();
            summaryFormData.append('user-action', 'dataflow_summary');

            let summaryData = {};
            try {
                const res = await fetch('/PlatformIO/BatchIngress/', {
                    method: 'POST',
                    headers: { 'X-CSRFToken': csrfToken },
                    body: summaryFormData,
                });
                if (res.ok) {
                    summaryData = await res.json();
                    window.lastSummaryData = summaryData;
                }
            } catch (e) {

                // Error loading dataflow_summary
            }

            let totalRecordsToday = 0;
            let runsToday = 0;
            const failedList = [];
            const anomalies = [];

            const uniqueDFs = new Set();
            let runningCount = 0;

            const monthNames = [
                'Jan',
                'Feb',
                'Mar',
                'Apr',
                'May',
                'Jun',
                'Jul',
                'Aug',
                'Sep',
                'Oct',
                'Nov',
                'Dec',
            ];
            const d = new Date();
            const todayPrefix =
                String(d.getDate()).padStart(2, '0') +
                '-' +
                monthNames[d.getMonth()] +
                '-' +
                String(d.getFullYear()).slice(-2);

            Object.values(bulletinData).forEach((log) => {
                const isToday =
                    log.DateTime && log.DateTime.startsWith(todayPrefix);

                if (isToday) {
                    if (log.Status !== 'Started') {
                        runsToday++;
                    }
                    totalRecordsToday += parseRecordCount(log.Total_Records);
                }

                // Track the latest status of each Dataflow
                if (!uniqueDFs.has(log.Dataflow_ID)) {
                    uniqueDFs.add(log.Dataflow_ID);
                    if (log.Status === 'Started') {
                        runningCount++;
                    }
                }

                if (
                    log.Status === 'Failure' ||
                    String(log.Status).toLowerCase().includes('fail') ||
                    (log.Msg && log.Msg.toLowerCase().includes('fail'))
                ) {
                    if (isToday && !failedList.includes(log.Dataflow_Name)) {
                        failedList.push(log.Dataflow_Name);
                    }
                    const alreadyInAnomalies = anomalies.find(
                        (a) => a.name === log.Dataflow_Name && a.type === 'err',
                    );
                    if (!alreadyInAnomalies) {
                        anomalies.push({
                            type: 'err',
                            name: log.Dataflow_Name,
                            id: log.Dataflow_Type || 'df_error',
                            what: `Failed last run — <strong>${log.Msg || 'Unknown write error'}</strong>`,
                            when: 'last 24h',
                        });
                    }
                }
            });

            // Dynamically update the Running Now card
            const runningNowVal = document.querySelector('.s-tile.hl .v');
            if (runningNowVal) {
                runningNowVal.textContent = runningCount;
            }

            const recordsTodayVal = document.getElementById(
                'bulletin-records-today',
            );
            if (recordsTodayVal)
                recordsTodayVal.innerHTML =
                    totalRecordsToday > 0
                        ? formatRecordCount(totalRecordsToday)
                        : '0';

            const runsTodayVal = document.getElementById('bulletin-runs-today');
            if (runsTodayVal)
                runsTodayVal.textContent = `across ${runsToday} runs`;

            const failedTodayVal = document.getElementById(
                'bulletin-failed-today',
            );
            if (failedTodayVal) failedTodayVal.textContent = failedList.length;

            const failedListVal = document.getElementById(
                'bulletin-failed-list',
            );
            if (failedListVal)
                failedListVal.textContent =
                    failedList.length > 0 ? failedList.join(' · ') : 'None';

            const totalRecords14d = window.stats14d
                ? window.stats14d.totalRecords
                : 0;
            const avg14d = window.stats14d ? window.stats14d.avgPerDay : 0;

            const records14dVal = document.getElementById(
                'bulletin-records-14d',
            );
            if (records14dVal)
                records14dVal.innerHTML =
                    totalRecords14d > 0
                        ? formatRecordCount(totalRecords14d)
                        : '0';

            const trend14dVal = document.getElementById('bulletin-trend-14d');
            if (trend14dVal) {
                const avgStr = formatRecordCount(avg14d);
                trend14dVal.innerHTML = `avg ${avgStr}/day`;
            }

            const runNames = new Set(
                Object.values(bulletinData).map((l) => l.Dataflow_Name),
            );
            window.dataflow_info.forEach((df) => {
                if (
                    df.periodicity === 'DAILY' &&
                    !runNames.has(df.dataflow_name)
                ) {
                    anomalies.push({
                        type: 'late',
                        name: df.dataflow_name,
                        id: df.dataflow_id,
                        what: '<strong>Late</strong> — expected to run today, but no successful run recorded',
                        when: 'overdue',
                    });
                }
            });

            // Hardcoded "Volume dropped" mockup removed

            const trueAnomalies = anomalies.filter((an) => an.type !== 'err');
            const anomalyCountVal = document.getElementById(
                'bulletin-anomalies-count',
            );
            const anomalyListVal = document.getElementById(
                'bulletin-anomalies-list',
            );

            if (anomalyCountVal) {
                anomalyCountVal.textContent = trueAnomalies.length;
            }
            if (anomalyListVal) {
                anomalyListVal.textContent =
                    trueAnomalies.length > 0
                        ? trueAnomalies.map((a) => a.name).join(' · ')
                        : 'No anomalies detected';
            }

            const anomaliesList = document.getElementById('anomaliesList');
            const badge = document.getElementById('anomalies-count-badge');

            if (anomaliesList) {
                anomaliesList.innerHTML = '';
                if (anomalies.length === 0) {
                    anomaliesList.innerHTML = `
            <div class="anomaly" style="cursor: default; display: flex; align-items: center; justify-content: center; padding: var(--s-5);">
              <div style="color: var(--ink-4); font-size: 13px;">✓ All systems operational. No items requiring attention.</div>
            </div>`;
                    if (badge) badge.textContent = '0 items';
                } else {
                    if (badge) badge.textContent = `${anomalies.length} items`;

                    anomalies.forEach((an) => {
                        const div = document.createElement('div');
                        div.className = 'anomaly';
                        div.dataset.id = an.id;
                        div.dataset.name = an.name;

                        const icClass = an.type;
                        let svg = '';
                        if (an.type === 'err') {
                            svg =
                                '<svg class="ic" viewBox="0 0 24 24"><path d="M18 6L6 18M6 6l12 12"/></svg>';
                        } else if (an.type === 'late') {
                            svg =
                                '<svg class="ic" viewBox="0 0 24 24"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>';
                        } else {
                            svg =
                                '<svg class="ic" viewBox="0 0 24 24"><polyline points="23 6 13.5 15.5 8.5 10.5 1 18"/><polyline points="17 6 23 6 23 12"/></svg>';
                        }

                        div.innerHTML = `
              <div class="ic-wrap ${icClass}">${svg}</div>
              <div>
                <div class="name">${an.name} <span class="id">${an.id}</span></div>
              </div>
              <div class="what">${an.what}</div>
              <div class="when">${an.when}</div>
            `;
                        anomaliesList.appendChild(div);
                    });
                }
            }

            // Dynamically calculate spark data for Today
            const todayRunsDesc = Object.values(bulletinData).map((log) =>
                parseRecordCount(log.Total_Records),
            );
            let todaySparkData = todayRunsDesc.slice(0, 14).reverse();
            if (todaySparkData.length < 14) {
                todaySparkData = [
                    ...new Array(14 - todaySparkData.length).fill(0),
                    ...todaySparkData,
                ];
            }
            renderTileSparks('bulletin-spark-today', todaySparkData);

            const stats14dData =
                window.stats14d && window.stats14d.dailyRecords
                    ? window.stats14d.dailyRecords
                    : new Array(14).fill(0);
            renderTileSparks('bulletin-spark-14d', stats14dData);

            const activeRangeBtn = document.querySelector(
                '#heatmapRangePick button.active',
            );
            const activeRange = activeRangeBtn
                ? parseInt(activeRangeBtn.dataset.range, 10)
                : 14;
            console.log(
                `📅 Status pane check: rendering heatmap with ${activeRange} days`,
            );
            renderHeatmap(summaryData, activeRange, bulletinData);
            initHeatmapSearch();
        }

        // Shared Heatmap Tooltip
        const tip = document.createElement('div');
        tip.className = 'heatmap-tooltip';
        document.body.appendChild(tip);

        function buildTip (cell) {
            const raw = cell.dataset.tip || '';
            const parts = raw.split('|');
            if (parts.length < 3) return raw;
            const [name, date, vol, ...extra] = parts;
            let body = `<div class="t-name">${name}</div><div class="t-date">${date}</div>`;
            if (vol === 'FAILED') {
                body +=
                    '<div class="t-vol" style="color:#ffb3a3;">Run failed</div>';
            } else if (vol === 'Not scheduled this day') {
                body +=
                    '<div style="margin-top:6px; opacity:0.7;">Not scheduled</div>';
            } else {
                const m = vol.match(/^(\d+(?:\.\d+)?)([KMB]?)$/);
                if (m) {
                    body += `<div class="t-vol">${m[1]}<span class="unit">${m[2]} records</span></div>`;
                } else {
                    body += `<div class="t-vol">${vol}</div>`;
                }
                if (extra.length) {
                    const e = extra.join(' ');
                    const cls =
                        e.includes('-') && e.includes('%')
                            ? e.includes('+')
                                ? 'good'
                                : 'bad'
                            : '';
                    body += `<div class="t-delta ${cls}">${e}</div>`;
                }
            }
            return body;
        }

        document.addEventListener('mouseover', (e) => {
            const cell = e.target.closest('.heatmap-table td.cell');
            if (!cell || !cell.dataset.tip) return;
            tip.innerHTML = buildTip(cell);
            tip.classList.add('show');
            const r = cell.getBoundingClientRect();
            const tr = tip.getBoundingClientRect();
            let left = r.left + r.width / 2 - tr.width / 2;
            let top = r.top - tr.height - 8;
            if (top < 8) {
                top = r.bottom + 8;
            }
            left = Math.max(
                8,
                Math.min(left, window.innerWidth - tr.width - 8),
            );
            tip.style.left = left + 'px';
            tip.style.top = top + 'px';
        });
        document.addEventListener('mouseout', (e) => {
            if (e.target.closest('.heatmap-table td.cell'))
                tip.classList.remove('show');
        });

        // Initialize any static custom multi-selects present in HTML (e.g. initial File Role)
        document
            .querySelectorAll('select[multiple]')
            .forEach((sel) => initCustomMultiSelect(sel));

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

            //let selectedCluster = null;

            if (!window.cluster_info) return;

            // Sync hidden inputs for dataflow type / ingestion
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
                if (!window.cluster_info) return;
                Object.values(window.cluster_info).forEach((c) => {
                    const btn = document.createElement('button');
                    btn.className = 'dd-opt';
                    btn.dataset.val = c.cluster_name;

                    const nodeInfo = c.node_info || {};
                    const nodeCount = Object.keys(nodeInfo).length;

                    btn.innerHTML = `${c.cluster_name} <span class="dd-opt-meta">${nodeCount} nodes</span>`;

                    btn.onclick = (e) => {
                        if (e) e.preventDefault();
                        //selectedCluster = c;
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
                        summary.style.display = 'flex';

                        checkServiceSupport(s);

                        const connTypeInput =
                            document.querySelector('[name="conn_type"]') ||
                            document.getElementById('addConnType');
                        const connType = connTypeInput
                            ? connTypeInput.value
                            : '';
                        if (
                            connType === 'Fin_Data' ||
                            connType === 'churnData'
                        ) {
                            fetchConnTypeConfig(connType, s.service_name);
                        }
                    };
                    svcOpts.appendChild(btn);
                });
            }

            async function fetchConnTypeConfig (connType, serviceName) {
                const csrfToken =
                    document.querySelector('[name="csrfmiddlewaretoken"]')
                        ?.value || '';
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
                                    if (sourceSelect.dataset.prefill) {
                                        sourceSelect.value =
                                            sourceSelect.dataset.prefill;
                                        delete sourceSelect.dataset.prefill;
                                    }
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
                                    if (symbolsSelect.dataset.prefill) {
                                        try {
                                            const prefilledSymbols = JSON.parse(
                                                symbolsSelect.dataset.prefill,
                                            );
                                            Array.from(
                                                symbolsSelect.options,
                                            ).forEach((opt) => {
                                                opt.selected =
                                                    prefilledSymbols.includes(
                                                        opt.value,
                                                    );
                                            });
                                        } catch (e) {}
                                        delete symbolsSelect.dataset.prefill;
                                    }
                                    setTimeout(() => {
                                        if (window.initCustomMultiSelect)
                                            initCustomMultiSelect(
                                                symbolsSelect,
                                            );
                                    }, 0);
                                }
                            } else if (connType === 'churnData') {
                                const circles_list = config.circles_list || [];
                                const circlesSelect =
                                    document.getElementById('addCirclesList');
                                if (circlesSelect) {
                                    circlesSelect.innerHTML = '';
                                    circles_list.forEach((c) => {
                                        const opt =
                                            document.createElement('option');
                                        opt.value = c;
                                        opt.textContent = c;
                                        circlesSelect.appendChild(opt);
                                    });

                                    // If in edit mode, apply prefill values (JSON array) and lock
                                    const prefillVal =
                                        circlesSelect.dataset.prefill;
                                    if (prefillVal) {
                                        let prefilledCircles = [];
                                        try {
                                            prefilledCircles =
                                                JSON.parse(prefillVal);
                                        } catch (e) {
                                            prefilledCircles = [prefillVal];
                                        }
                                        prefilledCircles.forEach((c) => {
                                            const exists = Array.from(
                                                circlesSelect.options,
                                            ).some((o) => o.value === c);
                                            if (!exists) {
                                                const opt =
                                                    document.createElement(
                                                        'option',
                                                    );
                                                opt.value = c;
                                                opt.textContent = c;
                                                circlesSelect.appendChild(opt);
                                            }
                                        });
                                        Array.from(
                                            circlesSelect.options,
                                        ).forEach((opt) => {
                                            opt.selected =
                                                prefilledCircles.includes(
                                                    opt.value,
                                                );
                                        });
                                        delete circlesSelect.dataset.prefill;
                                        circlesSelect.disabled = true;
                                    }

                                    setTimeout(() => {
                                        initCustomMultiSelect(circlesSelect);
                                        circlesSelect.dispatchEvent(
                                            new Event('change'),
                                        );
                                        const wrapEl =
                                            circlesSelect.nextElementSibling;
                                        if (wrapEl && wrapEl.syncDisabledVisual)
                                            wrapEl.syncDisabledVisual();
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
                    console.error('Failed to fetch connection config:', e);
                }
            }

            function checkServiceSupport (serviceData) {
                let supportedTypes = null;
                const sType = serviceData.service_type;
                if (
                    window.dataflowConfig &&
                    sType &&
                    window.dataflowConfig[sType]
                ) {
                    supportedTypes = window.dataflowConfig[sType];
                }

                const dftGrid = document.getElementById('dftGrid');

                const connTypeInput =
                    document.querySelector('[name="conn_type"]') ||
                    document.getElementById('addConnType');
                const connType = connTypeInput ? connTypeInput.value : '';

                if (!supportedTypes || supportedTypes.length === 0) {
                    if (connType !== 'Fin_Data' && connType !== 'churnData') {
                        errMsg.style.display = 'block';
                    } else {
                        errMsg.style.display = 'none';
                    }
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
                        // ── 1. Readable display name: split camelCase into spaced words ──
                        let displayName = type
                            .replace(/_/g, ' ')
                            .replace(/([a-z])([A-Z])/g, '$1 $2')
                            .replace(/([A-Z]+)([A-Z][a-z])/g, '$1 $2')
                            .trim();
                        displayName =
                            displayName.charAt(0).toUpperCase() +
                            displayName.slice(1);

                        // ── 2. Category tag: extract meaningful prefix ──
                        const categoryMap = {
                            CDR: {
                                label: 'CDR',
                                color: '#4f46e5',
                                bg: '#eef2ff',
                            },
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
                            NEP: {
                                label: 'NEP',
                                color: '#059669',
                                bg: '#ecfdf5',
                            },
                            MNP: {
                                label: 'MNP',
                                color: '#d97706',
                                bg: '#fffbeb',
                            },
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
                        };

                        const typeUpper = type
                            .toUpperCase()
                            .replace(/[_\s]/g, '');
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

                        // ── 3. Icon: unique per category ──
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
                        };

                        let iconSvg =
                            '<svg class="ic" viewBox="0 0 24 24" style="width:18px;height:18px;"><path d="M21 16V8a2 2 0 00-1-1.73l-7-4a2 2 0 00-2 0l-7 4A2 2 0 003 8v8a2 2 0 001 1.73l7 4a2 2 0 002 0l7-4A2 2 0 0021 16z"/></svg>';
                        for (const [key, val] of Object.entries(iconMap)) {
                            if (typeUpper.startsWith(key)) {
                                iconSvg = val;
                                break;
                            }
                        }

                        // ── 4. Description ──
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
                        };

                        dftGrid.appendChild(card);
                    });
                }

                // pre-select if available in hidden input
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
                // Initialize clean slate
                buildClusters();

                let targetCluster =
                    appName && appName !== 'None' ? appName : null;
                let targetNode = null;

                if (serviceName && window.cluster_info) {
                    for (const c of Object.values(window.cluster_info)) {
                        if (c.node_info) {
                            for (const n of Object.values(c.node_info)) {
                                if (n.service_info) {
                                    for (const s of Object.values(
                                        n.service_info,
                                    )) {
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
                    //selectedCluster = null;
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

            // initial build
            buildClusters();
        };

        // Logs view logic
        let allLogsData = {};

        async function loadAllLogs () {
            const logStream = document.getElementById('globalLogStream');
            const metaInfo = document.getElementById('globalLogMeta');
            if (logStream)
                logStream.innerHTML =
                    '<div class="log-line"><span class="msg" style="color:var(--ink-4);">Loading logs…</span></div>';

            const csrfTokenInput = document.querySelector(
                '[name="csrfmiddlewaretoken"]',
            );
            const csrfToken = csrfTokenInput ? csrfTokenInput.value : '';

            const formData = new FormData();
            formData.append('user-action', 'bulletin_board');

            try {
                const res = await fetch('/PlatformIO/BatchIngress/', {
                    method: 'POST',
                    headers: { 'X-CSRFToken': csrfToken },
                    body: formData,
                });
                if (res.ok) {
                    allLogsData = await res.json();
                    renderGlobalLogs();
                    if (metaInfo) {
                        const total = Object.keys(allLogsData).length;
                        metaInfo.textContent = `Showing all recent logs (${total} total)`;
                    }
                } else {
                    if (logStream)
                        logStream.innerHTML =
                            '<div class="log-line"><span class="msg" style="color:var(--err);">Failed to fetch logs</span></div>';
                }
            } catch (e) {
                if (logStream)
                    logStream.innerHTML = `<div class="log-line"><span class="msg" style="color:var(--err);">Error: ${e.message}</span></div>`;
            }
        }

        function renderGlobalLogs () {
            const logStream = document.getElementById('globalLogStream');
            if (!logStream) return;

            const dfFilter = document.getElementById('globalLogDfFilter')
                ? document.getElementById('globalLogDfFilter').value
                : '';
            const lvlFilterBtn = document.querySelector(
                '#globalLogLevelPick button.active',
            );
            const lvlFilter = lvlFilterBtn ? lvlFilterBtn.dataset.lvl : 'ALL';
            const searchFilter = document.getElementById('globalLogFilter')
                ? document.getElementById('globalLogFilter').value.toLowerCase()
                : '';

            logStream.innerHTML = '';

            const logsArray = Object.keys(allLogsData).map(
                (k) => allLogsData[k],
            );

            let count = 0;
            let rowsHtml = '';

            logsArray.forEach((log) => {
                const status = (log.Status || 'INFO').toUpperCase();
                const statusClass =
                    status === 'SUCCESS' ||
                    status === 'OK' ||
                    status.includes('✅')
                        ? 'OK'
                        : status.includes('FAIL') ||
                            status.includes('❌') ||
                            status === 'ERR'
                            ? 'ERR'
                            : status === 'WARN'
                                ? 'WARN'
                                : status;

                // Filters
                if (lvlFilter !== 'ALL') {
                    if (lvlFilter === 'ERR' && statusClass !== 'ERR') return;
                    if (lvlFilter === 'OK' && statusClass !== 'OK') return;
                    if (
                        lvlFilter !== 'ERR' &&
                        lvlFilter !== 'OK' &&
                        statusClass !== lvlFilter
                    )
                        return;
                }

                if (
                    dfFilter &&
                    log.Dataflow_ID !== dfFilter &&
                    log.Dataflow_Name !== dfFilter
                )
                    return;

                const msgText = log.Msg || '';

                if (searchFilter) {
                    const searchable = (
                        msgText +
                        ' ' +
                        (log.Dataflow_Name || '') +
                        ' ' +
                        (log.log_id || '')
                    ).toLowerCase();
                    if (!searchable.includes(searchFilter)) return;
                }

                count++;

                const timeStr =
                    log.DateTime ||
                    `${log.Time || ''} ${log.Date || ''}`.trim() ||
                    '-';
                const dfName = log.Dataflow_Name || log.Dataflow_ID || 'System';

                let pillClass = 'pill-muted';
                if (statusClass === 'OK') pillClass = 'pill-ok';
                else if (statusClass === 'ERR') pillClass = 'pill-err';
                else if (statusClass === 'WARN') pillClass = 'pill-warn';
                else if (statusClass === 'INFO') pillClass = 'pill-live';

                const statusLabel =
                    statusClass === 'OK'
                        ? 'Success'
                        : statusClass === 'ERR'
                            ? 'Error'
                            : statusClass === 'WARN'
                                ? 'Warning'
                                : statusClass === 'INFO'
                                    ? 'Info'
                                    : statusClass;

                rowsHtml += `
                    <tr>
                        <td class="gl-time">${timeStr}</td>
                        <td class="gl-df">
                            <div>${dfName}</div>
                        </td>
                        <td class="gl-status">
                            <span class="pill-mini ${pillClass}">${statusLabel}</span>
                        </td>
                        <td class="gl-msg">${msgText}</td>
                    </tr>
                `;
            });

            if (count === 0) {
                logStream.innerHTML =
                    '<div style="padding:var(--s-6); text-align:center; color:var(--ink-4); font-size:13px;">No logs match the current filters.</div>';
            } else {
                logStream.innerHTML = `
                    <table class="global-logs-table">
                        <thead>
                            <tr>
                                <th style="width:160px">Timestamp</th>
                                <th style="width:250px">Dataflow</th>
                                <th style="width:120px">Level</th>
                                <th>Message</th>
                            </tr>
                        </thead>
                        <tbody>
                            ${rowsHtml}
                        </tbody>
                    </table>
                `;
            }
        }

        // Wire up filters
        const dfSelect = document.getElementById('globalLogDfFilter');
        if (dfSelect) {
            dfSelect.addEventListener('change', renderGlobalLogs);
        }

        const searchInput = document.getElementById('globalLogFilter');
        if (searchInput) {
            searchInput.addEventListener('input', () => {
                // debounce
                clearTimeout(searchInput.timeout);
                searchInput.timeout = setTimeout(renderGlobalLogs, 300);
            });
        }

        const refreshBtn = document.getElementById('globalLogRefresh');
        if (refreshBtn) {
            refreshBtn.addEventListener('click', loadAllLogs);
        }

        const lvlBtns = document.querySelectorAll('#globalLogLevelPick button');
        lvlBtns.forEach((btn) => {
            btn.addEventListener('click', () => {
                lvlBtns.forEach((b) => b.classList.remove('active'));
                btn.classList.add('active');
                renderGlobalLogs();
            });
        });

        window.initScheduleUI = function () {
            const scheduleBtns = document.querySelectorAll(
                '#scheduleBtns .dd-opt',
            );
            const periodicityInput =
                document.getElementById('periodicityInput');

            const defaultVal = periodicityInput
                ? periodicityInput.value || 'DAILY'
                : 'DAILY';

            function selectSchedule (val) {
                scheduleBtns.forEach((btn) => btn.classList.remove('selected'));
                const targetBtn = document.querySelector(
                    `#scheduleBtns .dd-opt[data-val="${val}"]`,
                );
                if (targetBtn) {
                    targetBtn.classList.add('selected');
                }
                if (periodicityInput) periodicityInput.value = val;
            }

            scheduleBtns.forEach((btn) => {
                btn.addEventListener('click', (e) => {
                    e.preventDefault();
                    selectSchedule(btn.dataset.val);
                });
            });

            if (scheduleBtns.length > 0) {
                selectSchedule(defaultVal);
            }

            // Always set smart defaults if we're in "add" mode (no pre-existing value)
            const schedDate = document.getElementById('schedDate');
            const schedTime = document.getElementById('schedTime');
            const tzSelect =
                document.getElementById('schedTz') ||
                document.querySelector(
                    '#scheduleTimeFields select[name="time_zone"]',
                );

            // Always set smart defaults for date/time/timezone
            if (schedDate && !schedDate.dataset.prefilled) {
                const today = new Date();
                const yyyy = today.getFullYear();
                const mm = String(today.getMonth() + 1).padStart(2, '0');
                const dd = String(today.getDate()).padStart(2, '0');
                schedDate.value = `${yyyy}-${mm}-${dd}`;
            }
            if (schedTime && !schedTime.dataset.prefilled) {
                schedTime.value = '02:00';
            }
            if (tzSelect && !tzSelect.dataset.prefilled) {
                tzSelect.value = 'Asia/Kolkata';
            }
        };

        window.initScheduleUI();
        window.initDrilldown();

        // ----------------------------------------------------
        // Dataflow Filtering and Refresh Logic
        // ----------------------------------------------------
        const dfSearchInput = document.getElementById('dfSearchInput');
        const activeFiltersContainer = document.getElementById(
            'activeFiltersContainer',
        );
        const addFilterBtn = document.getElementById('addFilterBtn');
        const filterDropdownMenu =
            document.getElementById('filterDropdownMenu');
        const grid = document.getElementById('dataflowsGrid');
        const dfTabsContainer = document.getElementById('dfTabsContainer');

        let activeTab = 'all';
        const activeFilters = []; // Array of {type: 'status', val: 'failed', label: 'Status: Failed'}

        function renderActiveFilters () {
            if (!activeFiltersContainer) return;
            activeFiltersContainer.innerHTML = '';
            activeFilters.forEach((f, idx) => {
                const chip = document.createElement('div');
                chip.className = 'chip active';
                chip.innerHTML = `<span class="chip-text">${f.label}</span> <span class="x" data-idx="${idx}">×</span>`;
                activeFiltersContainer.appendChild(chip);
            });

            // Bind remove clicks
            activeFiltersContainer.querySelectorAll('.x').forEach((btn) => {
                btn.addEventListener('click', function (e) {
                    e.stopPropagation();
                    const i = parseInt(this.dataset.idx, 10);
                    activeFilters.splice(i, 1);
                    renderActiveFilters();
                    filterDataflows();
                });
            });
        }

        function filterDataflows () {
            if (!grid) return;
            const query = dfSearchInput
                ? dfSearchInput.value.toLowerCase()
                : '';
            const cards = grid.querySelectorAll('.df-card');
            let anyVisible = false;

            cards.forEach((card) => {
                const name = (card.dataset.name || '').toLowerCase();
                const status = (card.dataset.status || '').toLowerCase();
                const flowType = (card.dataset.flowtype || '').toLowerCase();

                // 1. Check Search
                let matchesSearch = true;
                if (
                    query &&
                    !name.includes(query) &&
                    !flowType.includes(query)
                ) {
                    matchesSearch = false;
                }

                // 2. Check Tab Filter
                let matchesTab = true;
                if (activeTab === 'active' && status === 'disable')
                    matchesTab = false;
                if (activeTab === 'disabled' && status !== 'disable')
                    matchesTab = false;
                if (activeTab === 'daily' && !name.includes('daily'))
                    matchesTab = false;
                if (activeTab === 'monthly' && !name.includes('monthly'))
                    matchesTab = false;

                // 3. Check Active Filters (Chips)
                let matchesFilters = true;
                activeFilters.forEach((f) => {
                    if (f.type === 'status') {
                        const isFailed =
                            status !== 'enable' && status !== 'active';
                        if (f.val === 'failed' && !isFailed)
                            matchesFilters = false;
                        if (f.val === 'active' && isFailed)
                            matchesFilters = false;
                    }
                });

                if (matchesSearch && matchesTab && matchesFilters) {
                    card.style.display = '';
                    anyVisible = true;
                } else {
                    card.style.display = 'none';
                }
            });

            let emptyMsg = grid.querySelector('.empty-filtered-msg');
            if (!anyVisible && cards.length > 0) {
                if (!emptyMsg) {
                    emptyMsg = document.createElement('div');
                    emptyMsg.className = 'empty empty-filtered-msg';
                    emptyMsg.style.gridColumn = '1 / -1';
                    emptyMsg.textContent = 'No dataflows match your filters.';
                    grid.appendChild(emptyMsg);
                }
                emptyMsg.style.display = '';
            } else if (emptyMsg) {
                emptyMsg.style.display = 'none';
            }
        }

        if (dfSearchInput) {
            dfSearchInput.addEventListener('input', filterDataflows);
        }

        // Dropdown toggle logic
        if (addFilterBtn && filterDropdownMenu) {
            addFilterBtn.addEventListener('click', function (e) {
                e.stopPropagation();
                filterDropdownMenu.style.display =
                    filterDropdownMenu.style.display === 'none'
                        ? 'block'
                        : 'none';
            });

            // Handle option clicks
            filterDropdownMenu
                .querySelectorAll('.filter-option')
                .forEach((opt) => {
                    opt.addEventListener('click', function (e) {
                        e.stopPropagation();
                        const type = this.dataset.filterType;
                        const val = this.dataset.filterVal;
                        const label = this.textContent;

                        // Add if not exists
                        if (
                            !activeFilters.find(
                                (f) => f.type === type && f.val === val,
                            )
                        ) {
                            activeFilters.push({ type, val, label });
                            renderActiveFilters();
                            filterDataflows();
                        }
                        filterDropdownMenu.style.display = 'none';
                    });
                });

            // Close dropdown when clicking outside
            document.addEventListener('click', function (e) {
                if (!addFilterBtn.contains(e.target)) {
                    filterDropdownMenu.style.display = 'none';
                }
            });
        }

        // Tabs Logic
        if (dfTabsContainer) {
            const tabs = dfTabsContainer.querySelectorAll('.tab');
            tabs.forEach((tab) => {
                tab.addEventListener('click', function () {
                    tabs.forEach((t) => t.classList.remove('active'));
                    this.classList.add('active');
                    activeTab = this.dataset.filter || 'all';
                    filterDataflows();
                });
            });
        }

        // Initial run
        renderActiveFilters();
        filterDataflows();

        // ----------------------------------------------------
        // "Updated now" Timer Logic
        // ----------------------------------------------------
        const updatedText = document.getElementById('updatedTimeText');
        if (updatedText) {
            const lastRefreshTime = Date.now();

            setInterval(() => {
                const diffMs = Date.now() - lastRefreshTime;
                const diffMins = Math.floor(diffMs / 60000);
                if (diffMins === 0) {
                    updatedText.innerHTML =
                        'Updated <strong style="color:var(--ink-2);">now</strong>';
                } else {
                    updatedText.innerHTML = `Updated <strong style="color:var(--ink-2);">${diffMins}m ago</strong>`;
                }
            }, 10000);

            // Adaptive poll: 15s when any card is Running, otherwise 60s

            // ── Helper: format + write Last Run date/time and Records on a card ─────────
            function _updateCardStats (card, log) {
                if (!log || !log.date) return;
                card.querySelectorAll('.df-stat').forEach((stat) => {
                    const label = stat.querySelector('.l');
                    const val = stat.querySelector('.v');
                    if (!label || !val) return;
                    const lTxt = label.textContent.trim().toLowerCase();

                    if (lTxt === 'last run') {
                        try {
                            const d = new Date(log.date);
                            const months = [
                                'Jan',
                                'Feb',
                                'Mar',
                                'Apr',
                                'May',
                                'Jun',
                                'Jul',
                                'Aug',
                                'Sep',
                                'Oct',
                                'Nov',
                                'Dec',
                            ];
                            const dd = String(d.getDate()).padStart(2, '0');
                            const mon = months[d.getMonth()];
                            const yr = String(d.getFullYear()).slice(-2);
                            const datePart = `${dd}-${mon}-${yr}`;
                            // Time arrives as "16:56:37" — trim to "16:56"
                            const timePart = log.time
                                ? log.time.substring(0, 5)
                                : '';
                            val.innerHTML = timePart
                                ? `${datePart}<br>${timePart}`
                                : datePart;
                        } catch (e) {

                            val.textContent = log.date;
                        }
                    }

                    if (
                        lTxt === 'records' &&
                        log.records &&
                        log.records !== '-'
                    ) {
                        const num = parseInt(log.records, 10);
                        val.textContent = isNaN(num)
                            ? log.records
                            : num.toLocaleString();
                    }
                });

                // Keep in-memory copy fresh too
                if (window.dataflow_info) {
                    const mem = window.dataflow_info.find(
                        (d) => d.dataflow_id === card.dataset.id,
                    );
                    if (mem) {
                        mem.last_run = log.date;
                        mem.total_records = log.records;
                    }
                }

                // Rebuild spark bars from recent_runs data
                if (log.recent_runs && log.recent_runs.length > 0) {
                    const sparkEl = card.querySelector('.df-foot .spark');
                    if (sparkEl) {
                        sparkEl.innerHTML = log.recent_runs
                            .map(
                                (run) =>
                                    `<div class="b ${run.status}" style="height:${run.height}%"></div>`,
                            )
                            .join('');
                    }
                }
            }

            // ── Helper: update pill + status for Running→resolved transitions ────────────
            function _patchCardFromLog (card, log) {
                const pill = card.querySelector('.pill-mini, .pill');
                if (log.status === 'Success') {
                    if (pill) {
                        pill.textContent = 'Active';
                        pill.className = pill.className
                            .replace(/pill-(info|live|err|muted|warn)/g, '')
                            .trim();
                        if (!pill.className.includes('pill-ok'))
                            pill.classList.add('pill-ok');
                    }
                    card.dataset.status = 'enable';
                    _updateCardStats(card, log);
                } else if (log.status === 'Failure' || log.status === 'Error') {
                    if (pill) {
                        pill.textContent = 'Failed';
                        pill.className = pill.className
                            .replace(/pill-(info|live|ok|muted|warn)/g, '')
                            .trim();
                        if (!pill.className.includes('pill-err'))
                            pill.classList.add('pill-err');
                    }
                    card.dataset.status = 'err';
                    _updateCardStats(card, log);
                }
                // If still 'Started' → leave pill as Running
            }

            async function _pollDataflowStatus () {
                try {
                    const res = await fetch('/PlatformIO/DataflowStatus/');
                    if (!res.ok) return;
                    const data = await res.json();

                    // Update "Running now" tile
                    const runningNowVal =
                        document.querySelector('.s-tile.hl .v');
                    if (runningNowVal) {
                        runningNowVal.textContent =
                            data.running_count !== undefined
                                ? data.running_count
                                : 'NA';
                    }

                    if (!data.dataflow_logs) return;

                    let anyPatched = false;

                    document
                        .querySelectorAll('.df-card[data-id]')
                        .forEach((card) => {
                            const log = data.dataflow_logs[card.dataset.id];
                            if (!log) return;

                            const st = (
                                card.dataset.status || ''
                            ).toLowerCase();

                            if (st === 'running' || st === 'live') {
                                // Running card: full patch including pill update
                                _patchCardFromLog(card, log);
                                anyPatched = true;
                            } else if (st !== 'disable' && st !== 'disabled') {
                                // Active/enabled card: handle transition to Running or just refresh stats
                                if (log.status === 'Started') {
                                    const pill =
                                        card.querySelector('.pill-mini, .pill');
                                    if (pill) {
                                        pill.textContent = 'Running';
                                        pill.className = pill.className
                                            .replace(
                                                /pill-(ok|err|muted|warn)/g,
                                                '',
                                            )
                                            .trim();
                                        if (
                                            !pill.className.includes(
                                                'pill-info',
                                            )
                                        )
                                            pill.classList.add('pill-info');
                                    }
                                    card.dataset.status = 'running';
                                    anyPatched = true;
                                } else if (
                                    log.status === 'Success' ||
                                    log.status === 'Failure'
                                ) {
                                    _patchCardFromLog(card, log);
                                    anyPatched = true;
                                }
                            }
                            // Disabled cards: skip entirely — don't change their pill or data
                        });

                    if (anyPatched) {
                        // Only recalculate in-memory counts — DO NOT call refreshDashboards()
                        // here because it fires loadBulletinBoard() + loadAllLogs() which POST
                        // to BatchIngress (3 expensive requests) on every single poll cycle.
                        // DataflowStatus already gives us everything we need.
                        updateDataflowCounts();
                    }
                } catch (e) {
                    // eslint-disable-next-line no-console
                    console.error('Failed to fetch DataflowStatus:', e);
                } finally {
                    // Reschedule: 60s
                    const interval = 60000;
                    setTimeout(_pollDataflowStatus, interval);
                }
            }

            // Kick off the first poll after 60s
            setTimeout(_pollDataflowStatus, 60000);
        }

        const dfRefreshBtn = document.getElementById('refreshDataflowsBtn');
        if (dfRefreshBtn) {
            dfRefreshBtn.addEventListener('click', function () {
                window.location.reload();
            });
        }

        // ── Dynamic Dashboard Refresh Orchestrator ──────────────────────────
        window.refreshDashboards = function () {
            // Update tab badges based on current DOM elements
            const allCards = document.querySelectorAll(
                '#dataflowsGrid .df-card:not(.empty)',
            );
            let activeCount = 0;
            let failedCount = 0;
            let runningCount = 0;
            let scheduledCount = 0;

            allCards.forEach((card) => {
                const status = (card.dataset.status || '').toLowerCase();
                if (
                    status === 'enable' ||
                    status === 'active' ||
                    status === 'running'
                )
                    activeCount++;
                if (status === 'disable' || status === 'failed') failedCount++;
                if (status === 'running') runningCount++;

                const schedEl = card.querySelector('.df-stat:last-child .v');
                if (
                    schedEl &&
                    schedEl.textContent.trim().toUpperCase() !== 'ON_DEMAND'
                )
                    scheduledCount++;
            });

            // Update the stepper badges
            const allBadge = document.querySelector(
                '.stepper .step[data-step="1"] .badge',
            );
            if (allBadge) allBadge.textContent = allCards.length;

            const activeBadge = document.querySelector(
                '.stepper .step[data-step="2"] .badge',
            );
            if (activeBadge) activeBadge.textContent = activeCount;

            const failedBadge = document.querySelector(
                '.stepper .step[data-step="3"] .badge',
            );
            if (failedBadge) failedBadge.textContent = failedCount;

            const runningBadge = document.querySelector(
                '.stepper .step[data-step="4"] .badge',
            );
            if (runningBadge) runningBadge.textContent = runningCount;

            const scheduledBadge = document.querySelector(
                '.stepper .step[data-step="5"] .badge',
            );
            if (scheduledBadge) scheduledBadge.textContent = scheduledCount;

            // Reload global logs and bulletin board silently in background
            if (typeof loadBulletinBoard === 'function') loadBulletinBoard();
            if (typeof loadAllLogs === 'function') loadAllLogs();
        };

        // ── Color auto-tags on server-rendered cards ──────────────────────────
        const DF_CATEGORY_MAP = {
            CDR: { label: 'CDR', color: '#4f46e5', bg: '#eef2ff' },
            RIBBON: { label: 'RIBBON', color: '#7c3aed', bg: '#f5f3ff' },
            GROUNDHOG: { label: 'GROUNDHOG', color: '#0891b2', bg: '#ecfeff' },
            NEP: { label: 'NEP', color: '#059669', bg: '#ecfdf5' },
            MNP: { label: 'MNP', color: '#d97706', bg: '#fffbeb' },
            CHURN: { label: 'CHURN', color: '#dc2626', bg: '#fef2f2' },
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
            PREPAID: { label: 'PREPAID', color: '#16a34a', bg: '#f0fdf4' },
            POSTPAID: { label: 'POSTPAID', color: '#2563eb', bg: '#eff6ff' },
            RECHARGE: { label: 'RECHARGE', color: '#ea580c', bg: '#fff7ed' },
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
        };

        window.colorTypeTags = function (root) {
            const scope = root || document;
            scope
                .querySelectorAll('.df-type-tag--auto')
                .forEach(function (tag) {
                    const raw = (tag.dataset.dftype || tag.textContent || '')
                        .toUpperCase()
                        .replace(/[_\s]/g, '');
                    let cat = {
                        label: raw || 'STD',
                        color: '#64748b',
                        bg: '#f8fafc',
                    };
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

        // Apply to all cards rendered by the server on first load
        window.colorTypeTags();

        // Fetch bulletin board statistics on initial load so the summary cards are populated
        if (typeof loadBulletinBoard === 'function') {
            loadBulletinBoard();
        }
    });
})();
