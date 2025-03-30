import os
from dotenv import load_dotenv
import json
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Import the literature searcher
from literature_searcher import create_literature_searcher

# Load environment variables
load_dotenv()

# Get API keys from environment
openai_api_key = os.getenv("OPENAI_API_KEY")
email_for_openalex = os.getenv("RESEARCHER_EMAIL")

if not openai_api_key:
    print("ERROR: OpenAI API key not found in environment variables.")
    print("Please set the OPENAI_API_KEY environment variable.")
    exit(1)

if not email_for_openalex:
    print("WARNING: Email for OpenAlex not found. Using default.")
    email_for_openalex = "test@example.com"

# Create literature searcher
searcher = create_literature_searcher(openai_api_key, email_for_openalex)

# Test basic search
def test_basic_search():
    print("\n=== Testing Basic Literature Search ===")
    query = "Recent advancements in quantum error correction and their implications for quantum computing"
    
    result = searcher.search(
        query=query,
        max_results=5,
        from_year=2020,
        analyze_results=True
    )
    
    print(f"Search Status: {result['status']}")
    print(f"Found {len(result.get('results', []))} results")
    
    # Display structured query
    print("\nStructured Query:")
    print(json.dumps(result.get('structured_query', {}), indent=2))
    
    # Display first result if available
    if result.get('results'):
        first_result = result['results'][0]
        print("\nTop Result:")
        print(f"Title: {first_result.get('title')}")
        print(f"Authors: {', '.join(first_result.get('authors', []))}")
        print(f"Relevance Score: {first_result.get('relevance_score')}")
        
        # Display analysis if available
        if 'analysis' in result and 'literature_summary' in result['analysis']:
            print("\nLiterature Summary:")
            summary = result['analysis']['literature_summary']
            print(f"Top Themes: {', '.join(summary.get('top_themes', []))}")
            print(f"Knowledge Gaps: {', '.join(summary.get('knowledge_gaps', []))}")

# Test interdisciplinary search
def test_interdisciplinary_search():
    print("\n=== Testing Interdisciplinary Search ===")
    
    result = searcher.interdisciplinary_search(
        primary_discipline="Quantum Computing",
        secondary_disciplines=["Machine Learning", "Cryptography"],
        max_results=3,
        from_year=2020
    )
    
    print(f"Search Status: {result['status']}")
    print(f"Found {len(result.get('results', []))} results")
    
    # Display interdisciplinary analysis
    if 'interdisciplinary_analysis' in result:
        print("\nInterdisciplinary Analysis:")
        analysis = result['interdisciplinary_analysis']
        print(f"Intersection Keywords: {', '.join(analysis.get('intersection_keywords', []))}")
        print(f"Bridging Concepts: {', '.join(analysis.get('bridging_concepts', []))}")
    
    # Display synthesis if available
    if 'interdisciplinary_synthesis' in result:
        print("\nInterdisciplinary Synthesis:")
        synthesis = result['interdisciplinary_synthesis']
        print(f"Interdisciplinary Significance: {synthesis.get('interdisciplinary_significance')}")
        print(f"Knowledge Gaps: {', '.join(synthesis.get('knowledge_gaps', []))}")

# Test advanced search
def test_advanced_search():
    print("\n=== Testing Advanced Search ===")
    
    result = searcher.advanced_search(
        research_areas=["Quantum Computing", "Quantum Information"],
        specific_topics=["Quantum Error Correction", "Surface Codes"],
        methodologies=["Numerical Simulation", "Experimental Validation"],
        max_results=3,
        from_year=2020
    )
    
    print(f"Search Status: {result['status']}")
    print(f"Found {len(result.get('results', []))} results")
    
    # Display first result if available
    if result.get('results'):
        first_result = result['results'][0]
        print("\nTop Result:")
        print(f"Title: {first_result.get('title')}")
        print(f"Relevance Score: {first_result.get('relevance_score')}")

# Run tests
test_basic_search()
test_interdisciplinary_search()
test_advanced_search()