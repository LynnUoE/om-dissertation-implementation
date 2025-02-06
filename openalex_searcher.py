from typing import Dict, List, Optional
import requests
import time
from datetime import datetime
from dataclasses import dataclass
import logging
from urllib.parse import quote
import html

@dataclass
class ExpertResult:
    """Structured container for expert data"""
    id: str
    name: str
    institutions: List[str]
    works_count: int
    citations_count: int
    concepts: List[Dict[str, str]]
    last_known_institution: Optional[str] = None
    counts_by_year: Optional[List[Dict]] = None
    
    @classmethod
    def from_api_response(cls, data: Dict) -> 'ExpertResult':
        """Create ExpertResult from API response data"""
        institutions = []
        last_known_institution = None
        
        if data.get('last_known_institution'):
            last_known_institution = data['last_known_institution'].get('display_name')
            if last_known_institution:
                institutions.append(last_known_institution)
        
        return cls(
            id=data.get('id', ''),
            name=html.unescape(data.get('display_name', '')),
            institutions=institutions,
            works_count=data.get('works_count', 0),
            citations_count=data.get('cited_by_count', 0),
            concepts=data.get('x_concepts', []),
            last_known_institution=last_known_institution,
            counts_by_year=data.get('counts_by_year', [])
        )

@dataclass
class SearchResponse:
    """Data class to store structured search responses"""
    status_code: int
    experts: List[ExpertResult]
    error: Optional[str] = None
    meta: Optional[Dict] = None

class OpenAlexSearcher:
    """Enhanced searcher for finding research experts through OpenAlex API"""
    
    def __init__(self, email: str, max_retries: int = 3, rate_limit_delay: float = 1.0):
        """Initialize the searcher with configuration parameters"""
        self.base_url = "https://api.openalex.org"
        self.email = email
        self.max_retries = max_retries
        self.rate_limit_delay = rate_limit_delay
        
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': f'ResearchCollaborationTool ({email})',
            'Accept': 'application/json'
        })
        
        self.logger = logging.getLogger('OpenAlexSearcher')
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
    ) -> Dict:
        """Make an API request with retry logic and rate limiting"""
        url = f"{self.base_url}/{endpoint}"
        if params is None:
            params = {}
        
        params['mailto'] = self.email
        
        for attempt in range(self.max_retries):
            try:
                prepared_request = requests.Request(
                    method,
                    url,
                    params=params
                ).prepare()
                
                self.logger.info(f"Making API request: {prepared_request.url}")
                
                response = self.session.send(prepared_request)
                
                if response.status_code != 200:
                    error_message = f"API Error: {response.status_code}"
                    self.logger.error(error_message)
                    
                    if response.status_code == 429:
                        wait_time = float(response.headers.get('Retry-After', self.rate_limit_delay * 2))
                        self.logger.warning(f"Rate limit exceeded. Waiting {wait_time} seconds.")
                        time.sleep(wait_time)
                        continue
                    
                    return {'error': error_message}
                
                return response.json()
                
            except requests.exceptions.RequestException as e:
                self.logger.error(f"Request failed (attempt {attempt + 1}/{self.max_retries}): {str(e)}")
                if attempt == self.max_retries - 1:
                    return {'error': str(e)}
                time.sleep(self.rate_limit_delay * (attempt + 1))
            
            time.sleep(self.rate_limit_delay)
        
        return {'error': 'Max retries exceeded'}

    def _construct_search_filter(self, query: str, from_year: Optional[int] = None) -> str:
        """Construct OpenAlex filter string"""
        filters = []
        
        # Add display name search
        if query:
            filters.append(f'display_name.search:"{query}"')
        
        # Add publication year filter if specified
        if from_year:
            current_year = datetime.now().year
            filters.append(f'last_known_year:{from_year}-{current_year}')
        
        return ' AND '.join(filters)

    def search_experts(
        self,
        query: str,
        from_year: Optional[int] = None,
        max_results: int = 20,
        min_works: Optional[int] = None,
        min_citations: Optional[int] = None,
        page: int = 1,
        per_page: int = 50
    ) -> SearchResponse:
        """
        Search for experts using OpenAlex API
        
        Args:
            query: Search query string
            from_year: Filter results from this year onwards
            max_results: Maximum number of experts to return
            min_works: Minimum number of works required
            min_citations: Minimum number of citations required
            page: Page number for pagination
            per_page: Results per page (max 200)
        """
        filter_string = self._construct_search_filter(query, from_year)
        
        params = {
            'filter': filter_string,
            'per-page': min(per_page, 200),
            'page': page,
            'sort': 'cited_by_count:desc'
        }
        
        if min_citations:
            params['filter'] += f' AND cited_by_count:>={min_citations}'
            
        if min_works:
            params['filter'] += f' AND works_count:>={min_works}'
        
        response_data = self._make_request('authors', params)
        
        if 'error' in response_data:
            return SearchResponse(
                status_code=500,
                experts=[],
                error=response_data['error']
            )
        
        experts = []
        for expert_data in response_data.get('results', [])[:max_results]:
            experts.append(ExpertResult.from_api_response(expert_data))
        
        return SearchResponse(
            status_code=200,
            experts=experts,
            meta=response_data.get('meta')
        )

    def get_expert_details(self, expert_id: str) -> Dict:
        """Get detailed information about a specific expert"""
        if 'openalex.org' in expert_id:
            expert_id = expert_id.split('/')[-1]
            
        return self._make_request(f'authors/{expert_id}')

    def filter_experts(
        self,
        experts: List[ExpertResult],
        concept_ids: Optional[List[str]] = None,
        min_citations: Optional[int] = None,
        min_works: Optional[int] = None
    ) -> List[ExpertResult]:
        """
        Filter experts based on various criteria
        
        Args:
            experts: List of ExpertResult objects
            concept_ids: List of OpenAlex concept IDs to filter by
            min_citations: Minimum number of citations required
            min_works: Minimum number of works required
        """
        filtered_experts = experts
        
        if concept_ids:
            filtered_experts = [
                expert for expert in filtered_experts
                if any(
                    concept['id'] in concept_ids
                    for concept in expert.concepts
                )
            ]
        
        if min_citations is not None:
            filtered_experts = [
                expert for expert in filtered_experts
                if expert.citations_count >= min_citations
            ]
            
        if min_works is not None:
            filtered_experts = [
                expert for expert in filtered_experts
                if expert.works_count >= min_works
            ]
        
        return filtered_experts

def create_searcher(email: str) -> OpenAlexSearcher:
    """Factory function to create an OpenAlexSearcher instance"""
    return OpenAlexSearcher(email)

searcher = create_searcher("lchen")

# Search for experts
response = searcher.search_experts(
    query="machine learning neural networks",
    from_year=2018,
    max_results=10,
    min_citations=0,
    min_works=20
)

# Filter results if needed
filtered_experts = searcher.filter_experts(
    response.experts,
    concept_ids=["C154945302"],  # OpenAlex concept ID for machine learning
    min_citations=2000
)