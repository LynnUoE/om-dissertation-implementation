# resource_retriever.py
import requests
from typing import List, Dict, Optional
from datetime import datetime

class ResourceRetriever:
    def __init__(self, email: str):
        self.email = email
        self.openalex_base_url = "https://api.openalex.org"
        self.headers = {'Accept': 'application/json'}
    
    def search_researchers(self, query_analysis: Dict, limit: int = 5) -> List[Dict]:
        disciplines = [d['name'] for d in query_analysis.get('disciplines', [])]
        expertise = query_analysis.get('search_criteria', {}).get('must_have', [])
        
        search_query = ' '.join(disciplines + expertise)
        params = {
            'filter': f'display_name.search:"{search_query}"',
            'per_page': limit,
            'mailto': self.email,
            'sort': 'cited_by_count:desc'
        }
        
        try:
            response = requests.get(
                f"{self.openalex_base_url}/authors",
                params=params,
                headers=self.headers
            )
            
            if response.status_code == 200:
                return response.json().get('results', [])
            return []
        except Exception as e:
            print(f"Search error: {e}")
            return []

    def get_researcher_details(self, researcher_id: str) -> Dict:
        try:
            if 'openalex.org' in researcher_id:
                researcher_id = researcher_id.split('/')[-1]
            
            params = {'mailto': self.email}
            response = requests.get(
                f"{self.openalex_base_url}/authors/{researcher_id}",
                params=params,
                headers=self.headers
            )
            
            if response.status_code == 200:
                researcher = response.json()
                return self._enrich_researcher_data(researcher)
            return {}
        except Exception as e:
            print(f"Error fetching researcher details: {e}")
            return {}

    def _enrich_researcher_data(self, researcher: Dict) -> Dict:
        try:
            # Get recent works
            works_params = {
                'filter': f'author.id:{researcher["id"]}',
                'per_page': 5,
                'sort': 'publication_date:desc',
                'mailto': self.email
            }
            
            works_response = requests.get(
                f"{self.openalex_base_url}/works",
                params=works_params,
                headers=self.headers
            )
            
            if works_response.status_code == 200:
                researcher['recent_works'] = works_response.json().get('results', [])
            
            return researcher
        except Exception as e:
            print(f"Error enriching researcher data: {e}")
            return researcher

    def filter_researchers(self, researchers: List[Dict], query_analysis: Dict) -> List[Dict]:
        required_expertise = set(query_analysis.get('search_criteria', {}).get('must_have', []))
        filtered_results = []
        
        for researcher in researchers:
            concepts = [c['display_name'].lower() for c in researcher.get('x_concepts', [])]
            expertise_match = any(req.lower() in ' '.join(concepts) for req in required_expertise)
            
            if expertise_match:
                filtered_results.append(researcher)
        
        return filtered_results
