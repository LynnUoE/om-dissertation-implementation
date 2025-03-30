from flask import Flask, request, jsonify, send_from_directory, abort
from flask_cors import CORS
import logging
import os
import json
from datetime import datetime
from typing import Dict, List, Any, Optional
import time

# Import custom modules
from query_processor import create_query_processor
from openalex_client import create_client
from research_analyzer import create_analyzer
from literature_searcher import create_literature_searcher, LiteratureSearcher

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

# Configuration
class Config:
    """Application configuration"""
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    RESEARCHER_EMAIL = os.getenv("RESEARCHER_EMAIL", "research@example.com")
    STATIC_FOLDER = os.getenv("STATIC_FOLDER", "../frontend")
    CACHE_DURATION = int(os.getenv("CACHE_DURATION", "24"))  # Hours
    DEBUG = os.getenv("DEBUG", "False").lower() == "true"
    HOST = os.getenv("HOST", "0.0.0.0")
    PORT = int(os.getenv("PORT", "5000"))
    REQUEST_TIMEOUT = int(os.getenv("REQUEST_TIMEOUT", "120"))  # Seconds
    MAX_RESULTS = int(os.getenv("MAX_RESULTS", "20"))
    
    @classmethod
    def validate(cls):
        """Validate required configuration"""
        if not cls.OPENAI_API_KEY:
            raise ValueError("OPENAI_API_KEY is required")
        
        if not os.path.isdir(cls.STATIC_FOLDER):
            raise ValueError(f"Static folder does not exist: {cls.STATIC_FOLDER}")

# Initialize Flask application
app = Flask(__name__, static_folder=Config.STATIC_FOLDER)
CORS(app)  # Enable CORS for all routes

# Configure logging
logging.basicConfig(
    level=logging.INFO if Config.DEBUG else logging.WARNING,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('api_server')

# Initialize literature searcher (main component that orchestrates the others)
literature_searcher: Optional[LiteratureSearcher] = None

def get_literature_searcher() -> LiteratureSearcher:
    """Get or initialize the literature searcher singleton"""
    global literature_searcher
    if literature_searcher is None:
        literature_searcher = create_literature_searcher(
            Config.OPENAI_API_KEY,
            Config.RESEARCHER_EMAIL
        )
    return literature_searcher

# Request tracking for analytics and debugging
request_stats = {
    'total_requests': 0,
    'successful_requests': 0,
    'failed_requests': 0,
    'average_response_time': 0
}

# API Routes
@app.route('/')
def index():
    """Serve the main index page"""
    return send_from_directory(app.static_folder, 'index.html')

@app.route('/<path:path>')
def static_files(path):
    """Serve static files"""
    try:
        return send_from_directory(app.static_folder, path)
    except:
        # If the file doesn't exist, return the index for client-side routing
        return send_from_directory(app.static_folder, 'index.html')

@app.route('/api/health_check')
def health_check():
    """Health check endpoint for monitoring"""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'version': '1.0.0',
        'stats': request_stats
    })

@app.route('/api/search', methods=['POST'])
def search_literature():
    """
    Natural language literature search endpoint
    
    Expects JSON with:
    - query: Natural language query describing research interests
    - options: Optional parameters for search customization
    """
    start_time = time.time()
    request_stats['total_requests'] += 1
    
    try:
        # Get request data
        data = request.json
        if not data or 'query' not in data:
            request_stats['failed_requests'] += 1
            return jsonify({
                'status': 'error',
                'message': 'Missing query parameter'
            }), 400
        
        query = data['query']
        options = data.get('options', {})
        
        # Extract search parameters
        max_results = min(options.get('max_results', Config.MAX_RESULTS), 50)  # Limit to 50 max
        from_year = options.get('from_year')
        to_year = options.get('to_year')
        min_citations = options.get('min_citations')
        publication_types = options.get('publication_types')
        open_access_only = options.get('open_access_only', False)
        analyze_results = options.get('analyze_results', True)
        
        # Create request timeout context
        def timeout_handler():
            abort(408, description="Request timeout")
        
        # Set timeout
        # Note: In production, you'd implement this differently as Flask doesn't have native request timeouts
        # This is a placeholder for the actual implementation
        
        # Perform literature search
        searcher = get_literature_searcher()
        result = searcher.search(
            query=query,
            max_results=max_results,
            from_year=from_year,
            to_year=to_year,
            min_citations=min_citations,
            publication_types=publication_types,
            open_access_only=open_access_only,
            analyze_results=analyze_results
        )
        
        # Log results
        if result['status'] == 'success':
            logger.info(
                f"Search successful: '{query[:50]}...' - Found {len(result.get('results', []))} results"
            )
            request_stats['successful_requests'] += 1
        else:
            logger.error(f"Search failed: '{query[:50]}...' - {result.get('message', 'Unknown error')}")
            request_stats['failed_requests'] += 1
        
        # Update average response time
        elapsed_time = time.time() - start_time
        request_stats['average_response_time'] = (
            (request_stats['average_response_time'] * (request_stats['total_requests'] - 1) + elapsed_time) / 
            request_stats['total_requests']
        )
        
        # Add response time to result
        result['response_time'] = elapsed_time
        
        return jsonify(result)
        
    except Exception as e:
        logger.exception(f"Error processing search request: {str(e)}")
        request_stats['failed_requests'] += 1
        return jsonify({
            'status': 'error',
            'message': f'An error occurred while processing your request: {str(e)}'
        }), 500

@app.route('/api/advanced-search', methods=['POST'])
def advanced_search():
    """
    Advanced search endpoint with explicit parameters
    
    Expects JSON with:
    - research_areas: List of research areas or fields
    - specific_topics: Optional list of specific research topics
    - methodologies: Optional list of methodologies or techniques
    - options: Optional parameters for search customization
    """
    start_time = time.time()
    request_stats['total_requests'] += 1
    
    try:
        # Get request data
        data = request.json
        if not data or 'research_areas' not in data:
            request_stats['failed_requests'] += 1
            return jsonify({
                'status': 'error',
                'message': 'Missing research_areas parameter'
            }), 400
        
        research_areas = data['research_areas']
        specific_topics = data.get('specific_topics', [])
        methodologies = data.get('methodologies', [])
        options = data.get('options', {})
        
        # Extract search parameters
        max_results = min(options.get('max_results', Config.MAX_RESULTS), 50)
        from_year = options.get('from_year')
        to_year = options.get('to_year')
        analyze_results = options.get('analyze_results', True)
        
        # Perform advanced search
        searcher = get_literature_searcher()
        result = searcher.advanced_search(
            research_areas=research_areas,
            specific_topics=specific_topics,
            methodologies=methodologies,
            max_results=max_results,
            from_year=from_year,
            to_year=to_year,
            analyze_results=analyze_results
        )
        
        # Log results
        if result['status'] == 'success':
            logger.info(
                f"Advanced search successful: '{', '.join(research_areas[:3])}...' - Found {len(result.get('results', []))} results"
            )
            request_stats['successful_requests'] += 1
        else:
            logger.error(f"Advanced search failed: '{', '.join(research_areas[:3])}...' - {result.get('message', 'Unknown error')}")
            request_stats['failed_requests'] += 1
        
        # Update average response time
        elapsed_time = time.time() - start_time
        request_stats['average_response_time'] = (
            (request_stats['average_response_time'] * (request_stats['total_requests'] - 1) + elapsed_time) / 
            request_stats['total_requests']
        )
        
        # Add response time to result
        result['response_time'] = elapsed_time
        
        return jsonify(result)
        
    except Exception as e:
        logger.exception(f"Error processing advanced search request: {str(e)}")
        request_stats['failed_requests'] += 1
        return jsonify({
            'status': 'error',
            'message': f'An error occurred while processing your request: {str(e)}'
        }), 500

@app.route('/api/interdisciplinary-search', methods=['POST'])
def interdisciplinary_search():
    """
    Specialized search for interdisciplinary research
    
    Expects JSON with:
    - primary_discipline: Main research discipline
    - secondary_disciplines: List of related disciplines to find intersections with
    - options: Optional parameters for search customization
    """
    start_time = time.time()
    request_stats['total_requests'] += 1
    
    try:
        # Get request data
        data = request.json
        if not data or 'primary_discipline' not in data or 'secondary_disciplines' not in data:
            request_stats['failed_requests'] += 1
            return jsonify({
                'status': 'error',
                'message': 'Missing required parameters (primary_discipline and/or secondary_disciplines)'
            }), 400
        
        primary_discipline = data['primary_discipline']
        secondary_disciplines = data['secondary_disciplines']
        options = data.get('options', {})
        
        # Extract search parameters
        max_results = min(options.get('max_results', Config.MAX_RESULTS), 50)
        from_year = options.get('from_year')
        recent_years = options.get('recent_years', 5)
        
        # Perform interdisciplinary search
        searcher = get_literature_searcher()
        result = searcher.interdisciplinary_search(
            primary_discipline=primary_discipline,
            secondary_disciplines=secondary_disciplines,
            max_results=max_results,
            from_year=from_year,
            recent_years=recent_years
        )
        
        # Log results
        if result['status'] == 'success':
            logger.info(
                f"Interdisciplinary search successful: '{primary_discipline} + {len(secondary_disciplines)} others' - Found {len(result.get('results', []))} results"
            )
            request_stats['successful_requests'] += 1
        else:
            logger.error(f"Interdisciplinary search failed: '{primary_discipline}' - {result.get('message', 'Unknown error')}")
            request_stats['failed_requests'] += 1
        
        # Update average response time
        elapsed_time = time.time() - start_time
        request_stats['average_response_time'] = (
            (request_stats['average_response_time'] * (request_stats['total_requests'] - 1) + elapsed_time) / 
            request_stats['total_requests']
        )
        
        # Add response time to result
        result['response_time'] = elapsed_time
        
        return jsonify(result)
        
    except Exception as e:
        logger.exception(f"Error processing interdisciplinary search request: {str(e)}")
        request_stats['failed_requests'] += 1
        return jsonify({
            'status': 'error',
            'message': f'An error occurred while processing your request: {str(e)}'
        }), 500

@app.route('/api/publication/<publication_id>', methods=['GET'])
def get_publication_details(publication_id):
    """
    Get detailed information about a specific publication
    
    Args:
        publication_id: Publication identifier
    """
    start_time = time.time()
    request_stats['total_requests'] += 1
    
    try:
        # Validate publication ID
        if not publication_id:
            request_stats['failed_requests'] += 1
            return jsonify({
                'status': 'error',
                'message': 'Missing publication ID'
            }), 400
        
        # Get publication details
        searcher = get_literature_searcher()
        result = searcher.get_publication_details(publication_id)
        
        # Log results
        if result['status'] == 'success':
            logger.info(f"Publication details successful: '{publication_id}'")
            request_stats['successful_requests'] += 1
        else:
            logger.error(f"Publication details failed: '{publication_id}' - {result.get('message', 'Unknown error')}")
            request_stats['failed_requests'] += 1
        
        # Update average response time
        elapsed_time = time.time() - start_time
        request_stats['average_response_time'] = (
            (request_stats['average_response_time'] * (request_stats['total_requests'] - 1) + elapsed_time) / 
            request_stats['total_requests']
        )
        
        # Add response time to result
        result['response_time'] = elapsed_time
        
        return jsonify(result)
        
    except Exception as e:
        logger.exception(f"Error getting publication details: {str(e)}")
        request_stats['failed_requests'] += 1
        return jsonify({
            'status': 'error',
            'message': f'An error occurred while retrieving publication details: {str(e)}',
            'publication_id': publication_id
        }), 500

@app.route('/api/process-query', methods=['POST'])
def process_query():
    """
    Process a research query without performing a search
    
    Expects JSON with:
    - query: Natural language query to process
    """
    start_time = time.time()
    request_stats['total_requests'] += 1
    
    try:
        # Get request data
        data = request.json
        if not data or 'query' not in data:
            request_stats['failed_requests'] += 1
            return jsonify({
                'status': 'error',
                'message': 'Missing query parameter'
            }), 400
        
        query = data['query']
        
        # Process query
        searcher = get_literature_searcher()
        structured_query = searcher.query_processor.process_query(query)
        
        # Log results
        logger.info(f"Query processing successful: '{query[:50]}...'")
        request_stats['successful_requests'] += 1
        
        # Update average response time
        elapsed_time = time.time() - start_time
        request_stats['average_response_time'] = (
            (request_stats['average_response_time'] * (request_stats['total_requests'] - 1) + elapsed_time) / 
            request_stats['total_requests']
        )
        
        return jsonify({
            'status': 'success',
            'original_query': query,
            'structured_query': structured_query,
            'response_time': elapsed_time
        })
        
    except Exception as e:
        logger.exception(f"Error processing query: {str(e)}")
        request_stats['failed_requests'] += 1
        return jsonify({
            'status': 'error',
            'message': f'An error occurred while processing your query: {str(e)}'
        }), 500

# Error handlers
@app.errorhandler(404)
def not_found(error):
    """Handle 404 errors"""
    return jsonify({
        'status': 'error',
        'message': 'Resource not found'
    }), 404

@app.errorhandler(405)
def method_not_allowed(error):
    """Handle 405 errors"""
    return jsonify({
        'status': 'error',
        'message': 'Method not allowed'
    }), 405

@app.errorhandler(408)
def request_timeout(error):
    """Handle 408 errors"""
    return jsonify({
        'status': 'error',
        'message': 'Request timeout'
    }), 408

@app.errorhandler(500)
def server_error(error):
    """Handle 500 errors"""
    return jsonify({
        'status': 'error',
        'message': 'Internal server error'
    }), 500

# Application initialization
def initialize_app():
    """Initialize the application"""
    try:
        # Validate configuration
        Config.validate()
        
        # Initialize literature searcher (this will initialize all other components)
        get_literature_searcher()
        
        logger.info("Application initialized successfully")
        return True
    except Exception as e:
        logger.error(f"Error initializing application: {str(e)}")
        return False

# Main entry point
if __name__ == '__main__':
    if initialize_app():
        logger.info(f"Starting server on {Config.HOST}:{Config.PORT} (Debug: {Config.DEBUG})")
        app.run(debug=Config.DEBUG, host=Config.HOST, port=Config.PORT)
    else:
        logger.error("Failed to initialize application. Exiting.")