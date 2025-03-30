import os
from dotenv import load_dotenv
import json
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Import the query processor
from query_processor import create_query_processor

# Load environment variables
load_dotenv()

# Get API key from environment
api_key = os.getenv("OPENAI_API_KEY")

if not api_key:
    print("ERROR: OpenAI API key not found in environment variables.")
    print("Please set the OPENAI_API_KEY environment variable.")
    exit(1)

# Create query processor
processor = create_query_processor(api_key)

# Test queries for literature search
test_queries = [
    "Find recent publications on quantum error correction and its applications in quantum machine learning",
    "I need papers about high-resolution climate models for predicting extreme weather events published in the last 5 years",
    "What are the latest developments in bioinformatics approaches to protein folding prediction?",
    "Search for literature on sustainable urban planning and smart city technologies"
]

# Process each query and display results
for i, query in enumerate(test_queries):
    print(f"\n=== Testing Literature Search Query {i+1} ===")
    print(f"Query: {query}")
    
    result = processor.process_query(query)
    
    print("\nStructured Search Parameters:")
    print(json.dumps(result, indent=2))
    
    # If there are expanded terms, display them
    if 'expanded_terms' in result:
        print("\nExpanded Search Terms:")
        for term, expansions in result['expanded_terms'].items():
            print(f"  {term}: {', '.join(expansions)}")
    
    # Analyze interdisciplinary aspects if there are multiple research areas
    if len(result.get('research_areas', [])) > 1:
        interdisciplinary = processor.analyze_interdisciplinary_aspects(result)
        print("\nInterdisciplinary Analysis:")
        print(json.dumps(interdisciplinary, indent=2))

    print("\n" + "="*50)