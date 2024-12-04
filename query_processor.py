# query_processor.py
import json
import requests
from typing import Dict, List, Optional

class QueryProcessor:
    def __init__(self, openai_api_key: str):
        """
        Initialize the QueryProcessor with OpenAI API key.
        
        Args:
            openai_api_key (str): OpenAI API key for GPT processing
        """
        self.openai_api_key = openai_api_key
        self.openai_headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {openai_api_key}'
        }

    def process_query(self, query: str) -> Dict:
        """
        Process and analyze the search query to extract structured information.
        
        Args:
            query (str): Raw search query from user
            
        Returns:
            Dict: Structured query analysis
        """
        # Clean the query
        cleaned_query = self._clean_query(query)
        
        # Generate the analysis prompt
        prompt = self._generate_analysis_prompt(cleaned_query)
        
        # Get LLM analysis
        analysis = self._get_llm_analysis(prompt)
        
        try:
            # Parse the response into structured format
            structured_analysis = json.loads(analysis) if analysis else {}
            
            # Validate and clean the analysis
            validated_analysis = self._validate_analysis(structured_analysis)
            
            return validated_analysis
            
        except json.JSONDecodeError as e:
            print(f"Error parsing LLM response: {e}")
            return self._get_default_analysis()

    def _clean_query(self, query: str) -> str:
        """
        Clean and normalize the query string.
        """
        # Remove extra whitespace and special characters
        cleaned = query.strip()
        cleaned = ' '.join(cleaned.split())  # Normalize whitespace
        return cleaned

    def _generate_analysis_prompt(self, query: str) -> str:
        """
        Generate a detailed prompt for the LLM to analyze the query.
        """
        return f"""As an academic research analyst, analyze this query and break it down into specific components:
        Query: "{query}"

        Provide a detailed analysis with:
        1. Main academic disciplines involved (maximum 3) with their importance (high/medium/low) and key research areas
        2. Specific expertise requirements or qualifications needed
        3. Potential interdisciplinary connections
        4. Research focus indicators (theoretical/applied/both)
        5. Required vs preferred criteria

        Format the response as a structured JSON with these exact keys:
        {{
            "disciplines": [
                {{
                    "name": "discipline name",
                    "importance": "high/medium/low",
                    "key_areas": ["area1", "area2", "area3"]
                }}
            ],
            "interdisciplinary_connections": [
                {{
                    "field1": "field name",
                    "field2": "field name",
                    "relevance": "description"
                }}
            ],
            "expertise_indicators": [
                {{
                    "type": "requirement type",
                    "description": "detailed description",
                    "importance": "required/preferred"
                }}
            ],
            "research_focus": {{
                "type": "theoretical/applied/both",
                "description": "focus description"
            }},
            "search_criteria": {{
                "must_have": ["criteria1", "criteria2"],
                "preferred": ["criteria1", "criteria2"]
            }}
        }}"""

    def _get_llm_analysis(self, prompt: str) -> Optional[str]:
        """
        Get analysis from OpenAI API.
        """
        try:
            data = {
                'model': 'gpt-3.5-turbo',
                'messages': [
                    {
                        'role': 'system',
                        'content': 'You are a specialized academic research analyst focusing on analyzing research queries and expertise requirements.'
                    },
                    {
                        'role': 'user',
                        'content': prompt
                    }
                ],
                'temperature': 0.7,
                'max_tokens': 800
            }

            response = requests.post(
                'https://api.openai.com/v1/chat/completions',
                json=data,
                headers=self.openai_headers
            )

            if response.status_code == 200:
                return response.json()['choices'][0]['message']['content']
            else:
                print(f"OpenAI API error: {response.status_code}")
                return None

        except Exception as e:
            print(f"Error in OpenAI API call: {str(e)}")
            return None

    def _validate_analysis(self, analysis: Dict) -> Dict:
        """
        Validate and clean the analysis structure.
        """
        validated = {
            'disciplines': [],
            'interdisciplinary_connections': [],
            'expertise_indicators': [],
            'research_focus': {},
            'search_criteria': {
                'must_have': [],
                'preferred': []
            }
        }

        # Validate disciplines
        if 'disciplines' in analysis:
            for discipline in analysis['disciplines']:
                if isinstance(discipline, dict) and 'name' in discipline:
                    validated['disciplines'].append({
                        'name': discipline.get('name', ''),
                        'importance': discipline.get('importance', 'medium'),
                        'key_areas': discipline.get('key_areas', [])
                    })

        # Validate other fields
        if 'interdisciplinary_connections' in analysis:
            validated['interdisciplinary_connections'] = analysis['interdisciplinary_connections']

        if 'expertise_indicators' in analysis:
            validated['expertise_indicators'] = analysis['expertise_indicators']

        if 'research_focus' in analysis:
            validated['research_focus'] = analysis['research_focus']

        if 'search_criteria' in analysis:
            criteria = analysis['search_criteria']
            validated['search_criteria']['must_have'] = criteria.get('must_have', [])
            validated['search_criteria']['preferred'] = criteria.get('preferred', [])

        return validated

    def _get_default_analysis(self) -> Dict:
        """
        Provide a default analysis structure in case of errors.
        """
        return {
            'disciplines': [],
            'interdisciplinary_connections': [],
            'expertise_indicators': [],
            'research_focus': {
                'type': 'both',
                'description': 'Not specified'
            },
            'search_criteria': {
                'must_have': [],
                'preferred': []
            }
        }

# Example usage code
def main():
    # Initialize with your OpenAI API key
    OPENAI_API_KEY = 'your-openai-api-key'
    processor = QueryProcessor(OPENAI_API_KEY)

    # Test queries
    test_queries = [
        "machine learning experts in healthcare with focus on medical imaging",
        "quantum computing researchers with experience in algorithm development",
        "data science professors working on natural language processing"
    ]

    for query in test_queries:
        print(f"\nProcessing query: {query}")
        result = processor.process_query(query)
        print("\nAnalysis Results:")
        print(json.dumps(result, indent=2))
        print("-" * 80)

if __name__ == "__main__":
    main()