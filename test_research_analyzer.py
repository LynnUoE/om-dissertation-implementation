import os
from typing import List
from datetime import datetime

# Import ResearchResource from openalex_searcher instead
from openalex_searcher import ResearchResource
from research_analyzer import create_analyzer

def create_sample_resources() -> List[ResearchResource]:
    """Create sample research resources for testing."""
    return [
        ResearchResource(
            title="Deep Learning Approaches in Healthcare: A Comprehensive Review",
            authors=["Sarah Johnson", "Michael Chen", "David Wilson"],
            publication_date="2023-06-15",
            doi="10.1234/dl-healthcare-2023",
            citations_count=145,
            concepts=["deep learning", "healthcare", "artificial intelligence", "medical imaging"],
            institution="Stanford University",
            publication_type="journal-article",
            abstract="""This comprehensive review examines the application of deep learning 
            techniques in healthcare settings. We analyze recent developments in medical imaging, 
            diagnosis prediction, and treatment planning. Our findings suggest significant 
            improvements in diagnostic accuracy and treatment optimization when deep learning 
            methods are properly implemented."""
        ),
        ResearchResource(
            title="Quantum Computing Applications in Drug Discovery",
            authors=["Emily Brown", "James Martinez"],
            publication_date="2023-08-20",
            doi="10.5678/qc-drug-2023",
            citations_count=89,
            concepts=["quantum computing", "drug discovery", "molecular modeling", "pharmaceutical research"],
            institution="MIT",
            publication_type="journal-article",
            abstract="""We present a novel approach to drug discovery utilizing quantum 
            computing algorithms. The study demonstrates improved efficiency in molecular 
            modeling and binding affinity predictions. Results show a 40% reduction in 
            computational time compared to traditional methods."""
        ),
        ResearchResource(
            title="Sustainable Energy Systems: AI-Driven Optimization",
            authors=["Lisa Zhang", "Robert Taylor"],
            publication_date="2023-09-10",
            doi="10.9012/ai-energy-2023",
            citations_count=56,
            concepts=["artificial intelligence", "sustainable energy", "optimization", "smart grid"],
            institution="Berkeley",
            publication_type="journal-article",
            abstract="""This research investigates the role of artificial intelligence in 
            optimizing sustainable energy systems. We propose a novel framework for smart 
            grid management using reinforcement learning. The implementation resulted in 
            15% improved energy efficiency across test scenarios."""
        )
    ]

def create_sample_query() -> dict:
    """Create a sample structured query for testing."""
    return {
        "research_areas": [
            "artificial intelligence",
            "healthcare",
            "medical imaging"
        ],
        "expertise": [
            "deep learning",
            "medical data analysis",
            "neural networks"
        ],
        "collaboration_type": "Research partnership for developing AI-based medical imaging solutions",
        "requirements": [
            "Experience with healthcare datasets",
            "Published work in medical AI"
        ],
        "search_keywords": [
            "AI healthcare",
            "medical imaging",
            "deep learning medicine"
        ]
    }

def main():
    # Get API key from environment variable
    api_key = "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"
    # Create analyzer instance
    analyzer = create_analyzer(api_key)
    
    print("Starting analysis of sample resources...")
    
    # Create sample data
    resources = create_sample_resources()
    structured_query = create_sample_query()
    
    # Analyze resources
    analyzed_results = analyzer.analyze_resources(
        resources,
        structured_query,
        min_relevance=0.3  # Lower threshold for testing
    )
    
    print(f"\nAnalyzed {len(analyzed_results)} resources:")
    
    # Display results
    for result in analyzed_results:
        analysis = result['analysis']
        resource = result['resource']
        
        print("\n" + "="*80)
        print(f"Title: {resource.title}")
        print(f"Institution: {resource.institution}")
        print(f"Relevance Score: {analysis.relevance_score}")
        print("\nKey Findings:")
        for finding in analysis.key_findings:
            print(f"- {finding}")
        print("\nExpertise Match:")
        for expertise, score in analysis.expertise_match.items():
            print(f"- {expertise}: {score}")
        print(f"\nCollaboration Potential: {analysis.collaboration_potential}")
    
    # Get recommendations
    recommendations = analyzer.get_collaboration_recommendations(analyzed_results)
    
    print("\n" + "="*80)
    print("\nCollaboration Recommendations:")
    for rec in recommendations:
        print("\n" + "-"*40)
        print(f"Title: {rec['title']}")
        print(f"Authors: {', '.join(rec['authors'])}")
        print(f"Recommendation: {rec['recommendation']}")

if __name__ == "__main__":
    main()