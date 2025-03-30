/**
 * LitFinder - Results Handler
 * Manages and displays search results for literature search
 */

document.addEventListener('DOMContentLoaded', function() {
    // Check if we're on the results page
    const publicationsContainer = document.getElementById('publications-container');
    if (!publicationsContainer) return;
    
    // Initialize the results page
    initializeResultsPage();
    
    // Set up filter and sort functionality
    initializeFiltersAndSorting();
});

/**
 * Initialize the results page with query data and results
 */
function initializeResultsPage() {
    try {
        // Load query data from session storage
        const queryData = getStoredQueryData();
        if (!queryData) {
            redirectToHome();
            return;
        }
        
        // Display query information
        displayQuerySummary(queryData);
        
        // Load and display publication results
        const publications = getStoredPublicationResults();
        if (publications && publications.length > 0) {
            displayPublicationResults(publications);
            updateResultsCount(publications.length);
        } else {
            displayNoResults();
        }
        
        // Set up Modify Search button
        setupModifySearchButton();
        
    } catch (error) {
        console.error('Error initializing results page:', error);
        displayErrorMessage('There was an error loading the results. Please try a new search.');
    }
}

/**
 * Get stored query data from session storage
 */
function getStoredQueryData() {
    const queryJson = sessionStorage.getItem('research_query');
    const processedQueryJson = sessionStorage.getItem('processed_query');
    
    if (!queryJson) return null;
    
    const queryData = JSON.parse(queryJson);
    
    // Add processed data if available
    if (processedQueryJson) {
        queryData.processed = JSON.parse(processedQueryJson);
    }
    
    return queryData;
}

/**
 * Get stored publication results from session storage
 */
function getStoredPublicationResults() {
    const resultsJson = sessionStorage.getItem('publication_results');
    return resultsJson ? JSON.parse(resultsJson) : null;
}

/**
 * Display query summary information
 */
function displayQuerySummary(queryData) {
    // Set original query text
    const queryTextElement = document.getElementById('original-query');
    if (queryTextElement) {
        queryTextElement.textContent = queryData.query;
    }
    
    // Set research areas tags
    const researchAreasContainer = document.getElementById('research-areas-tags');
    if (researchAreasContainer) {
        researchAreasContainer.innerHTML = '';
        
        const areasToShow = queryData.processed?.research_areas || queryData.research_areas;
        areasToShow.forEach(area => {
            const tag = document.createElement('span');
            tag.className = 'tag';
            tag.textContent = area;
            researchAreasContainer.appendChild(tag);
        });
    }
    
    // Set key topics tags
    const topicsContainer = document.getElementById('expertise-tags');
    if (topicsContainer) {
        topicsContainer.innerHTML = '';
        
        const topicsToShow = queryData.processed?.expertise || queryData.expertise;
        topicsToShow.forEach(item => {
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
    const container = document.getElementById('publications-container');
    if (!container) return;
    
    container.innerHTML = '';
    
    publications.forEach(publication => {
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
    const topTopic = Object.entries(publication.topic_matches || {})
        .sort((a, b) => b[1] - a[1])
        .slice(0, 1)[0] || ['No matching topic', 0];
    
    // Format publication date
    const pubDate = publication.publication_date ? 
        new Date(publication.publication_date).getFullYear() : 'N/A';
    
    // Truncate abstract
    const abstract = publication.abstract ? 
        (publication.abstract.length > 250 ? 
            publication.abstract.substring(0, 250) + '...' : 
            publication.abstract) : 
        'No abstract available.';
    
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
    
    const topicPercentage = Math.round(topTopic[1] * 100);
    
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
            year: new Date(publication.publication_date).getFullYear(),
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
            window.location.href = 'index.html';
        });
    }
    
    // Update count to zero
    updateResultsCount(0);
}

/**
 * Display error message
 */
function displayErrorMessage(message) {
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
            window.location.href = 'index.html';
        });
    }
}

/**
 * Redirect to home page
 */
function redirectToHome() {
    window.location.href = 'index.html';
}

/**
 * Setup the Modify Search button
 */
function setupModifySearchButton() {
    const modifyButton = document.getElementById('modify-search');
    if (!modifyButton) return;
    
    modifyButton.addEventListener('click', function() {
        window.location.href = 'index.html';
    });
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
    const publications = getStoredPublicationResults();
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
    const publications = getStoredPublicationResults();
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