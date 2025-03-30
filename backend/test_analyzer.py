import os
from dotenv import load_dotenv
import json
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Import the analyzer
from research_analyzer import create_analyzer

# Load environment variables
load_dotenv()

# Get API key from environment
api_key = os.getenv("OPENAI_API_KEY")

if not api_key:
    print("ERROR: OpenAI API key not found in environment variables.")
    print("Please set the OPENAI_API_KEY environment variable.")
    exit(1)

# Create analyzer
analyzer = create_analyzer(api_key)

# Sample publications (in a real scenario, these would come from OpenAlex)
sample_publications = [
    {
        "title": "Advances in Quantum Error Correction for Superconducting Qubits",
        "authors": ["Johnson, S.", "Wilson, D.", "Chen, E."],
        "abstract": "This paper presents a novel approach to quantum error correction that improves error thresholds for superconducting qubit architectures by 35% compared to previous methods. We introduce a modified surface code that is particularly well-suited for the connectivity constraints and noise characteristics of superconducting quantum processors.",
        "publication_date": "2023-03-15",
        "journal": "Nature Quantum Information"
    },
    {
        "title": "Quantum Machine Learning Applications in Near-Term Quantum Computers",
        "authors": ["Taylor, R.", "Martinez, J.", "Johnson, S."],
        "abstract": "This comprehensive review examines quantum machine learning algorithms that can be implemented on current and near-term quantum computing hardware. We analyze the potential advantages and practical limitations of these approaches, with particular focus on variational quantum algorithms and their applications in classification and generative modeling.",
        "publication_date": "2022-08-22",
        "journal": "Science"
    }
]

# Sample query context
query_context = {
    "research_areas": ["Quantum Computing", "Machine Learning"],
    "expertise": ["Quantum Error Correction", "Superconducting Qubits", "Quantum Machine Learning"],
    "search_keywords": ["NISQ", "variational quantum algorithms"]
}

# Original user query
original_query = "Find recent publications on quantum error correction and its applications in quantum machine learning"

# Test analysis of publications
print("=== Testing Publication Analysis ===")
analyzed_results = analyzer.analyze_publications(
    publications=sample_publications,
    query_context=query_context,
    min_relevance=0.1  # Lower threshold for the sample
)

print(f"Analyzed {len(analyzed_results)} publications")

# Display analysis results for the first publication
if analyzed_results:
    print("\nAnalysis of first publication:")
    first_analysis = analyzed_results[0]['analysis']
    print(f"Primary Topics: {', '.join(first_analysis['primary_topics'])}")
    print(f"Relevance Score: {first_analysis['relevance_score']}")
    print(f"Key Findings: {', '.join(first_analysis['key_findings'])}")
    print(f"Technical Complexity: {first_analysis['technical_complexity']}/5")

# Test synthesis of analyses
print("\n=== Testing Synthesis of Analyses ===")
synthesis = analyzer.synthesize_analyses(
    analyzed_results=analyzed_results,
    original_query=original_query
)

print("Synthesis Results:")
print(f"Research Themes: {', '.join(synthesis['research_themes'])}")
print(f"Consensus Findings: {', '.join(synthesis['consensus_findings'])}")
print(f"Knowledge Gaps: {', '.join(synthesis['knowledge_gaps'])}")

# Test methodology analysis
print("\n=== Testing Methodology Analysis ===")
methodology_analysis = analyzer.analyze_methodologies(analyzed_results)

print("Methodology Analysis Results:")
print(f"Dominant Paradigms: {', '.join(methodology_analysis['dominant_paradigms'])}")
print(f"Innovative Methods: {', '.join(methodology_analysis['innovative_methods'])}")

# Test literature summary generation
print("\n=== Testing Literature Summary ===")
summary = analyzer.generate_literature_summary(
    analyzed_results=analyzed_results,
    synthesis=synthesis,
    original_query=original_query
)

print("Literature Summary:")
print(json.dumps(summary, indent=2))