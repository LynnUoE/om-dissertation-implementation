from openai import OpenAI
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Union
import json
import logging
from datetime import datetime

@dataclass
class AnalysisResult:
    """Data class to store structured literature analysis results."""
    primary_topics: List[str]
    key_findings: List[str]
    methodology: List[str]
    practical_applications: List[str]
    relevance_score: float
    technical_complexity: int
    citation_context: str
    knowledge_gaps: List[str]
    temporal_context: str
    timestamp: str

class ResearchAnalyzer:
    """Analyzes academic literature using LLM capabilities."""
    
    def __init__(self, api_key: str):
        """Initialize the analyzer with OpenAI API key."""
        self.client = OpenAI(api_key=api_key)
        
        # Configure logging
        self.logger = logging.getLogger('ResearchAnalyzer')
        self.logger.setLevel(logging.INFO)
        
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
        
        # Comprehensive analysis prompt for individual publications
        self.publication_analysis_prompt = """
        Analyze the following academic publication in the context of the user's research query.
        
        PUBLICATION DETAILS:
        Title: {title}
        Authors: {authors}
        Abstract: {abstract}
        Publication Date: {pub_date}
        
        USER QUERY CONTEXT:
        Research Areas: {query_areas}
        Specific Topics: {query_topics}
        
        Provide a comprehensive analysis of this publication addressing:
        1. Primary topics and themes
        2. Key findings and contributions
        3. Methodology and approach
        4. Practical applications or implications
        5. Relevance to the user's query (scale 0.0-1.0)
        6. Technical complexity (scale 1-5)
        7. Citation context (how and why this work would be cited)
        8. Knowledge gaps or limitations identified
        9. Temporal context (how recent/current the research is relative to the field)
        
        YOU MUST RETURN YOUR ANALYSIS AS A VALID JSON OBJECT with these exact keys:
        - primary_topics: list of main topics addressed
        - key_findings: list of major findings or contributions
        - methodology: list of research methods used
        - practical_applications: list of potential applications or implications
        - relevance_score: float between 0.0 and 1.0
        - technical_complexity: integer from 1 to 5
        - citation_context: string explaining how this work would be cited
        - knowledge_gaps: list of limitations or areas for future research
        - temporal_context: string describing how current the research is
        
        Response (as JSON only):
        """
        
        # Prompt for synthesizing multiple publication analyses
        self.synthesis_prompt = """
        Synthesize the analyses of the following academic publications related to the user's query.
        
        USER QUERY:
        {original_query}
        
        PUBLICATION ANALYSES:
        {publication_analyses}
        
        Create a comprehensive research synthesis that addresses:
        1. Dominant research themes across publications
        2. Consensus findings and points of disagreement
        3. Methodological approaches and their effectiveness
        4. Practical implications of the research
        5. Current research frontiers and knowledge gaps
        6. Historical development of key ideas (if apparent)
        7. Suggestions for promising research directions
        
        YOU MUST RETURN YOUR SYNTHESIS AS A VALID JSON OBJECT with these exact keys:
        - research_themes: list of major themes across the literature
        - consensus_findings: list of points where there is general agreement
        - disagreements: list of points where findings diverge
        - methodological_trends: list of common methodological approaches
        - practical_implications: list of real-world applications
        - knowledge_gaps: list of areas needing further research
        - research_timeline: brief description of how ideas have evolved
        - suggested_directions: list of promising research avenues
        
        Response (as JSON only):
        """
        
        # Specialized prompt for analyzing methodologies
        self.methodology_analysis_prompt = """
        Analyze the research methodologies used in the following academic publications.
        
        PUBLICATIONS AND METHODS:
        {publications_methods}
        
        Provide an analysis of the methodological approaches addressing:
        1. Dominant methodological paradigms
        2. Innovative or novel methods
        3. Comparative strengths and limitations
        4. Methodological trends or evolution
        5. Recommendations for methodology selection
        
        YOU MUST RETURN YOUR ANALYSIS AS A VALID JSON OBJECT with these exact keys:
        - dominant_paradigms: list of prevalent methodological approaches
        - innovative_methods: list of novel or emerging methods
        - comparative_assessment: dictionary mapping methods to their strengths/limitations
        - methodological_trends: string describing evolution of methods
        - recommendations: list of methodological recommendations
        
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
        import re
        
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
            # Return empty dictionary in case of parsing failure
            return {}

    def analyze_publication(
        self,
        publication: Dict,
        query_context: Dict
    ) -> Optional[AnalysisResult]:
        """
        Analyze a single academic publication in the context of the user's query.
        
        Args:
            publication: Publication data with title, authors, abstract, etc.
            query_context: Dictionary containing query information
            
        Returns:
            AnalysisResult object or None if analysis fails
        """
        try:
            self.logger.info(f"Analyzing publication: {publication.get('title', 'Untitled')[:50]}...")
            
            # Prepare the prompt with publication and query information
            prompt_data = {
                'title': publication.get('title', 'Untitled'),
                'authors': ', '.join(publication.get('authors', ['Unknown'])),
                'abstract': publication.get('abstract', 'No abstract available'),
                'pub_date': publication.get('publication_date', 'Unknown date'),
                'query_areas': ', '.join(query_context.get('research_areas', [])),
                'query_topics': ', '.join(query_context.get('expertise', [])) 
            }
            
            # Get analysis from LLM
            response = self.client.chat.completions.create(
                model="gpt-4o",
                messages=[{
                    "role": "user",
                    "content": self.publication_analysis_prompt.format(**prompt_data)
                }],
                temperature=0.2,
                response_format={"type": "json_object"}
            )
            
            # Get response text
            response_text = response.choices[0].message.content
            
            # Parse the JSON response
            try:
                analysis_data = json.loads(response_text)
            except json.JSONDecodeError:
                # Try to extract JSON from text if direct parsing fails
                self.logger.warning("Failed to parse direct JSON response, attempting to extract JSON from text")
                analysis_data = self.extract_json_from_text(response_text)
            
            if not analysis_data:
                self.logger.error("Failed to extract valid JSON from LLM response")
                return None
            
            # Create and return AnalysisResult
            return AnalysisResult(
                primary_topics=analysis_data.get('primary_topics', []),
                key_findings=analysis_data.get('key_findings', []),
                methodology=analysis_data.get('methodology', []),
                practical_applications=analysis_data.get('practical_applications', []),
                relevance_score=float(analysis_data.get('relevance_score', 0.0)),
                technical_complexity=int(analysis_data.get('technical_complexity', 3)),
                citation_context=analysis_data.get('citation_context', ''),
                knowledge_gaps=analysis_data.get('knowledge_gaps', []),
                temporal_context=analysis_data.get('temporal_context', ''),
                timestamp=datetime.now().isoformat()
            )
            
        except Exception as e:
            self.logger.error(f"Error analyzing publication: {str(e)}")
            return None

    def analyze_publications(
        self,
        publications: List[Dict],
        query_context: Dict,
        min_relevance: float = 0.5,
        max_publications: int = 10
    ) -> List[Dict]:
        """
        Analyze multiple publications and filter by relevance.
        
        Args:
            publications: List of publication dictionaries
            query_context: Dictionary containing query information
            min_relevance: Minimum relevance score to include in results
            max_publications: Maximum number of publications to analyze
            
        Returns:
            List of dictionaries containing publication and analysis information
        """
        self.logger.info(f"Analyzing {len(publications)} publications for query relevance")
        
        # Limit the number of publications to analyze to avoid excessive API usage
        limited_publications = publications[:max_publications]
        
        analyzed_results = []
        
        for publication in limited_publications:
            analysis = self.analyze_publication(publication, query_context)
            
            if analysis and analysis.relevance_score >= min_relevance:
                analyzed_results.append({
                    'publication': publication,
                    'analysis': self._analysis_result_to_dict(analysis)
                })
        
        # Sort by relevance score
        analyzed_results.sort(
            key=lambda x: x['analysis']['relevance_score'],
            reverse=True
        )
        
        self.logger.info(f"Completed analysis of {len(analyzed_results)} relevant publications")
        return analyzed_results

    def synthesize_analyses(
        self,
        analyzed_results: List[Dict],
        original_query: str
    ) -> Dict:
        """
        Synthesize analyses from multiple publications to create a comprehensive overview.
        
        Args:
            analyzed_results: List of analyzed publications with their analyses
            original_query: The original user query
            
        Returns:
            Dictionary containing synthesis results
        """
        try:
            if not analyzed_results:
                return {
                    "research_themes": [],
                    "consensus_findings": [],
                    "disagreements": [],
                    "methodological_trends": [],
                    "practical_implications": [],
                    "knowledge_gaps": [],
                    "research_timeline": "No information available",
                    "suggested_directions": []
                }
            
            self.logger.info(f"Synthesizing analyses of {len(analyzed_results)} publications")
            
            # Format publication analyses for the prompt
            publication_analyses_text = ""
            for i, result in enumerate(analyzed_results):
                pub = result['publication']
                analysis = result['analysis']
                
                publication_analyses_text += f"PUBLICATION {i+1}:\n"
                publication_analyses_text += f"Title: {pub.get('title', 'Untitled')}\n"
                publication_analyses_text += f"Date: {pub.get('publication_date', 'Unknown')}\n"
                publication_analyses_text += f"Primary Topics: {', '.join(analysis.get('primary_topics', []))}\n"
                publication_analyses_text += f"Key Findings: {', '.join(analysis.get('key_findings', []))}\n"
                publication_analyses_text += f"Methodology: {', '.join(analysis.get('methodology', []))}\n"
                publication_analyses_text += f"Relevance Score: {analysis.get('relevance_score', 0.0)}\n\n"
            
            # Get synthesis from LLM
            response = self.client.chat.completions.create(
                model="gpt-4o",
                messages=[{
                    "role": "user",
                    "content": self.synthesis_prompt.format(
                        original_query=original_query,
                        publication_analyses=publication_analyses_text
                    )
                }],
                temperature=0.3,
                response_format={"type": "json_object"}
            )
            
            # Get response text
            synthesis_text = response.choices[0].message.content
            
            # Parse the JSON response
            try:
                synthesis_data = json.loads(synthesis_text)
            except json.JSONDecodeError:
                # Try to extract JSON from text if direct parsing fails
                self.logger.warning("Failed to parse direct JSON response for synthesis, attempting to extract JSON")
                synthesis_data = self.extract_json_from_text(synthesis_text)
            
            if not synthesis_data:
                self.logger.error("Failed to extract valid JSON from LLM synthesis response")
                return {
                    "research_themes": [],
                    "consensus_findings": [],
                    "disagreements": [],
                    "methodological_trends": [],
                    "practical_implications": [],
                    "knowledge_gaps": [],
                    "research_timeline": "Error in synthesis",
                    "suggested_directions": []
                }
            
            return synthesis_data
            
        except Exception as e:
            self.logger.error(f"Error synthesizing analyses: {str(e)}")
            return {
                "research_themes": [],
                "consensus_findings": [],
                "disagreements": [],
                "methodological_trends": [],
                "practical_implications": [],
                "knowledge_gaps": [],
                "research_timeline": f"Error: {str(e)}",
                "suggested_directions": []
            }

    def analyze_methodologies(
        self,
        analyzed_results: List[Dict]
    ) -> Dict:
        """
        Perform specialized analysis of methodologies across publications.
        
        Args:
            analyzed_results: List of analyzed publications with their analyses
            
        Returns:
            Dictionary containing methodology analysis
        """
        try:
            if not analyzed_results:
                return {
                    "dominant_paradigms": [],
                    "innovative_methods": [],
                    "comparative_assessment": {},
                    "methodological_trends": "No information available",
                    "recommendations": []
                }
            
            self.logger.info(f"Analyzing methodologies across {len(analyzed_results)} publications")
            
            # Format publication methods for the prompt
            publications_methods_text = ""
            for i, result in enumerate(analyzed_results):
                pub = result['publication']
                analysis = result['analysis']
                
                publications_methods_text += f"PUBLICATION {i+1}:\n"
                publications_methods_text += f"Title: {pub.get('title', 'Untitled')}\n"
                publications_methods_text += f"Date: {pub.get('publication_date', 'Unknown')}\n"
                publications_methods_text += f"Methodology: {', '.join(analysis.get('methodology', []))}\n\n"
            
            # Get methodology analysis from LLM
            response = self.client.chat.completions.create(
                model="gpt-4o",
                messages=[{
                    "role": "user",
                    "content": self.methodology_analysis_prompt.format(
                        publications_methods=publications_methods_text
                    )
                }],
                temperature=0.3,
                response_format={"type": "json_object"}
            )
            
            # Get response text
            methodology_text = response.choices[0].message.content
            
            # Parse the JSON response
            try:
                methodology_data = json.loads(methodology_text)
            except json.JSONDecodeError:
                # Try to extract JSON from text if direct parsing fails
                self.logger.warning("Failed to parse direct JSON response for methodology analysis, attempting to extract JSON")
                methodology_data = self.extract_json_from_text(methodology_text)
            
            if not methodology_data:
                self.logger.error("Failed to extract valid JSON from LLM methodology analysis response")
                return {
                    "dominant_paradigms": [],
                    "innovative_methods": [],
                    "comparative_assessment": {},
                    "methodological_trends": "Error in analysis",
                    "recommendations": []
                }
            
            return methodology_data
            
        except Exception as e:
            self.logger.error(f"Error analyzing methodologies: {str(e)}")
            return {
                "dominant_paradigms": [],
                "innovative_methods": [],
                "comparative_assessment": {},
                "methodological_trends": f"Error: {str(e)}",
                "recommendations": []
            }

    def generate_literature_summary(
        self,
        analyzed_results: List[Dict],
        synthesis: Dict,
        original_query: str
    ) -> Dict:
        """
        Generate a comprehensive literature summary based on analyses and synthesis.
        
        Args:
            analyzed_results: List of analyzed publications with their analyses
            synthesis: Results of synthesis analysis
            original_query: The original user query
            
        Returns:
            Dictionary containing formatted summary
        """
        try:
            if not analyzed_results or not synthesis:
                return {"summary": "Insufficient data for literature summary."}
            
            # Extract publication details
            publications = [result['publication'] for result in analyzed_results]
            publication_count = len(publications)
            
            # Calculate date range
            pub_dates = [
                datetime.fromisoformat(pub.get('publication_date', '2020-01-01')) 
                for pub in publications 
                if pub.get('publication_date')
            ]
            
            date_range = "Unknown date range"
            if pub_dates:
                oldest = min(pub_dates).year
                newest = max(pub_dates).year
                date_range = f"{oldest} to {newest}"
            
            # Find top themes
            research_themes = synthesis.get('research_themes', [])
            top_themes = research_themes[:3] if research_themes else []
            
            # Format key findings
            consensus_findings = synthesis.get('consensus_findings', [])
            
            # Format knowledge gaps
            knowledge_gaps = synthesis.get('knowledge_gaps', [])
            
            # Prepare summary structure
            summary = {
                "query": original_query,
                "publication_count": publication_count,
                "date_range": date_range,
                "top_themes": top_themes,
                "consensus_findings": consensus_findings,
                "knowledge_gaps": knowledge_gaps,
                "suggested_directions": synthesis.get('suggested_directions', []),
                "top_publications": self._get_top_publications(analyzed_results, 3)
            }
            
            return summary
            
        except Exception as e:
            self.logger.error(f"Error generating literature summary: {str(e)}")
            return {"summary": f"Error generating literature summary: {str(e)}"}

    def _analysis_result_to_dict(self, analysis: AnalysisResult) -> Dict:
        """Convert AnalysisResult to dictionary format"""
        return {
            'primary_topics': analysis.primary_topics,
            'key_findings': analysis.key_findings,
            'methodology': analysis.methodology,
            'practical_applications': analysis.practical_applications,
            'relevance_score': analysis.relevance_score,
            'technical_complexity': analysis.technical_complexity,
            'citation_context': analysis.citation_context,
            'knowledge_gaps': analysis.knowledge_gaps,
            'temporal_context': analysis.temporal_context,
            'timestamp': analysis.timestamp
        }

    def _get_top_publications(
        self, 
        analyzed_results: List[Dict],
        count: int = 3
    ) -> List[Dict]:
        """Get the top publications by relevance score"""
        sorted_results = sorted(
            analyzed_results,
            key=lambda x: x['analysis']['relevance_score'],
            reverse=True
        )
        
        top_publications = []
        for result in sorted_results[:count]:
            pub = result['publication']
            analysis = result['analysis']
            
            top_publications.append({
                'title': pub.get('title', 'Untitled'),
                'authors': pub.get('authors', []),
                'publication_date': pub.get('publication_date', 'Unknown date'),
                'relevance_score': analysis.get('relevance_score', 0.0),
                'key_findings': analysis.get('key_findings', [])[:2]  # Just the top 2 findings
            })
        
        return top_publications

def create_analyzer(api_key: str) -> ResearchAnalyzer:
    """Factory function to create a ResearchAnalyzer instance."""
    return ResearchAnalyzer(api_key)