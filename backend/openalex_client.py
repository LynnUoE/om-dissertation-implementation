from typing import Dict, List, Optional, Union
import requests
import time
from datetime import datetime
from dataclasses import dataclass
import logging
from urllib.parse import quote
import html

@dataclass
class WorkResult:
    """Structured container for work data"""
    title: str
    publication_date: str
    citations: int
    doi: Optional[str]
    authors: List[str]
    abstract: Optional[str]
    
    @classmethod
    def from_api_response(cls, data: Dict) -> 'WorkResult':
        """Create WorkResult from API response data"""
        # First ensure data is a dictionary
        if data is None:
            data = {}
        
        # Get title safely
        title = ''
        if data.get('title') is not None:
            title = html.unescape(data.get('title', ''))
        
        # Get authors safely
        authors = []
        for auth in data.get('authorships', []):
            if auth is not None and isinstance(auth, dict):
                author_obj = auth.get('author', {})
                if isinstance(author_obj, dict):
                    display_name = author_obj.get('display_name', '')
                    if display_name:
                        authors.append(display_name)
        
        # Get other fields with safe defaults
        return cls(
            title=title,
            publication_date=data.get('publication_date', ''),
            citations=data.get('cited_by_count', 0),
            doi=data.get('doi'),
            authors=authors,
            abstract=data.get('abstract')
        )

@dataclass
class OpenAlexResponse:
    """Data class to store structured API responses"""
    status_code: int
    data: Dict
    error: Optional[str] = None
    meta: Optional[Dict] = None
    
    def get_works(self) -> List[WorkResult]:
        """Extract and structure work results"""
        if self.error or 'results' not in self.data:
            return []
        
        seen_titles = set()
        unique_works = []
        
        for work_data in self.data.get('results', []):
            if work_data is None:
                continue
            
            try:
                work = WorkResult.from_api_response(work_data)
                normalized_title = work.title.lower().strip() if work.title else ""
                if normalized_title and normalized_title not in seen_titles:
                    seen_titles.add(normalized_title)
                    unique_works.append(work)
            except Exception as e:
                # Log the error but continue processing other works
                logging.getLogger('OpenAlexClient').warning(f"Error processing work: {e}")
                continue
                    
        return unique_works

class OpenAlexClient:
    """Client for interacting with the OpenAlex API"""
    
    def __init__(self, email: str, max_retries: int = 3, rate_limit_delay: float = 1.0):
        self.base_url = "https://api.openalex.org"
        self.email = email
        self.max_retries = max_retries
        self.rate_limit_delay = rate_limit_delay
        
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': f'ResearchCollaborationTool ({email})',
            'Accept': 'application/json'
        })
        
        self.logger = logging.getLogger('OpenAlexClient')
        self.logger.setLevel(logging.INFO)
        
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)

    def _make_request(
        self,
        endpoint: str,
        params: Optional[Dict] = None,
        method: str = 'GET'
    ) -> OpenAlexResponse:
        """Make an API request with retry logic and rate limiting."""
        url = f"{self.base_url}/{endpoint}"
        if params is None:
            params = {}
        
        params['mailto'] = self.email
        
        for attempt in range(self.max_retries):
            try:
                # Prepare the request
                prepared_request = requests.Request(
                    method, 
                    url,
                    params=params
                ).prepare()
                
                # Log the full URL with parameters
                self.logger.info(f"Making API request: {prepared_request.url}")
                
                response = self.session.request(method, url, params=params)
                
                if response.status_code != 200:
                    error_data = response.json() if response.content else {}
                    error_message = error_data.get('message', str(response.content))
                    self.logger.error(f"API Error: {error_message}")
                    
                    if response.status_code == 429:
                        wait_time = float(response.headers.get('Retry-After', self.rate_limit_delay * 2))
                        self.logger.warning(f"Rate limit exceeded. Waiting {wait_time} seconds.")
                        time.sleep(wait_time)
                        continue
                    
                    return OpenAlexResponse(
                        status_code=response.status_code,
                        data={},
                        error=error_message
                    )
                
                # Try to parse JSON response safely
                try:
                    response_data = response.json()
                except ValueError:
                    return OpenAlexResponse(
                        status_code=response.status_code,
                        data={},
                        error="Invalid JSON response from API"
                    )
                
                return OpenAlexResponse(
                    status_code=response.status_code,
                    data=response_data,
                    meta=response_data.get('meta')
                )
                
            except requests.exceptions.RequestException as e:
                self.logger.error(f"Request failed (attempt {attempt + 1}/{self.max_retries}): {str(e)}")
                if attempt == self.max_retries - 1:
                    return OpenAlexResponse(
                        status_code=getattr(e.response, 'status_code', 500),
                        data={},
                        error=str(e)
                    )
                time.sleep(self.rate_limit_delay * (attempt + 1))
            except Exception as e:
                self.logger.error(f"Unexpected error during API request: {str(e)}")
                return OpenAlexResponse(
                    status_code=500,
                    data={},
                    error=f"Unexpected error: {str(e)}"
                )
            
            time.sleep(self.rate_limit_delay)
    
    def search_works(
        self,
        query: str,
        from_year: Optional[int] = None,
        to_year: Optional[int] = None,
        page: int = 1,
        per_page: int = 25,
        sort: Optional[str] = None,
        min_citations: Optional[int] = None
    ) -> OpenAlexResponse:
        """Search for works in OpenAlex."""
        params = {
            'search': query,
            'page': page,
            'per-page': min(per_page, 200)
        }
        
        filter_parts = []
        
        if from_year is not None or to_year is not None:
            year_range = f"{from_year or ''}-{to_year or ''}"
            filter_parts.append(f"publication_year:{year_range}")
        
        if min_citations is not None:
            filter_parts.append(f"cited_by_count:{min_citations}")
        
        if filter_parts:
            params['filter'] = ','.join(filter_parts)
            
        if sort:
            params['sort'] = sort
        
        return self._make_request('works', params)

def create_client(email: str) -> OpenAlexClient:
    """Factory function to create an OpenAlexClient instance."""
    return OpenAlexClient(email)

# Example usage
if __name__ == "__main__":
    client = create_client("your-email@example.com")
    
    response = client.search_works(
        query="artificial intelligence",
        from_year=2023,
        to_year=2024,
        sort="relevance_score:desc",
        per_page=10,
        #min_citations = 100  # Set minimum citations threshold
    )
    
    if not response.error:
        print("\nHighly Cited AI Papers (2023-2024):")
        print("-" * 50)
        
        for work in response.get_works():
            print(f"Title: {work.title}")
            print(f"Publication Date: {work.publication_date}")
            print(f"Citations: {work.citations}")
            if work.doi:
                print(f"DOI: {work.doi}")
            if work.authors:
                authors_display = (
                    f"Authors: {', '.join(work.authors[:3])}"
                    f"{' and others' if len(work.authors) > 3 else ''}"
                )
                
            print("-" * 50)
    else:
        print(f"Error: {response.error}")