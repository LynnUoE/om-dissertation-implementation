/**
 * LitFinder - Main JavaScript
 * Global functionality shared across all pages
 */

// Define loading indicator functions immediately to ensure they're available
window.showLoading = function(message) {
    console.log('Loading started:', message || 'Processing request...');
    
    // Create a loading overlay if it doesn't exist
    let loadingOverlay = document.getElementById('loading-overlay');
    if (!loadingOverlay) {
        loadingOverlay = document.createElement('div');
        loadingOverlay.id = 'loading-overlay';
        loadingOverlay.className = 'loading-overlay';
        loadingOverlay.innerHTML = `
            <div class="spinner"></div>
            <p>${message || 'Processing your request...'}</p>
        `;
        
        // Add styles if not already in CSS
        if (!document.querySelector('style#loading-styles')) {
            const style = document.createElement('style');
            style.id = 'loading-styles';
            style.textContent = `
                .loading-overlay {
                    position: fixed;
                    top: 0;
                    left: 0;
                    right: 0;
                    bottom: 0;
                    background-color: rgba(0, 0, 0, 0.7);
                    display: flex;
                    flex-direction: column;
                    justify-content: center;
                    align-items: center;
                    z-index: 9999;
                    color: white;
                }
                .spinner {
                    width: 50px;
                    height: 50px;
                    border: 5px solid rgba(255, 255, 255, 0.3);
                    border-top-color: white;
                    border-radius: 50%;
                    animation: spin 1s linear infinite;
                    margin-bottom: 15px;
                }
                @keyframes spin {
                    to { transform: rotate(360deg); }
                }
            `;
            document.head.appendChild(style);
        }
        
        document.body.appendChild(loadingOverlay);
    } else {
        loadingOverlay.style.display = 'flex';
        const messageElement = loadingOverlay.querySelector('p');
        if (messageElement && message) {
            messageElement.textContent = message;
        }
    }
};

window.hideLoading = function() {
    console.log('Loading finished');
    const loadingOverlay = document.getElementById('loading-overlay');
    if (loadingOverlay) {
        loadingOverlay.style.display = 'none';
    }
};

document.addEventListener('DOMContentLoaded', function() {
    // Check if elements exist before initializing
    const tagsInputContainers = document.querySelectorAll('.tags-input');
    if (tagsInputContainers && tagsInputContainers.length > 0) {
        initializeTagsInput();
    } else {
        console.log("No tags input containers found on this page");
    }
    
    // Initialize other UI components with similar checks
    const tabButtons = document.querySelectorAll('.tab-btn');
    if (tabButtons && tabButtons.length > 0) {
        initializeTabsSystem();
    }
    
    const forms = document.querySelectorAll('form');
    if (forms && forms.length > 0) {
        setupFormValidation();
    }
    // Initialize common UI elements
    initializeTagsInput();
    initializeTabsSystem();
    setupFormValidation();
    
    // Check API health on startup
    checkApiHealth();
    
    // Load saved publications if on saved publications page
    if (document.getElementById('saved-publications-container')) {
        loadSavedPublications();
    }
});

/**
 * Check API health to ensure backend is reachable
 */
async function checkApiHealth() {
    try {
        // Only check health on the home page
        if (!document.getElementById('research-query-form')) {
            return;
        }
        
        const healthStatus = await ApiService.checkHealth();
        
        if (healthStatus.status !== 'healthy') {
            showApiWarning();
        }
    } catch (error) {
        console.error('API Health check failed:', error);
        showApiWarning();
    }
}

/**
 * Show API warning message if backend is unreachable
 */
function showApiWarning() {
    const warningContainer = document.createElement('div');
    warningContainer.className = 'api-warning';
    warningContainer.innerHTML = `
        <div class="warning-content">
            <i class="fas fa-exclamation-triangle"></i>
            <span>Warning: Could not connect to the search backend. Some features may be unavailable.</span>
        </div>
    `;
    
    document.body.insertBefore(warningContainer, document.body.firstChild);
}

/**
 * Tags Input Component
 * Allows users to input multiple tags (research areas, expertise)
 */
function initializeTagsInput() {
    const tagsContainers = document.querySelectorAll('.tags-input');
    
    tagsContainers.forEach(container => {
        const input = container.querySelector('input');
        
        if (!input) return;
        
        input.addEventListener('keydown', function(e) {
            if (e.key === 'Enter' || e.key === ',') {
                e.preventDefault();
                
                const value = this.value.trim();
                if (value) {
                    addTag(container, value);
                    this.value = '';
                }
            }
        });
        
        // Add predefined tags if found in data attribute
        const predefinedTags = container.dataset.tags;
        if (predefinedTags) {
            const tags = predefinedTags.split(',');
            tags.forEach(tag => {
                if (tag.trim()) {
                    addTag(container, tag.trim());
                }
            });
        }
    });
}

/**
 * Add new tag to a tags input container
 */
function addTag(container, text) {
    const tag = document.createElement('span');
    tag.classList.add('tag');
    tag.innerHTML = `
        ${text}
        <span class="tag-remove">&times;</span>
    `;
    
    // Add remove event listener
    tag.querySelector('.tag-remove').addEventListener('click', function() {
        tag.remove();
    });
    
    // Insert before the input
    const input = container.querySelector('input');
    container.insertBefore(tag, input);
}

/**
 * Get all tags from a specific container
 */
function getTags(containerId) {
    const container = document.getElementById(containerId);
    if (!container) return [];
    
    const tags = container.querySelectorAll('.tag');
    return Array.from(tags).map(tag => {
        // Get text without the remove button
        return tag.textContent.trim().replace('×', '');
    });
}

/**
 * Tabs System
 * For navigating between different content sections
 */
function initializeTabsSystem() {
    const tabButtons = document.querySelectorAll('.tab-btn');
    
    tabButtons.forEach(button => {
        button.addEventListener('click', function() {
            const tabId = this.dataset.tab;
            const tabContainer = this.closest('.tabs-container');
            
            // Remove active class from all tabs
            tabContainer.querySelectorAll('.tab-btn').forEach(btn => {
                btn.classList.remove('active');
            });
            
            // Hide all tab contents
            tabContainer.querySelectorAll('.tab-content').forEach(content => {
                content.classList.remove('active');
            });
            
            // Activate current tab and content
            this.classList.add('active');
            document.getElementById(`${tabId}-tab`).classList.add('active');
        });
    });
}

/**
 * Form validation
 * Basic validation for all forms
 */
function setupFormValidation() {
    const forms = document.querySelectorAll('form');
    
    forms.forEach(form => {
        form.addEventListener('submit', function(e) {
            let isValid = true;
            
            // Check required fields
            const requiredFields = form.querySelectorAll('[required]');
            requiredFields.forEach(field => {
                if (!field.value.trim()) {
                    isValid = false;
                    highlightInvalidField(field);
                } else {
                    removeFieldHighlight(field);
                }
            });
            
            // Check tag inputs (require at least one tag)
            const tagContainers = form.querySelectorAll('.tags-input[data-required="true"]');
            tagContainers.forEach(container => {
                const tags = container.querySelectorAll('.tag');
                if (tags.length === 0) {
                    isValid = false;
                    highlightInvalidField(container);
                } else {
                    removeFieldHighlight(container);
                }
            });
            
            if (!isValid) {
                e.preventDefault();
                showValidationMessage(form);
            }
        });
    });
}

/**
 * Highlight invalid form field
 */
function highlightInvalidField(field) {
    field.classList.add('invalid');
    field.addEventListener('input', function onInput() {
        field.classList.remove('invalid');
        field.removeEventListener('input', onInput);
    }, { once: true });
}

/**
 * Remove highlight from a form field
 */
function removeFieldHighlight(field) {
    field.classList.remove('invalid');
}

/**
 * Show validation error message
 */
function showValidationMessage(form) {
    // Check if message already exists
    let message = form.querySelector('.validation-message');
    
    if (!message) {
        message = document.createElement('div');
        message.classList.add('validation-message');
        message.textContent = 'Please fill in all required fields';
        
        // Add to beginning of form or form actions
        const formActions = form.querySelector('.form-actions');
        if (formActions) {
            formActions.insertBefore(message, formActions.firstChild);
        } else {
            form.insertBefore(message, form.firstChild);
        }
    }
    
    // Highlight message with animation
    message.classList.add('show');
    setTimeout(() => message.classList.remove('show'), 100);
}

/**
 * Loading indicator for API calls
 */
function setupLoadingIndicator() {
    // Create loading overlay if it doesn't exist
    let loadingOverlay = document.getElementById('loading-overlay');
    
    if (!loadingOverlay) {
        loadingOverlay = document.createElement('div');
        loadingOverlay.id = 'loading-overlay';
        loadingOverlay.className = 'hidden';
        loadingOverlay.innerHTML = `
            <div class="spinner"></div>
            <p>Processing your request...</p>
        `;
        document.body.appendChild(loadingOverlay);
    }
    
    window.showLoading = function(message) {
        if (message) {
            const messageElement = loadingOverlay.querySelector('p');
            if (messageElement) {
                messageElement.textContent = message;
            }
        }
        loadingOverlay.classList.remove('hidden');
    };
    
    window.hideLoading = function() {
        loadingOverlay.classList.add('hidden');
        // Reset default message
        const messageElement = loadingOverlay.querySelector('p');
        if (messageElement) {
            messageElement.textContent = 'Processing your request...';
        }
    };
}

/**
 * Load and display saved publications
 */
function loadSavedPublications() {
    const container = document.getElementById('saved-publications-container');
    if (!container) return;
    
    // Get saved publications from localStorage
    const savedJson = localStorage.getItem('saved_publications');
    const savedPublications = savedJson ? JSON.parse(savedJson) : [];
    
    if (savedPublications.length === 0) {
        container.innerHTML = `
            <div class="no-saved-items">
                <i class="fas fa-bookmark"></i>
                <h3>No Saved Publications</h3>
                <p>Publications you save will appear here for easy reference.</p>
                <a href="index.html" class="btn btn-primary">Search for Publications</a>
            </div>
        `;
        return;
    }
    
    // Sort by date saved (most recent first)
    savedPublications.sort((a, b) => {
        const dateA = new Date(a.saved_at);
        const dateB = new Date(b.saved_at);
        return dateB - dateA;
    });
    
    // Create list of saved publications
    const savedList = document.createElement('div');
    savedList.className = 'saved-publications-list';
    
    savedPublications.forEach(publication => {
        const item = document.createElement('div');
        item.className = 'saved-publication-item';
        
        item.innerHTML = `
            <div class="publication-info">
                <h3 class="publication-title">${publication.title}</h3>
                <p class="publication-authors">${publication.authors.join(', ')}</p>
                <p class="publication-source">
                    <span class="journal-name">${publication.journal || 'Unknown Source'}</span>, 
                    <span class="publication-year">${publication.year}</span>
                </p>
                <p class="saved-date">Saved on ${formatDate(publication.saved_at)}</p>
            </div>
            <div class="publication-actions">
                <a href="publication.html?id=${publication.id}" class="btn btn-primary">View Details</a>
                <button class="btn btn-outline remove-publication" data-id="${publication.id}">
                    <i class="fas fa-trash"></i> Remove
                </button>
            </div>
        `;
        
        savedList.appendChild(item);
    });
    
    // Add clear all button
    const clearAllSection = document.createElement('div');
    clearAllSection.className = 'clear-all-section';
    clearAllSection.innerHTML = `
        <button id="clear-all-saved" class="btn btn-outline">
            <i class="fas fa-trash-alt"></i> Clear All Saved Publications
        </button>
    `;
    
    // Clear container and add elements
    container.innerHTML = '';
    container.appendChild(savedList);
    container.appendChild(clearAllSection);
    
    // Add event listeners for remove buttons
    document.querySelectorAll('.remove-publication').forEach(button => {
        button.addEventListener('click', function() {
            const pubId = this.dataset.id;
            removeSavedPublication(pubId);
            // Remove the item from the DOM
            this.closest('.saved-publication-item').remove();
            
            // Check if we have any left
            if (document.querySelectorAll('.saved-publication-item').length === 0) {
                loadSavedPublications(); // Reload to show empty state
            }
        });
    });
    
    // Add event listener for clear all button
    document.getElementById('clear-all-saved').addEventListener('click', function() {
        if (confirm('Are you sure you want to remove all saved publications?')) {
            localStorage.removeItem('saved_publications');
            loadSavedPublications(); // Reload to show empty state
        }
    });
}

/**
 * Remove a saved publication
 */
function removeSavedPublication(publicationId) {
    const savedJson = localStorage.getItem('saved_publications');
    if (!savedJson) return;
    
    const savedPublications = JSON.parse(savedJson);
    const updatedPublications = savedPublications.filter(pub => pub.id !== publicationId);
    
    localStorage.setItem('saved_publications', JSON.stringify(updatedPublications));
}

/**
 * Format date in readable format
 */
function formatDate(dateString) {
    const options = { year: 'numeric', month: 'long', day: 'numeric' };
    return new Date(dateString).toLocaleDateString(undefined, options);
}

/**
 * Format number with comma separators
 */
function formatNumber(num) {
    return num.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ",");
}