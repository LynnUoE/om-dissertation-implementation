# example_usage.py
from integrated_research_system import create_integrated_system
import json
from pprint import pprint

def print_section(title):
    """Print a section title with formatting"""
    print("\n" + "=" * 80)
    print(f"  {title}")
    print("=" * 80)

def main():
    """
    Demonstrate the integrated research system functionality
    """
    # Configuration
    EMAIL = "s2231967@ed.ac.uk"
    OPENAI_API_KEY = "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"
    
    # Create the integrated system
    system = create_integrated_system(EMAIL, OPENAI_API_KEY)
    
    # Example 1: Find experts based on a natural language query
    print_section("Example 1: Find Experts")
    
    query1 = """
    I'm looking for researchers with expertise in quantum computing and machine learning 
    who might be interested in collaborating on quantum algorithms for neural networks.
    """
    
    print(f"Query: {query1}\n")
    results1 = system.find_experts(query1, max_results=3)
    
    if "error" in results1:
        print(f"Error: {results1['error']}")
    elif "message" in results1:
        print(f"Message: {results1['message']}")
    else:
        print(f"Found {results1['count']} experts:")
        
        for i, expert in enumerate(results1['experts'], 1):
            print(f"\nExpert {i}: {expert['name']}")
            print(f"Institution: {expert['institution'] or 'Unknown'}")
            print(f"Citations: {expert['citation_count']}")
            print(f"Works: {expert['works_count']}")
            
            analysis = expert['analysis']
            print(f"Match score: {analysis['overall_match']:.2f}")
            print(f"Recommendation: {analysis['recommendation']}")
            
            # Print top work if available
            if expert['top_works']:
                print(f"Top work: {expert['top_works'][0]['title']}")
    
    # Example 2: Find multidisciplinary experts
    print_section("Example 2: Multidisciplinary Experts")
    
    query2 = "I need experts in artificial intelligence"
    secondary = ["healthcare", "medicine"]
    
    print(f"Primary query: {query2}")
    print(f"Secondary disciplines: {', '.join(secondary)}")
    
    results2 = system.find_multidisciplinary_experts(
        query2,
        secondary_disciplines=secondary,
        max_results=3
    )
    
    if "error" in results2:
        print(f"Error: {results2['error']}")
    elif "message" in results2:
        print(f"Message: {results2['message']}")
    else:
        print(f"\nPrimary discipline: {results2['primary_discipline']}")
        print(f"Secondary disciplines: {', '.join(results2['secondary_disciplines'])}")
        print(f"Found {results2['count']} multidisciplinary experts:")
        
        for i, expert in enumerate(results2['experts'], 1):
            print(f"\nExpert {i}: {expert['name']}")
            print(f"Institution: {expert['institution'] or 'Unknown'}")
            print(f"Citations: {expert['citation_count']}")
            print(f"Relevance score: {expert['relevance_score']:.2f}")
            print(f"Recommendation: {expert['analysis']['recommendation']}")
    
    # Example 3: Search for research resources
    print_section("Example 3: Research Resources")
    
    query3 = """
    I'm interested in finding research on renewable energy technologies,
    particularly solar power and energy storage solutions.
    """
    
    print(f"Query: {query3}\n")
    results3 = system.search_resources_for_collaboration(query3, max_results=3)
    
    if "error" in results3:
        print(f"Error: {results3['error']}")
    elif "message" in results3:
        print(f"Message: {results3['message']}")
    else:
        print(f"Found {results3['count']} relevant research resources:")
        
        for i, resource in enumerate(results3['resources'], 1):
            print(f"\nResource {i}: {resource['title']}")
            print(f"Authors: {', '.join(resource['authors'])}")
            print(f"Institution: {resource['institution'] or 'Unknown'}")
            print(f"Citations: {resource['citations']}")
            print(f"Relevance: {resource['relevance_score']:.2f}")
            print(f"Collaboration potential: {resource['collaboration_potential']}")
            print(f"Recommendation: {resource['recommendation']}")

if __name__ == "__main__":
    main()