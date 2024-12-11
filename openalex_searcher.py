from typing import Dict, List, Optional
import requests
import time
from dataclasses import dataclass
from datetime import datetime

@dataclass
class ResearchResource:
    """Data class to store structured research resource information."""
    title: str
    authors: List[str]
    publication_date: str
    doi: Optional[str]
    citations_count: int
    concepts: List[str]
    institution: Optional[str]
    publication_type: str
    abstract: Optional[str]

class OpenAlexSearcher:
    """Class to search for research resources using the OpenAlex API."""
    
    BASE_URL = "https://api.openalex.org"
    
    def __init__(self, email: str):
        """Initialize the searcher with user's email for API politeness."""
        self.headers = {'User-Agent': f'ResearchMatcher ({email})'}
        self.session = requests.Session()
        self.session.headers.update(self.headers)
    
    def _construct_query(self, structured_query: Dict) -> str:
        """Construct OpenAlex query string from structured query."""
        query_parts = []
        
        # Add research areas and keywords to search
        search_terms = (
            structured_query['research_areas'] +
            structured_query['search_keywords'] +
            structured_query['expertise']
        )
        if search_terms:
            terms_query = ' OR '.join(f'"{term}"' for term in search_terms)
            query_parts.append(f'search:{terms_query}')
        
        # Filter for recent publications (last 5 years)
        current_year = datetime.now().year
        query_parts.append(f'publication_year:{current_year-5}-{current_year}')
        
        return ' AND '.join(query_parts)
    
    def _parse_response(self, result: Dict) -> ResearchResource:
        """Parse OpenAlex API response into ResearchResource object."""
        authors = [
            author.get('author', {}).get('display_name', 'Unknown Author')
            for author in result.get('authorships', [])
        ]
        
        # Get primary institution if available
        institution = None
        if result.get('authorships') and result['authorships'][0].get('institutions'):
            institution = result['authorships'][0]['institutions'][0].get('display_name')
        
        # Extract concepts
        concepts = [
            concept.get('display_name')
            for concept in result.get('concepts', [])
            if concept.get('display_name')
        ]
        
        return ResearchResource(
            title=result.get('title', 'Untitled'),
            authors=authors,
            publication_date=result.get('publication_date', 'Unknown'),
            doi=result.get('doi'),
            citations_count=result.get('cited_by_count', 0),
            concepts=concepts,
            institution=institution,
            publication_type=result.get('type', 'Unknown'),
            abstract=result.get('abstract')
        )
    
    def search(self, structured_query: Dict, max_results: int = 50) -> List[ResearchResource]:
        """
        Search for research resources using the OpenAlex API.
        
        Args:
            structured_query: Dictionary containing query information from QueryProcessor
            max_results: Maximum number of results to return
            
        Returns:
            List of ResearchResource objects
        """
        query_string = self._construct_query(structured_query)
        results = []
        page = 1
        per_page = min(max_results, 50)  # OpenAlex maximum per page
        
        try:
            while len(results) < max_results:
                response = self.session.get(
                    f"{self.BASE_URL}/works",
                    params={
                        'filter': query_string,
                        'per-page': per_page,
                        'page': page,
                        'sort': 'cited_by_count:desc'  # Sort by citation count
                    }
                )
                response.raise_for_status()
                data = response.json()
                
                if not data.get('results'):
                    break
                    
                for result in data['results']:
                    results.append(self._parse_response(result))
                    if len(results) >= max_results:
                        break
                
                page += 1
                time.sleep(1)  # Rate limiting
                
        except requests.exceptions.RequestException as e:
            print(f"Error searching OpenAlex API: {str(e)}")
            return results
        
        return results
    
    def filter_results(
        self,
        resources: List[ResearchResource],
        min_citations: int = 0,
        required_concepts: List[str] = None
    ) -> List[ResearchResource]:
        """
        Filter research resources based on criteria.
        
        Args:
            resources: List of ResearchResource objects
            min_citations: Minimum number of citations required
            required_concepts: List of concepts that must be present
            
        Returns:
            Filtered list of ResearchResource objects
        """
        filtered = []
        for resource in resources:
            if resource.citations_count < min_citations:
                continue
                
            if required_concepts and not any(
                concept in resource.concepts
                for concept in required_concepts
            ):
                continue
                
            filtered.append(resource)
            
        return filtered

def create_searcher(email: str) -> OpenAlexSearcher:
    """Factory function to create an OpenAlexSearcher instance."""
    return OpenAlexSearcher(email)