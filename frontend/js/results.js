/**
 * LitFinder: results page. Runs the search described by the URL, shows
 * progress while it runs, then renders results with client-side sorting
 * and narrowing.
 */

const LOADING_STEPS = {
    search: [
        { label: 'Understanding your request', at: 0 },
        { label: 'Searching OpenAlex by meaning', at: 2 },
        { label: 'Ranking papers by relevance', at: 4 },
    ],
    agent: [
        { label: 'Planning searches', at: 0 },
        { label: 'Searching and reading abstracts', at: 5 },
        { label: 'Checking the best candidates', at: 18 },
        { label: 'Writing up the answer', at: 30 },
    ],
};

const state = {
    search: null,
    result: null,
    papers: [],  // Results with their original rank
};

document.addEventListener('DOMContentLoaded', () => {
    state.search = searchFromParams(new URLSearchParams(window.location.search));
    initSearchForm(document.getElementById('search-form'), { initial: state.search, compact: true });

    if (!state.search.query) {
        renderState('fas fa-magnifying-glass', 'Start with a search',
            'Describe the research you are looking for in the box above.');
        return;
    }
    document.title = `${state.search.query.slice(0, 60)} · LitFinder`;
    setupControls();
    runSearch();
});

// --------------------------------------------------------------------------
// Running the search
// --------------------------------------------------------------------------

function cacheKey() {
    return `litfinder_result:${window.location.search}`;
}

async function runSearch({ force = false } = {}) {
    // Reloading or coming back to a results page shouldn't pay for the search again
    const cached = force ? null : store.get(cacheKey(), null, sessionStorage);
    if (cached) {
        showResults(cached);
        return;
    }

    const controller = new AbortController();
    const stopProgress = showProgress(controller);
    const search = state.search;
    try {
        const result = search.mode === 'agent'
            ? await ApiService.agentSearch(search.query, controller.signal)
            : await ApiService.search(search.query, pipelineOptions(search), controller.signal);
        stopProgress();
        store.set(cacheKey(), result, sessionStorage);
        RecentSearches.add(search.query, search.mode);
        showResults(result);
    } catch (error) {
        stopProgress();
        if (error.name === 'AbortError') {
            renderState('fas fa-circle-stop', 'Search cancelled', 'Edit your request above, or run it again.',
                [{ label: 'Run again', icon: 'fas fa-rotate-right', onClick: () => runSearch({ force: true }) }]);
        } else {
            showError(error);
        }
    }
}

function pipelineOptions(search) {
    const options = { max_results: 20 };
    if (search.fromYear) options.from_year = search.fromYear;
    if (search.toYear) options.to_year = search.toYear;
    if (search.minCitations) options.min_citations = search.minCitations;
    if (search.type) options.publication_types = [search.type];
    if (search.openAccess) options.open_access_only = true;
    return options;
}

/** Show the loading card; returns a function that stops it */
function showProgress(controller) {
    const steps = LOADING_STEPS[state.search.mode];
    const status = document.getElementById('status');
    document.getElementById('results').hidden = true;
    document.getElementById('query-plan').hidden = true;
    status.innerHTML = `
        <div class="loading-card">
            <div class="spinner" aria-hidden="true"></div>
            <div class="loading-text" style="flex:1">
                <h2>${state.search.mode === 'agent' ? 'The agent is researching your question' : 'Finding papers'}</h2>
                <p><span id="elapsed">0</span> s · ${state.search.mode === 'agent' ? 'usually 20-60 s' : 'usually about 5 s'}</p>
                <ul class="loading-steps">
                    ${steps.map((s, i) => `<li data-step="${i}"><i class="far fa-circle"></i> ${s.label}</li>`).join('')}
                </ul>
            </div>
            <button type="button" class="btn btn-ghost btn-sm" id="cancel-search"><i class="fas fa-xmark"></i> Cancel</button>
        </div>
        ${'<div class="skeleton" style="margin-bottom:12px"><div class="bar" style="width:70%"></div><div class="bar" style="width:45%"></div><div class="bar"></div><div class="bar" style="width:90%"></div></div>'.repeat(3)}
    `;
    document.getElementById('cancel-search').addEventListener('click', () => controller.abort());

    const start = Date.now();
    const tick = () => {
        const seconds = Math.floor((Date.now() - start) / 1000);
        const elapsed = document.getElementById('elapsed');
        if (elapsed) elapsed.textContent = seconds;
        // Steps advance on typical timings; the last one stays active until the answer arrives
        const current = steps.reduce((acc, s, i) => (seconds >= s.at ? i : acc), 0);
        status.querySelectorAll('.loading-steps li').forEach((li, i) => {
            li.className = i < current ? 'done' : i === current ? 'active' : '';
            li.querySelector('i').className = i < current ? 'fas fa-circle-check' : i === current ? 'fas fa-circle-notch fa-spin' : 'far fa-circle';
        });
    };
    tick();
    const timer = setInterval(tick, 500);
    return () => {
        clearInterval(timer);
        status.innerHTML = '';
    };
}

function showError(error) {
    const quota = /budget|rate limit/i.test(error.message);
    const actions = [{ label: 'Try again', icon: 'fas fa-rotate-right', onClick: () => runSearch({ force: true }) }];
    if (state.search.mode === 'agent') {
        actions.push({ label: 'Use fast search instead', icon: 'fas fa-bolt',
            onClick: () => { window.location.href = resultsUrl({ ...state.search, mode: 'search' }); } });
    }
    renderState('fas fa-triangle-exclamation', quota ? 'The paper database is busy' : 'The search didn\'t work',
        quota ? `${error.message}. Try again later.` : error.message, actions, 'error');
}

/** Render an empty/error state in the status area */
function renderState(icon, title, text, actions = [], kind = '') {
    document.getElementById('results').hidden = true;
    document.getElementById('query-plan').hidden = true;
    const status = document.getElementById('status');
    status.innerHTML = `
        <div class="state ${kind}">
            <i class="${icon} big"></i>
            <h2>${escapeHtml(title)}</h2>
            <p>${escapeHtml(text)}</p>
            <div class="chip-row" style="justify-content:center"></div>
        </div>`;
    const row = status.querySelector('.chip-row');
    actions.forEach(a => {
        const button = document.createElement('button');
        button.type = 'button';
        button.className = 'btn btn-ghost';
        button.innerHTML = `<i class="${a.icon}"></i> ${escapeHtml(a.label)}`;
        button.addEventListener('click', a.onClick);
        row.appendChild(button);
    });
}

// --------------------------------------------------------------------------
// Rendering results
// --------------------------------------------------------------------------

function showResults(result) {
    state.result = result;
    state.papers = (result.results || []).map((p, i) => ({ ...p, rank: i + 1 }));
    rememberPapers(state.papers);

    if (state.papers.length === 0) {
        renderState('far fa-folder-open', 'No papers found',
            state.search.mode === 'search' && hasFilters(state.search)
                ? 'Your filters may be too strict. Try removing some of them.'
                : 'Try describing your topic with different or more general terms.',
            state.search.mode === 'search'
                ? [{ label: 'Try agent mode', icon: 'fas fa-wand-magic-sparkles',
                     onClick: () => { window.location.href = resultsUrl({ ...state.search, mode: 'agent' }); } }]
                : []);
        return;
    }

    document.getElementById('results').hidden = false;
    renderQueryPlan(result);
    renderAgent(result);
    fillTypeOptions();
    renderList();
}

/** Show what the pipeline actually searched for (metadata.recall from the API) */
function renderQueryPlan(result) {
    const plan = document.getElementById('query-plan');
    const recall = (result.metadata || {}).recall;
    const chips = [];
    if (recall) {
        if (recall.semantic_query) chips.push('<i class="fas fa-brain"></i> Semantic search on your request');
        (recall.queries || []).forEach(q => chips.push(escapeHtml(q)));
        if (recall.citation_expansion) chips.push('<i class="fas fa-diagram-project"></i> + papers the best matches cite most');
    }
    if (!chips.length) {
        plan.hidden = true;
        return;
    }
    plan.innerHTML = '<span><i class="fas fa-magnifying-glass"></i> Searched OpenAlex with</span>' +
        chips.map(c => `<span class="chip chip-static">${c}</span>`).join('');
    plan.hidden = false;
}

function renderAgent(result) {
    const card = document.getElementById('agent-card');
    const side = document.getElementById('side');
    const layout = document.getElementById('results-layout');
    if (!result.agent) {
        card.innerHTML = '';
        side.hidden = true;
        layout.classList.remove('with-side');
        return;
    }

    const agent = result.agent;
    const usage = agent.usage || {};
    const trace = agent.trace || [];
    card.innerHTML = `
        <div class="agent-card">
            <h2><i class="fas fa-wand-magic-sparkles"></i> What the agent found</h2>
            <p class="agent-summary">${escapeHtml(result.summary)}</p>
            <div class="agent-stats">
                <span><i class="fas fa-screwdriver-wrench"></i> ${trace.length} tool calls</span>
                <span><i class="fas fa-comments"></i> ${usage.llm_calls || 0} LLM calls</span>
                <span><i class="fas fa-coins"></i> ${formatNumber((usage.prompt_tokens || 0) + (usage.completion_tokens || 0))} tokens</span>
                <span><i class="fas fa-microchip"></i> ${escapeHtml(agent.model)}</span>
            </div>
            <details class="trace">
                <summary>How it searched</summary>
                <ol>${trace.map(t => `
                    <li class="${String(t.result).startsWith('error') ? 'error' : ''}">
                        <span class="step-no">Step ${t.step}</span>
                        <span><code>${escapeHtml(t.tool)}(${escapeHtml(describeArgs(t.arguments))})</code>
                        <span class="result">→ ${escapeHtml(t.result)} · ${formatNumber(t.duration_ms)} ms</span></span>
                    </li>`).join('')}
                </ol>
            </details>
        </div>`;

    const authors = result.authors || [];
    if (authors.length) {
        side.innerHTML = `
            <div class="side-card">
                <h2><i class="fas fa-user-graduate"></i> Researchers to know</h2>
                ${authors.map(a => `
                    <div class="person">
                        <div class="person-name"><a href="https://openalex.org/${encodeURIComponent(a.author_id)}" target="_blank" rel="noopener">${escapeHtml(a.name)}</a></div>
                        <div class="person-meta">${[a.institution, a.h_index != null ? `h-index ${a.h_index}` : '', `${formatNumber(a.citations)} citations`].filter(Boolean).map(escapeHtml).join(' · ')}</div>
                        <div class="person-reason">${escapeHtml(a.reason)}</div>
                    </div>`).join('')}
            </div>`;
        side.hidden = false;
        layout.classList.add('with-side');
    }
}

function describeArgs(args) {
    if (!args || typeof args !== 'object') return String(args ?? '');
    return Object.entries(args)
        .filter(([, v]) => v !== null && v !== undefined)
        .map(([k, v]) => `${k}=${JSON.stringify(v)}`)
        .join(', ');
}

// --------------------------------------------------------------------------
// Sorting and narrowing (client-side, on the returned results)
// --------------------------------------------------------------------------

function setupControls() {
    const panel = document.getElementById('refine-panel');
    const toggle = document.getElementById('refine-toggle');
    toggle.addEventListener('click', () => {
        panel.hidden = !panel.hidden;
        toggle.setAttribute('aria-expanded', String(!panel.hidden));
    });
    ['sort', 'refine-from', 'refine-citations', 'refine-type', 'refine-oa'].forEach(id => {
        const el = document.getElementById(id);
        el.addEventListener(el.type === 'number' ? 'input' : 'change', renderList);
    });
    document.getElementById('refine-clear').addEventListener('click', () => {
        ['refine-from', 'refine-citations', 'refine-type'].forEach(id => { document.getElementById(id).value = ''; });
        document.getElementById('refine-oa').checked = false;
        renderList();
    });
}

function fillTypeOptions() {
    const select = document.getElementById('refine-type');
    const types = [...new Set(state.papers.map(p => p.type).filter(t => TYPE_LABELS[t]))];
    select.innerHTML = '<option value="">Any type</option>' +
        types.map(t => `<option value="${t}">${TYPE_LABELS[t]}</option>`).join('');
}

function currentRefinement() {
    return {
        from: parseInt(document.getElementById('refine-from').value, 10) || null,
        minCitations: parseInt(document.getElementById('refine-citations').value, 10) || 0,
        type: document.getElementById('refine-type').value,
        openAccess: document.getElementById('refine-oa').checked,
    };
}

function renderList() {
    const refine = currentRefinement();
    const sort = document.getElementById('sort').value;

    let papers = state.papers.filter(p =>
        (!refine.from || (parseInt(yearOf(p), 10) || 0) >= refine.from) &&
        (p.citations || 0) >= refine.minCitations &&
        (!refine.type || p.type === refine.type) &&
        (!refine.openAccess || p.open_access));

    const date = p => p.publication_date || '';
    const sorters = {
        relevance: (a, b) => a.rank - b.rank,
        citations: (a, b) => (b.citations || 0) - (a.citations || 0),
        newest: (a, b) => date(b).localeCompare(date(a)),
        oldest: (a, b) => date(a).localeCompare(date(b)),
    };
    papers = [...papers].sort(sorters[sort]);

    const active = [refine.from, refine.minCitations, refine.type, refine.openAccess].filter(Boolean).length;
    document.getElementById('refine-count').textContent = active ? ` · ${active}` : '';

    const total = state.papers.length;
    const seconds = (state.result.metadata || {}).processing_time;
    document.getElementById('results-count').innerHTML =
        (papers.length === total ? `${total} papers` : `${papers.length} of ${total} papers`) +
        (seconds ? ` <span class="muted">· found in ${Number(seconds).toFixed(1)} s</span>` : '');

    const list = document.getElementById('paper-list');
    list.innerHTML = '';
    if (papers.length === 0) {
        list.innerHTML = `<div class="state"><i class="fas fa-filter-circle-xmark big"></i>
            <h2>Nothing matches these filters</h2><p>Loosen or clear the filters to see more papers.</p></div>`;
        return;
    }
    papers.forEach(p => list.appendChild(createPaperCard(p, { rank: p.rank })));
}
