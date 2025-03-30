/**
 * LitFinder - API Service
 * Handles all API communication with the backend
 */

const API_BASE_URL = 'http://localhost:5000/api';

const ApiService = {
    // Search for literature based on natural language query
    searchLiterature: async function(query, options = {}) {
        try {
            console.log("Sending search request:", { query, options });
            
            const response = await fetch(`${API_BASE_URL}/search`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    query: query,
                    options: options
                })
            });
            
            if (!response.ok) {
                throw new Error(`API error: ${response.status}`);
            }
            
            const data = await response.json();
            console.log("Search API response:", data);
            
            return data;
        } catch (error) {
            console.error('Error searching literature:', error);
            throw error;
        }
    },
    
    // Perform advanced search with specific parameters
    advancedSearch: async function(researchAreas, specificTopics, methodologies, options = {}) {
        try {
            console.log("Sending advanced search request:", { 
                researchAreas, specificTopics, methodologies, options 
            });
            
            const response = await fetch(`${API_BASE_URL}/advanced-search`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    research_areas: researchAreas,
                    specific_topics: specificTopics,
                    methodologies: methodologies,
                    options: options
                })
            });
            
            if (!response.ok) {
                throw new Error(`API error: ${response.status}`);
            }
            
            const data = await response.json();
            console.log("Advanced search API response:", data);
            
            return data;
        } catch (error) {
            console.error('Error performing advanced search:', error);
            throw error;
        }
    },
    
    // Perform interdisciplinary search
    interdisciplinarySearch: async function(primaryDiscipline, secondaryDisciplines, options = {}) {
        try {
            console.log("Sending interdisciplinary search request:", { 
                primaryDiscipline, secondaryDisciplines, options 
            });
            
            const response = await fetch(`${API_BASE_URL}/interdisciplinary-search`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    primary_discipline: primaryDiscipline,
                    secondary_disciplines: secondaryDisciplines,
                    options: options
                })
            });
            
            if (!response.ok) {
                throw new Error(`API error: ${response.status}`);
            }
            
            const data = await response.json();
            console.log("Interdisciplinary search API response:", data);
            
            return data;
        } catch (error) {
            console.error('Error performing interdisciplinary search:', error);
            throw error;
        }
    },
    
    // Get detailed information about a specific publication
    getPublicationDetails: async function(publicationId) {
        try {
            console.log("Fetching publication details for:", publicationId);
            
            const response = await fetch(`${API_BASE_URL}/publication/${publicationId}`, {
                method: 'GET',
                headers: {
                    'Content-Type': 'application/json',
                }
            });
            
            if (!response.ok) {
                throw new Error(`API error: ${response.status}`);
            }
            
            const data = await response.json();
            console.log("Publication details API response:", data);
            
            return data;
        } catch (error) {
            console.error('Error getting publication details:', error);
            throw error;
        }
    },
    
    // Process query without performing search
    processQuery: async function(query) {
        try {
            console.log("Processing query:", query);
            
            const response = await fetch(`${API_BASE_URL}/process-query`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    query: query
                })
            });
            
            if (!response.ok) {
                throw new Error(`API error: ${response.status}`);
            }
            
            const data = await response.json();
            console.log("Query processing API response:", data);
            
            return data;
        } catch (error) {
            console.error('Error processing query:', error);
            throw error;
        }
    },
    
    // Check API health
    checkHealth: async function() {
        try {
            console.log("Checking API health");
            
            const response = await fetch(`${API_BASE_URL}/health_check`, {
                method: 'GET',
                headers: {
                    'Content-Type': 'application/json',
                }
            });
            
            if (!response.ok) {
                throw new Error(`API error: ${response.status}`);
            }
            
            const data = await response.json();
            console.log("Health check API response:", data);
            
            return data;
        } catch (error) {
            console.error('Error checking API health:', error);
            throw error;
        }
    }
};

// Export the API service
window.ApiService = ApiService;