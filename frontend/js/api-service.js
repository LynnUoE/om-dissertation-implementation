/**
 * LitFinder: calls to the backend API (same origin; Flask serves the frontend).
 */
const API_BASE_URL = '/api';

/** Throw an Error carrying the backend's message, not just the status code */
async function apiRequest(path, options = {}) {
    const response = await fetch(`${API_BASE_URL}${path}`, {
        headers: { 'Content-Type': 'application/json' },
        ...options,
    });
    let body = null;
    try {
        body = await response.json();
    } catch (e) {
        // Non-JSON body, e.g. a proxy error page
    }
    if (!response.ok || (body && body.status === 'error')) {
        const message = (body && body.message) || `The server returned an error (HTTP ${response.status}).`;
        const error = new Error(message);
        error.status = response.status;
        throw error;
    }
    return body;
}

const ApiService = {
    /** Pipeline search. options: max_results, from_year, to_year, min_citations, publication_types, open_access_only */
    search(query, options = {}, signal) {
        return apiRequest('/search', { method: 'POST', body: JSON.stringify({ query, options }), signal });
    },

    /** Agent search: the LLM plans and runs the searches itself */
    agentSearch(query, signal) {
        return apiRequest('/agent-search', { method: 'POST', body: JSON.stringify({ query, options: {} }), signal });
    },

    /** One paper by OpenAlex ID or DOI, with related works */
    getPublication(id) {
        return apiRequest(`/publication/${encodeURIComponent(id)}`);
    },

    /** LLM analysis of one paper (one LLM call) */
    analyzePublication(id) {
        return apiRequest(`/publication/${encodeURIComponent(id)}/analyze`);
    },

    checkHealth() {
        return apiRequest('/health_check');
    },
};
