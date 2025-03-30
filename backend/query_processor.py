from openai import OpenAI
from typing import Dict, List, Optional, Any
import json
import logging
from datetime import datetime
import re

class QueryProcessor:
    def __init__(self, api_key: str):
        self.client = OpenAI(api_key=api_key)
        
        # Configure logging
        self.logger = logging.getLogger('QueryProcessor')
        self.logger.setLevel(logging.INFO)
        
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
        
        # Prompt optimized for literature search queries
        self.query_prompt = """
        Analyze the following research literature search query and extract key information for finding relevant academic publications.
        
        Important considerations:
        - Identify primary research topics and their subfields
        - Extract specific methodologies, theories, or techniques mentioned
        - Recognize both technical terminology and general descriptions
        - Identify potential interdisciplinary connections
        
        YOU MUST PROVIDE THE RESPONSE AS A VALID JSON OBJECT with these exact keys:
        - research_areas: list of broader research fields or disciplines relevant to the query
        - specific_topics: list of specific research topics, problems, or phenomena being investigated
        - methodologies: list of relevant research methods, approaches, or techniques
        - temporal_context: any time periods or date ranges mentioned (or "current" if recent research is implied)
        - search_keywords: additional keywords that would help identify relevant literature
        
        Query: {query}
        
        Response (as JSON only):
        """
        
        # Template for expanding search terms
        self.expansion_prompt = """
        For each of the following research terms, provide alternative phrasings, broader/narrower terms, and related concepts that might appear in academic literature on this topic.
        
        YOU MUST FORMAT YOUR RESPONSE AS A VALID JSON OBJECT where each key is one of the original terms,
        and each value is a list of related terms that would help in a literature search.
        
        Research terms: {terms}
        
        Response (as JSON only):
        """

    def extract_json_from_text(self, text: str) -> Dict:
        """
        Extract JSON from text, handling cases where the model might add explanatory text
        
        Args:
            text: Text that might contain JSON
            
        Returns:
            Extracted JSON as a dictionary
        """
        # Look for JSON in markdown code blocks
        json_match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', text)
        if json_match:
            json_str = json_match.group(1)
        else:
            # Try to find JSON object between curly braces if no code block
            json_match = re.search(r'\{[\s\S]*\}', text)
            if json_match:
                json_str = json_match.group(0)
            else:
                # Just use the original text if no clear JSON pattern found
                json_str = text
        
        # Remove any non-JSON text before or after (like explanations)
        json_str = json_str.strip()
        
        try:
            return json.loads(json_str)
        except json.JSONDecodeError as e:
            self.logger.error(f"Failed to parse JSON: {e}")
            self.logger.debug(f"Attempted to parse text: {json_str}")
            # Return basic structure in case of parsing failure
            return {}

    def process_query(self, query: str) -> Dict:
        """
        Process a natural language query to extract structured information for literature search
        
        Args:
            query: Natural language query describing research literature needs
            
        Returns:
            Dictionary containing structured search parameters
        """
        try:
            self.logger.info(f"Processing literature search query: {query[:100]}...")
            
            # Clean input query
            processed_query = self.preprocess_query(query)
            
            # Get structured analysis from LLM
            response = self.client.chat.completions.create(
                model="gpt-4o",
                messages=[{
                    "role": "user",
                    "content": self.query_prompt.format(query=processed_query)
                }],
                temperature=0.2,
                response_format={"type": "json_object"}  # Specify JSON response format
            )
            
            # Get response text
            response_text = response.choices[0].message.content
            
            # Parse the JSON response
            try:
                structured_response = json.loads(response_text)
            except json.JSONDecodeError:
                # Try to extract JSON from text if direct parsing fails
                self.logger.warning("Failed to parse direct JSON response, attempting to extract JSON from text")
                structured_response = self.extract_json_from_text(response_text)
            
            # Validate and normalize the response structure
            structured_response = self.normalize_response(structured_response)
            
            # Create a combined list of all search terms for expansion
            all_terms = []
            for field in ['research_areas', 'specific_topics', 'methodologies']:
                if field in structured_response and structured_response[field]:
                    all_terms.extend(structured_response[field])
            
            # Get term expansions if we have at least one term
            if all_terms:
                # Select at most 5 terms to avoid overloading the prompt
                selected_terms = all_terms[:5]
                expanded_terms = self.expand_search_terms(selected_terms)
                structured_response['expanded_terms'] = expanded_terms
            
            # Add timestamp for tracking
            structured_response['processed_at'] = datetime.now().isoformat()
            
            # Format the response for compatibility with literature searcher
            search_parameters = self.format_for_searcher(structured_response)
            
            return search_parameters
            
        except Exception as e:
            self.logger.error(f"Error processing literature search query: {str(e)}")
            # Return a basic structure in case of error
            return {
                'research_areas': [],
                'expertise': [],
                'search_keywords': [],
                'requirements': [],
                'error': str(e)
            }
    
    def normalize_response(self, response: Dict) -> Dict:
        """
        Normalize and validate the structured response
        
        Args:
            response: Raw response dictionary
            
        Returns:
            Normalized response dictionary
        """
        normalized = {}
        
        # Define expected fields and their default values
        expected_fields = {
            'research_areas': [],
            'specific_topics': [],
            'methodologies': [],
            'temporal_context': 'current',
            'search_keywords': []
        }
        
        # Ensure all expected fields exist with appropriate types
        for field, default in expected_fields.items():
            if field in response and response[field] is not None:
                # Ensure list fields are actually lists
                if isinstance(default, list) and not isinstance(response[field], list):
                    if isinstance(response[field], str):
                        normalized[field] = [response[field]]
                    else:
                        normalized[field] = default
                else:
                    normalized[field] = response[field]
            else:
                normalized[field] = default
        
        return normalized
    
    def expand_search_terms(self, terms: List[str]) -> Dict[str, List[str]]:
        """
        Expand search terms with related concepts and alternative phrasings
        
        Args:
            terms: List of search terms to expand
            
        Returns:
            Dictionary mapping original terms to lists of related terms
        """
        if not terms:
            return {}
            
        try:
            # Get expansion suggestions from LLM
            response = self.client.chat.completions.create(
                model="gpt-4o",
                messages=[{
                    "role": "user",
                    "content": self.expansion_prompt.format(terms=", ".join(terms))
                }],
                temperature=0.3,
                response_format={"type": "json_object"}  # Specify JSON response format
            )
            
            # Get response text
            expansion_text = response.choices[0].message.content
            
            # Parse the JSON response
            try:
                expansions = json.loads(expansion_text)
            except json.JSONDecodeError:
                # Try to extract JSON from text if direct parsing fails
                self.logger.warning("Failed to parse direct JSON response for expansions, attempting to extract JSON")
                expansions = self.extract_json_from_text(expansion_text)
            
            # Ensure we have the proper structure
            validated_expansions = {}
            for term in terms:
                if term in expansions and isinstance(expansions[term], list):
                    # Remove duplicates while preserving order
                    unique_expansions = []
                    seen = set()
                    for item in expansions[term]:
                        item_lower = item.lower()
                        if item_lower not in seen:
                            seen.add(item_lower)
                            unique_expansions.append(item)
                    
                    validated_expansions[term] = unique_expansions
                else:
                    validated_expansions[term] = []
                    
            return validated_expansions
            
        except Exception as e:
            self.logger.error(f"Error expanding search terms: {str(e)}")
            # Return empty expansions in case of error
            return {term: [] for term in terms}
    
    def preprocess_query(self, query: str) -> str:
        """
        Preprocess the query to improve LLM analysis
        
        Args:
            query: Original query string
            
        Returns:
            Preprocessed query string
        """
        # Remove excessive whitespace
        cleaned_query = ' '.join(query.split())
        return cleaned_query
    
    def format_for_searcher(self, structured_response: Dict) -> Dict:
        """
        Format the structured response for compatibility with the literature searcher component
        
        Args:
            structured_response: The normalized structured response
            
        Returns:
            Formatted parameters for literature search
        """
        search_parameters = {
            'research_areas': structured_response.get('research_areas', []),
            'expertise': structured_response.get('specific_topics', []) + structured_response.get('methodologies', []),
            'search_keywords': structured_response.get('search_keywords', []),
            'requirements': []  # Compatibility with existing interface
        }
        
        # Add expanded terms if available
        if 'expanded_terms' in structured_response:
            search_parameters['expanded_terms'] = structured_response['expanded_terms']
        
        # Add temporal context if specified
        if structured_response.get('temporal_context') and structured_response['temporal_context'] != 'current':
            search_parameters['temporal_context'] = structured_response['temporal_context']
        
        # Copy over additional fields that might be useful
        for field in ['processed_at']:
            if field in structured_response:
                search_parameters[field] = structured_response[field]
        
        return search_parameters
    
    def analyze_interdisciplinary_aspects(self, structured_query: Dict) -> Dict[str, Any]:
        """
        Analyze potential interdisciplinary connections in the query
        
        Args:
            structured_query: Structured query information
            
        Returns:
            Dictionary with interdisciplinary analysis
        """
        research_areas = structured_query.get('research_areas', [])
        if len(research_areas) <= 1:
            return {"is_interdisciplinary": False, "connections": []}
            
        try:
            # Construct a prompt to analyze interdisciplinary connections
            interdisciplinary_prompt = f"""
            Analyze potential interdisciplinary connections between these research areas:
            {', '.join(research_areas)}
            
            Additional topics mentioned: {', '.join(structured_query.get('expertise', []))}
            
            Identify specific connection points and potential research insights at these intersections.
            
            YOU MUST PROVIDE YOUR RESPONSE AS A VALID JSON OBJECT with:
            - is_interdisciplinary: boolean indicating if this is truly interdisciplinary
            - primary_discipline: the main discipline if one dominates, or null if balanced
            - connections: list of specific connection points between disciplines
            - key_journals: list of academic journals that might publish interdisciplinary research in these areas
            
            Response (as JSON only):
            """
            
            response = self.client.chat.completions.create(
                model="gpt-4o",
                messages=[{
                    "role": "user",
                    "content": interdisciplinary_prompt
                }],
                temperature=0.2,
                response_format={"type": "json_object"}  # Specify JSON response format
            )
            
            # Get response text
            analysis_text = response.choices[0].message.content
            
            # Parse the JSON response
            try:
                analysis = json.loads(analysis_text)
            except json.JSONDecodeError:
                # Try to extract JSON from text if direct parsing fails
                self.logger.warning("Failed to parse direct JSON for interdisciplinary analysis, attempting to extract")
                analysis = self.extract_json_from_text(analysis_text)
                
            return analysis
            
        except Exception as e:
            self.logger.error(f"Error analyzing interdisciplinary aspects: {str(e)}")
            return {"is_interdisciplinary": False, "connections": []}

def create_query_processor(api_key: str) -> QueryProcessor:
    """Factory function to create a QueryProcessor instance"""
    return QueryProcessor(api_key)