# integrated_research_system.py
from typing import Dict, List, Optional
import logging
from datetime import datetime

# Import components from existing system
from query_processor import QueryProcessor
from research_analyzer import ResearchAnalyzer, create_analyzer, AnalysisResult

# Import the new ExpertSearcher
from expert_searcher import ExpertSearcher, create_expert_searcher, ResearchExpert

class IntegratedResearchSystem:
    """
    Integrated research collaboration system that combines query processing,
    expert searching, and research analysis capabilities.
    """
    
    def __init__(self, email: str, openai_api_key: str):
        """
        Initialize the integrated system with API credentials
        
        Args:
            email: Email for OpenAlex API identification
            openai_api_key: API key for OpenAI services
        """
        # Initialize system components
        self.query_processor = QueryProcessor(api_key=openai_api_key)
        self.expert_searcher = create_expert_searcher(email)
        self.research_analyzer = create_analyzer(openai_api_key)
        
        # Configure logging
        self.logger = logging.getLogger('IntegratedResearchSystem')
        self.logger.setLevel(logging.INFO)
        
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
            
        self.logger.info("Integrated Research System initialized")
    
    def process_query(self, query: str) -> Dict:
        """
        Process a natural language query into structured format
        
        Args:
            query: Natural language query string
            
        Returns:
            Dictionary containing structured query information
        """
        self.logger.info(f"Processing query: {query}")
        
        # Use QueryProcessor to structure the query
        structured_query = self.query_processor.process_query(query)
        
        if not structured_query:
            self.logger.error("Failed to process query")
            return {"error": "Unable to process query"}
        
        if not self.query_processor.validate_query(structured_query):
            self.logger.error("Invalid query structure")
            return {"error": "Query structure is invalid"}
            
        self.logger.info("Query processed successfully")
        return structured_query
    
    def find_experts(
        self, 
        query: str, 
        max_results: int = 5
    ) -> Dict:
        """
        Find experts based on a natural language query
        
        Args:
            query: Natural language query
            max_results: Maximum number of results to return
            
        Returns:
            Dictionary containing experts and analysis
        """
        # Process the query
        structured_query = self.process_query(query)
        
        if "error" in structured_query:
            return {"error": structured_query["error"]}
        
        # Find experts using ExpertSearcher
        experts = self.expert_searcher.search_experts(
            structured_query,
            max_results=max_results,
            min_works=3
        )
        
        if not experts:
            self.logger.warning("No experts found")
            return {"message": "No experts found matching your criteria"}
        
        # Convert to dictionary format
        expert_data = [expert.to_dict() for expert in experts]
        
        # Analyze each expert for match quality
        analyzed_experts = []
        for expert in expert_data:
            analysis = self._analyze_expert_match(expert, structured_query)
            analyzed_experts.append({
                **expert,
                "analysis": analysis
            })
        
        return {
            "query": structured_query,
            "experts": analyzed_experts,
            "count": len(analyzed_experts)
        }
    
    def find_multidisciplinary_experts(
        self,
        query: str,
        secondary_disciplines: Optional[List[str]] = None,
        max_results: int = 5
    ) -> Dict:
        """
        Find experts working across multiple disciplines
        
        Args:
            query: Query describing primary discipline
            secondary_disciplines: List of secondary disciplines
            max_results: Maximum number of results
            
        Returns:
            Dictionary containing experts and analysis
        """
        # Process the query to extract primary discipline
        structured_query = self.process_query(query)
        
        if "error" in structured_query:
            return {"error": structured_query["error"]}
        
        # Extract primary discipline
        if "research_areas" not in structured_query or not structured_query["research_areas"]:
            return {"error": "No primary discipline identified in query"}
            
        primary_discipline = structured_query["research_areas"][0]
        
        # Use provided secondary disciplines or extract from query
        if not secondary_disciplines and "expertise" in structured_query:
            secondary_disciplines = structured_query["expertise"]
        
        if not secondary_disciplines:
            return {"error": "Secondary disciplines not identified"}
        
        # Search for multidisciplinary experts
        experts = self.expert_searcher.search_multidisciplinary(
            primary_discipline,
            secondary_disciplines,
            max_results=max_results,
            require_all=False
        )
        
        if not experts:
            return {"message": "No multidisciplinary experts found"}
            
        # Add analysis for each expert
        for expert in experts:
            expert["analysis"] = {
                "recommendation": self._generate_recommendation(
                    expert["name"],
                    expert["relevance_score"]
                )
            }
        
        return {
            "primary_discipline": primary_discipline,
            "secondary_disciplines": secondary_disciplines,
            "experts": experts,
            "count": len(experts)
        }
    
    def search_resources_for_collaboration(
        self, 
        query: str,
        max_results: int = 5,
        min_relevance: float = 0.5
    ) -> Dict:
        """
        Search for research resources relevant to collaboration
        
        Args:
            query: Natural language query
            max_results: Maximum number of results
            min_relevance: Minimum relevance score threshold
            
        Returns:
            Dictionary with research resources and analysis
        """
        # Process the query
        structured_query = self.process_query(query)
        
        if "error" in structured_query:
            return {"error": structured_query["error"]}
        
        # Extract search terms
        search_terms = []
        
        if "research_areas" in structured_query:
            search_terms.extend(structured_query["research_areas"])
            
        if "expertise" in structured_query:
            search_terms.extend(structured_query["expertise"])
        
        if not search_terms:
            return {"error": "No search terms identified in query"}
        
        # Convert experts to research resources
        # This would normally use OpenAlexSearcher, but we can adapt ExpertSearcher results
        experts = self.expert_searcher.search_experts(
            structured_query,
            max_results=max_results * 2  # Get more for filtering
        )
        
        if not experts:
            return {"message": "No relevant research found"}
        
        # Convert experts to research resources
        resources = []
        for expert in experts:
            if not expert.top_works:
                continue
                
            # Take the top work from each expert
            top_work = expert.top_works[0]
            
            # Create a research resource from the top work
            resource = ResearchResource(
                title=top_work.get("title", "Unknown"),
                authors=[expert.name],
                publication_date=top_work.get("publication_date", ""),
                doi=None,  # Not available from expert searcher
                citations_count=top_work.get("citations", 0),
                concepts=list(expert.expertise_areas)[:10],
                institution=expert.institution,
                publication_type="journal-article",  # Default assumption
                abstract=""  # Not available from expert searcher
            )
            
            resources.append(resource)
        
        # Analyze resources using ResearchAnalyzer
        analyzed_results = self.research_analyzer.analyze_resources(
            resources,
            structured_query,
            min_relevance=min_relevance
        )
        
        # Format results
        formatted_results = []
        for result in analyzed_results:
            resource = result["resource"]
            analysis = result["analysis"]
            
            formatted_results.append({
                "title": resource.title,
                "authors": resource.authors,
                "institution": resource.institution,
                "citations": resource.citations_count,
                "relevance_score": analysis.relevance_score,
                "key_findings": analysis.key_findings,
                "collaboration_potential": analysis.collaboration_potential,
                "recommendation": self._generate_recommendation_from_analysis(analysis)
            })
        
        return {
            "query": structured_query,
            "resources": formatted_results,
            "count": len(formatted_results)
        }
    
    def _analyze_expert_match(self, expert: Dict, structured_query: Dict) -> Dict:
        """
        Analyze how well an expert matches the query
        
        Args:
            expert: Expert information
            structured_query: Structured query information
            
        Returns:
            Dictionary with analysis results
        """
        # Calculate expertise match scores
        expertise_match = {}
        
        if "expertise" in structured_query and structured_query["expertise"]:
            for skill in structured_query["expertise"]:
                skill_lower = skill.lower()
                
                # Check if skill matches any expertise areas
                match_score = 0.0
                for area in expert["expertise_areas"]:
                    area_lower = area.lower()
                    if skill_lower in area_lower or area_lower in skill_lower:
                        match_score = 1.0
                        break
                
                expertise_match[skill] = match_score
        
        # Calculate average match score
        avg_match = (
            sum(expertise_match.values()) / len(expertise_match) 
            if expertise_match else 0.0
        )
        
        # Calculate overall match score
        match_score = (avg_match + expert["relevance_score"]) / 2
        
        return {
            "expertise_match": expertise_match,
            "overall_match": match_score,
            "recommendation": self._generate_recommendation(expert["name"], match_score)
        }
    
    def _generate_recommendation(self, name: str, match_score: float) -> str:
        """
        Generate a collaboration recommendation
        
        Args:
            name: Expert name
            match_score: Match score between 0 and 1
            
        Returns:
            Recommendation string
        """
        if match_score > 0.8:
            priority = "High"
            message = (
                f"{name} is an excellent match for your research interests. "
                "Their expertise directly aligns with your collaboration needs."
            )
        elif match_score > 0.6:
            priority = "Medium"
            message = (
                f"{name} is a good match for your research. "
                "They have relevant expertise that could benefit your collaboration."
            )
        else:
            priority = "Low"
            message = (
                f"{name} has some relevant expertise, but may not be an ideal fit. "
                "Consider them if other candidates are unavailable."
            )
            
        return f"Priority: {priority}. {message}"
    
    def _generate_recommendation_from_analysis(self, analysis: AnalysisResult) -> str:
        """
        Generate recommendation from analysis result
        
        Args:
            analysis: AnalysisResult object
            
        Returns:
            Recommendation string
        """
        # Calculate overall score from relevance and expertise match
        avg_expertise = (
            sum(analysis.expertise_match.values()) / len(analysis.expertise_match)
            if analysis.expertise_match else 0.0
        )
        
        overall_score = (analysis.relevance_score + avg_expertise) / 2
        
        if overall_score > 0.8:
            return (
                "High Priority. This research strongly aligns with your interests. "
                f"Focus areas include {', '.join(analysis.research_areas[:2])}. "
                f"{analysis.collaboration_potential}"
            )
        elif overall_score > 0.6:
            return (
                "Medium Priority. This research is relevant to your interests. "
                f"Consider collaboration in areas like {', '.join(analysis.research_areas[:1])}. "
                f"{analysis.collaboration_potential}"
            )
        else:
            return (
                "Low Priority. This research has limited alignment with your interests. "
                f"{analysis.collaboration_potential}"
            )

# Factory function to create an integrated system instance
def create_integrated_system(email: str, openai_api_key: str) -> IntegratedResearchSystem:
    """Create an instance of the IntegratedResearchSystem"""
    return IntegratedResearchSystem(email, openai_api_key)