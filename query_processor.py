from openai import OpenAI
from typing import Dict, List
import json

class QueryProcessor:
    def __init__(self, api_key: str = None):
        self.client = OpenAI(api_key=api_key)
        
        self.query_prompt = """
        Analyze the following research collaboration query and extract key information.
        Focus on:
        1. Research areas and subfields
        2. Required expertise and skills
        3. Type of collaboration sought
        4. Any specific requirements or constraints
        
        Provide the response in JSON format with these exact keys:
        - research_areas: list of relevant research areas
        - expertise: list of required skills and expertise
        - collaboration_type: string describing the type of collaboration
        - requirements: list of specific requirements or constraints
        - search_keywords: list of keywords for database search
        
        Query: {query}
        """

    def process_query(self, query: str) -> Dict:
        try:
            response = self.client.chat.completions.create(
                model="gpt-4",
                messages=[{
                    "role": "user",
                    "content": self.query_prompt.format(query=query)
                }],
                temperature=0.7
            )
            
            # Parse the response content as JSON
            response_text = response.choices[0].message.content
            structured_response = json.loads(response_text)
            
            return structured_response
            
        except Exception as e:
            print(f"Error processing query: {str(e)}")
            return None
    
    def validate_query(self, structured_query: Dict) -> bool:
        required_fields = [
            'research_areas',
            'expertise',
            'collaboration_type',
            'requirements',
            'search_keywords'
        ]
        return all(field in structured_query for field in required_fields)
    
    def expand_research_areas(self, areas: List[str]) -> List[str]:
        return areas

    def preprocess_query(self, query: str) -> str:
        cleaned_query = ''.join(char for char in query if char.isalnum() or char.isspace())
        cleaned_query = cleaned_query.lower()
        cleaned_query = ' '.join(cleaned_query.split())
        return cleaned_query