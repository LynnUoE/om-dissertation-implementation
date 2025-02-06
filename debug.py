from typing import Dict, List, Optional
import requests
import time
from dataclasses import dataclass
from datetime import datetime
import logging
import json
import sys
from http.client import HTTPConnection

# Enable HTTP debugging
HTTPConnection.debuglevel = 1

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

# Create loggers
logger = logging.getLogger(__name__)
requests_log = logging.getLogger("requests.packages.urllib3")
requests_log.setLevel(logging.DEBUG)
requests_log.propagate = True

class APILogger:
    """Helper class to log API requests and responses"""
    @staticmethod
    def log_request(request):
        logger.debug("----- API Request -----")
        logger.debug(f"URL: {request.url}")
        logger.debug(f"Method: {request.method}")
        logger.debug("Headers:")
        for header, value in request.headers.items():
            logger.debug(f"  {header}: {value}")
        if request.body:
            logger.debug(f"Body: {request.body}")

    @staticmethod
    def log_response(response):
        logger.debug("----- API Response -----")
        logger.debug(f"Status Code: {response.status_code}")
        logger.debug("Headers:")
        for header, value in response.headers.items():
            logger.debug(f"  {header}: {value}")
        try:
            logger.debug("Response JSON:")
            logger.debug(json.dumps(response.json(), indent=2))
        except:
            logger.debug(f"Response Text: {response.text}")

class OpenAlexSearcher:
    """Class to search for research resources using the OpenAlex API."""
    
    BASE_URL = "https://api.openalex.org"
    
    def __init__(self, email: str):
        self.headers = {'User-Agent': f'ResearchMatcher ({email})'}
        self.session = requests.Session()
        self.session.headers.update(self.headers)
        logger.info(f"Initialized OpenAlexSearcher with email: {email}")
    
    def search(self, structured_query: Dict, max_results: int = 50) -> List[Dict]:
        """
        Search the OpenAlex API with detailed logging.
        """
        logger.info("Starting API search...")
        
        try:
            # Construct search parameters
            search_terms = (
                structured_query.get('research_areas', []) +
                structured_query.get('search_keywords', []) +
                structured_query.get('expertise', [])
            )
            
            terms_query = ' OR '.join(f'"{term}"' for term in search_terms)
            current_year = datetime.now().year
            filter_query = f'keyword.search:{terms_query} AND publication_year:{current_year-5}-{current_year}'
            
            # Make API request
            logger.info(f"Sending request to OpenAlex API...")
            response = self.session.get(
                f"{self.BASE_URL}/works",
                params={
                    'filter': filter_query,
                    'per-page': min(max_results, 50),
                    'page': 1,
                    'sort': 'cited_by_count:desc'
                }
            )
            
            # Log request details
            APILogger.log_request(response.request)
            
            # Log response details
            APILogger.log_response(response)
            
            # Check for errors
            response.raise_for_status()
            
            return response.json().get('results', [])
            
        except requests.exceptions.RequestException as e:
            logger.error(f"API request failed: {str(e)}")
            if hasattr(e, 'response'):
                logger.error(f"Response Status Code: {e.response.status_code}")
                logger.error(f"Response Text: {e.response.text}")
            raise

def main():
    """Test function to demonstrate API logging"""
    searcher = OpenAlexSearcher('s2231967@ed.ac.uk')
    
    test_query = {
        'research_areas': ['artificial intelligence'],
        'expertise': ['machine learning'],
        'search_keywords': ['neural networks'],
        'collaboration_type': 'research',
        'requirements': []
    }
    
    print("\nSending test query to OpenAlex API...\n")
    try:
        results = searcher.search(test_query, max_results=5)
        print(f"\nFound {len(results)} results")
    except Exception as e:
        print(f"\nError occurred: {str(e)}")

if __name__ == '__main__':
    main()