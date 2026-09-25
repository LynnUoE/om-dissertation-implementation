/**
 * LitFinder: helpers shared by every page (formatting, paper cards,
 * saved papers, recent searches, toasts).
 */

const TYPE_LABELS = {
    'journal-article': 'Journal article',
    'conference-paper': 'Conference paper',
    'review': 'Review',
    'book-chapter': 'Book chapter',
    'preprint': 'Preprint',
};

/** Escape text from the API (titles, abstracts, LLM output) before putting it in HTML */
function escapeHtml(text) {
    return String(text ?? '')
        .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}

/**
 * OpenAlex titles sometimes contain markup (<i>, <sub>) or a literal "\n"; show plain text.
 * DOMParser builds an inert document: nothing in it loads or runs.
 */
function cleanTitle(title) {
    const html = String(title || 'Untitled').replace(/\\n/g, ' ');
    const text = new DOMParser().parseFromString(html, 'text/html').body.textContent || '';
    return text.replace(/\s+/g, ' ').trim() || 'Untitled';
}

function formatNumber(n) {
    return Number(n || 0).toLocaleString('en-US');
}

function formatAuthors(authors, max = 3) {
    if (!authors || authors.length === 0) return 'Unknown authors';
    return authors.length <= max ? authors.join(', ') : `${authors.slice(0, max).join(', ')} et al.`;
}

function yearOf(publication) {
    const date = publication.publication_date || '';
    return /^\d{4}/.test(date) ? date.slice(0, 4) : '';
}

/** Best link for a paper: its DOI, else its OpenAlex page */
function paperUrl(publication) {
    if (publication.doi) return publication.doi;
    if (publication.url) return publication.url;
    if (/^W\d+$/.test(publication.id || '')) return `https://openalex.org/${publication.id}`;
    return null;
}

/** A plain-text reference in an APA-like style */
function formatCitation(publication) {
    const authors = publication.authors || [];
    const who = authors.length > 6 ? `${authors.slice(0, 6).join(', ')}, et al.` : authors.join(', ');
    const parts = [
        `${who || 'Unknown authors'} (${yearOf(publication) || 'n.d.'}).`,
        `${cleanTitle(publication.title)}.`,
    ];
    if (publication.journal) parts.push(`${publication.journal}.`);
    if (publication.doi) parts.push(publication.doi);
    return parts.join(' ');
}

/** A BibTeX entry; the key is surname + year + first long title word */
function formatBibtex(pub) {
    const authors = pub.authors || [];
    const surname = (authors[0] || 'unknown').split(' ').pop().toLowerCase().replace(/[^a-z]/g, '') || 'unknown';
    const firstWord = cleanTitle(pub.title).split(/\s+/).find(w => w.length > 3) || 'paper';
    const key = `${surname}${yearOf(pub)}${firstWord.toLowerCase().replace(/[^a-z]/g, '')}`;
    const fields = [
        ['title', `{${cleanTitle(pub.title)}}`],
        ['author', authors.join(' and ')],
        ['year', yearOf(pub)],
        [pub.type === 'conference-paper' ? 'booktitle' : 'journal', pub.journal],
        ['doi', (pub.doi || '').replace('https://doi.org/', '')],
    ].filter(([, v]) => v);
    const entryType = pub.type === 'conference-paper' ? 'inproceedings' : 'article';
    return `@${entryType}{${key},\n${fields.map(([k, v]) => `  ${k} = {${v}}`).join(',\n')}\n}`;
}

async function copyText(text) {
    try {
        await navigator.clipboard.writeText(text);
    } catch (e) {  // Older browsers / insecure contexts
        const area = document.createElement('textarea');
        area.value = text;
        document.body.appendChild(area);
        area.select();
        document.execCommand('copy');
        area.remove();
    }
}

let toastTimer;
function showToast(message) {
    let toast = document.getElementById('toast');
    if (!toast) {
        toast = document.createElement('div');
        toast.id = 'toast';
        toast.className = 'toast';
        toast.setAttribute('role', 'status');
        document.body.appendChild(toast);
    }
    toast.textContent = message;
    toast.classList.add('show');
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => toast.classList.remove('show'), 2200);
}

// --------------------------------------------------------------------------
// Storage (wrapped: private windows and blocked site data can throw)
// --------------------------------------------------------------------------

const store = {
    get(key, fallback, storage = localStorage) {
        try {
            const raw = storage.getItem(key);
            return raw ? JSON.parse(raw) : fallback;
        } catch (e) {
            return fallback;
        }
    },
    set(key, value, storage = localStorage) {
        try {
            storage.setItem(key, JSON.stringify(value));
        } catch (e) {
            // Quota exceeded or storage unavailable: the feature just doesn't persist
        }
    },
};

const Saved = {
    KEY: 'litfinder_saved',
    all() { return store.get(this.KEY, []); },
    has(id) { return this.all().some(p => p.id === id); },
    toggle(publication) {
        const saved = this.all();
        const index = saved.findIndex(p => p.id === publication.id);
        if (index >= 0) {
            saved.splice(index, 1);
        } else {
            const { agent_reason, relevance_score, topic_matches, ...paper } = publication;
            saved.unshift({ ...paper, saved_at: new Date().toISOString() });
        }
        store.set(this.KEY, saved);
        updateSavedCount();
        return index < 0;
    },
    clear() { store.set(this.KEY, []); updateSavedCount(); },
};

const RecentSearches = {
    KEY: 'litfinder_recent',
    all() { return store.get(this.KEY, []); },
    add(query, mode) {
        const recent = this.all().filter(r => r.query !== query);
        recent.unshift({ query, mode });
        store.set(this.KEY, recent.slice(0, 6));
    },
    clear() { store.set(this.KEY, []); },
};

/** Remember papers seen in results, so the details page can render them instantly */
function rememberPapers(publications) {
    const seen = store.get('litfinder_seen', {}, sessionStorage);
    publications.forEach(p => { if (p.id) seen[p.id] = p; });
    store.set('litfinder_seen', seen, sessionStorage);
}

function updateSavedCount() {
    const badge = document.getElementById('saved-count');
    if (badge) {
        const n = Saved.all().length;
        badge.textContent = n ? String(n) : '';
    }
}

// --------------------------------------------------------------------------
// Paper card (results and saved pages)
// --------------------------------------------------------------------------

/**
 * Build a result card.
 * options.rank: number shown on the left; options.onUnsave: called after un-saving
 */
function createPaperCard(publication, options = {}) {
    const card = document.createElement('article');
    card.className = options.rank ? 'paper' : 'paper no-rank';

    const title = cleanTitle(publication.title);
    const url = paperUrl(publication);
    const year = yearOf(publication);
    const detailsHref = publication.id ? `publication.html?id=${encodeURIComponent(publication.id)}` : null;
    const abstract = (publication.abstract || '').trim();
    const isSaved = Saved.has(publication.id);

    const byline = [
        `<span>${escapeHtml(formatAuthors(publication.authors))}</span>`,
        publication.journal ? `<span class="dot venue">${escapeHtml(publication.journal)}</span>` : '',
        year ? `<span class="dot">${year}</span>` : '',
    ].join('');

    card.innerHTML = `
        ${options.rank ? `<span class="paper-rank" aria-label="Rank ${options.rank}">${options.rank}</span>` : ''}
        <button class="save-toggle" type="button" aria-pressed="${isSaved}"
                title="${isSaved ? 'Remove from saved' : 'Save for later'}">
            <i class="${isSaved ? 'fas' : 'far'} fa-bookmark"></i>
        </button>
        <h3 class="paper-title">
            ${detailsHref ? `<a href="${detailsHref}">${escapeHtml(title)}</a>` : escapeHtml(title)}
        </h3>
        <div class="paper-byline">${byline}</div>
        <div class="paper-badges">
            ${publication.type && TYPE_LABELS[publication.type] ? `<span class="badge badge-type">${TYPE_LABELS[publication.type]}</span>` : ''}
            <span class="badge"><i class="fas fa-quote-right"></i> ${formatNumber(publication.citations)} citations</span>
            ${publication.open_access ? '<span class="badge badge-oa"><i class="fas fa-lock-open"></i> Open access</span>' : ''}
        </div>
        ${abstract
            ? `<p class="paper-abstract clamped">${escapeHtml(abstract)}</p>
               <button class="link-btn toggle-abstract" type="button" hidden>Show full abstract</button>`
            : '<p class="paper-abstract missing">No abstract available in OpenAlex.</p>'}
        ${publication.agent_reason ? `
            <div class="paper-reason"><strong><i class="fas fa-wand-magic-sparkles"></i> Why it's here:</strong>
                ${escapeHtml(publication.agent_reason)}</div>` : ''}
        <div class="paper-actions">
            ${url ? `<a class="btn btn-ghost btn-sm" href="${escapeHtml(url)}" target="_blank" rel="noopener">
                <i class="fas fa-arrow-up-right-from-square"></i> Open paper</a>` : ''}
            ${detailsHref ? `<a class="btn btn-ghost btn-sm" href="${detailsHref}"><i class="fas fa-circle-info"></i> Details</a>` : ''}
            <button class="btn btn-ghost btn-sm copy-citation" type="button"><i class="far fa-copy"></i> Copy citation</button>
        </div>
    `;

    // Only offer "show more" when the abstract is actually cut off
    const abstractEl = card.querySelector('.paper-abstract.clamped');
    const toggle = card.querySelector('.toggle-abstract');
    if (abstractEl && toggle) {
        requestAnimationFrame(() => {
            if (abstractEl.scrollHeight > abstractEl.clientHeight + 2) toggle.hidden = false;
        });
        toggle.addEventListener('click', () => {
            const expanded = abstractEl.classList.toggle('clamped');
            toggle.textContent = expanded ? 'Show full abstract' : 'Show less';
        });
    }

    const saveButton = card.querySelector('.save-toggle');
    saveButton.addEventListener('click', () => {
        const nowSaved = Saved.toggle(publication);
        saveButton.setAttribute('aria-pressed', String(nowSaved));
        saveButton.title = nowSaved ? 'Remove from saved' : 'Save for later';
        saveButton.innerHTML = `<i class="${nowSaved ? 'fas' : 'far'} fa-bookmark"></i>`;
        showToast(nowSaved ? 'Saved' : 'Removed from saved');
        if (!nowSaved && options.onUnsave) options.onUnsave(card);
    });

    card.querySelector('.copy-citation').addEventListener('click', async () => {
        await copyText(formatCitation(publication));
        showToast('Citation copied');
    });

    return card;
}

document.addEventListener('DOMContentLoaded', updateSavedCount);
