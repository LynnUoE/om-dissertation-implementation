/**
 * LitFinder - Publication View
 * Handles publication detail page functionality
 */

document.addEventListener('DOMContentLoaded', function() {
    // Get publication ID from URL
    const urlParams = new URLSearchParams(window.location.search);
    const publicationId = urlParams.get('id');
    
    if (publicationId) {
        loadPublicationDetails(publicationId);
    } else {
        displayError('No publication ID specified');
    }
    
    // Set up tab switching
    setupTabSwitching();
});

/**
 * Load publication data from API
 */
async function loadPublicationDetails(publicationId) {
    try {
        if (typeof window.showLoading === 'function') {
            window.showLoading("Loading publication details...");
        }
        
        console.log("Loading publication details for:", publicationId);
        
        // Load basic publication details
        const publicationData = await ApiService.getPublicationDetails(publicationId);
        
        if (publicationData.status !== 'success') {
            throw new Error(publicationData.message || 'Failed to load publication details');
        }
        
        // Display basic publication information
        displayPublicationDetails(publicationData.publication);
        
        if (publicationData.related_publications && publicationData.related_publications.length > 0) {
            displayRelatedPublications(publicationData.related_publications);
        }
        
        // Now load analysis separately
        loadPublicationAnalysis(publicationId);
        
    } catch (error) {
        console.error('Error loading publication details:', error);
        displayError('Error loading publication details: ' + error.message);
    } finally {
        if (typeof window.hideLoading === 'function') {
            window.hideLoading();
        }
    }
}

/**
 * Load and display publication analysis
 */
async function loadPublicationAnalysis(publicationId) {
    try {
        // Show a secondary loading indicator for analysis specifically
        const analysisContainer = document.getElementById('analysis-container');
        if (!analysisContainer) return;
        
        analysisContainer.innerHTML = `<div class="loading-analysis">
            <i class="fas fa-spinner fa-spin"></i>
            <p>Analyzing publication content...</p>
        </div>`;
        
        // Get query context from session storage if available
        let queryContext = null;
        const searchResultsJson = sessionStorage.getItem('search_results');
        if (searchResultsJson) {
            try {
                const searchResults = JSON.parse(searchResultsJson);
                if (searchResults.structured_query) {
                    queryContext = {
                        research_areas: searchResults.structured_query.research_areas || [],
                        expertise: searchResults.structured_query.expertise || []
                    };
                }
            } catch (e) {
                console.warn('Error parsing search results for context:', e);
            }
        }
        
        // Request analysis via the analysis endpoint
        const analysisData = await ApiService.analyzePublication(publicationId, queryContext);
        
        if (analysisData.status === 'success' && analysisData.analysis) {
            displayPublicationAnalysis(analysisData.analysis);
        } else {
            throw new Error(analysisData.message || 'Failed to analyze publication');
        }
        
    } catch (error) {
        console.error('Error loading publication analysis:', error);
        
        // Show error but don't interrupt viewing the publication
        const analysisContainer = document.getElementById('analysis-container');
        if (analysisContainer) {
            analysisContainer.innerHTML = `<div class="analysis-error">
                <i class="fas fa-exclamation-circle"></i>
                <p>Unable to load analysis: ${error.message}</p>
                <button class="btn btn-outline retry-analysis-btn">
                    <i class="fas fa-redo"></i> Retry Analysis
                </button>
            </div>`;
            
            // Add retry event listener
            const retryButton = analysisContainer.querySelector('.retry-analysis-btn');
            if (retryButton) {
                retryButton.addEventListener('click', () => {
                    loadPublicationAnalysis(publicationId);
                });
            }
        }
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
    } else if (abstractContent) {
        abstractContent.innerHTML = '<p>Abstract not available for this publication.</p>';
    }
    
    // Update action buttons based on availability
    updateActionButtons(publication);
}

/**
 * Display related publications
 */
function displayRelatedPublications(relatedPublications) {
    const similarList = document.querySelector('.similar-list');
    if (!similarList || !relatedPublications || relatedPublications.length === 0) {
        return;
    }
    
    similarList.innerHTML = '';
    
    relatedPublications.forEach(publication => {
        const li = document.createElement('li');
        
        // Extract year from publication date
        let year = 'Unknown';
        if (publication.publication_date) {
            const date = new Date(publication.publication_date);
            year = date.getFullYear();
        }
        
        li.innerHTML = `
            <a href="publication.html?id=${encodeURIComponent(publication.id)}">${publication.title}</a>
            <span class="pub-year">${year}</span>
        `;
        
        similarList.appendChild(li);
    });
}

/**
 * Display publication analysis results
 */
function displayPublicationAnalysis(analysis) {
    if (!analysis) return;
    
    const analysisContainer = document.getElementById('analysis-container');
    if (!analysisContainer) return;
    
    // Prepare analysis sections
    let topicsHtml = '';
    if (analysis.primary_topics && analysis.primary_topics.length > 0) {
        topicsHtml = `
            <div class="analysis-section">
                <h3>Primary Topics</h3>
                <ul>
                    ${analysis.primary_topics.map(topic => `<li>${topic}</li>`).join('')}
                </ul>
            </div>
        `;
    }
    
    let findingsHtml = '';
    if (analysis.key_findings && analysis.key_findings.length > 0) {
        findingsHtml = `
            <div class="analysis-section">
                <h3>Key Findings</h3>
                <ul>
                    ${analysis.key_findings.map(finding => `<li>${finding}</li>`).join('')}
                </ul>
            </div>
        `;
    }
    
    let methodologyHtml = '';
    if (analysis.methodology && analysis.methodology.length > 0) {
        methodologyHtml = `
            <div class="analysis-section">
                <h3>Methodology</h3>
                <ul>
                    ${analysis.methodology.map(method => `<li>${method}</li>`).join('')}
                </ul>
            </div>
        `;
    }
    
    let applicationsHtml = '';
    if (analysis.practical_applications && analysis.practical_applications.length > 0) {
        applicationsHtml = `
            <div class="analysis-section">
                <h3>Practical Applications</h3>
                <ul>
                    ${analysis.practical_applications.map(app => `<li>${app}</li>`).join('')}
                </ul>
            </div>
        `;
    }
    
    let gapsHtml = '';
    if (analysis.knowledge_gaps && analysis.knowledge_gaps.length > 0) {
        gapsHtml = `
            <div class="analysis-section">
                <h3>Knowledge Gaps & Future Research</h3>
                <ul>
                    ${analysis.knowledge_gaps.map(gap => `<li>${gap}</li>`).join('')}
                </ul>
            </div>
        `;
    }
    
    // Combine all sections into final HTML
    analysisContainer.innerHTML = `
        <h2>Publication Analysis</h2>
        <div class="analysis-overview">
            <div class="analysis-metric">
                <span class="metric-label">Technical Complexity</span>
                <span class="metric-value">${analysis.technical_complexity}/5</span>
            </div>
            <div class="analysis-metric">
                <span class="metric-label">Temporal Context</span>
                <span class="metric-value">${analysis.temporal_context}</span>
            </div>
        </div>
        
        ${topicsHtml}
        ${findingsHtml}
        ${methodologyHtml}
        ${applicationsHtml}
        ${gapsHtml}
        
        <div class="analysis-citation">
            <h3>Citation Context</h3>
            <p>${analysis.citation_context}</p>
        </div>
    `;
}

/**
 * Update action buttons based on publication availability
 */
function updateActionButtons(publication) {
    const viewFullTextBtn = document.getElementById('view-full-text');
    if (viewFullTextBtn) {
        if (publication.url) {
            viewFullTextBtn.href = publication.url;
            viewFullTextBtn.target = '_blank';
        } else if (publication.doi) {
            viewFullTextBtn.href = `https://doi.org/${publication.doi}`;
            viewFullTextBtn.target = '_blank';
        } else {
            viewFullTextBtn.addEventListener('click', function(e) {
                e.preventDefault();
                alert('Full text URL is not available for this publication.');
            });
            viewFullTextBtn.classList.add('btn-disabled');
        }
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
 * Format authors for display
 */
function formatAuthors(authors) {
    if (!authors || authors.length === 0) return 'Unknown Authors';
    
    if (authors.length <= 3) {
        return authors.join(', ');
    } else {
        return `${authors.slice(0, 3).join(', ')} et al.`;
    }
}

/**
 * Format number with comma separators
 */
function formatNumber(num) {
    return num.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ",");
}

/**
 * Format date in readable format
 */
function formatDate(dateString) {
    const options = { year: 'numeric', month: 'long', day: 'numeric' };
    return new Date(dateString).toLocaleDateString(undefined, options);
}

/**
 * Save a publication to saved list
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
            year: publication.publication_date ? new Date(publication.publication_date).getFullYear() : 'Unknown',
            saved_at: new Date().toISOString()
        });
        
        // Save back to localStorage
        localStorage.setItem('saved_publications', JSON.stringify(savedPublications));
    } catch (error) {
        console.error('Error saving publication:', error);
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
 * Display error message
 */
function displayError(message) {
    const mainContent = document.querySelector('main');
    if (!mainContent) return;
    
    console.error("Displaying error:", message);
    
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
    
    // Clear existing content and show error
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