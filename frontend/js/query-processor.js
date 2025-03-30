/**
 * LitFinder - Query Processor
 * Handles research query submission and processing
 */

document.addEventListener('DOMContentLoaded', function() {
    // For the query form
    const queryForm = document.getElementById('research-query-form');
    if (queryForm) {
        initializeQueryForm(queryForm);
    }

    // Safely initialize other forms only if they exist
    const interdisciplinaryForm = document.getElementById('interdisciplinary-search-form');
    if (interdisciplinaryForm) {
        initializeInterdisciplinaryForm(interdisciplinaryForm);
    }

    const advancedSearchForm = document.getElementById('advanced-search-form');
    if (advancedSearchForm) {
        initializeAdvancedSearchForm(advancedSearchForm);
    }
});

/**
 * Initialize the query form with event handlers
 */
function initializeQueryForm(form) {
    // Handle form submission
    form.addEventListener('submit', async function(e) {
        e.preventDefault();
        
        try {
            // Validate form before submission
            if (!validateQueryForm(form)) {
                return;
            }
            
            // Show loading indicator
            if (typeof window.showLoading === 'function') {
                window.showLoading("Processing your search query...");
            }
            
            // Get form data
            const queryData = getQueryFormData(form);
            
            // Store the original query for displaying on results page
            sessionStorage.setItem('original_query', queryData.query);
            
            console.log("Processing query:", queryData.query);
            
            // Perform the literature search
            const searchOptions = {
                max_results: 20,
                analyze_results: true
            };
            
            // Add year range if specified
            const yearFrom = document.getElementById('year-from');
            const yearTo = document.getElementById('year-to');
            
            if (yearFrom && yearFrom.value) {
                searchOptions.from_year = parseInt(yearFrom.value);
            }
            
            if (yearTo && yearTo.value) {
                searchOptions.to_year = parseInt(yearTo.value);
            }
            
            // Add publication type if specified
            const publicationType = document.getElementById('publication-type');
            if (publicationType && publicationType.value !== 'all') {
                searchOptions.publication_types = [publicationType.value];
            }
            
            // Check for open access filter
            const openAccessFilter = document.querySelector('input[name="open-access-filter"]');
            if (openAccessFilter && openAccessFilter.checked) {
                searchOptions.open_access_only = true;
            }
            
            // Perform the search
            console.log("Sending search request with options:", searchOptions);
            
            try {
                const searchResult = await ApiService.searchLiterature(queryData.query, searchOptions);
                
                // Add validation for search result structure
                if (!searchResult) {
                    throw new Error('Received empty response from search API');
                }
                
                if (searchResult.status !== 'success') {
                    throw new Error(searchResult.message || 'Error searching literature');
                }
                
                // Ensure search result has expected properties
                if (!searchResult.results) {
                    console.warn('Search response is missing results array');
                    searchResult.results = [];
                }
                
                if (!searchResult.structured_query) {
                    searchResult.structured_query = {};
                }
                
                // Store search results for the results page
                sessionStorage.setItem('search_results', JSON.stringify(searchResult));
                
                // Navigate to results page
                window.location.href = '/result.html';
            } catch (searchError) {
                console.error('Search API error:', searchError);
                alert(`Search failed: ${searchError.message || 'Unknown error'}`);
            }
            
        } catch (error) {
            console.error('Error processing query:', error);
            
            // Provide a more descriptive message based on the error
            let errorMessage = 'There was an error processing your query. Please try again.';
            
            if (error.message.includes('NoneType')) {
                errorMessage = 'Unable to retrieve search results. The external research database may be unavailable.';
            } else if (error.message.includes('API error: 5')) {
                errorMessage = 'Cannot connect to the search server. Please try again later.';
            }
            
            alert(errorMessage);
        } finally {
            // Hide loading indicator
            if (typeof window.hideLoading === 'function') {
                window.hideLoading();
            }
        }
    });
    
    // Setup example queries if dropdown exists
    const exampleDropdown = document.getElementById('example-queries');
    if (exampleDropdown) {
        exampleDropdown.addEventListener('change', function() {
            if (this.value) {
                loadExampleQuery(this.value, form);
            }
        });
    }

    // Initialize tags input fields
    initializeTagsInput(form);
}

/**
 * Initialize advanced search form
 */
function initializeAdvancedSearchForm(form) {
    form.addEventListener('submit', async function(e) {
        e.preventDefault();
        
        try {
            // Validate the form
            if (!validateAdvancedSearchForm(form)) {
                return;
            }
            
            // Show loading indicator with safe check
            if (typeof window.showLoading === 'function') {
                window.showLoading("Processing advanced search...");
            }
            
            // Get form data
            const researchAreas = getTags('research-areas-container');
            const specificTopics = getTags('specific-topics-container');
            const methodologies = getTags('methodologies-container');
            
            if (researchAreas.length === 0) {
                throw new Error('At least one research area is required');
            }
            
            // Prepare search options
            const searchOptions = {
                max_results: 20
            };
            
            // Add year range if specified
            const yearFrom = document.getElementById('year-from');
            const yearTo = document.getElementById('year-to');
            
            if (yearFrom && yearFrom.value) {
                searchOptions.from_year = parseInt(yearFrom.value);
            }
            
            if (yearTo && yearTo.value) {
                searchOptions.to_year = parseInt(yearTo.value);
            }
            
            // Perform advanced search
            const searchResult = await ApiService.advancedSearch(
                researchAreas,
                specificTopics,
                methodologies,
                searchOptions
            );
            
            // Validate the search result
            if (!searchResult) {
                throw new Error('Received empty response from search API');
            }
            
            if (searchResult.status !== 'success') {
                throw new Error(searchResult.message || 'Error performing advanced search');
            }
            
            // Ensure result has expected properties
            if (!searchResult.results) {
                searchResult.results = [];
            }
            
            if (!searchResult.structured_query) {
                searchResult.structured_query = {};
            }
            
            // Create a synthetic query for display purposes
            const syntheticQuery = `Research in ${researchAreas.join(', ')}`;
            sessionStorage.setItem('original_query', syntheticQuery);
            
            // Store search results
            sessionStorage.setItem('search_results', JSON.stringify(searchResult));
            
            // Navigate to results page
            window.location.href = '/result.html';
            
        } catch (error) {
            console.error('Error performing advanced search:', error);
            alert(`Advanced search error: ${error.message}`);
        } finally {
            // Hide loading indicator with safe check
            if (typeof window.hideLoading === 'function') {
                window.hideLoading();
            }
        }
    });

    // Initialize tags input fields if the form exists
    if (form) {
        initializeTagsInput(form);
    }
}

/**
 * Initialize interdisciplinary search form
 */
function initializeInterdisciplinaryForm(form) {
    form.addEventListener('submit', async function(e) {
        e.preventDefault();
        
        try {
            // Validate the form
            if (!validateInterdisciplinaryForm(form)) {
                return;
            }
            
            // Show loading indicator with safe check
            if (typeof window.showLoading === 'function') {
                window.showLoading("Processing interdisciplinary search...");
            }
            
            // Get form data
            const primaryDiscipline = document.getElementById('primary-discipline').value;
            const secondaryDisciplines = getTags('secondary-disciplines-container');
            
            if (!primaryDiscipline) {
                throw new Error('Primary discipline is required');
            }
            
            if (secondaryDisciplines.length === 0) {
                throw new Error('At least one secondary discipline is required');
            }
            
            // Prepare search options
            const searchOptions = {
                max_results: 20
            };
            
            // Add year range if specified
            const yearFrom = document.getElementById('year-from');
            if (yearFrom && yearFrom.value) {
                searchOptions.from_year = parseInt(yearFrom.value);
            } else {
                // By default, search for recent 5 years
                searchOptions.recent_years = 5;
            }
            
            // Perform interdisciplinary search
            const searchResult = await ApiService.interdisciplinarySearch(
                primaryDiscipline,
                secondaryDisciplines,
                searchOptions
            );
            
            // Validate the search result
            if (!searchResult) {
                throw new Error('Received empty response from search API');
            }
            
            if (searchResult.status !== 'success') {
                throw new Error(searchResult.message || 'Error performing interdisciplinary search');
            }
            
            // Ensure result has expected properties
            if (!searchResult.results) {
                searchResult.results = [];
            }
            
            // Create a synthetic query for display purposes
            const syntheticQuery = `Research at the intersection of ${primaryDiscipline} and ${secondaryDisciplines.join(', ')}`;
            sessionStorage.setItem('original_query', syntheticQuery);
            
            // Store search results
            sessionStorage.setItem('search_results', JSON.stringify(searchResult));
            sessionStorage.setItem('is_interdisciplinary', 'true');
            
            // Navigate to results page
            window.location.href = '/result.html';
            
        } catch (error) {
            console.error('Error performing interdisciplinary search:', error);
            alert(`Interdisciplinary search error: ${error.message}`);
        } finally {
            // Hide loading indicator with safe check
            if (typeof window.hideLoading === 'function') {
                window.hideLoading();
            }
        }
    });

    // Initialize tags input fields if the form exists
    if (form) {
        initializeTagsInput(form);
    }
}

/**
 * Initialize tags input functionality
 */
function initializeTagsInput(form) {
    // Check if form exists
    if (!form) {
        console.warn("Form element not found for tags input initialization");
        return;
    }
    
    // Get tag containers with a safe method
    const tagsContainers = form.querySelectorAll('.tags-input');
    if (!tagsContainers || tagsContainers.length === 0) {
        console.warn("No tags input containers found in the form");
        return;
    }
    
    tagsContainers.forEach(container => {
        if (!container) return;
        
        const input = container.querySelector('input');
        
        if (!input) {
            console.warn("Input element not found in tags container");
            return;
        }
        
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
    });
}

/**
 * Add a new tag to a tags input container
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
 * Validate the query form before submission
 */
function validateQueryForm(form) {
    let isValid = true;
    const errorMessages = [];
    
    // Check main query text
    const queryInput = form.querySelector('#research-query');
    if (!queryInput || !queryInput.value.trim()) {
        isValid = false;
        highlightInvalidField(queryInput);
        errorMessages.push('Please describe your research query');
    }
    
    // Display errors if any
    if (!isValid) {
        displayFormErrors(form, errorMessages);
    }
    
    return isValid;
}

/**
 * Validate the advanced search form
 */
function validateAdvancedSearchForm(form) {
    let isValid = true;
    const errorMessages = [];
    
    // Check for research areas
    const researchAreas = getTags('research-areas-container');
    if (researchAreas.length === 0) {
        isValid = false;
        highlightInvalidField(document.getElementById('research-areas-container'));
        errorMessages.push('Please add at least one research area');
    }
    
    // Display errors if any
    if (!isValid) {
        displayFormErrors(form, errorMessages);
    }
    
    return isValid;
}

/**
 * Validate the interdisciplinary search form
 */
function validateInterdisciplinaryForm(form) {
    let isValid = true;
    const errorMessages = [];
    
    // Check primary discipline
    const primaryDiscipline = document.getElementById('primary-discipline');
    if (!primaryDiscipline || !primaryDiscipline.value.trim()) {
        isValid = false;
        highlightInvalidField(primaryDiscipline);
        errorMessages.push('Primary discipline is required');
    }
    
    // Check secondary disciplines
    const secondaryDisciplines = getTags('secondary-disciplines-container');
    if (secondaryDisciplines.length === 0) {
        isValid = false;
        highlightInvalidField(document.getElementById('secondary-disciplines-container'));
        errorMessages.push('Please add at least one secondary discipline');
    }
    
    // Display errors if any
    if (!isValid) {
        displayFormErrors(form, errorMessages);
    }
    
    return isValid;
}

/**
 * Display error messages for form validation
 */
function displayFormErrors(form, errorMessages) {
    const errorContainer = document.createElement('div');
    errorContainer.className = 'error-container';
    errorContainer.innerHTML = errorMessages.map(msg => `<p>${msg}</p>`).join('');
    
    // Remove existing error container if present
    const existingError = form.querySelector('.error-container');
    if (existingError) {
        existingError.remove();
    }
    
    form.insertBefore(errorContainer, form.firstChild);
}

/**
 * Highlight an invalid form field
 */
function highlightInvalidField(field) {
    if (!field) return;
    
    field.classList.add('invalid');
    
    // Remove highlight when user interacts with the field
    field.addEventListener('input', function onInput() {
        field.classList.remove('invalid');
        field.removeEventListener('input', onInput);
    }, { once: true });
}

/**
 * Extract data from the query form
 */
function getQueryFormData(form) {
    const query = form.querySelector('#research-query').value.trim();
    const researchAreas = getTags('research-areas-container');
    const expertise = getTags('expertise-container');
    let collaborationType = '';
    
    const typeSelect = form.querySelector('#collaboration-type');
    if (typeSelect) {
        collaborationType = typeSelect.value;
    }
    
    // Create form data object
    const formData = {
        query,
        research_areas: researchAreas,
        expertise: expertise,
        collaboration_type: collaborationType,
        timestamp: new Date().toISOString()
    };
    
    return formData;
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
 * Load an example query into the form
 */
function loadExampleQuery(exampleId, form) {
    const examples = {
        'quantum-computing': {
            query: 'Recent advances in quantum error correction and their implications for quantum computing',
            researchAreas: ['Quantum Computing', 'Quantum Information Science'],
            expertise: ['Quantum Error Correction', 'Superconducting Qubits'],
            collaborationType: 'research-project'
        },
        'climate-modeling': {
            query: 'High-resolution climate models for predicting extreme weather events',
            researchAreas: ['Climate Science', 'Atmospheric Physics'],
            expertise: ['Climate Modeling', 'Data Visualization'],
            collaborationType: 'research-project'
        },
        'medical-ai': {
            query: 'Applications of deep learning for medical image analysis in neurological disorders',
            researchAreas: ['Medical Imaging', 'Artificial Intelligence'],
            expertise: ['Deep Learning', 'Neuroimaging'],
            collaborationType: 'grant-proposal'
        }
    };
    
    const example = examples[exampleId];
    if (!example) return;
    
    // Set query text
    const queryInput = form.querySelector('#research-query');
    if (queryInput) {
        queryInput.value = example.query;
    }
    
    // Clear existing tags
    const researchAreasContainer = document.getElementById('research-areas-container');
    const expertiseContainer = document.getElementById('expertise-container');
    
    if (researchAreasContainer) {
        Array.from(researchAreasContainer.querySelectorAll('.tag')).forEach(tag => tag.remove());
        
        // Add new tags
        example.researchAreas.forEach(area => {
            addTag(researchAreasContainer, area);
        });
    }
    
    if (expertiseContainer) {
        Array.from(expertiseContainer.querySelectorAll('.tag')).forEach(tag => tag.remove());
        
        // Add new tags
        example.expertise.forEach(exp => {
            addTag(expertiseContainer, exp);
        });
    }
    
    // Set collaboration type
    const collaborationTypeSelect = form.querySelector('#collaboration-type');
    if (collaborationTypeSelect) {
        collaborationTypeSelect.value = example.collaborationType;
    }
}