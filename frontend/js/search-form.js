/**
 * LitFinder: the search box used on the home and results pages.
 *
 * A search is described by URL parameters, so results pages can be
 * bookmarked, shared and reloaded:
 *   q      the request text
 *   mode   "agent" for agent search (default: pipeline search)
 *   from, to, minc, type, oa   pipeline filters
 */

const MODE_HELP = {
    search: 'Fast: finds papers by meaning, adds the key papers they cite, then ranks everything against your request. Usually about 5 seconds.',
    agent: 'Thorough: the LLM runs the searches itself, reads abstracts and explains each pick. Takes 20-60 seconds; filters are set by what you write.',
};

/** Read a search from URL parameters */
function searchFromParams(params) {
    const int = (key) => {
        const value = parseInt(params.get(key), 10);
        return Number.isFinite(value) ? value : null;
    };
    return {
        query: (params.get('q') || '').trim(),
        mode: params.get('mode') === 'agent' ? 'agent' : 'search',
        fromYear: int('from'),
        toYear: int('to'),
        minCitations: int('minc'),
        type: params.get('type') || '',
        openAccess: params.get('oa') === '1',
    };
}

/** Build result.html?... for a search */
function resultsUrl(search) {
    const params = new URLSearchParams({ q: search.query });
    if (search.mode === 'agent') {
        params.set('mode', 'agent');
    } else {
        if (search.fromYear) params.set('from', search.fromYear);
        if (search.toYear) params.set('to', search.toYear);
        if (search.minCitations) params.set('minc', search.minCitations);
        if (search.type) params.set('type', search.type);
        if (search.openAccess) params.set('oa', '1');
    }
    return `result.html?${params}`;
}

function hasFilters(search) {
    return Boolean(search.fromYear || search.toYear || search.minCitations || search.type || search.openAccess);
}

/**
 * Render the search box into a <form>.
 * options.initial: a search to prefill; options.compact: smaller, for the results page
 */
function initSearchForm(form, options = {}) {
    const initial = options.initial || { query: '', mode: 'search' };
    const thisYear = new Date().getFullYear();
    const modKey = /Mac|iPhone|iPad/.test(navigator.platform || navigator.userAgent) ? '⌘' : 'Ctrl';

    form.innerHTML = `
        <label class="sr-only" for="query">Describe the research you're looking for</label>
        <textarea id="query" name="q" rows="${options.compact ? 1 : 2}" maxlength="1000"
            placeholder="e.g. Recent work on speculative decoding to speed up LLM inference"></textarea>
        <div class="search-box-bar">
            <div class="search-box-left">
                <div class="segmented" role="group" aria-label="Search mode">
                    <button type="button" data-mode="search"><i class="fas fa-bolt"></i> Search</button>
                    <button type="button" data-mode="agent"><i class="fas fa-wand-magic-sparkles"></i> Agent</button>
                </div>
                <button type="button" class="btn btn-ghost btn-sm" id="filters-toggle" aria-expanded="false" aria-controls="filters-panel">
                    <i class="fas fa-sliders"></i> Filters<span id="filters-active"></span>
                </button>
            </div>
            <div class="search-box-left">
                <span class="kbd-hint"><kbd>${modKey}</kbd> <kbd>Enter</kbd></span>
                <button type="submit" class="btn btn-primary"><i class="fas fa-magnifying-glass"></i> Search</button>
            </div>
        </div>
        <div class="filters-panel" id="filters-panel" hidden>
            <div>
                <label class="field-label" for="from-year">From year</label>
                <input class="input" type="number" id="from-year" min="1800" max="${thisYear}" placeholder="Any">
            </div>
            <div>
                <label class="field-label" for="to-year">To year</label>
                <input class="input" type="number" id="to-year" min="1800" max="${thisYear}" placeholder="${thisYear}">
            </div>
            <div>
                <label class="field-label" for="min-citations">Min. citations</label>
                <input class="input" type="number" id="min-citations" min="0" placeholder="0">
            </div>
            <div>
                <label class="field-label" for="pub-type">Type</label>
                <select class="input" id="pub-type">
                    <option value="">Any type</option>
                    ${Object.entries(TYPE_LABELS).map(([value, label]) => `<option value="${value}">${label}</option>`).join('')}
                </select>
            </div>
            <label class="check"><input type="checkbox" id="open-access"> Open access only</label>
            <p class="filters-note">Agent mode ignores these filters; mention years or other limits in your request instead.</p>
        </div>
        <div class="form-error" id="form-error" role="alert" hidden></div>
    `;

    const textarea = form.querySelector('#query');
    const modeButtons = form.querySelectorAll('.segmented button');
    const filtersToggle = form.querySelector('#filters-toggle');
    const filtersPanel = form.querySelector('#filters-panel');
    const error = form.querySelector('#form-error');
    const fields = {
        fromYear: form.querySelector('#from-year'),
        toYear: form.querySelector('#to-year'),
        minCitations: form.querySelector('#min-citations'),
        type: form.querySelector('#pub-type'),
        openAccess: form.querySelector('#open-access'),
    };
    let mode = initial.mode || 'search';

    const autoGrow = () => {
        textarea.style.height = 'auto';
        textarea.style.height = `${textarea.scrollHeight}px`;
    };

    const setMode = (next) => {
        mode = next;
        modeButtons.forEach(b => b.setAttribute('aria-pressed', String(b.dataset.mode === mode)));
        filtersToggle.disabled = mode === 'agent';
        if (mode === 'agent') {
            filtersPanel.hidden = true;
            filtersToggle.setAttribute('aria-expanded', 'false');
        }
        if (options.onModeChange) options.onModeChange(mode, MODE_HELP[mode]);
    };

    const readSearch = () => ({
        query: textarea.value.trim(),
        mode,
        fromYear: parseInt(fields.fromYear.value, 10) || null,
        toYear: parseInt(fields.toYear.value, 10) || null,
        minCitations: parseInt(fields.minCitations.value, 10) || null,
        type: fields.type.value,
        openAccess: fields.openAccess.checked,
    });

    const showFilterCount = () => {
        const search = readSearch();
        const n = ['fromYear', 'toYear', 'minCitations', 'type', 'openAccess'].filter(k => search[k]).length;
        form.querySelector('#filters-active').textContent = n ? ` · ${n}` : '';
    };

    const showError = (message) => {
        error.innerHTML = `<i class="fas fa-circle-exclamation"></i><span>${escapeHtml(message)}</span>`;
        error.hidden = false;
    };

    // Prefill
    textarea.value = initial.query || '';
    fields.fromYear.value = initial.fromYear || '';
    fields.toYear.value = initial.toYear || '';
    fields.minCitations.value = initial.minCitations || '';
    fields.type.value = initial.type || '';
    fields.openAccess.checked = Boolean(initial.openAccess);
    setMode(mode);
    showFilterCount();
    requestAnimationFrame(autoGrow);

    // Events
    modeButtons.forEach(b => b.addEventListener('click', () => setMode(b.dataset.mode)));
    textarea.addEventListener('input', () => { autoGrow(); error.hidden = true; });
    textarea.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) {
            e.preventDefault();
            form.requestSubmit();
        } else if (e.key === 'Enter' && !e.shiftKey && options.compact) {
            e.preventDefault();  // One-line box on the results page: Enter searches
            form.requestSubmit();
        }
    });
    filtersToggle.addEventListener('click', () => {
        filtersPanel.hidden = !filtersPanel.hidden;
        filtersToggle.setAttribute('aria-expanded', String(!filtersPanel.hidden));
    });
    Object.values(fields).forEach(f => f.addEventListener('change', showFilterCount));

    form.addEventListener('submit', (e) => {
        e.preventDefault();
        const search = readSearch();
        if (search.query.length < 3) {
            showError('Describe what you are looking for in a few words first.');
            textarea.focus();
            return;
        }
        if (search.fromYear && search.toYear && search.fromYear > search.toYear) {
            showError('"From year" is after "To year".');
            return;
        }
        window.location.href = resultsUrl(search);
    });

    return {
        textarea,
        setQuery(text, nextMode) {
            textarea.value = text;
            if (nextMode) setMode(nextMode);
            autoGrow();
            textarea.focus();
        },
    };
}
