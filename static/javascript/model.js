/* global confirm, fetch, location */
/* exported deleteModel */

const algoOptions = JSON.parse(
    document.getElementById('algo-data').textContent,
);
const categoryDropdown = document.getElementById('categoryDropdown');
const algoDropdown = document.getElementById('algoDropdown');
const searchInput = document.getElementById('searchInput');
const tabs = document.querySelectorAll('.tab');
const cards = document.querySelectorAll('.model-card:not(#inviteCard)');
const inviteCard = document.getElementById('inviteCard');

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

function applyFilters () {
    const activeStatus = document.querySelector('.tab.active').dataset.status;
    const activeCategory = categoryDropdown.value;
    const activeAlgo = algoDropdown.value;
    const query = searchInput.value.trim().toLowerCase();

    cards.forEach((card) => {
        const statusMatch =
            activeStatus === 'All' || card.dataset.status === activeStatus;
        const categoryMatch =
            activeCategory === 'All' ||
            card.dataset.category === activeCategory;
        const algoMatch =
            activeAlgo === 'All' || card.dataset.algo === activeAlgo;
        const searchMatch =
            !query ||
            card.dataset.name.includes(query) ||
            (card.dataset.category || '').toLowerCase().includes(query) ||
            (card.dataset.algo || '').toLowerCase().includes(query);

        card.style.display =
            statusMatch && categoryMatch && algoMatch && searchMatch
                ? ''
                : 'none';
    });

    inviteCard.style.display = '';
}

tabs.forEach((tab) => {
    tab.addEventListener('click', function () {
        tabs.forEach((t) => t.classList.remove('active'));
        this.classList.add('active');
        applyFilters();
    });
});

categoryDropdown.addEventListener('change', function () {
    const selected = this.value;

    while (algoDropdown.options.length > 1) {
        algoDropdown.remove(1);
    }

    if (selected !== 'All' && algoOptions[selected]) {
        algoOptions[selected].forEach((algo) => {
            const opt = document.createElement('option');
            opt.value = algo;
            opt.textContent = algo;
            algoDropdown.appendChild(opt);
        });
    }

    applyFilters();
});

algoDropdown.addEventListener('change', applyFilters);
searchInput.addEventListener('input', applyFilters);

const modelData = JSON.parse(document.getElementById('model-data').textContent);

function getCookie (name) {
    let cookieValue = null;

    document.cookie.split(';').forEach((cookie) => {
        cookie = cookie.trim();
        if (cookie.startsWith(name + '=')) {
            cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
        }
    });

    return cookieValue;
}

function deleteModel (index) {
    const modelReport = modelData[index];

    if (
        !confirm(
            `Delete model "${modelReport['model_name']}"? This cannot be undone.`,
        )
    ) {
        return;
    }

    const payload = { 'user-action': 'delete' };
    payload['json_data'] = { model_name: modelReport['model_name'] };

    fetch(window.location.href, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCookie('csrftoken'),
        },
        body: JSON.stringify(payload),
    })
        .then((response) => response.text())
        .then(() => {
            location.reload();
        })
        .catch(() => {});
}

/**
 * Navigate to the edit page for a Scheduled training job.
 * @param {string} modelName
 */
//function editModel (modelName) {
//    window.location.href = '/PlatformIO/ModelCreate/?mode=edit&model_name=' + encodeURIComponent(modelName);
//}

/**
 * Navigate to the read-only view page for a running / completed / failed job.
 * @param {string} modelName
 */
//function viewModel (modelName) {
//    window.location.href = '/PlatformIO/ModelCreate/?mode=view&model_name=' + encodeURIComponent(modelName);
//}
