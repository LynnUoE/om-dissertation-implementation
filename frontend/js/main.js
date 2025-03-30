/**
 * ResearchMatch - Main JavaScript
 * Global functionality shared across all pages
 */

document.addEventListener('DOMContentLoaded', function() {
    // Initialize common UI elements
    initializeTagsInput();
    initializeTabsSystem();
    setupFormValidation();
    
    // Setup loading indicator for API calls
    setupLoadingIndicator();
});

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
    window.showLoading = function() {
        const overlay = document.getElementById('loading-overlay');
        if (overlay) {
            overlay.classList.remove('hidden');
        }
    };
    
    window.hideLoading = function() {
        const overlay = document.getElementById('loading-overlay');
        if (overlay) {
            overlay.classList.add('hidden');
        }
    };
}

/**
 * Utility function for API calls
 */
async function apiCall(endpoint, method = 'GET', data = null) {
    const apiBaseUrl = '/api'; // Base URL for API endpoints
    const url = `${apiBaseUrl}${endpoint}`;
    
    const options = {
        method,
        headers: {
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }
    };
    
    if (data && (method === 'POST' || method === 'PUT')) {
        options.body = JSON.stringify(data);
    }
    
    try {
        window.showLoading();
        const response = await fetch(url, options);
        
        if (!response.ok) {
            throw new Error(`API error: ${response.status}`);
        }
        
        const result = await response.json();
        return result;
    } catch (error) {
        console.error('API call failed:', error);
        throw error;
    } finally {
        window.hideLoading();
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
 * Generate a truncated text with ellipsis
 */
function truncateText(text, maxLength) {
    if (text.length <= maxLength) return text;
    return text.substr(0, maxLength) + '...';
}