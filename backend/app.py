from flask import Flask, request, jsonify
from flask_cors import CORS
from query_processor import QueryProcessor
from expert_searcher import ExpertSearcher
from research_analyzer import create_analyzer

app = Flask(__name__)
CORS(app)  # Enable cross-origin requests

# Initialize your existing components
API_KEY = "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"
query_processor = QueryProcessor(api_key=API_KEY)
expert_searcher = ExpertSearcher(email="s2231967@ed.ac.uk")
research_analyzer = create_analyzer(api_key=API_KEY)

@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint to verify API is working"""
    return jsonify({"status": "ok"})

@app.route('/api/process-query', methods=['POST'])
def process_query():
    """Process a research query and return structured analysis"""
    data = request.json
    query = data.get('query', '')
    
    # Use your existing QueryProcessor to process the query
    analysis = query_processor.process_query(query)
    
    return jsonify(analysis)

@app.route('/api/search-experts', methods=['POST'])
def search_experts():
    """Search for experts based on query analysis"""
    data = request.json
    query_analysis = data.get('queryAnalysis', {})
    options = data.get('options', {})
    
    # Extract parameters from options
    recent_years = options.get('recentYears', 5)
    min_works = options.get('minWorks', 3)
    min_citations = options.get('minCitations', 100)
    require_all = options.get('requireAllDisciplines', False)
    
    # Use your existing ExpertSearcher to search for experts
    experts = expert_searcher.search_experts(
        query_analysis, 
        max_results=20,
        recent_years=recent_years,
        min_works=min_works
    )
    
    return jsonify(experts)

@app.route('/api/expert/<id>', methods=['GET'])
def get_expert(id):
    """Get detailed information about a specific expert"""
    # Get expert details
    expert = expert_searcher.get_expert_details(id)
    if not expert:
        return jsonify({"error": "Expert not found"}), 404
    return jsonify(expert)

@app.route('/api/experts/related/<id>', methods=['GET'])
def get_related_experts(id):
    """Get experts related to the specified expert"""
    # Find related experts
    related = expert_searcher.search_multidisciplinary(
        id, 
        max_results=3
    )
    return jsonify(related)

def create_analyzer(api_key):
    """Import the create_analyzer function from research_analyzer"""
    from research_analyzer import create_analyzer
    return create_analyzer(api_key)

if __name__ == '__main__':
    app.run(debug=True, port=5000)