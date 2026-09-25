/**
 * LitFinder: paper details page (publication.html?id=W123 or a DOI).
 *
 * Renders straight away from the search results already in the browser,
 * then loads the full record and related works from the API (single-work
 * lookups are free in OpenAlex). The LLM summary runs only on request.
 */

document.addEventListener('DOMContentLoaded', async () => {
    const id = new URLSearchParams(window.location.search).get('id');
    setupBackLink();
    if (!id) {
        showError('No paper selected', 'Open a paper from your search results or saved list.');
        return;
    }

    const seen = store.get('litfinder_seen', {}, sessionStorage)[id] ||
        Saved.all().find(p => p.id === id);
    // Search results carry keyword matches, not OpenAlex topics; topics come with the full record
    if (seen) render({ ...seen, topic_matches: {} }, null, { loadingRelated: true });

    try {
        const data = await ApiService.getPublication(id);
        // Keep the agent's explanation from the results page, if there was one
        render({ ...data.publication, agent_reason: seen && seen.agent_reason }, data.references || [],
            { relatedError: data.references === null });
    } catch (error) {
        if (seen) {
            render({ ...seen, topic_matches: {} }, [], { relatedError: true });
        } else {
            showError('Couldn\'t load this paper', error.message);
        }
    }
});

function setupBackLink() {
    const link = document.getElementById('back-link');
    const fromResults = document.referrer && new URL(document.referrer).pathname.endsWith('result.html');
    if (fromResults) {
        link.innerHTML = '<i class="fas fa-arrow-left"></i> Back to results';
        link.addEventListener('click', (e) => { e.preventDefault(); history.back(); });
    }
}

function showError(title, text) {
    document.getElementById('page').innerHTML = `
        <div class="state error"><i class="fas fa-triangle-exclamation big"></i>
            <h2>${escapeHtml(title)}</h2><p>${escapeHtml(text)}</p>
            <a class="btn btn-ghost" href="index.html"><i class="fas fa-magnifying-glass"></i> New search</a></div>`;
}

function render(pub, related, flags = {}) {
    const title = cleanTitle(pub.title);
    document.title = `${title.slice(0, 70)} · LitFinder`;
    const url = paperUrl(pub);
    const year = yearOf(pub);
    const authors = pub.authors || [];
    const topics = Object.entries(pub.topic_matches || {})
        .filter(([name]) => name.length < 60)
        .sort((a, b) => b[1] - a[1]).slice(0, 10).map(([name]) => name);
    const isSaved = Saved.has(pub.id);

    document.getElementById('page').innerHTML = `
        <div class="pub-header">
            <h1>${escapeHtml(title)}</h1>
            <div class="pub-authors" id="pub-authors">${escapeHtml(formatAuthors(authors, 12))}
                ${authors.length > 12 ? `<button type="button" class="link-btn" id="all-authors">Show all ${authors.length}</button>` : ''}</div>
            <div class="pub-venue">${[pub.journal, pub.publication_date, TYPE_LABELS[pub.type]].filter(Boolean).map(escapeHtml).join(' · ')}</div>
            <div class="pub-stats">
                <div class="stat"><div class="value">${formatNumber(pub.citations)}</div><div class="label">Citations</div></div>
                <div class="stat"><div class="value">${year || '–'}</div><div class="label">Year</div></div>
                <div class="stat"><div class="value">${pub.open_access ? 'Yes' : 'No'}</div><div class="label">Open access</div></div>
            </div>
            <div class="paper-actions">
                ${url ? `<a class="btn btn-primary" href="${escapeHtml(url)}" target="_blank" rel="noopener"><i class="fas fa-arrow-up-right-from-square"></i> Read the paper</a>` : ''}
                <button type="button" class="btn btn-ghost" id="save-btn"></button>
                <button type="button" class="btn btn-ghost" id="copy-cite"><i class="far fa-copy"></i> Copy citation</button>
                <button type="button" class="btn btn-ghost" id="copy-bibtex"><i class="fas fa-code"></i> BibTeX</button>
            </div>
        </div>

        <div class="pub-grid">
            <div>
                ${pub.agent_reason ? `<div class="paper-reason" style="margin:0 0 18px"><strong><i class="fas fa-wand-magic-sparkles"></i> Why the agent picked it:</strong> ${escapeHtml(pub.agent_reason)}</div>` : ''}
                <section class="panel">
                    <h2>Abstract</h2>
                    ${pub.abstract
                        ? `<p class="pub-abstract">${escapeHtml(pub.abstract)}</p>`
                        : '<p class="paper-abstract missing">OpenAlex has no abstract for this paper. Use "Read the paper" to see it at the publisher.</p>'}
                </section>
                <section class="panel" id="analysis-panel">
                    <h2><i class="fas fa-wand-magic-sparkles" style="color:#8a5cf6"></i> Reading notes</h2>
                    <p class="note" style="margin-top:0">An LLM summarizes the key findings, methods and limitations from the abstract. It takes a few seconds and uses one LLM call.</p>
                    <button type="button" class="btn btn-ghost" id="analyze-btn" ${pub.abstract ? '' : 'disabled title="Needs an abstract"'}>
                        <i class="fas fa-wand-magic-sparkles"></i> Generate reading notes</button>
                    <div id="analysis"></div>
                </section>
            </div>
            <aside>
                ${topics.length ? `<section class="panel"><h2>Topics</h2><div class="topic-list">
                    ${topics.map(t => `<span class="chip chip-static">${escapeHtml(t)}</span>`).join('')}</div></section>` : ''}
                <section class="panel">
                    <h2>Key references</h2>
                    <p class="note" style="margin-top:-4px">The most-cited papers this one builds on.</p>
                    ${renderRelated(related, flags)}
                </section>
            </aside>
        </div>`;

    const allAuthors = document.getElementById('all-authors');
    if (allAuthors) {
        allAuthors.addEventListener('click', () => {
            document.getElementById('pub-authors').textContent = authors.join(', ');
        });
    }

    const saveButton = document.getElementById('save-btn');
    const showSaved = (saved) => {
        saveButton.innerHTML = saved ? '<i class="fas fa-bookmark"></i> Saved' : '<i class="far fa-bookmark"></i> Save';
    };
    showSaved(isSaved);
    saveButton.addEventListener('click', () => {
        const saved = Saved.toggle(pub);
        showSaved(saved);
        showToast(saved ? 'Saved' : 'Removed from saved');
    });

    document.getElementById('copy-cite').addEventListener('click', async () => {
        await copyText(formatCitation(pub));
        showToast('Citation copied');
    });
    document.getElementById('copy-bibtex').addEventListener('click', async () => {
        await copyText(formatBibtex(pub));
        showToast('BibTeX copied');
    });
    document.getElementById('analyze-btn').addEventListener('click', () => analyze(pub.id));
}

function renderRelated(related, flags) {
    if (related === null || flags.loadingRelated) {
        return '<p class="note"><i class="fas fa-circle-notch fa-spin"></i> Loading…</p>';
    }
    if (flags.relatedError) return '<p class="note">Couldn\'t load references.</p>';
    if (!related.length) return '<p class="note">OpenAlex lists no references for this paper.</p>';
    return `<ul class="related-list">${related.map(r => `
        <li><a href="publication.html?id=${encodeURIComponent(r.id)}">${escapeHtml(cleanTitle(r.title))}</a>
            <div class="meta">${[formatAuthors(r.authors, 2), (r.publication_date || '').slice(0, 4),
                r.citations != null ? `${formatNumber(r.citations)} citations` : ''].filter(Boolean).map(escapeHtml).join(' · ')}</div>
        </li>`).join('')}</ul>`;
}

async function analyze(id) {
    const button = document.getElementById('analyze-btn');
    const target = document.getElementById('analysis');
    button.disabled = true;
    button.innerHTML = '<i class="fas fa-circle-notch fa-spin"></i> Reading the abstract…';
    try {
        const { analysis } = await ApiService.analyzePublication(id);
        const list = (title, items) => items && items.length
            ? `<div><h3>${title}</h3><ul>${items.map(i => `<li>${escapeHtml(i)}</li>`).join('')}</ul></div>` : '';
        target.innerHTML = `<div class="analysis-grid" style="margin-top:14px">
            ${list('Key findings', analysis.key_findings)}
            ${list('Methods', analysis.methodology)}
            ${list('Applications', analysis.practical_applications)}
            ${list('Limitations and open questions', analysis.knowledge_gaps)}
            ${analysis.citation_context ? `<div><h3>When to cite it</h3><p>${escapeHtml(analysis.citation_context)}</p></div>` : ''}
            <p class="note">Generated from the abstract; check the paper before relying on it.</p>
        </div>`;
        button.remove();
    } catch (error) {
        button.disabled = false;
        button.innerHTML = '<i class="fas fa-rotate-right"></i> Try again';
        target.innerHTML = `<div class="form-error" style="margin-top:12px"><i class="fas fa-circle-exclamation"></i><span>${escapeHtml(error.message)}</span></div>`;
    }
}
