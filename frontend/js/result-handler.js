/**
 * LitFinder - Results Handler
 * Manages and displays search results for literature search
 */

document.addEventListener('DOMContentLoaded', function() {
    console.log("Result handler initialized");
    
    // Check if we're on the results page
    const publicationsContainer = document.getElementById('publications-container');
    if (!publicationsContainer) {
        console.log('Not on results page - publications container not found');
        return;
    }
    
    console.log('On results page - initializing');
    
    // Initialize the results page
    initializeResultsPage();
    
    // Set up filter and sort functionality
    initializeFiltersAndSorting();
});

/**
 * Initialize the results page with query data and results
 */
async function initializeResultsPage() {
    try {
        console.log("Initializing results page");
        
        // Show loading indicator if available
        if (typeof window.showLoading === 'function') {
            window.showLoading("Loading search results...");
        }
        
        // Get stored search results from session storage
        const searchResultsJson = sessionStorage.getItem('search_results');
        if (!searchResultsJson) {
            console.error('No search results found in session storage');
            displayErrorMessage('No search results found. Please try a new search.');
            return;
        }
        
        console.log('Retrieved search results from session storage');
        
        let searchResults;
        try {
            searchResults = JSON.parse(searchResultsJson);
            console.log('Parsed search results:', searchResults);
        } catch (parseError) {
            console.error('Error parsing search results JSON:', parseError);
            displayErrorMessage('Error loading search results. Please try a new search.');
            return;
        }
        
        // Check if results were found
        if (searchResults.status !== 'success') {
            console.error('Search results status not success:', searchResults.status);
            displayErrorMessage(searchResults.message || 'Error retrieving search results');
            return;
        }
        
        // Display query information
        displayQuerySummary(searchResults);
        
        // Display publication results
        if (searchResults.results && searchResults.results.length > 0) {
            console.log(`Displaying ${searchResults.results.length} publication results`);
            displayPublicationResults(searchResults.results);
            updateResultsCount(searchResults.results.length);
        } else {
            console.log('No publication results to display');
            displayNoResults();
        }
        
        // Display analysis if available
        if (searchResults.analysis) {
            console.log('Displaying analysis');
            displayAnalysis(searchResults.analysis);
        }
        
        // Display interdisciplinary analysis if available
        const isInterdisciplinary = sessionStorage.getItem('is_interdisciplinary') === 'true';
        if (isInterdisciplinary && searchResults.interdisciplinary_analysis) {
            console.log('Displaying interdisciplinary analysis');
            displayInterdisciplinaryAnalysis(searchResults.interdisciplinary_analysis, searchResults.interdisciplinary_synthesis);
        }
        
        // Set up Modify Search button
        setupModifySearchButton();
        
    } catch (error) {
        console.error('Error initializing results page:', error);
        displayErrorMessage('There was an error loading the results. Please try a new search.');
    } finally {
        // Hide loading indicator if available
        if (typeof window.hideLoading === 'function') {
            window.hideLoading();
        }
    }
}

/**
 * Display query summary information
 */
function displayQuerySummary(searchResults) {
    console.log('Displaying query summary');
    
    // Original query from session storage
    const originalQuery = sessionStorage.getItem('original_query');
    console.log('Original query:', originalQuery);
    
    // Set original query text
    const queryTextElement = document.getElementById('original-query');
    if (queryTextElement && originalQuery) {
        queryTextElement.textContent = originalQuery;
    } else if (queryTextElement) {
        queryTextElement.textContent = 'Query not available';
    }
    
    // Get structured query from search results
    const structuredQuery = searchResults.structured_query;
    if (!structuredQuery) {
        console.warn('No structured query in search results');
        return;
    }
    
    console.log('Structured query:', structuredQuery);
    
    // Set research areas tags
    const researchAreasContainer = document.getElementById('research-areas-tags');
    if (researchAreasContainer && structuredQuery.research_areas) {
        researchAreasContainer.innerHTML = '';
        
        structuredQuery.research_areas.forEach(area => {
            const tag = document.createElement('span');
            tag.className = 'tag';
            tag.textContent = area;
            researchAreasContainer.appendChild(tag);
        });
    }
    
    // Set expertise/topics tags
    const topicsContainer = document.getElementById('expertise-tags');
    if (topicsContainer && structuredQuery.expertise) {
        topicsContainer.innerHTML = '';
        
        structuredQuery.expertise.forEach(item => {
            const tag = document.createElement('span');
            tag.className = 'tag';
            tag.textContent = item;
            topicsContainer.appendChild(tag);
        });
    }
}

/**
 * Display publication results
 */
function displayPublicationResults(publications) {
    console.log(`Creating ${publications.length} publication cards`);
    
    const container = document.getElementById('publications-container');
    if (!container) {
        console.error('Publications container not found');
        return;
    }
    
    container.innerHTML = '';
    
    publications.forEach((publication, index) => {
        console.log(`Creating card for publication ${index + 1}:`, publication.title);
        const publicationCard = createPublicationCard(publication);
        container.appendChild(publicationCard);
    });
}

/**
 * Create a publication card element
 */
function createPublicationCard(publication) {
    const card = document.createElement('div');
    card.className = 'publication-card';
    
    // Get top topic match for display
    let topTopic = ['No matching topic', 0];
    if (publication.topic_matches && Object.keys(publication.topic_matches).length > 0) {
        topTopic = Object.entries(publication.topic_matches)
            .sort((a, b) => b[1] - a[1])
            .slice(0, 1)[0];
    }
    
    // Format publication date
    let pubDate = 'N/A';
    if (publication.publication_date) {
        try {
            pubDate = new Date(publication.publication_date).getFullYear();
        } catch (e) {
            console.warn('Error formatting date:', e);
            pubDate = publication.publication_date;
        }
    }
    
    // Truncate abstract
    let abstract = 'No abstract available.';
    if (publication.abstract) {
        abstract = publication.abstract.length > 250 ? 
            publication.abstract.substring(0, 250) + '...' : 
            publication.abstract;
    }
    
    // Determine publication type icon and label
    let pubTypeIcon = 'fas fa-file-alt';
    let pubTypeLabel = 'Publication';
    
    switch (publication.type) {
        case 'journal-article':
            pubTypeIcon = 'fas fa-book';
            pubTypeLabel = 'Journal Article';
            break;
        case 'conference-paper':
            pubTypeIcon = 'fas fa-users';
            pubTypeLabel = 'Conference Paper';
            break;
        case 'review':
            pubTypeIcon = 'fas fa-star';
            pubTypeLabel = 'Review';
            break;
        case 'book-chapter':
            pubTypeIcon = 'fas fa-bookmark';
            pubTypeLabel = 'Book Chapter';
            break;
        case 'preprint':
            pubTypeIcon = 'fas fa-file-alt';
            pubTypeLabel = 'Preprint';
            break;
    }
    
    const topicPercentage = Math.round((topTopic[1] || 0) * 100);
    
    card.innerHTML = `
        <div class="publication-info">
            <h3 class="publication-title">${publication.title || 'Untitled Publication'}</h3>
            <p class="publication-authors">${formatAuthors(publication.authors || [])}</p>
            <p class="publication-source">
                <span class="journal-name">${publication.journal || 'Unknown Source'}</span>, 
                <span class="publication-year">${pubDate}</span>
            </p>
            <div class="publication-metrics">
                <span><i class="fas fa-quote-right"></i> ${formatNumber(publication.citations || 0)} Citations</span>
                <span><i class="${pubTypeIcon}"></i> ${pubTypeLabel}</span>
                ${publication.open_access ? '<span><i class="fas fa-unlock"></i> Open Access</span>' : ''}
            </div>
            <div class="publication-abstract">
                <p>${abstract}</p>
            </div>
            <div class="relevance-match">
                <h4>Topic Match:</h4>
                <div class="match-bars">
                    <div class="match-item">
                        <span>${topTopic[0]}</span>
                        <div class="progress-bar">
                            <div class="progress" style="width: ${topicPercentage}%"></div>
                        </div>
                        <span>${topicPercentage}%</span>
                    </div>
                </div>
            </div>
        </div>
        <div class="publication-actions">
            <a href="publication.html?id=${publication.id}" class="btn btn-primary">View Details</a>
            <button class="btn btn-outline save-publication" data-id="${publication.id}">
                <i class="fas fa-bookmark"></i> Save
            </button>
        </div>
    `;
    
    // Add event listener for save button
    const saveButton = card.querySelector('.save-publication');
    saveButton.addEventListener('click', function() {
        savePublication(publication);
        this.innerHTML = '<i class="fas fa-check"></i> Saved';
        this.disabled = true;
    });
    
    return card;
}

/**
 * Format author names for display
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
 * Update the results count display
 */
function updateResultsCount(count) {
    const countElement = document.querySelector('#results-count span');
    if (countElement) {
        countElement.textContent = count;
    }
    
    // Update pagination if available
    updatePagination(count);
}

/**
 * Update pagination display
 */
function updatePagination(totalResults) {
    const paginationInfo = document.querySelector('.pagination-info');
    if (!paginationInfo) return;
    
    const resultsPerPage = 10;
    const totalPages = Math.ceil(totalResults / resultsPerPage);
    
    paginationInfo.textContent = `Page 1 of ${totalPages}`;
    
    // Enable/disable next/prev buttons
    const prevButton = document.querySelector('.pagination button:first-child');
    const nextButton = document.querySelector('.pagination button:last-child');
    
    if (prevButton) prevButton.disabled = true;
    if (nextButton) nextButton.disabled = totalPages <= 1;
}

/**
 * Display a message when no results are found
 */
function displayNoResults() {
    const container = document.getElementById('publications-container');
    if (!container) return;
    
    container.innerHTML = `
        <div class="no-results">
            <i class="fas fa-search"></i>
            <h3>No matching publications found</h3>
            <p>Try adjusting your search criteria or broadening your research areas.</p>
            <button id="new-search" class="btn btn-primary">
                <i class="fas fa-redo"></i> Try a New Search
            </button>
        </div>
    `;
    
    // Add event listener for new search button
    const newSearchButton = document.getElementById('new-search');
    if (newSearchButton) {
        newSearchButton.addEventListener('click', function() {
            window.location.href = '/';
        });
    }
    
    // Update count to zero
    updateResultsCount(0);
}

/**
 * Display error message
 */
function displayErrorMessage(message) {
    console.error('Displaying error message:', message);
    
    const container = document.getElementById('publications-container');
    if (!container) return;
    
    container.innerHTML = `
        <div class="error-message">
            <i class="fas fa-exclamation-circle"></i>
            <h3>Error</h3>
            <p>${message}</p>
            <button id="return-home" class="btn btn-primary">
                <i class="fas fa-home"></i> Return to Home
            </button>
        </div>
    `;
    
    // Add event listener for return home button
    const returnButton = document.getElementById('return-home');
    if (returnButton) {
        returnButton.addEventListener('click', function() {
            window.location.href = '/';
        });
    }
}

/**
 * Redirect to home page
 */
function redirectToHome() {
    window.location.href = '/';
}

/**
 * Setup the Modify Search button
 */
function setupModifySearchButton() {
    const modifyButton = document.getElementById('modify-search');
    if (!modifyButton) return;
    
    modifyButton.addEventListener('click', function() {
        window.location.href = '/';
    });
}

/**
 * Display analysis results if available
 */
function displayAnalysis(analysis) {
    // Check if analysis container exists
    const analysisContainer = document.getElementById('analysis-container');
    if (!analysisContainer) return;
    
    // Make analysis container visible
    analysisContainer.classList.remove('hidden');
    
    // Display literature summary if available
    if (analysis.literature_summary) {
        const summaryContainer = document.getElementById('literature-summary');
        if (summaryContainer) {
            const summary = analysis.literature_summary;
            
            let summaryHtml = '<h3>Literature Summary</h3>';
            
            if (summary.top_themes && summary.top_themes.length > 0) {
                summaryHtml += `<div class="summary-section">
                    <h4>Key Themes</h4>
                    <ul>
                        ${summary.top_themes.map(theme => `<li>${theme}</li>`).join('')}
                    </ul>
                </div>`;
            }
            
            if (summary.consensus_findings && summary.consensus_findings.length > 0) {
                summaryHtml += `<div class="summary-section">
                    <h4>Consensus Findings</h4>
                    <ul>
                        ${summary.consensus_findings.map(finding => `<li>${finding}</li>`).join('')}
                    </ul>
                </div>`;
            }
            
            if (summary.knowledge_gaps && summary.knowledge_gaps.length > 0) {
                summaryHtml += `<div class="summary-section">
                    <h4>Research Gaps</h4>
                    <ul>
                        ${summary.knowledge_gaps.map(gap => `<li>${gap}</li>`).join('')}
                    </ul>
                </div>`;
            }
            
            summaryContainer.innerHTML = summaryHtml;
        }
    }
    
    // Display methodology analysis if available
    if (analysis.methodology_analysis) {
        const methodologyContainer = document.getElementById('methodology-analysis');
        if (methodologyContainer) {
            const methodologyData = analysis.methodology_analysis;
            
            let methodologyHtml = '<h3>Methodology Analysis</h3>';
            
            if (methodologyData.dominant_paradigms && methodologyData.dominant_paradigms.length > 0) {
                methodologyHtml += `<div class="summary-section">
                    <h4>Dominant Research Methods</h4>
                    <ul>
                        ${methodologyData.dominant_paradigms.map(method => `<li>${method}</li>`).join('')}
                    </ul>
                </div>`;
            }
            
            if (methodologyData.innovative_methods && methodologyData.innovative_methods.length > 0) {
                methodologyHtml += `<div class="summary-section">
                    <h4>Innovative Approaches</h4>
                    <ul>
                        ${methodologyData.innovative_methods.map(method => `<li>${method}</li>`).join('')}
                    </ul>
                </div>`;
            }
            
            methodologyContainer.innerHTML = methodologyHtml;
        }
    }
    
    // Display synthesis if available
    if (analysis.synthesis) {
        const synthesisContainer = document.getElementById('research-synthesis');
        if (synthesisContainer) {
            const synthesis = analysis.synthesis;
            
            let synthesisHtml = '<h3>Research Synthesis</h3>';
            
            if (synthesis.research_themes && synthesis.research_themes.length > 0) {
                synthesisHtml += `<div class="summary-section">
                    <h4>Major Research Themes</h4>
                    <ul>
                        ${synthesis.research_themes.map(theme => `<li>${theme}</li>`).join('')}
                    </ul>
                </div>`;
            }
            
            if (synthesis.suggested_directions && synthesis.suggested_directions.length > 0) {
                synthesisHtml += `<div class="summary-section">
                    <h4>Future Research Directions</h4>
                    <ul>
                        ${synthesis.suggested_directions.map(direction => `<li>${direction}</li>`).join('')}
                    </ul>
                </div>`;
            }
            
            synthesisContainer.innerHTML = synthesisHtml;
        }
    }
}

/**
 * Display interdisciplinary analysis if available
 */
function displayInterdisciplinaryAnalysis(interdisciplinaryAnalysis, interdisciplinarySynthesis) {
    // Check if container exists
    const container = document.getElementById('interdisciplinary-analysis');
    if (!container) return;
    
    // Make container visible
    container.classList.remove('hidden');
    
    // Create analysis content
    let analysisHtml = '<h3>Interdisciplinary Research Analysis</h3>';
    
    // Display intersection keywords
    if (interdisciplinaryAnalysis.intersection_keywords && interdisciplinaryAnalysis.intersection_keywords.length > 0) {
        analysisHtml += `<div class="summary-section">
            <h4>Key Interdisciplinary Concepts</h4>
            <div class="tags-container">
                ${interdisciplinaryAnalysis.intersection_keywords.map(keyword => 
                    `<span class="tag">${keyword}</span>`).join('')}
            </div>
        </div>`;
    }
    
    // Display bridging concepts
    if (interdisciplinaryAnalysis.bridging_concepts && interdisciplinaryAnalysis.bridging_concepts.length > 0) {
        analysisHtml += `<div class="summary-section">
            <h4>Bridging Concepts</h4>
            <ul>
                ${interdisciplinaryAnalysis.bridging_concepts.map(concept => 
                    `<li>${concept}</li>`).join('')}
            </ul>
        </div>`;
    }
    
    // Display synthesis if available
    if (interdisciplinarySynthesis) {
        if (interdisciplinarySynthesis.interdisciplinary_significance) {
            analysisHtml += `<div class="summary-section">
                <h4>Significance of This Intersection</h4>
                <p>${interdisciplinarySynthesis.interdisciplinary_significance}</p>
            </div>`;
        }
        
        if (interdisciplinarySynthesis.knowledge_gaps && interdisciplinarySynthesis.knowledge_gaps.length > 0) {
            analysisHtml += `<div class="summary-section">
                <h4>Research Gaps at This Intersection</h4>
                <ul>
                    ${interdisciplinarySynthesis.knowledge_gaps.map(gap => 
                        `<li>${gap}</li>`).join('')}
                </ul>
            </div>`;
        }
        
        if (interdisciplinarySynthesis.future_directions && interdisciplinarySynthesis.future_directions.length > 0) {
            analysisHtml += `<div class="summary-section">
                <h4>Promising Research Directions</h4>
                <ul>
                    ${interdisciplinarySynthesis.future_directions.map(direction => 
                        `<li>${direction}</li>`).join('')}
                </ul>
            </div>`;
        }
    }
    
    container.innerHTML = analysisHtml;
}

/**
 * Initialize filters and sorting functionality
 */
function initializeFiltersAndSorting() {
    // Sort dropdown
    const sortDropdown = document.getElementById('sort-results');
    if (sortDropdown) {
        sortDropdown.addEventListener('change', function() {
            const sortOption = this.value;
            sortPublicationResults(sortOption);
        });
    }
    
    // Publication type checkboxes
    const typeCheckboxes = document.querySelectorAll('.filter-section input[type="checkbox"]');
    typeCheckboxes.forEach(checkbox => {
        checkbox.addEventListener('change', function() {
            applyFilters();
        });
    });
    
    // Year range slider
    const yearSlider = document.getElementById('year-filter');
    if (yearSlider) {
        const minYearValue = document.getElementById('min-year-value');
        
        yearSlider.addEventListener('input', function() {
            if (minYearValue) {
                minYearValue.textContent = this.value;
            }
        });
        
        yearSlider.addEventListener('change', function() {
            applyFilters();
        });
    }
    
    // Citations range slider
    const citationsSlider = document.getElementById('citations-filter');
    if (citationsSlider) {
        const minCitationsValue = document.getElementById('min-citations-value');
        
        citationsSlider.addEventListener('input', function() {
            if (minCitationsValue) {
                minCitationsValue.textContent = this.value;
            }
        });
        
        citationsSlider.addEventListener('change', function() {
            applyFilters();
        });
    }
}

/**
 * Sort publication results based on selected option
 */
function sortPublicationResults(sortOption) {
    // Get search results from session storage
    const searchResultsJson = sessionStorage.getItem('search_results');
    if (!searchResultsJson) return;
    
    const searchResults = JSON.parse(searchResultsJson);
    const publications = searchResults.results;
    
    if (!publications || publications.length === 0) return;
    
    let sortedPublications = [...publications];
    
    switch (sortOption) {
        case 'relevance':
            sortedPublications.sort((a, b) => (b.relevance_score || 0) - (a.relevance_score || 0));
            break;
        case 'citations':
            sortedPublications.sort((a, b) => (b.citations || 0) - (a.citations || 0));
            break;
        case 'recency':
            sortedPublications.sort((a, b) => {
                const dateA = a.publication_date ? new Date(a.publication_date) : new Date(0);
                const dateB = b.publication_date ? new Date(b.publication_date) : new Date(0);
                return dateB - dateA;
            });
            break;
        case 'oldest':
            sortedPublications.sort((a, b) => {
                const dateA = a.publication_date ? new Date(a.publication_date) : new Date(0);
                const dateB = b.publication_date ? new Date(b.publication_date) : new Date(0);
                return dateA - dateB;
            });
            break;
    }
    
    // Display sorted results
    displayPublicationResults(sortedPublications);
}

/**
 * Apply all active filters to publication results
 */
function applyFilters() {
    // Get search results from session storage
    const searchResultsJson = sessionStorage.getItem('search_results');
    if (!searchResultsJson) return;
    
    const searchResults = JSON.parse(searchResultsJson);
    const publications = searchResults.results;
    
    if (!publications || publications.length === 0) return;
    
    // Get filter values
    const minYear = parseInt(document.getElementById('year-filter')?.value || '2000');
    const minCitations = parseInt(document.getElementById('citations-filter')?.value || '0');
    const openAccessOnly = document.querySelector('.filter-group:nth-child(4) input')?.checked || false;
    
    // Get selected publication types
    const selectedTypes = [];
    const typeCheckboxes = document.querySelectorAll('.filter-group:nth-child(1) input[type="checkbox"]');
    typeCheckboxes.forEach((checkbox, index) => {
        if (checkbox.checked) {
            // Map index to publication type
            const types = ['journal-article', 'conference-paper', 'review', 'book-chapter', 'preprint'];
            if (index < types.length) {
                selectedTypes.push(types[index]);
            }
        }
    });
    
    // Apply filters
    let filteredPublications = publications.filter(publication => {
        // Publication year filter
        const pubYear = publication.publication_date ? 
            new Date(publication.publication_date).getFullYear() : 0;
        if (pubYear < minYear && pubYear !== 0) {
            return false;
        }
        
        // Citation count filter
        if ((publication.citations || 0) < minCitations) {
            return false;
        }
        
        // Publication type filter
        if (selectedTypes.length > 0 && publication.type && 
            !selectedTypes.includes(publication.type)) {
            return false;
        }
        
        // Open access filter
        if (openAccessOnly && !publication.open_access) {
            return false;
        }
        
        return true;
    });
    
    // Display filtered results
    displayPublicationResults(filteredPublications);
    updateResultsCount(filteredPublications.length);
}