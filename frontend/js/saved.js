/**
 * LitFinder: saved papers page (stored in this browser's localStorage).
 */

document.addEventListener('DOMContentLoaded', () => {
    render();

    document.getElementById('copy-all-bibtex').addEventListener('click', async () => {
        await copyText(Saved.all().map(formatBibtex).join('\n\n'));
        showToast('BibTeX for all saved papers copied');
    });
    document.getElementById('copy-all-citations').addEventListener('click', async () => {
        await copyText(Saved.all().map(formatCitation).join('\n\n'));
        showToast('Citations copied');
    });
    document.getElementById('clear-saved').addEventListener('click', () => {
        if (confirm('Remove all saved papers?')) {
            Saved.clear();
            render();
        }
    });
});

function render() {
    const saved = Saved.all();
    const list = document.getElementById('saved-list');
    document.getElementById('saved-toolbar').hidden = saved.length === 0;
    document.getElementById('saved-summary').textContent = saved.length
        ? `${saved.length} paper${saved.length === 1 ? '' : 's'}` : '';

    list.innerHTML = '';
    if (saved.length === 0) {
        list.innerHTML = `
            <div class="state">
                <i class="far fa-bookmark big"></i>
                <h2>Nothing saved yet</h2>
                <p>Click the bookmark on any search result to keep it here, then export your list as citations or BibTeX.</p>
                <a class="btn btn-primary" href="index.html"><i class="fas fa-magnifying-glass"></i> Find papers</a>
            </div>`;
        return;
    }
    saved.forEach(p => list.appendChild(createPaperCard(p, { onUnsave: render })));
}
