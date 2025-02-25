# example_expert_search.py
from expert_searcher import create_expert_searcher
import json
from query_processor import QueryProcessor

def format_expert_display(expert):
    """Format expert information for display"""
    return {
        "name": expert["name"],
        "institution": expert["institution"] or "Unknown affiliation",
        "citation_count": expert["citation_count"],
        "works_count": expert["works_count"],
        "expertise": ", ".join(expert["expertise_areas"][:5]) + 
                    ("..." if len(expert["expertise_areas"]) > 5 else ""),
        "top_work": expert["top_works"][0]["title"] if expert["top_works"] else "No works found",
        "recent_activity": ", ".join(str(y) for y in expert["recent_years"][:3])
    }

def main():
    # Configuration
    EMAIL = "s2231967@ed.ac.uk"
    OPENAI_API_KEY = "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"
    
    # Create the query processor and expert searcher
    processor = QueryProcessor(api_key=OPENAI_API_KEY)
    searcher = create_expert_searcher(EMAIL)
    
    # Example 1: Search using a natural language query
    print("\n===== Example 1: Natural Language Query =====")
    
    query = """
    I'm looking for researchers with expertise in quantum computing and machine learning 
    who might be interested in collaborating on quantum algorithms for neural networks.
    """
    
    print(f"Query: {query}\n")
    
    # Process the query
    structured_query = processor.process_query(query)
    if structured_query:
        print("Structured Query:")
        for key, value in structured_query.items():
            print(f"  {key}: {value}")
        
        # Search for experts
        experts = searcher.search_experts(structured_query, max_results=3)
        
        if experts:
            print(f"\nFound {len(experts)} matching experts:")
            for i, expert in enumerate(experts, 1):
                expert_dict = expert.to_dict()
                print(f"\nExpert #{i}: {expert_dict['name']}")
                print(f"  Institution: {expert_dict['institution'] or 'Unknown'}")
                print(f"  Citations: {expert_dict['citation_count']}")
                print(f"  Works: {expert_dict['works_count']}")
                print(f"  Expertise areas: {', '.join(expert_dict['expertise_areas'][:5])}" +
                      ("..." if len(expert_dict['expertise_areas']) > 5 else ""))
                if expert_dict['top_works']:
                    print(f"  Top work: {expert_dict['top_works'][0]['title']}")
                print(f"  Relevance score: {expert_dict['relevance_score']:.2f}")
        else:
            print("No experts found.")
    else:
        print("Failed to process query.")

    # Example 2: Multidisciplinary search
    print("\n\n===== Example 2: Multidisciplinary Search =====")
    
    primary = "artificial intelligence"
    secondary = ["healthcare", "medicine"]
    print(f"Primary discipline: {primary}")
    print(f"Secondary disciplines: {', '.join(secondary)}\n")
    
    experts = searcher.search_multidisciplinary(
        primary,
        secondary,
        max_results=3,
        require_all=False
    )
    
    if experts:
        print(f"Found {len(experts)} multidisciplinary experts:")
        for i, expert in enumerate(experts, 1):
            formatted = format_expert_display(expert)
            print(f"\nExpert #{i}: {formatted['name']}")
            print(f"  Institution: {formatted['institution']}")
            print(f"  Citations: {formatted['citation_count']}")
            print(f"  Expertise: {formatted['expertise']}")
            print(f"  Top work: {formatted['top_work']}")
            print(f"  Recent activity: {formatted['recent_activity']}")
    else:
        print("No multidisciplinary experts found.")

    # Example 3: Discipline-based search
    print("\n\n===== Example 3: Discipline-based Search =====")
    
    disciplines = ["climate change", "renewable energy", "sustainability"]
    print(f"Disciplines: {', '.join(disciplines)}\n")
    
    experts = searcher.search_by_disciplines(
        disciplines,
        max_results=3,
        min_citations=50
    )
    
    if experts:
        print(f"Found {len(experts)} experts in specified disciplines:")
        for i, expert in enumerate(experts, 1):
            formatted = format_expert_display(expert)
            print(f"\nExpert #{i}: {formatted['name']}")
            print(f"  Institution: {formatted['institution']}")
            print(f"  Citations: {formatted['citation_count']}")
            print(f"  Works count: {formatted['works_count']}")
            print(f"  Expertise: {formatted['expertise']}")
            print(f"  Recent activity: {formatted['recent_activity']}")
    else:
        print("No experts found in specified disciplines.")

if __name__ == "__main__":
    main()