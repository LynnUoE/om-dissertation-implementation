/**
 * LitFinder - Publication View
 * Handles publication detail page functionality
 */

document.addEventListener('DOMContentLoaded', function() {
    // Check if we're on the publication detail page
    const publicationOverview = document.querySelector('.publication-overview');
    if (!publicationOverview) return;
    
    // Get publication ID from URL
    const urlParams = new URLSearchParams(window.location.search);
    const publicationId = urlParams.get('id');
    
    if (!publicationId) {
        displayErrorMessage('Publication ID is missing. Please go back to the results page.');
        return;
    }
    
    // Load publication data
    loadPublicationData(publicationId);
    
    // Set up tab switching
    setupTabSwitching();
    
    // Set up citation sorting
    setupCitationSorting();
    
    // Set up action buttons
    setupActionButtons();
});

/**
 * Load publication data from API or session storage
 */
async function loadPublicationData(publicationId) {
    try {
        window.showLoading();
        
        // Try to load from session storage first (if coming from results page)
        const storedResults = sessionStorage.getItem('publication_results');
        let publication = null;
        
        if (storedResults) {
            const allPublications = JSON.parse(storedResults);
            publication = allPublications.find(p => p.id === publicationId);
        }
        
        // If not found in session storage, fetch from API
        if (!publication) {
            publication = await apiCall(`/publication/${publicationId}`, 'GET');
        }
        
        // Display publication data
        displayPublicationDetails(publication);
        
        // Load citations if needed
        if (!publication.citations_list) {
            await loadPublicationCitations(publicationId);
        } else {
            displayCitations(publication.citations_list);
        }
        
    } catch (error) {
        console.error('Error loading publication data:', error);
        displayErrorMessage('Could not load publication details. Please try again later.');
    } finally {
        window.hideLoading();
    }
}

/**
 * Display publication details
 */
function displayPublicationDetails(publication) {
    // Set title and authors
    document.getElementById('publication-title').textContent = publication.title || 'Untitled Publication';
    document.getElementById('publication-authors').textContent = formatAuthors(publication.authors || []);
    
    // Set source information
    const sourceElement = document.getElementById('publication-source');
    if (sourceElement) {
        const publicationDate = publication.publication_date ? 
            new Date(publication.publication_date) : null;
        
        const journalSpan = sourceElement.querySelector('.journal-name');
        if (journalSpan) journalSpan.textContent = publication.journal || 'Unknown Source';
        
        const yearSpan = sourceElement.querySelector('.publication-year');
        if (yearSpan) yearSpan.textContent = publicationDate ? publicationDate.getFullYear() : 'Unknown Year';
        
        const typeSpan = sourceElement.querySelector('.publication-type');
        if (typeSpan) {
            let pubTypeLabel = 'Publication';
            switch (publication.type) {
                case 'journal-article': pubTypeLabel = 'Journal Article'; break;
                case 'conference-paper': pubTypeLabel = 'Conference Paper'; break;
                case 'review': pubTypeLabel = 'Review'; break;
                case 'book-chapter': pubTypeLabel = 'Book Chapter'; break;
                case 'preprint': pubTypeLabel = 'Preprint'; break;
            }
            typeSpan.textContent = pubTypeLabel;
        }
    }
    
    // Set metrics
    const metrics = document.querySelectorAll('.metric-value');
    if (metrics.length >= 3) {
        metrics[0].textContent = formatNumber(publication.citations || 0);
        
        const pubDate = publication.publication_date ? 
            formatDate(publication.publication_date) : 'Unknown';
        metrics[1].textContent = pubDate;
        
        const accessType = publication.open_access ? 'Open Access' : 'Subscription';
        metrics[2].textContent = accessType;
    }
    
    // Set relevance score
    const scoreCircle = document.querySelector('.score-circle span');
    if (scoreCircle) {
        const matchPercentage = Math.round((publication.relevance_score || 0) * 100);
        scoreCircle.textContent = `${matchPercentage}%`;
    }
    
    // Set topic breakdown
    const topicBreakdown = document.getElementById('topic-breakdown');
    if (topicBreakdown && publication.topic_matches) {
        topicBreakdown.innerHTML = '';
        
        // Sort topics by match score
        const sortedTopics = Object.entries(publication.topic_matches)
            .sort((a, b) => b[1] - a[1])
            .slice(0, 5); // Top 5 topics
        
        sortedTopics.forEach(([topic, score]) => {
            const percentage = Math.round(score * 100);
            
            const topicItem = document.createElement('div');
            topicItem.className = 'topic-item';
            topicItem.innerHTML = `
                <div class="topic-header">
                    <span>${topic}</span>
                    <span class="topic-score">${percentage}%</span>
                </div>
                <div class="progress-bar">
                    <div class="progress" style="width: ${percentage}%"></div>
                </div>
            `;
            
            topicBreakdown.appendChild(topicItem);
        });
    }
    
    // Set journal metrics
    const journalMetrics = document.querySelector('.journal-metrics');
    if (journalMetrics && publication.journal_metrics) {
        const impactFactor = journalMetrics.querySelector('.journal-metric:nth-child(1) .metric-value');
        if (impactFactor) impactFactor.textContent = publication.journal_metrics.impact_factor?.toFixed(2) || 'N/A';
        
        const h5Index = journalMetrics.querySelector('.journal-metric:nth-child(2) .metric-value');
        if (h5Index) h5Index.textContent = publication.journal_metrics.h5_index || 'N/A';
        
        const quartile = journalMetrics.querySelector('.journal-metric:nth-child(3) .metric-value');
        if (quartile) quartile.textContent = publication.journal_metrics.quartile || 'N/A';
    }
    
    // Set abstract text
    const abstractContent = document.querySelector('.abstract-content');
    if (abstractContent && publication.abstract) {
        abstractContent.innerHTML = '';
        
        // Split abstract into paragraphs
        const paragraphs = publication.abstract.split('\n\n');
        paragraphs.forEach(paragraph => {
            if (paragraph.trim()) {
                const p = document.createElement('p');
                p.textContent = paragraph.trim();
                abstractContent.appendChild(p);
            }
        });
    }
    
    // Set keywords
    const keywordList = document.querySelector('.keyword-list');
    if (keywordList && publication.keywords) {
        keywordList.innerHTML = '';
        
        publication.keywords.forEach(keyword => {
            const span = document.createElement('span');
            span.className = 'keyword';
            span.textContent = keyword;
            keywordList.appendChild(span);
        });
    }
    
    // Set methods content if available
    if (publication.methods) {
        const methodsContent = document.querySelector('.methods-content');
        if (methodsContent) {
            methodsContent.innerHTML = formatSectionContent(publication.methods);
        }
    }
    
    // Set findings content if available
    if (publication.findings) {
        const findingsContent = document.querySelector('.findings-content');
        if (findingsContent) {
            findingsContent.innerHTML = '';
            
            publication.findings.forEach((finding, index) => {
                const findingItem = document.createElement('div');
                findingItem.className = 'finding-item';
                
                findingItem.innerHTML = `
                    <h3>${finding.title || `Finding ${index + 1}`}</h3>
                    <p>${finding.description || ''}</p>
                `;
                
                findingsContent.appendChild(findingItem);
            });
        }
    }
    
    // Set references if available
    if (publication.references) {
        const referenceList = document.querySelector('.reference-list');
        if (referenceList) {
            referenceList.innerHTML = '';
            
            publication.references.forEach(reference => {
                const li = document.createElement('li');
                const p = document.createElement('p');
                p.className = 'reference-text';
                p.innerHTML = reference;
                li.appendChild(p);
                referenceList.appendChild(li);
            });
        }
    }
    
    // Set similar publications
    if (publication.similar_publications) {
        const similarList = document.querySelector('.similar-list');
        if (similarList) {
            similarList.innerHTML = '';
            
            publication.similar_publications.forEach(similar => {
                const li = document.createElement('li');
                li.innerHTML = `
                    <a href="publication.html?id=${similar.id}">${similar.title}</a>
                    <span class="pub-year">${similar.year}</span>
                `;
                similarList.appendChild(li);
            });
        }
    }
    
    // Update action buttons based on availability
    updateActionButtons(publication);
}

/**
 * Format authors for display
 */
function formatAuthors(authors) {
    if (!authors || authors.length === 0) return 'Unknown Authors';
    return authors.join(', ');
}

/**
 * Format section content with headings and paragraphs
 */
function formatSectionContent(content) {
    if (typeof content === 'string') {
        return `<p>${content}</p>`;
    }
    
    if (typeof content === 'object') {
        let html = '';
        
        // Process each section
        for (const [heading, text] of Object.entries(content)) {
            html += `<h3>${heading}</h3>`;
            
            if (Array.isArray(text)) {
                // If text is an array, create a list
                html += '<ul>';
                text.forEach(item => {
                    html += `<li>${item}</li>`;
                });
                html += '</ul>';
            } else {
                // Otherwise, create paragraphs
                html += `<p>${text}</p>`;
            }
        }
        
        return html;
    }
    
    return '';
}

/**
 * Load publication citations
 */
async function loadPublicationCitations(publicationId) {
    try {
        // Make API call to get citations
        const citations = await apiCall(`/publication/${publicationId}/citations`, 'GET');
        
        // Display citations
        displayCitations(citations || []);
        
    } catch (error) {
        console.error('Error loading citations:', error);
        const citationsTab = document.getElementById('citations-tab');
        if (citationsTab) {
            citationsTab.innerHTML += `
                <p class="error-message">Could not load citations. Please try again later.</p>
            `;
        }
    }
}

/**
 * Display citations in the citations tab
 */
function displayCitations(citations) {
    const citationsList = document.querySelector('.citations-list');
    if (!citationsList) return;
    
    // Clear existing citations
    citationsList.innerHTML = '';
    
    if (citations.length === 0) {
        citationsList.innerHTML = `
            <p class="no-citations-message">No citations found for this publication.</p>
        `;
        
        // Hide "See All" button
        const seeMoreButton = document.querySelector('.see-more button');
        if (seeMoreButton) {
            seeMoreButton.style.display = 'none';
        }
        
        return;
    }
    
    // Display first 3 citations
    citations.slice(0, 3).forEach(citation => {
        const citationItem = createCitationItem(citation);
        citationsList.appendChild(citationItem);
    });
    
    // Update "See All" button
    const seeMoreButton = document.querySelector('.see-more button');
    if (seeMoreButton) {
        if (citations.length > 3) {
            seeMoreButton.textContent = `See All Citations (${citations.length}) `;
            seeMoreButton.innerHTML += '<i class="fas fa-chevron-down"></i>';
            seeMoreButton.style.display = 'inline-block';
            
            // Store all citations in a data attribute
            citationsList.dataset.allCitations = JSON.stringify(citations);
            
            // Add click event
            seeMoreButton.addEventListener('click', function() {
                toggleAllCitations(this);
            });
        } else {
            seeMoreButton.style.display = 'none';
        }
    }
}

/**
 * Create a citation item element
 */
function createCitationItem(citation) {
    const item = document.createElement('div');
    item.className = 'citation-item';
    
    // Format publication date
    const pubYear = citation.publication_date ? 
        new Date(citation.publication_date).getFullYear() : 'N/A';
    
    item.innerHTML = `
        <h3 class="citation-title">
            <a href="publication.html?id=${citation.id}">${citation.title || 'Untitled Citation'}</a>
        </h3>
        <p class="citation-authors">${formatAuthors(citation.authors || [])}</p>
        <p class="citation-source">
            <span class="journal-name">${citation.journal || 'Unknown Source'}</span>, 
            <span class="citation-year">${pubYear}</span>
        </p>
        <p class="citation-excerpt">
            "${citation.excerpt || 'No excerpt available.'}"
        </p>
    `;
    
    return item;
}

/**
 * Toggle between showing all citations and limited set
 */
function toggleAllCitations(button) {
    const citationsList = document.querySelector('.citations-list');
    if (!citationsList || !citationsList.dataset.allCitations) return;
    
    const isExpanded = button.getAttribute('data-expanded') === 'true';
    const allCitations = JSON.parse(citationsList.dataset.allCitations);
    
    if (isExpanded) {
        // Show limited citations
        citationsList.innerHTML = '';
        
        allCitations.slice(0, 3).forEach(citation => {
            const citationItem = createCitationItem(citation);
            citationsList.appendChild(citationItem);
        });
        
        button.innerHTML = `See All Citations (${allCitations.length}) <i class="fas fa-chevron-down"></i>`;
        button.setAttribute('data-expanded', 'false');
    } else {
        // Show all citations
        citationsList.innerHTML = '';
        
        allCitations.forEach(citation => {
            const citationItem = createCitationItem(citation);
            citationsList.appendChild(citationItem);
        });
        
        button.innerHTML = 'Show Less <i class="fas fa-chevron-up"></i>';
        button.setAttribute('data-expanded', 'true');
    }
}

/**
 * Setup tab switching functionality
 */
function setupTabSwitching() {
    const tabButtons = document.querySelectorAll('.tab-btn');
    const tabContents = document.querySelectorAll('.tab-content');
    
    tabButtons.forEach(button => {
        button.addEventListener('click', function() {
            // Remove active class from all buttons and contents
            tabButtons.forEach(btn => btn.classList.remove('active'));
            tabContents.forEach(content => content.classList.remove('active'));
            
            // Add active class to clicked button and corresponding content
            this.classList.add('active');
            const tabName = this.getAttribute('data-tab');
            document.getElementById(`${tabName}-tab`).classList.add('active');
        });
    });
}

/**
 * Setup citation sorting functionality
 */
function setupCitationSorting() {
    const sortSelect = document.getElementById('citation-sort');
    if (!sortSelect) return;
    
    sortSelect.addEventListener('change', function() {
        const sortOption = this.value;
        
        const citationsList = document.querySelector('.citations-list');
        if (!citationsList || !citationsList.dataset.allCitations) return;
        
        const allCitations = JSON.parse(citationsList.dataset.allCitations);
        let sortedCitations = [...allCitations];
        
        // Sort citations
        if (sortOption === 'recent') {
            sortedCitations.sort((a, b) => {
                const dateA = a.publication_date ? new Date(a.publication_date) : new Date(0);
                const dateB = b.publication_date ? new Date(b.publication_date) : new Date(0);
                return dateB - dateA;
            });
        } else if (sortOption === 'influential') {
            sortedCitations.sort((a, b) => (b.citations || 0) - (a.citations || 0));
        }
        
        // Update the stored citations
        citationsList.dataset.allCitations = JSON.stringify(sortedCitations);
        
        // Update the display
        const seeMoreButton = document.querySelector('.see-more button');
        const isExpanded = seeMoreButton ? 
            seeMoreButton.getAttribute('data-expanded') === 'true' : false;
        
        citationsList.innerHTML = '';
        
        if (isExpanded) {
            // Show all citations
            sortedCitations.forEach(citation => {
                const citationItem = createCitationItem(citation);
                citationsList.appendChild(citationItem);
            });
        } else {
            // Show limited citations
            sortedCitations.slice(0, 3).forEach(citation => {
                const citationItem = createCitationItem(citation);
                citationsList.appendChild(citationItem);
            });
        }
    });
}

/**
 * Update action buttons based on publication availability
 */
function updateActionButtons(publication) {
    const viewFullTextBtn = document.getElementById('view-full-text');
    if (viewFullTextBtn) {
        if (publication.full_text_url) {
            viewFullTextBtn.href = publication.full_text_url;
            viewFullTextBtn.target = '_blank';
        } else {
            viewFullTextBtn.addEventListener('click', function(e) {
                e.preventDefault();
                alert('Full text is not available for this publication.');
            });
            viewFullTextBtn.classList.add('btn-disabled');
        }
    }
    
    const exportCitationBtn = document.getElementById('export-citation');
    if (exportCitationBtn) {
        exportCitationBtn.addEventListener('click', function(e) {
            e.preventDefault();
            exportCitation(publication);
        });
    }
    
    const savePublicationBtn = document.getElementById('save-publication');
    if (savePublicationBtn) {
        // Check if already saved
        const savedJson = localStorage.getItem('saved_publications');
        if (savedJson) {
            const savedPublications = JSON.parse(savedJson);
            const isAlreadySaved = savedPublications.some(saved => saved.id === publication.id);
            
            if (isAlreadySaved) {
                savePublicationBtn.innerHTML = '<i class="fas fa-check"></i> Saved';
                savePublicationBtn.disabled = true;
            }
        }
        
        savePublicationBtn.addEventListener('click', function() {
            savePublication(publication);
            this.innerHTML = '<i class="fas fa-check"></i> Saved';
            this.disabled = true;
        });
    }
}

/**
 * Setup action buttons functionality
 */
function setupActionButtons() {
    // This setup happens in updateActionButtons to ensure 
    // we have the publication data first
}

/**
 * Save publication to saved items
 */
function savePublication(publication) {
    try {
        // Get existing saved publications
        const savedJson = localStorage.getItem('saved_publications');
        const savedPublications = savedJson ? JSON.parse(savedJson) : [];
        
        // Check if already saved
        const isAlreadySaved = savedPublications.some(saved => saved.id === publication.id);
        if (isAlreadySaved) return;
        
        // Add to saved list
        savedPublications.push({
            id: publication.id,
            title: publication.title,
            authors: publication.authors,
            journal: publication.journal,
            year: publication.publication_date ? new Date(publication.publication_date).getFullYear() : null,
            saved_at: new Date().toISOString()
        });
        
        // Save back to localStorage
        localStorage.setItem('saved_publications', JSON.stringify(savedPublications));
    } catch (error) {
        console.error('Error saving publication:', error);
    }
}

/**
 * Export citation in different formats
 */
function exportCitation(publication) {
    // Create modal for choosing citation format
    const modal = document.createElement('div');
    modal.className = 'citation-modal';
    
    modal.innerHTML = `
        <div class="modal-content">
            <div class="modal-header">
                <h3>Export Citation</h3>
                <button class="close-btn">&times;</button>
            </div>
            <div class="modal-body">
                <p>Choose citation format:</p>
                <div class="format-buttons">
                    <button class="btn btn-outline format-btn" data-format="bibtex">BibTeX</button>
                    <button class="btn btn-outline format-btn" data-format="apa">APA</button>
                    <button class="btn btn-outline format-btn" data-format="mla">MLA</button>
                    <button class="btn btn-outline format-btn" data-format="chicago">Chicago</button>
                </div>
                <div class="citation-output" style="display: none;">
                    <textarea id="citation-text" rows="8" readonly></textarea>
                    <button class="btn btn-primary copy-btn">
                        <i class="fas fa-copy"></i> Copy to Clipboard
                    </button>
                </div>
            </div>
        </div>
    `;
    
    // Add modal to the document
    document.body.appendChild(modal);
    
    // Setup close button
    const closeBtn = modal.querySelector('.close-btn');
    closeBtn.addEventListener('click', function() {
        modal.remove();
    });
    
    // Setup format buttons
    const formatButtons = modal.querySelectorAll('.format-btn');
    formatButtons.forEach(button => {
        button.addEventListener('click', function() {
            const format = this.getAttribute('data-format');
            const citationText = formatCitation(publication, format);
            
            const outputDiv = modal.querySelector('.citation-output');
            const textArea = modal.querySelector('#citation-text');
            
            textArea.value = citationText;
            outputDiv.style.display = 'block';
            
            // Highlight the selected format button
            formatButtons.forEach(btn => btn.classList.remove('selected'));
            this.classList.add('selected');
        });
    });
    
    // Setup copy button
    const copyBtn = modal.querySelector('.copy-btn');
    copyBtn.addEventListener('click', function() {
        const textArea = modal.querySelector('#citation-text');
        textArea.select();
        document.execCommand('copy');
        
        this.innerHTML = '<i class="fas fa-check"></i> Copied!';
        setTimeout(() => {
            this.innerHTML = '<i class="fas fa-copy"></i> Copy to Clipboard';
        }, 2000);
    });
    
    // Close modal when clicking outside
    modal.addEventListener('click', function(e) {
        if (e.target === modal) {
            modal.remove();
        }
    });
}

/**
 * Format citation based on selected format
 */
function formatCitation(publication, format) {
    const authors = publication.authors || ['Unknown Author'];
    const title = publication.title || 'Untitled Publication';
    const journal = publication.journal || '';
    const year = publication.publication_date ? new Date(publication.publication_date).getFullYear() : '';
    const volume = publication.volume || '';
    const issue = publication.issue || '';
    const pages = publication.pages || '';
    const doi = publication.doi || '';
    
    switch (format) {
        case 'bibtex':
            // Generate author string for BibTeX
            const bibtexAuthors = authors.map(author => {
                const nameParts = author.split(', ');
                if (nameParts.length === 2) {
                    return `${nameParts[0]}, ${nameParts[1]}`;
                }
                return author;
            }).join(' and ');
            
            // Create BibTeX ID based on first author's last name and year
            const firstAuthorLastName = authors[0].split(' ').pop().replace(/[^a-zA-Z]/g, '');
            const bibtexId = `${firstAuthorLastName}${year}`;
            
            return `@article{${bibtexId},
  author = {${bibtexAuthors}},
  title = {${title}},
  journal = {${journal}},
  year = {${year}}${volume ? `,
  volume = {${volume}}` : ''}${issue ? `,
  number = {${issue}}` : ''}${pages ? `,
  pages = {${pages}}` : ''}${doi ? `,
  doi = {${doi}}` : ''}
}`;
            
        case 'apa':
            // APA style: Author(s). (Year). Title. Journal, Volume(Issue), Pages. DOI
            const apaAuthors = authors.map(author => {
                const nameParts = author.split(' ');
                if (nameParts.length > 1) {
                    const lastName = nameParts.pop();
                    const initials = nameParts.map(n => `${n.charAt(0)}.`).join(' ');
                    return `${lastName}, ${initials}`;
                }
                return author;
            }).join(', ');
            
            return `${apaAuthors} (${year}). ${title}. ${journal}${volume ? `, ${volume}` : ''}${issue ? `(${issue})` : ''}${pages ? `, ${pages}` : ''}${doi ? `. https://doi.org/${doi}` : ''}`;
            
        case 'mla':
            // MLA style: Author(s). "Title." Journal, vol. Volume, no. Issue, Year, pp. Pages. DOI
            const mlaAuthors = authors.join(', ');
            
            return `${mlaAuthors}. "${title}." ${journal}${volume ? `, vol. ${volume}` : ''}${issue ? `, no. ${issue}` : ''}, ${year}${pages ? `, pp. ${pages}` : ''}${doi ? `. DOI: ${doi}` : ''}`;
            
        case 'chicago':
            // Chicago style: Author(s). "Title." Journal Volume, no. Issue (Year): Pages. DOI
            const chicagoAuthors = authors.join(', ');
            
            return `${chicagoAuthors}. "${title}." ${journal} ${volume}${issue ? `, no. ${issue}` : ''} (${year})${pages ? `: ${pages}` : ''}${doi ? `. https://doi.org/${doi}` : ''}`;
            
        default:
            return 'Citation format not supported.';
    }
}

/**
 * Display error message
 */
function displayErrorMessage(message) {
    const mainContent = document.querySelector('main');
    if (!mainContent) return;
    
    const errorElement = document.createElement('div');
    errorElement.className = 'error-container';
    errorElement.innerHTML = `
        <div class="error-message">
            <i class="fas fa-exclamation-circle"></i>
            <h2>Error</h2>
            <p>${message}</p>
            <button class="btn btn-primary return-button">
                <i class="fas fa-arrow-left"></i> Return to Results
            </button>
        </div>
    `;
    
    // Remove existing content
    mainContent.innerHTML = '';
    mainContent.appendChild(errorElement);
    
    // Add event listener for return button
    const returnButton = errorElement.querySelector('.return-button');
    if (returnButton) {
        returnButton.addEventListener('click', function() {
            window.location.href = 'results.html';
        });
    }
}