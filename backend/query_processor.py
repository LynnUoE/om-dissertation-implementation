from typing import Dict, List, Optional, Any
import json
import logging
from datetime import datetime
import re

from pydantic import BaseModel, Field

from llm import DEFAULT_LLM_MODEL, create_llm_client, structured_completion


class TermExpansion(BaseModel):
    term: str = Field(description="One of the extracted research areas, topics or methodologies")
    related_terms: List[str] = Field(description="Alternative phrasings, broader/narrower terms and related concepts")


class QueryAnalysis(BaseModel):
    """Structured Outputs schema for a literature search query"""
    research_areas: List[str] = Field(description="Broader research fields or disciplines relevant to the query")
    specific_topics: List[str] = Field(description="Specific research topics, problems or phenomena being investigated")
    methodologies: List[str] = Field(description="Relevant research methods, approaches or techniques")
    temporal_context: str = Field(description='Time period or date range mentioned, or "current" if none')
    search_keywords: List[str] = Field(description="Additional keywords that would help identify relevant literature")
    expanded_terms: List[TermExpansion] = Field(description="Expansions for the 5 most important extracted terms")


class QueryProcessor:
    def __init__(self, api_key: str, model: str = DEFAULT_LLM_MODEL, base_url: Optional[str] = None):
        self.client = create_llm_client(api_key, base_url)
        self.model = model
        
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
            # Own handler already prints; don't also bubble up to the root logger (duplicate lines)
            self.logger.propagate = False
        
        # Prompt optimized for literature search queries
        self.query_prompt = """
        Analyze the following research literature search query and extract key information for finding relevant academic publications.
        
        Important considerations:
        - Identify primary research topics and their subfields
        - Extract specific methodologies, theories, or techniques mentioned
        - Recognize both technical terminology and general descriptions
        - Identify potential interdisciplinary connections
        - For the 5 most important research areas, topics or methodologies, list alternative phrasings,
          broader/narrower terms and related concepts that might appear in academic literature
        
        Query: {query}
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
            
            # One call returns the analysis and the term expansions, validated against QueryAnalysis
            analysis = structured_completion(
                self.client,
                self.model,
                [{"role": "user", "content": self.query_prompt.format(query=processed_query)}],
                QueryAnalysis,
                temperature=0.2,
            )
            
            structured_response = analysis.model_dump(exclude={'expanded_terms'})
            structured_response['expanded_terms'] = {
                expansion.term: self._dedupe(expansion.related_terms)
                for expansion in analysis.expanded_terms
            }
            
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
    
    @staticmethod
    def _dedupe(terms: List[str]) -> List[str]:
        """Remove case-insensitive duplicates while preserving order"""
        seen = set()
        return [t for t in terms if not (t.lower() in seen or seen.add(t.lower()))]
    
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
                model=self.model,
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

def create_query_processor(api_key: str, model: str = DEFAULT_LLM_MODEL,
                           base_url: Optional[str] = None) -> QueryProcessor:
    """Factory function to create a QueryProcessor instance"""
    return QueryProcessor(api_key, model, base_url)
