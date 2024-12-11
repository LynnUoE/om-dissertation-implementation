import requests
from typing import Dict, List, Optional
import urllib.parse

class ResearcherSearch:
    def __init__(self, email: str = "s2231967@ed.ac.uk"):
        """
        Initialize the ResearcherSearch with OpenAlex API configuration
        
        Args:
            email: Your email for polite usage of OpenAlex API
        """
        self.base_url = "https://api.openalex.org/v1"  # Updated to include version
        self.email = email
        self.headers = {
            'User-Agent': f'ResearcherSearch/{email}'
        }
    
    def _construct_search_query(self, query_data: Dict) -> str:
        """
        Construct OpenAlex search query from processed query data
        """
        search_components = []
        
        # Add research areas and expertise to search
        all_topics = []
        if query_data.get('research_areas'):
            all_topics.extend(query_data['research_areas'])
        if query_data.get('expertise'):
            all_topics.extend(query_data['expertise'])
        
        if all_topics:
            # Create a combined topic search
            topics_query = ' OR '.join(f'"{topic}"' for topic in all_topics)
            search_components.append(f'display_name.search:({topics_query})')
        
        # Combine all components
        return ' AND '.join(search_components)

    def search_researchers(self, query_data: Dict, 
                         max_results: int = 20,
                         min_works: int = 5) -> List[Dict]:
        """
        Search for researchers based on processed query data
        """
        try:
            search_query = self._construct_search_query(query_data)
            
            params = {
                'filter': f'works_count>={min_works}',
                'search': search_query,
                'per-page': max_results,
                'sort': 'cited_by_count:desc'  # Sort by citation count
            }
            
            url = f"{self.base_url}/authors"
            
            print(f"\nMaking request to OpenAlex:")
            print(f"URL: {url}")
            print(f"Search Query: {search_query}")
            
            response = requests.get(
                url,
                params=params,
                headers=self.headers
            )
            
            response.raise_for_status()
            data = response.json()
            
            researchers = []
            for item in data.get('results', []):
                researcher = {
                    'id': item.get('id'),
                    'name': item.get('display_name'),
                    'works_count': item.get('works_count'),
                    'cited_by_count': item.get('cited_by_count'),
                    'institutions': [
                        inst.get('display_name') 
                        for inst in [item.get('last_known_institution')] 
                        if inst and inst.get('display_name')
                    ],
                    'concepts': [
                        {
                            'name': concept.get('display_name'),
                            'score': concept.get('score')
                        }
                        for concept in item.get('x_concepts', [])[:5]
                    ]
                }
                researchers.append(researcher)
            
            return researchers
            
        except requests.exceptions.RequestException as e:
            print(f"Error searching OpenAlex: {str(e)}")
            if hasattr(e.response, 'text'):
                print(f"Response content: {e.response.text}")
            return []

    def get_researcher_details(self, researcher_id: str) -> Optional[Dict]:
        """
        Get detailed information about a specific researcher
        """
        try:
            # Clean the researcher ID to ensure proper format
            researcher_id = researcher_id.replace('https://openalex.org/', '')
            url = f"{self.base_url}/authors/{researcher_id}"
            
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            
            data = response.json()
            
            return {
                'id': data.get('id'),
                'name': data.get('display_name'),
                'works_count': data.get('works_count'),
                'cited_by_count': data.get('cited_by_count'),
                'institutions': [
                    inst.get('display_name') 
                    for inst in [data.get('last_known_institution')]
                    if inst and inst.get('display_name')
                ],
                'concepts': [
                    {
                        'name': concept.get('display_name'),
                        'score': concept.get('score')
                    }
                    for concept in data.get('x_concepts', [])
                ]
            }
            
        except requests.exceptions.RequestException as e:
            print(f"Error fetching researcher details: {str(e)}")
            if hasattr(e.response, 'text'):
                print(f"Response content: {e.response.text}")
            return None