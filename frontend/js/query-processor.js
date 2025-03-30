/**
 * LitFinder - Query Processor
 * Handles research query submission and processing
 */

document.addEventListener('DOMContentLoaded', function() {
    const queryForm = document.getElementById('research-query-form');
    
    if (queryForm) {
        initializeQueryForm(queryForm);
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
            
            // Get form data
            const queryData = getQueryFormData(form);
            
            // Process query
            await processQuery(queryData);
            
            // Navigate to results page
            window.location.href = 'results.html';
        } catch (error) {
            console.error('Error processing query:', error);
            alert('There was an error processing your query. Please try again.');
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
}

/**
 * Validate the query form before submission
 */
function validateQueryForm(form) {
    let isValid = true;
    const errorMessages = [];
    
    // Check main query text
    const queryInput = form.querySelector('#research-query');
    if (!queryInput.value.trim()) {
        isValid = false;
        highlightInvalidField(queryInput);
        errorMessages.push('Please describe your research interests');
    }
    
    // Display errors if any
    if (!isValid) {
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
    
    return isValid;
}

/**
 * Extract data from the query form
 */
function getQueryFormData(form) {
    const query = form.querySelector('#research-query').value.trim();
    const researchAreas = getTags('research-areas-container');
    const expertise = getTags('expertise-container');
    
    // Get publication type and year range
    const publicationType = form.querySelector('#publication-type')?.value;
    const fromYear = parseInt(form.querySelector('#year-from')?.value);
    const toYear = parseInt(form.querySelector('#year-to')?.value);
    
    // Store form data in session storage for the results page
    const formData = {
        query,
        research_areas: researchAreas,
        expertise: expertise,
        publication_type: publicationType,
        from_year: fromYear,
        to_year: toYear,
        timestamp: new Date().toISOString()
    };
    
    // Save to session storage
    sessionStorage.setItem('research_query', JSON.stringify(formData));
    
    return formData;
}

/**
 * Process the research query
 */
async function processQuery(queryData) {
    try {
        window.showLoading();
        
        // Call the backend API to process the query
        const response = await apiCall('/process_query', 'POST', queryData);
        
        // Store the processed query results
        sessionStorage.setItem('processed_query', JSON.stringify(response));
        
        // Search for publications based on the processed query
        const publications = await searchPublications(response, queryData);
        
        // Store the publication results
        sessionStorage.setItem('publication_results', JSON.stringify(publications));
        
        return {
            processedQuery: response,
            publications: publications
        };
    } catch (error) {
        console.error('Query processing error:', error);
        throw error;
    } finally {
        window.hideLoading();
    }
}

/**
 * Search for publications based on processed query
 */
async function searchPublications(processedQuery, formData) {
    try {
        // Prepare search parameters from processed query and form data
        const searchParams = {
            research_areas: processedQuery.research_areas || [],
            expertise: processedQuery.expertise || [],
            keywords: processedQuery.search_keywords || [],
            from_year: formData.from_year,
            to_year: formData.to_year,
            max_results: 20
        };
        
        // Add publication type filter if specified
        if (formData.publication_type && formData.publication_type !== 'all') {
            searchParams.publication_types = [formData.publication_type];
        }
        
        // Log the search parameters for debugging
        console.log('Search parameters:', searchParams);
        
        // Call publications search API
        const publications = await apiCall('/search_publications', 'POST', searchParams);
        return publications;
    } catch (error) {
        console.error('Publication search error:', error);
        throw error;
    }
}

/**
 * Load an example query into the form
 */
function loadExampleQuery(exampleId, form) {
    const examples = {
        'quantum-computing': {
            query: 'Looking for publications on quantum computing with focus on quantum error correction and superconducting qubits with applications in quantum machine learning.',
            researchAreas: ['Quantum Computing', 'Machine Learning'],
            expertise: ['Quantum Error Correction', 'Superconducting Qubits'],
            publicationType: 'all',
            fromYear: 2020,
            toYear: 2025
        },
        'climate-modeling': {
            query: 'Need publications on climate modeling focused on predicting extreme weather events using high-resolution models, especially works on atmospheric physics and data visualization.',
            researchAreas: ['Climate Science', 'Atmospheric Physics'],
            expertise: ['Climate Modeling', 'Data Visualization'],
            publicationType: 'journal-article',
            fromYear: 2019,
            toYear: 2025
        },
        'medical-ai': {
            query: 'Looking for research on AI algorithms for medical image analysis, specifically for early detection of neurological disorders from MRI scans.',
            researchAreas: ['Medical Imaging', 'Artificial Intelligence'],
            expertise: ['Deep Learning', 'Neuroimaging'],
            publicationType: 'all',
            fromYear: 2021,
            toYear: 2025
        }
    };
    
    const example = examples[exampleId];
    if (!example) return;
    
    // Set query text
    form.querySelector('#research-query').value = example.query;
    
    // Clear existing tags
    const researchAreasContainer = document.getElementById('research-areas-container');
    const expertiseContainer = document.getElementById('expertise-container');
    
    Array.from(researchAreasContainer.querySelectorAll('.tag')).forEach(tag => tag.remove());
    Array.from(expertiseContainer.querySelectorAll('.tag')).forEach(tag => tag.remove());
    
    // Add new tags
    example.researchAreas.forEach(area => {
        addTag(researchAreasContainer, area);
    });
    
    example.expertise.forEach(exp => {
        addTag(expertiseContainer, exp);
    });
    
    // Set publication type
    const publicationTypeSelect = form.querySelector('#publication-type');
    if (publicationTypeSelect) {
        publicationTypeSelect.value = example.publicationType;
    }
    
    // Set year range
    const yearFromInput = form.querySelector('#year-from');
    const yearToInput = form.querySelector('#year-to');
    
    if (yearFromInput) yearFromInput.value = example.fromYear;
    if (yearToInput) yearToInput.value = example.toYear;
}
