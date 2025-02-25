from dataclasses import dataclass
from typing import Dict, List, Optional
from openai import OpenAI
import json
import logging
from datetime import datetime

@dataclass
class AnalysisResult:
    """Data class to store structured analysis results."""
    research_areas: List[str]
    key_findings: List[str]
    potential_applications: List[str]
    relevance_score: float
    technical_complexity: int
    collaboration_potential: str
    expertise_match: Dict[str, float]
    timestamp: str

class ResearchAnalyzer:
    """Analyzes research resources using LLM capabilities."""
    
    def __init__(self, api_key: str):
        """Initialize the analyzer with OpenAI API key."""
        self.client = OpenAI(api_key=api_key)
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            filename='research_analysis.log'
        )
        self.logger = logging.getLogger('ResearchAnalyzer')
        
        self.analysis_prompt = """
        Analyze the following research resource in the context of a potential collaboration.
        Consider these aspects:
        1. Main research areas and specific subfields
        2. Key findings and contributions
        3. Potential applications and impact
        4. Technical complexity (1-5 scale)
        5. Relevance to the query
        6. Collaboration potential
        7. Required expertise match
        
        Research:
        Title: {title}
        Authors: {authors}
        Abstract: {abstract}
        Concepts: {concepts}
        
        Query Context:
        Research Areas: {query_areas}
        Required Expertise: {query_expertise}
        Collaboration Type: {collaboration_type}
        
        Provide the analysis in JSON format with these exact keys:
        - research_areas: list of main research areas
        - key_findings: list of main findings and contributions
        - potential_applications: list of possible applications
        - relevance_score: float between 0-1
        - technical_complexity: integer 1-5
        - collaboration_potential: string describing collaboration possibilities
        - expertise_match: dictionary mapping required expertise to match score (0-1)
        """

    def analyze_resource(
        self,
        resource: 'ResearchResource',
        structured_query: Dict
    ) -> Optional[AnalysisResult]:
        """
        Analyze a single research resource in the context of the query.
        
        Args:
            resource: ResearchResource object to analyze
            structured_query: Dictionary containing query information
            
        Returns:
            AnalysisResult object or None if analysis fails
        """
        try:
            # Prepare the prompt with resource and query information
            prompt_data = {
                'title': resource.title,
                'authors': ', '.join(resource.authors),
                'abstract': resource.abstract or 'No abstract available',
                'concepts': ', '.join(resource.concepts),
                'query_areas': ', '.join(structured_query['research_areas']),
                'query_expertise': ', '.join(structured_query['expertise']),
                'collaboration_type': structured_query['collaboration_type']
            }
            
            # Get analysis from LLM
            response = self.client.chat.completions.create(
                model="gpt-4",
                messages=[{
                    "role": "user",
                    "content": self.analysis_prompt.format(**prompt_data)
                }],
                temperature=0.3
            )
            
            # Parse the response
            analysis_data = json.loads(response.choices[0].message.content)
            
            # Create and return AnalysisResult
            return AnalysisResult(
                research_areas=analysis_data['research_areas'],
                key_findings=analysis_data['key_findings'],
                potential_applications=analysis_data['potential_applications'],
                relevance_score=analysis_data['relevance_score'],
                technical_complexity=analysis_data['technical_complexity'],
                collaboration_potential=analysis_data['collaboration_potential'],
                expertise_match=analysis_data['expertise_match'],
                timestamp=datetime.now().isoformat()
            )
            
        except Exception as e:
            self.logger.error(f"Error analyzing resource {resource.title}: {str(e)}")
            return None

    def analyze_resources(
        self,
        resources: List['ResearchResource'],
        structured_query: Dict,
        min_relevance: float = 0.5
    ) -> List[Dict]:
        """
        Analyze multiple research resources and filter by relevance.
        
        Args:
            resources: List of ResearchResource objects
            structured_query: Dictionary containing query information
            min_relevance: Minimum relevance score to include in results
            
        Returns:
            List of dictionaries containing resource and analysis information
        """
        analyzed_results = []
        
        for resource in resources:
            analysis = self.analyze_resource(resource, structured_query)
            
            if analysis and analysis.relevance_score >= min_relevance:
                analyzed_results.append({
                    'resource': resource,
                    'analysis': analysis
                })
        
        # Sort by relevance score
        analyzed_results.sort(
            key=lambda x: x['analysis'].relevance_score,
            reverse=True
        )
        
        return analyzed_results

    def get_collaboration_recommendations(
        self,
        analyzed_results: List[Dict]
    ) -> List[Dict]:
        """
        Generate collaboration recommendations based on analyzed results.
        
        Args:
            analyzed_results: List of analyzed resources and their analyses
            
        Returns:
            List of collaboration recommendations
        """
        recommendations = []
        
        for result in analyzed_results:
            resource = result['resource']
            analysis = result['analysis']
            
            recommendations.append({
                'title': resource.title,
                'institution': resource.institution,
                'authors': resource.authors,
                'relevance_score': analysis.relevance_score,
                'collaboration_potential': analysis.collaboration_potential,
                'expertise_match': analysis.expertise_match,
                'recommendation': self._generate_recommendation(resource, analysis)
            })
        
        return recommendations

    def _generate_recommendation(
        self,
        resource: 'ResearchResource',
        analysis: AnalysisResult
    ) -> str:
        """Generate a specific collaboration recommendation."""
        avg_expertise_match = sum(analysis.expertise_match.values()) / len(analysis.expertise_match)
        
        if analysis.relevance_score > 0.8 and avg_expertise_match > 0.7:
            priority = "High"
        elif analysis.relevance_score > 0.6 and avg_expertise_match > 0.5:
            priority = "Medium"
        else:
            priority = "Low"
            
        return (
            f"Priority: {priority}. "
            f"This research aligns well with your interests in {', '.join(analysis.research_areas)}. "
            f"Potential collaboration could focus on {analysis.collaboration_potential}."
        )

def create_analyzer(api_key: str) -> ResearchAnalyzer:
    """Factory function to create a ResearchAnalyzer instance."""
    api_key ="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"
    return ResearchAnalyzer(api_key)