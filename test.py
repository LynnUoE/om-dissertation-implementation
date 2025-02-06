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
    relevance_score: Optional[float] = None
    
    @classmethod
    def from_api_response(cls, data: Dict) -> 'WorkResult':
        """Create WorkResult from API response data"""
        return cls(
            title=html.unescape(data.get('title', '')),
            publication_date=data.get('publication_date', ''),
            citations=data.get('cited_by_count', 0),
            doi=data.get('doi'),
            authors=[
                auth.get('author', {}).get('display_name', '')
                for auth in data.get('authorships', [])
            ],
            abstract=data.get('abstract'),
            relevance_score=data.get('relevance_score')
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
        
        for work_data in self.data['results']:
            work = WorkResult.from_api_response(work_data)
            normalized_title = work.title.lower().strip()
            if normalized_title not in seen_titles:
                seen_titles.add(normalized_title)
                unique_works.append(work)
                
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
                
                # Send the request
                response = self.session.send(prepared_request)
                
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
                
                return OpenAlexResponse(
                    status_code=response.status_code,
                    data=response.json(),
                    meta=response.json().get('meta')
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
            
            time.sleep(self.rate_limit_delay)
    
    def search_works(
        self,
        query: str,
        search_in: str = "title_and_abstract",
        from_year: Optional[int] = None,
        to_year: Optional[int] = None,
        page: int = 1,
        per_page: int = 25,
        sort: str = "relevance_score:desc",
        min_citations: Optional[int] = None
    ) -> OpenAlexResponse:
        """
        Search for works in OpenAlex with enhanced filtering options.
        
        Args:
            query: Search query string
            search_in: Where to search for the query (default: title_and_abstract)
            from_year: Start year for publication date filter
            to_year: End year for publication date filter
            page: Page number for pagination
            per_page: Results per page
            sort: Sort order (default: relevance_score:desc)
            min_citations: Minimum number of citations filter
        """
        params = {
            'page': page,
            'per-page': min(per_page, 200)
        }
        
        # Construct filter parts
        filter_parts = []
        
        # Add publication year filter
        if from_year is not None or to_year is not None:
            year_range = f"{from_year or ''}-{to_year or ''}"
            filter_parts.append(f"publication_year:{year_range}")
        
        # Add search filter
        if query:
            filter_parts.append(f"{search_in}.search:{quote(query)}")
        
        # Add citation count filter
        if min_citations is not None:
            filter_parts.append(f"cited_by_count:{min_citations}")
        
        # Combine filters
        if filter_parts:
            params['filter'] = ','.join(filter_parts)
        
        # Add sort parameter
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
        print("\nRelevant AI Papers (2023-2024):")
        print("-" * 50)
        
        for work in response.get_works():
            print(f"Title: {work.title}")
            print(f"Publication Date: {work.publication_date}")
            print(f"Citations: {work.citations}")
            if work.relevance_score is not None:
                print(f"Relevance Score: {work.relevance_score:.2f}")
            if work.doi:
                print(f"DOI: {work.doi}")
            if work.authors:
                authors_display = (
                    f"Authors: {', '.join(work.authors[:3])}"
                    f"{' and others' if len(work.authors) > 3 else ''}"
                )
                print(authors_display)
            print("-" * 50)
    else:
        print(f"Error: {response.error}")