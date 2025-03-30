from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import logging
import os
import json
from datetime import datetime

# Import custom modules
from query_processor import QueryProcessor
from literature_searcher import create_literature_searcher

from dotenv import load_dotenv
import os

# Load environment variables from .env file
load_dotenv()



app = Flask(__name__, static_folder='../static')
CORS(app)  # Enable CORS for all routes

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('api_server')

# Initialize components
query_processor = QueryProcessor(api_key=os.getenv("OPENAI_API_KEY"))
literature_searcher = create_literature_searcher(os.getenv("RESEARCHER_EMAIL"))

# Serve static files
@app.route('/')
def index():
    return send_from_directory(app.static_folder, 'index.html')

@app.route('/<path:path>')
def static_files(path):
    return send_from_directory(app.static_folder, path)

# API Endpoints
@app.route('/api/process_query', methods=['POST'])
def process_query():
    """Process a research query and extract structured information"""
    try:
        # Get query data from request
        data = request.json
        if not data or 'query' not in data:
            return jsonify({'error': 'Missing query data'}), 400
        
        # Process query
        structured_query = query_processor.process_query(data['query'])
        
        if not structured_query or not query_processor.validate_query(structured_query):
            return jsonify({'error': 'Could not process query'}), 400
        
        # Add any additional fields from the request
        if 'research_areas' in data and data['research_areas']:
            structured_query['research_areas'].extend(data['research_areas'])
            # Remove duplicates
            structured_query['research_areas'] = list(set(structured_query['research_areas']))
            
        if 'expertise' in data and data['expertise']:
            structured_query['expertise'].extend(data['expertise'])
            # Remove duplicates
            structured_query['expertise'] = list(set(structured_query['expertise']))
        
        return jsonify(structured_query), 200
        
    except Exception as e:
        logger.error(f"Error processing query: {str(e)}")
        return jsonify({'error': 'An error occurred while processing the query'}), 500

@app.route('/api/search_publications', methods=['POST'])
def search_publications():
    """Search for publications based on structured query"""
    try:
        # Get search parameters from request
        data = request.json
        if not data:
            return jsonify({'error': 'Missing search parameters'}), 400
        
        # Extract search parameters
        structured_query = {
            'research_areas': data.get('research_areas', []),
            'expertise': data.get('expertise', []),
            'search_keywords': data.get('keywords', [])
        }
        
        # Extract filter parameters
        from_year = data.get('from_year')
        to_year = data.get('to_year') 
        min_citations = data.get('min_citations')
        publication_types = data.get('publication_types')
        open_access_only = data.get('open_access_only', False)
        max_results = data.get('max_results', 20)
        
        # Search for publications
        publications = literature_searcher.search_literature(
            structured_query=structured_query,
            max_results=max_results,
            from_year=from_year,
            to_year=to_year,
            min_citations=min_citations,
            publication_types=publication_types,
            open_access_only=open_access_only
        )
        
        # Convert results to dictionaries
        results = [pub.to_dict() for pub in publications]
        
        # Store results in session storage (simulated here with a file)
        # In a real implementation, you might use Redis or another cache
        publication_results_file = 'publication_results.json'
        with open(publication_results_file, 'w') as f:
            json.dump(results, f)
        
        return jsonify(results), 200
        
    except Exception as e:
        logger.error(f"Error searching publications: {str(e)}")
        return jsonify({'error': 'An error occurred while searching for publications'}), 500

@app.route('/api/publication/<publication_id>', methods=['GET'])
def get_publication(publication_id):
    """Get detailed information about a specific publication"""
    try:
        # Get publication details
        publication = literature_searcher.get_publication_details(publication_id)
        
        if not publication:
            return jsonify({'error': 'Publication not found'}), 404
        
        return jsonify(publication), 200
        
    except Exception as e:
        logger.error(f"Error getting publication details: {str(e)}")
        return jsonify({'error': 'An error occurred while retrieving publication details'}), 500

@app.route('/api/publication/<publication_id>/citations', methods=['GET'])
def get_publication_citations(publication_id):
    """Get citations for a specific publication"""
    try:
        # In a real implementation, you would fetch actual citation data
        # Here we're returning a placeholder
        citations = [
            {
                "id": f"citation_{i}",
                "title": f"Citation Publication {i}",
                "authors": ["Author A", "Author B"],
                "journal": "Journal of Citations",
                "publication_date": "2024-01-01",
                "excerpt": "This is a citation excerpt referencing the original publication."
            }
            for i in range(1, 4)
        ]
        
        return jsonify(citations), 200
        
    except Exception as e:
        logger.error(f"Error getting publication citations: {str(e)}")
        return jsonify({'error': 'An error occurred while retrieving citations'}), 500

@app.route('/api/publication/<publication_id>/similar', methods=['GET'])
def get_similar_publications(publication_id):
    """Get publications similar to the specified publication"""
    try:
        # Get similar publications
        similar_publications = literature_searcher.get_similar_publications(
            publication_id,
            max_results=5
        )
        
        return jsonify(similar_publications), 200
        
    except Exception as e:
        logger.error(f"Error getting similar publications: {str(e)}")
        return jsonify({'error': 'An error occurred while retrieving similar publications'}), 500

@app.route('/api/search_by_keywords', methods=['POST'])
def search_by_keywords():
    """Search for publications by keywords"""
    try:
        # Get search parameters from request
        data = request.json
        if not data or 'keywords' not in data:
            return jsonify({'error': 'Missing keywords'}), 400
        
        # Extract parameters
        keywords = data['keywords']
        from_year = data.get('from_year')
        to_year = data.get('to_year')
        max_results = data.get('max_results', 20)
        
        # Search for publications
        publications = literature_searcher.search_by_keywords(
            keywords=keywords,
            max_results=max_results,
            from_year=from_year,
            to_year=to_year
        )
        
        return jsonify(publications), 200
        
    except Exception as e:
        logger.error(f"Error searching by keywords: {str(e)}")
        return jsonify({'error': 'An error occurred while searching by keywords'}), 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)