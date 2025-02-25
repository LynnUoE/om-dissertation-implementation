// View controller file 
const axios = require('axios');

// Display home page
exports.showHomePage = (req, res) => {
  res.render('index', {
    title: 'Research Expert Finder',
    path: '/',
    exampleQuery: 'Looking for collaborators in quantum computing with expertise in quantum error correction and superconducting qubits for a joint research project on quantum machine learning.'
  });
};

// Handle search and display results
exports.handleSearch = async (req, res) => {
  try {
    const query = req.body.query;
    
    // Since we're using proxy mode, send directly to /api/process-query
    // This request will be forwarded to the Python backend by the proxy middleware
    const analysisResponse = await axios.post('/api/process-query', { query });
    const queryAnalysis = analysisResponse.data;
    
    // Use query analysis results to search for experts
    const expertsResponse = await axios.post('/api/search-experts', { 
      queryAnalysis,
      options: {
        recentYears: parseInt(req.body.recentYears) || 5,
        minWorks: parseInt(req.body.minWorks) || 3,
        minCitations: parseInt(req.body.minCitations) || 100,
        requireAllDisciplines: req.body.requireAllDisciplines === 'on'
      }
    });
    const experts = expertsResponse.data;
    
    // Render results page
    res.render('results', {
      title: 'Search Results',
      path: '/results',
      query,
      analysis: queryAnalysis,
      experts,
      searchOptions: {
        recentYears: parseInt(req.body.recentYears) || 5,
        minWorks: parseInt(req.body.minWorks) || 3,
        minCitations: parseInt(req.body.minCitations) || 100,
        requireAllDisciplines: req.body.requireAllDisciplines === 'on'
      }
    });
  } catch (error) {
    console.error('Search processing error:', error);
    
    // Error handling
    res.status(500).render('error', {
      title: 'Processing Error',
      message: 'An error occurred while processing your search query',
      error: { 
        status: 500,
        details: error.response?.data?.message || error.message
      }
    });
  }
};

// Display expert details
exports.showExpertDetails = async (req, res) => {
  try {
    const expertId = req.params.id;
    
    // Get expert details through proxy
    const expertResponse = await axios.get(`/api/expert/${expertId}`);
    const expert = expertResponse.data;
    
    if (!expert) {
      return res.status(404).render('error', {
        title: 'Not Found',
        message: 'The requested expert information was not found',
        error: { status: 404 }
      });
    }
    
    // Get related expert suggestions
    let relatedExperts = [];
    try {
      const relatedResponse = await axios.get(`/api/experts/related/${expertId}`);
      relatedExperts = relatedResponse.data;
    } catch (e) {
      console.warn('Failed to get related experts:', e.message);
    }
    
    // Render expert detail page
    res.render('expert', {
      title: `${expert.name} - Expert Profile`,
      path: '/expert',
      expert,
      relatedExperts
    });
  } catch (error) {
    console.error('Error fetching expert details:', error);
    res.status(500).render('error', {
      title: 'Processing Error',
      message: 'An error occurred while retrieving expert information',
      error: { 
        status: 500,
        details: error.response?.data?.message || error.message
      }
    });
  }
};