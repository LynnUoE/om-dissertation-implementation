/**
 * LitFinder: home page (search box, examples, recent searches).
 */

const EXAMPLES = [
    { query: 'Speculative decoding to speed up large language model inference', mode: 'search' },
    { query: 'CRISPR base editing and prime editing without double-strand breaks', mode: 'search' },
    { query: 'Microplastic pollution in freshwater ecosystems', mode: 'search' },
    { query: 'Graph neural networks for molecular property prediction', mode: 'search' },
    { query: 'Who are the leading researchers on LLM hallucination detection, and what are their key papers?', mode: 'agent' },
];

document.addEventListener('DOMContentLoaded', () => {
    const help = document.getElementById('mode-help');
    const box = initSearchForm(document.getElementById('search-form'), {
        onModeChange: (mode, text) => { help.textContent = text; },
    });
    box.textarea.focus();

    const chip = (label, icon, onClick) => {
        const button = document.createElement('button');
        button.type = 'button';
        button.className = 'chip';
        button.innerHTML = `<i class="${icon}"></i> ${escapeHtml(label)}`;
        button.addEventListener('click', onClick);
        return button;
    };

    const examples = document.getElementById('examples');
    EXAMPLES.forEach(example => {
        const icon = example.mode === 'agent' ? 'fas fa-wand-magic-sparkles' : 'fas fa-magnifying-glass';
        examples.appendChild(chip(example.query, icon, () => box.setQuery(example.query, example.mode)));
    });

    const renderRecent = () => {
        const recent = RecentSearches.all();
        const block = document.getElementById('recent-block');
        const list = document.getElementById('recent-searches');
        block.hidden = recent.length === 0;
        list.innerHTML = '';
        recent.forEach(r => {
            list.appendChild(chip(r.query, 'fas fa-clock-rotate-left', () => {
                window.location.href = resultsUrl({ query: r.query, mode: r.mode });
            }));
        });
    };
    document.getElementById('clear-recent').addEventListener('click', () => {
        RecentSearches.clear();
        renderRecent();
    });
    renderRecent();

    // Tell the user up front if the backend is down, rather than after a search
    ApiService.checkHealth().catch(() => {
        const error = document.getElementById('form-error');
        error.innerHTML = '<i class="fas fa-plug-circle-xmark"></i><span>Can\'t reach the LitFinder server. Is the backend running?</span>';
        error.hidden = false;
    });
});
