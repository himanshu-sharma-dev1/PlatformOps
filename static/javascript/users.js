/* global clearTimeout, setTimeout, navigator, fetch, URLSearchParams, window ,Blob, FormData URL*/
(function () {
    const $ = (s, r) => (r || document).querySelector(s);
    const $$ = (s, r) => Array.from((r || document).querySelectorAll(s));

    // Global selection state (all users across all pages)
    const selectedUserIds = new Set();
    let bulkResendInProgress = false;

    // ─────────────────────────────────────────────────────────────────
    // Export to Excel (CSV download, opens in Excel)
    // ─────────────────────────────────────────────────────────────────
    function exportUsersToExcel () {
        const headers = [
            'Name',
            'Email',
            'Role',
            'Status',
            'Last Login',
            'Activity %',
            'Invited On',
        ];

        const rows = Array.from(document.querySelectorAll('#userTbody tr'))
            .map((tr) => {
                const name =
                    tr.querySelector('.primary')?.textContent.trim() || '';
                const email = tr.querySelector('.id')?.textContent.trim() || '';
                const role =
                    tr.querySelector('.pill')?.textContent.trim() || '';
                const status = tr.dataset.status || '';
                const lastLogin =
                    tr.querySelector('td[data-ts]')?.textContent.trim() || '—';
                const activity =
                    tr.querySelectorAll('td')[5]?.textContent.trim() || '';
                const invitedOn = tr.dataset.createdDate || '—';
                return [
                    name,
                    email,
                    role,
                    status,
                    lastLogin,
                    activity,
                    invitedOn,
                ];
            })
            .filter((r) => r[0]); // skip empty rows

        const csv = [headers, ...rows]
            .map((row) =>
                row
                    .map((cell) => `"${String(cell).replace(/"/g, '""')}"`)
                    .join(','),
            )
            .join('\r\n');

        const BOM = '\uFEFF'; // makes Excel open UTF-8 correctly
        const blob = new Blob([BOM + csv], { type: 'text/csv;charset=utf-8;' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `YantrAI-users-${new Date().toISOString().slice(0, 10)}.csv`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
        showToast('Exported to Excel', 'ok');
    }
    // ─────────────────────────────────────────────────────────────────
    // Helpers
    // ─────────────────────────────────────────────────────────────────
    function showToast (msg, kind) {
        const t = $('#toast');
        $('#toastMsg').textContent = msg;
        t.classList.remove('ok', 'err');
        if (kind) t.classList.add(kind);
        t.classList.add('show');
        clearTimeout(showToast._t);
        showToast._t = setTimeout(() => t.classList.remove('show'), 2400);
    }

    function escapeHtml (s) {
        return s.replace(
            /[&<>"']/g,
            (c) =>
                ({
                    '&': '&amp;',
                    '<': '&lt;',
                    '>': '&gt;',
                    '"': '&quot;',
                    '\'': '&#39;',
                })[c],
        );
    }

    // ─────────────────────────────────────────────────────────────────
    // Expiry bars — fill based on days since invite (pending rows only)
    // ─────────────────────────────────────────────────────────────────
    function updateExpiryBars () {
        $$('#userTbody tr[data-status="pending"]').forEach((tr) => {
            const createdStr = tr.dataset.createdDate; // e.g. "12-Mar-26"
            if (!createdStr) return;

            const created = new Date(createdStr);
            const now = new Date();
            const msPerDay = 1000 * 60 * 60 * 24;
            const daysSince = Math.floor((now - created) / msPerDay);
            const daysLeft = 30 - daysSince;
            const fillPct = Math.min(100, Math.max(0, (daysSince / 30) * 100));

            const fill = tr.querySelector('.expiry-bar .fill');
            const dot = tr.querySelector('.pending-meta .dot');
            const expiryText = tr.querySelector('.expiry-text');

            if (!fill) return;

            fill.style.width = fillPct + '%';

            fill.classList.remove('midway', 'expiring');
            dot.classList.remove('fresh', 'midway', 'expiring');

            if (daysLeft <= 0) {
                fill.classList.add('expiring');
                dot.classList.add('expiring');
                if (expiryText) {
                    expiryText.textContent = `expired ${Math.abs(daysLeft)} days ago`;
                    expiryText.classList.add('expired');
                }
            } else if (daysLeft <= 7) {
                fill.classList.add('expiring');
                dot.classList.add('expiring');
                if (expiryText) {
                    expiryText.textContent = `expires in ${daysLeft} days`;
                    expiryText.classList.add('expiring-soon');
                }
            } else if (daysLeft <= 14) {
                fill.classList.add('midway');
                dot.classList.add('midway');
                if (expiryText)
                    expiryText.textContent = `expires in ${daysLeft} days`;
            } else {
                dot.classList.add('fresh');
                if (expiryText)
                    expiryText.textContent = `expires in ${daysLeft} days`;
            }
        });
    }

    // ─────────────────────────────────────────────────────────────────
    // Pagination
    // ─────────────────────────────────────────────────────────────────
    const PAGE_SIZE = 10;
    let currentPage = 1;
    let currentFilter = 'all';

    function getFilteredRows () {
        return $$('#userTbody tr').filter((tr) => {
            if (tr.dataset.searchHidden === '1') return false;
            const status = tr.dataset.status;
            if (currentFilter === 'active') return status === 'active';
            if (currentFilter === 'pending') return status === 'pending';
            if (currentFilter === 'disabled')
                return status === 'disabled' || status === 'inactive';
            return true;
        });
    }

    function applyPagination () {
        const allRows = $$('#userTbody tr');
        const filteredRows = getFilteredRows();
        const totalRows = filteredRows.length;
        const totalPages = Math.max(1, Math.ceil(totalRows / PAGE_SIZE));

        currentPage = Math.min(currentPage, totalPages);

        const start = (currentPage - 1) * PAGE_SIZE;
        const end = currentPage * PAGE_SIZE;

        allRows.forEach((tr) => (tr.style.display = 'none'));
        filteredRows.forEach((tr, i) => {
            tr.style.display = i >= start && i < end ? '' : 'none';
        });

        $('#pageInfo').textContent = `Page ${currentPage} of ${totalPages}`;
        $('#prevBtn').disabled = currentPage === 1;
        $('#nextBtn').disabled = currentPage === totalPages;

        const totalUsersCount = $$('#userTbody tr').length;
        $('#showingInfo').innerHTML =
            `Showing <strong style="color:var(--ink-2);">${totalRows} of ${totalUsersCount}</strong>`;
    }

    $('#prevBtn').addEventListener('click', () => {
        if (currentPage > 1) {
            currentPage--;
            applyPagination();
        }
    });
    $('#nextBtn').addEventListener('click', () => {
        currentPage++;
        applyPagination();
    });

    // ─────────────────────────────────────────────────────────────────
    // Tab switching
    // ─────────────────────────────────────────────────────────────────
    $$('.tab').forEach((t) => {
        t.onclick = () => {
            $$('.tab').forEach((x) => x.classList.remove('active'));
            t.classList.add('active');
            currentFilter = t.dataset.filter || 'all';
            currentPage = 1;
            applyPagination();
        };
    });

    // ─────────────────────────────────────────────────────────────────
    // Search
    // ─────────────────────────────────────────────────────────────────
    $('.search input').addEventListener('input', (e) => {
        const query = e.target.value.trim().toLowerCase();
        $$('#userTbody tr').forEach((tr) => {
            const name = $('.primary', tr)?.textContent.toLowerCase() || '';
            const email = $('.id', tr)?.textContent.toLowerCase() || '';
            const role =
                tr.querySelector('.pill')?.textContent.toLowerCase() || '';
            tr.dataset.searchHidden =
                query &&
                !name.includes(query) &&
                !email.includes(query) &&
                !role.includes(query)
                    ? '1'
                    : '';
        });
        currentPage = 1;
        applyPagination();
    });

    // ─────────────────────────────────────────────────────────────────
    // Sort by last login
    // ─────────────────────────────────────────────────────────────────
    let sortOrder = 'desc';
    $('#sortLastLogin').addEventListener('click', () => {
        const tbody = $('#userTbody');
        const rows = $$('#userTbody tr');
        rows.sort((a, b) => {
            const tsA = parseFloat(
                a.querySelector('td[data-ts]')?.dataset.ts || 0,
            );
            const tsB = parseFloat(
                b.querySelector('td[data-ts]')?.dataset.ts || 0,
            );
            return sortOrder === 'desc' ? tsB - tsA : tsA - tsB;
        });
        rows.forEach((tr) => tbody.appendChild(tr));
        sortOrder = sortOrder === 'desc' ? 'asc' : 'desc';
        $('#sortIcon').textContent = sortOrder === 'asc' ? '↑' : '↓';
        currentPage = 1;
        applyPagination();
    });

    // ─────────────────────────────────────────────────────────────────
    // Edit drawer
    // ─────────────────────────────────────────────────────────────────
    function openEditDrawer (data) {
        $('#editName').value = data.name || '';
        $('#editEmail').value = data.email || '';
        $('#editPhone').value = data.number || '';
        //$('#editPassword').value = '';
        const roleSelect = $('#editRole');
        Array.from(roleSelect.options).forEach((opt) => {
            opt.selected = opt.value === data.role;
        });
        $('#db').classList.add('open');
        $('#dr').classList.add('open');
        setTimeout(() => $('#editName').focus(), 250);
    }

    function closeEditDrawer () {
        $('#db').classList.remove('open');
        $('#dr').classList.remove('open');
    }

    $('#closeEditBtn').addEventListener('click', closeEditDrawer);
    $('#cancelEditBtn').addEventListener('click', closeEditDrawer);
    $('#db').addEventListener('click', closeEditDrawer);

    // Event delegation so it works after pagination hides/shows rows
    document.addEventListener('click', (e) => {
        const btn = e.target.closest('.btn-edit');
        if (!btn) return;
        openEditDrawer({
            name: btn.dataset.userName,
            email: btn.dataset.userEmail,
            role: btn.dataset.userRole,
            number: btn.dataset.userNumber,
        });
    });

    // ─────────────────────────────────────────────────────────────────
    // Invite drawer
    // ─────────────────────────────────────────────────────────────────
    function openInviteDrawer () {
        $('#invName').value = '';
        $('#invEmail').value = '';
        $('#invPhone').value = '';
        $('#invRole').value = 'Management';
        $$('input[type=checkbox]', $('#inviteDrawer')).forEach(
            (c) => (c.checked = false),
        );
        updatePreview();
        $('#inviteBack').classList.add('open');
        $('#inviteDrawer').classList.add('open');
        setTimeout(() => $('#invName').focus(), 250);
    }

    function closeInviteDrawer () {
        $('#inviteBack').classList.remove('open');
        $('#inviteDrawer').classList.remove('open');
    }

    function updatePreview () {
        $('#prevEmail').textContent = $('#invEmail').value || 'name@iktara.io';
        $('#prevRole').textContent = $('#invRole').value;
    }
    $('#invEmail').addEventListener('input', updatePreview);
    $('#invRole').addEventListener('change', updatePreview);

    $$('.page-head .actions .btn').forEach((b) => {
        const label = b.textContent.trim().toLowerCase();
        if (label.includes('invite'))
            b.addEventListener('click', openInviteDrawer);
        if (label.includes('export'))
            b.addEventListener('click', exportUsersToExcel);
    });

    $('#inviteBack').addEventListener('click', () => closeInviteDrawer());
    $('#closeInviteBtn').addEventListener('click', () => closeInviteDrawer());
    $('#inviteCancelBtn').addEventListener('click', () => closeInviteDrawer());

    // Validation helpers
    function validateEmail (email) {
        return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);
    }
    function emailAlreadyExists (email) {
        return $$('#userTbody tr .id').some((el) =>
            el.textContent.includes(email),
        );
    }

    // Invite form: validate client-side then POST to backend
    $('#inviteForm').addEventListener('submit', (e) => {
        e.preventDefault();
        const name = $('#invName').value.trim();
        const email = $('#invEmail').value.trim();

        if (!name) {
            $('#invName').focus();
            showToast('Name is required', 'err');
            return;
        }
        if (!validateEmail(email)) {
            $('#invEmail').focus();
            showToast('Enter a valid email address', 'err');
            return;
        }
        if (emailAlreadyExists(email)) {
            showToast(`${email} is already in the user list`, 'err');
            return;
        }

        showToast(`Invitation sent to ${email}`, 'ok');
        e.target.submit();
    });

    // ─────────────────────────────────────────────────────────────────
    // Row overflow menu
    // ─────────────────────────────────────────────────────────────────
    let menuTarget = null;
    const menu = $('#rowMenu');

    function wireRowActions (scope) {
        $$('button[data-act]', scope || document).forEach((b) => {
            if (b.dataset.wired) return;
            b.dataset.wired = '1';
            b.addEventListener('click', (e) => {
                e.stopPropagation();
                const tr = b.closest('tr');
                const act = b.dataset.act;
                if (act === 'resend') handleResend(tr);
                else if (act === 'menu') openMenu(b, tr);
            });
        });
    }
    wireRowActions();

    function openMenu (button, tr) {
        menuTarget = tr;
        const status = tr.dataset.status;
        const isPending = status === 'pending';

        // Show/hide menu items based on row status
        $$('.menu-pending-only', menu).forEach(
            (el) => (el.style.display = isPending ? '' : 'none'),
        );
        $$('.menu-active-only', menu).forEach(
            (el) => (el.style.display = isPending ? 'none' : ''),
        );

        const r = button.getBoundingClientRect();
        menu.style.top = r.bottom + window.scrollY + 4 + 'px';
        menu.style.left = r.right + window.scrollX - 200 + 'px';
        menu.classList.add('open');
    }
    document.addEventListener('click', () => menu.classList.remove('open'));

    $$('#rowMenu button').forEach((b) => {
        b.addEventListener('click', (e) => {
            e.stopPropagation();
            menu.classList.remove('open');
            if (!menuTarget) return;
            const act = b.dataset.act;
            if (act === 'copy-link') openCopyLink(menuTarget);
            else if (act === 'resend') handleResend(menuTarget);
            //else if (act === 'change-role')  handleChangeRole(menuTarget);
            else if (act === 'revoke') openRevokeDialog(menuTarget);
            else if (act === 'delete-user') openDeleteUserDialog(menuTarget);
        });
    });

    // POST to backend (real resend)
    function handleResend (tr) {
        const email = $('.id', tr).textContent.trim();
        const form = document.createElement('form');
        form.method = 'POST';
        form.action = '/PlatformIO/Users/';
        form.innerHTML = `
            <input type="hidden" name="csrfmiddlewaretoken" value="${window.CSRF_TOKEN || ''}">
            <input type="hidden" name="user-action" value="resend_invite">
            <input type="hidden" name="user_email"  value="${escapeHtml(email)}">
        `;
        document.body.appendChild(form);
        form.submit();
    }

    //    function handleChangeRole (tr) {
    //        const currentRole = tr.children[2].textContent.trim();
    //        const roles       = ['Management', 'Operational', 'System_Admin'];
    //        const newRole     = prompt(
    //            `Change role for ${$('.primary', tr).textContent}\n\nCurrent: ${currentRole}\nNew role (Management/Operational/System_Admin):`,
    //            currentRole
    //        );
    //        if (!newRole || !roles.includes(newRole) || newRole === currentRole) return;
    //        tr.children[2].innerHTML = `<span class="pill pill-muted">${escapeHtml(newRole)}</span>`;
    //        showToast(`Role updated to ${newRole}`, 'ok');
    //    }

    // ─────────────────────────────────────────────────────────────────
    // Copy-link dialog
    // ─────────────────────────────────────────────────────────────────
    function openCopyLink (tr) {
        const name = $('.primary', tr).textContent;
        const menuBtn = tr.querySelector('button[data-act="menu"]');
        const token = menuBtn?.dataset.token || '';
        // Use real token from data attribute; fall back to placeholder text only
        const url = token
            ? `${window.CPLATFORM_URL || ''}/invite/accept/${token}/`
            : `${window.CPLATFORM_URL || ''} — token not found`;

        $('#copyLinkUser').textContent = name;
        $('#inviteUrlText').textContent = url;

        const days = 30 - parseInt(tr.dataset.daysSinceInvite || '0', 10);
        $('#copyLinkExpiry').textContent =
            days > 0 ? `in ${days} days` : 'today';
        $('#copyLinkBtn').textContent = 'Copy';
        $('#copyLinkBtn').classList.remove('copied');
        $('#copyLinkBack').classList.add('open');
    }
    $('#copyLinkCloseBtn').addEventListener('click', () =>
        $('#copyLinkBack').classList.remove('open'),
    );
    $('#copyLinkBack').addEventListener('click', (e) => {
        if (e.target === $('#copyLinkBack'))
            $('#copyLinkBack').classList.remove('open');
    });
    $('#copyLinkBtn').addEventListener('click', () => {
        const url = $('#inviteUrlText').textContent;
        try {
            if (navigator.clipboard && window.isSecureContext) {
                navigator.clipboard.writeText(url);
            } else {
                const ta = document.createElement('textarea');
                ta.value = url;
                ta.style.position = 'fixed';
                ta.style.opacity = '0';
                document.body.appendChild(ta);
                ta.focus();
                ta.select();
                document.execCommand('copy');
                document.body.removeChild(ta);
            }
        } catch {
            /* silent */
        }
        $('#copyLinkBtn').textContent = 'Copied';
        $('#copyLinkBtn').classList.add('copied');
        setTimeout(() => {
            $('#copyLinkBtn').textContent = 'Copy';
            $('#copyLinkBtn').classList.remove('copied');
        }, 1500);
    });

    // ─────────────────────────────────────────────────────────────────
    // Revoke dialog — POSTs to backend
    // ─────────────────────────────────────────────────────────────────
    let revokeTarget = null;
    function openRevokeDialog (tr) {
        revokeTarget = tr;
        const name = $('.primary', tr).textContent;
        const email = $('.id', tr).textContent.trim();
        $('#revokeUserName').textContent = name;
        $('#revokeConfirmEmail').textContent = email;
        $('#revokeConfirmInput').value = '';
        $('#revokeConfirmBtn').disabled = true;
        $('#revokeBack').classList.add('open');
        setTimeout(() => $('#revokeConfirmInput').focus(), 200);
    }
    $('#revokeConfirmInput').addEventListener('input', (e) => {
        const expected = $('#revokeConfirmEmail').textContent;
        $('#revokeConfirmBtn').disabled = e.target.value !== expected;
    });
    $('#revokeCancelBtn').addEventListener('click', () =>
        $('#revokeBack').classList.remove('open'),
    );
    $('#revokeBack').addEventListener('click', (e) => {
        if (e.target === $('#revokeBack'))
            $('#revokeBack').classList.remove('open');
    });
    $('#revokeConfirmBtn').addEventListener('click', () => {
        if (!revokeTarget) return;
        const email = $('#revokeConfirmEmail').textContent.trim();
        const form = document.createElement('form');
        form.method = 'POST';
        form.action = '/PlatformIO/Users/';
        form.innerHTML = `
            <input type="hidden" name="csrfmiddlewaretoken" value="${window.CSRF_TOKEN || ''}">
            <input type="hidden" name="user-action" value="revoke_invite">
            <input type="hidden" name="user_email"  value="${escapeHtml(email)}">
        `;
        document.body.appendChild(form);
        form.submit();
    });

    // ─────────────────────────────────────────────────────────────────
    // Delete user dialog — fetch POST, then removes row
    // ─────────────────────────────────────────────────────────────────
    let deleteTarget = null;

    function openDeleteUserDialog (tr) {
        deleteTarget = tr;
        const name = $('.primary', tr).textContent;
        const email = $('.id', tr).textContent.trim();
        $('#deleteUserName').textContent = name;
        $('#deleteConfirmEmail').textContent = email;
        $('#deleteConfirmInput').value = '';
        $('#deleteConfirmBtn').disabled = true;
        $('#deleteUserBack').classList.add('open');
        setTimeout(() => $('#deleteConfirmInput').focus(), 200);
    }

    $('#deleteConfirmInput').addEventListener('input', (e) => {
        const expected = $('#deleteConfirmEmail').textContent.trim();
        $('#deleteConfirmBtn').disabled = e.target.value.trim() !== expected;
    });
    $('#deleteCancelBtn').addEventListener('click', () =>
        $('#deleteUserBack').classList.remove('open'),
    );
    $('#deleteUserBack').addEventListener('click', (e) => {
        if (e.target === $('#deleteUserBack'))
            $('#deleteUserBack').classList.remove('open');
    });

    $('#deleteConfirmBtn').addEventListener('click', () => {
        if (!deleteTarget) return;
        const email = $('#deleteConfirmEmail').textContent.trim();
        const userId = deleteTarget.dataset.userId;

        $('#deleteConfirmBtn').disabled = true;
        $('#deleteConfirmBtn').textContent = 'Deleting…';

        fetch('/PlatformIO/Users/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/x-www-form-urlencoded',
                'X-CSRFToken': window.CSRF_TOKEN || '',
            },
            body: new URLSearchParams({
                'user-action': 'delete',
                user_email: email,
                user_id: userId,
            }),
        })
            .then((r) => {
                if (r.ok || r.redirected) {
                    $('#deleteUserBack').classList.remove('open');
                    deleteTarget.style.transition =
                        'opacity .25s, transform .25s';
                    deleteTarget.style.opacity = '0';
                    deleteTarget.style.transform = 'translateX(-12px)';
                    setTimeout(() => {
                        deleteTarget.remove();
                        showToast(`User ${email} deleted`, 'ok');
                        updateBulkBar();
                        applyPagination();
                    }, 250);
                } else {
                    showToast('Delete failed, please try again', 'err');
                    $('#deleteConfirmBtn').disabled = false;
                    $('#deleteConfirmBtn').textContent = 'Delete permanently';
                }
            })
            .catch(() => {
                showToast('Network error', 'err');
                $('#deleteConfirmBtn').disabled = false;
                $('#deleteConfirmBtn').textContent = 'Delete permanently';
            });
    });

    // ─────────────────────────────────────────────────────────────────
    // Bulk action bar
    // ─────────────────────────────────────────────────────────────────
    function updateBulkBar () {
        const bar = $('#bulkBar');
        const count = selectedUserIds.size;

        if (count === 0) {
            bar.classList.remove('show');
            const headerCheckbox = $('.tbl thead .ck input[type=checkbox]');
            if (headerCheckbox) headerCheckbox.checked = false;
            return;
        }

        bar.classList.add('show');
        $('#bulkCount').textContent = `${count} selected`;

        // Update visible row checkboxes based on selectedUserIds
        const rows = $$('#userTbody tr');
        rows.forEach((tr) => {
            const userId = tr.dataset.userId;
            const cb = tr.querySelector('.row-check');
            if (cb && userId) {
                cb.checked = selectedUserIds.has(userId);
            }
        });

        // Update header checkbox state
        const headerCheckbox = $('.tbl thead .ck input[type=checkbox]');
        if (headerCheckbox) {
            const visibleRows = rows.filter(
                (tr) =>
                    tr.style.display !== 'none' &&
                    tr.dataset.searchHidden !== '1',
            );
            const visibleChecked = visibleRows.filter((tr) => {
                const cb = tr.querySelector('.row-check');
                return cb && cb.checked;
            }).length;

            if (visibleChecked === 0) {
                headerCheckbox.checked = false;
                headerCheckbox.indeterminate = count > 0;
            } else if (visibleChecked === visibleRows.length) {
                headerCheckbox.checked = true;
                headerCheckbox.indeterminate = false;
            } else {
                headerCheckbox.indeterminate = true;
            }
        }
    }
    document.addEventListener('change', (e) => {
        const cb = e.target;
        if (!cb.classList || !cb.classList.contains('row-check')) return;

        const tr = cb.closest('tr');
        if (!tr) return;

        const userId = tr.dataset.userId;
        if (!userId) return;

        if (cb.checked) {
            selectedUserIds.add(userId);
        } else {
            selectedUserIds.delete(userId);
        }

        updateBulkBar();
    });
    const bulkClear = $('#bulkClear');
    if (bulkClear) {
        bulkClear.addEventListener('click', (e) => {
            e.preventDefault();
            e.stopPropagation();

            selectedUserIds.clear();

            $$('#userTbody .row-check').forEach((c) => {
                c.checked = false;
            });

            const headerCheckbox = $('.tbl thead .ck input[type=checkbox]');
            if (headerCheckbox) {
                headerCheckbox.checked = false;
                headerCheckbox.indeterminate = false;
            }

            updateBulkBar();
        });
    }
    $$('.bulk-bar [data-bulk-act]').forEach((b) => {
        b.addEventListener('click', () => {
            const act = b.dataset.bulkAct;

            if (act === 'resend') {
                if (bulkResendInProgress) return; // prevent double-submit

                const pendingEmails = [];
                let skippedCount = 0;

                selectedUserIds.forEach((userId) => {
                    const userData = window.ALL_USER_DATA?.find(
                        (u) => u.user_id === userId,
                    );
                    if (!userData) return;
                    if (userData.status === 'pending') {
                        pendingEmails.push(userData.user_email);
                    } else {
                        skippedCount++;
                    }
                });

                if (pendingEmails.length === 0) {
                    showToast(
                        'No pending invitations selected; only pending users can have invites resent.',
                        'err',
                    );
                    return;
                }

                // ── Lock the button & show spinner ──
                bulkResendInProgress = true;
                b.disabled = true;
                b.innerHTML = `
                    <svg style="width:13px;height:13px;animation:spin .7s linear infinite;vertical-align:middle;margin-right:5px;"
                         viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"
                         stroke-linecap="round" stroke-linejoin="round">
                      <path d="M21 12a9 9 0 1 1-6.219-8.56"/>
                    </svg>Sending…`;

                const formData = new FormData();
                formData.append('csrfmiddlewaretoken', window.CSRF_TOKEN || '');
                formData.append('user-action', 'resend_invite');
                pendingEmails.forEach((email) =>
                    formData.append('user_email', email),
                );

                fetch('/PlatformIO/Users/', {
                    method: 'POST',
                    body: formData,
                    credentials: 'same-origin',
                })
                    .then((response) => {
                        if (!response.ok && !response.redirected)
                            throw new Error('Request failed');

                        selectedUserIds.clear();
                        $$('#userTbody .row-check').forEach((c) => {
                            c.checked = false;
                        });
                        const headerCheckbox = $(
                            '.tbl thead .ck input[type=checkbox]',
                        );
                        if (headerCheckbox) {
                            headerCheckbox.checked = false;
                            headerCheckbox.indeterminate = false;
                        }
                        updateBulkBar();

                        showToast(
                            skippedCount > 0
                                ? `Invitation resent to ${pendingEmails.length} pending user${pendingEmails.length === 1 ? '' : 's'}; ${skippedCount} were already active and skipped.`
                                : `Invitation resent to ${pendingEmails.length} pending user${pendingEmails.length === 1 ? '' : 's'}.`,
                            'ok',
                        );

                        setTimeout(() => window.location.reload(), 600);
                    })
                    .catch(() => {
                        showToast(
                            'Network error while resending invites',
                            'err',
                        );

                        // ── Unlock on failure so user can retry ──
                        bulkResendInProgress = false;
                        b.disabled = false;
                        b.textContent = 'Resend invitations';
                    });

                return;
            }

            // No other bulk actions
            selectedUserIds.clear();
            applyPagination();
        });
    });

    // Header checkbox — select ALL users across all pages
    const headerCheckbox = $('.tbl thead .ck input[type=checkbox]');
    if (headerCheckbox) {
        headerCheckbox.addEventListener('change', () => {
            const rows = $$('#userTbody tr');

            if (headerCheckbox.checked) {
                // Add ALL user IDs to selection (across all pages)
                if (window.ALL_USER_IDS && Array.isArray(window.ALL_USER_IDS)) {
                    window.ALL_USER_IDS.forEach((userId) =>
                        selectedUserIds.add(userId),
                    );
                }

                // Check all visible row checkboxes on current page
                rows.forEach((tr) => {
                    if (
                        tr.style.display === 'none' ||
                        tr.dataset.searchHidden === '1'
                    )
                        return;
                    const cb = tr.querySelector('.row-check');
                    if (cb) cb.checked = true;
                });
            } else {
                // Unselect ALL users across all pages
                selectedUserIds.clear();

                // Uncheck all visible row checkboxes on current page
                rows.forEach((tr) => {
                    const cb = tr.querySelector('.row-check');
                    if (cb) cb.checked = false;
                });
            }

            // Force update bulk bar
            setTimeout(() => updateBulkBar(), 10);
        });
    }

    // ─────────────────────────────────────────────────────────────────
    // Escape closes any open modal / drawer
    // ─────────────────────────────────────────────────────────────────
    document.addEventListener('keydown', (e) => {
        if (e.key !== 'Escape') return;
        if ($('#deleteUserBack').classList.contains('open'))
            return $('#deleteUserBack').classList.remove('open');
        if ($('#revokeBack').classList.contains('open'))
            return $('#revokeBack').classList.remove('open');
        if ($('#copyLinkBack').classList.contains('open'))
            return $('#copyLinkBack').classList.remove('open');
        if ($('#inviteDrawer').classList.contains('open'))
            return closeInviteDrawer();
        if ($('#dr').classList.contains('open')) return closeEditDrawer();
        if (menu.classList.contains('open'))
            return menu.classList.remove('open');
    });

    // ─────────────────────────────────────────────────────────────────
    // Init
    // ─────────────────────────────────────────────────────────────────
    updateExpiryBars();
    applyPagination();
})();
