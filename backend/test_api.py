import requests
import json
import time
import sys

# Configuration
API_BASE_URL = "http://localhost:5000/api"
TIMEOUT = 120  # seconds

def print_header(message):
    """Print a formatted header"""
    print("\n" + "=" * 80)
    print(f" {message}")
    print("=" * 80)

def test_health_check():
    """Test the health check endpoint"""
    print_header("Testing Health Check")
    
    try:
        response = requests.get(f"{API_BASE_URL}/health_check", timeout=TIMEOUT)
        response.raise_for_status()
        
        data = response.json()
        print(f"Status: {data.get('status')}")
        print(f"Version: {data.get('version')}")
        print(f"Stats: {json.dumps(data.get('stats', {}), indent=2)}")
        
        return True
    except Exception as e:
        print(f"Health check failed: {str(e)}")
        return False

def test_simple_search():
    """Test the basic search endpoint"""
    print_header("Testing Simple Search")
    
    query = "Recent advances in quantum error correction for superconducting qubits"
    
    try:
        response = requests.post(
            f"{API_BASE_URL}/search",
            json={
                "query": query,
                "options": {
                    "max_results": 3,
                    "from_year": 2020,
                    "analyze_results": True
                }
            },
            timeout=TIMEOUT
        )
        response.raise_for_status()
        
        data = response.json()
        print(f"Status: {data.get('status')}")
        print(f"Response Time: {data.get('response_time', 0):.2f} seconds")
        print(f"Results: {len(data.get('results', []))} publications")
        
        if data.get('results'):
            print("\nTop Result:")
            top_result = data['results'][0]
            print(f"Title: {top_result.get('title')}")
            print(f"Authors: {', '.join(top_result.get('authors', []))}")
            print(f"Relevance Score: {top_result.get('relevance_score')}")
        
        if 'analysis' in data and 'literature_summary' in data['analysis']:
            print("\nLiterature Summary:")
            summary = data['analysis']['literature_summary']
            
            # Add null checks before accessing the list
            if summary and 'top_themes' in summary and summary['top_themes']:
                print(f"Top Themes: {', '.join(summary.get('top_themes', []))}")
            else:
                print("Top Themes: None available")
            
        return True
    except Exception as e:
        print(f"Simple search failed: {str(e)}")
        return False

def test_advanced_search():
    """Test the advanced search endpoint"""
    print_header("Testing Advanced Search")
    
    try:
        response = requests.post(
            f"{API_BASE_URL}/advanced-search",
            json={
                "research_areas": ["Quantum Computing", "Quantum Information"],
                "specific_topics": ["Quantum Error Correction", "Surface Codes"],
                "methodologies": ["Numerical Simulation"],
                "options": {
                    "max_results": 3,
                    "from_year": 2020
                }
            },
            timeout=TIMEOUT
        )
        response.raise_for_status()
        
        data = response.json()
        print(f"Status: {data.get('status')}")
        print(f"Response Time: {data.get('response_time', 0):.2f} seconds")
        print(f"Results: {len(data.get('results', []))} publications")
        
        if data.get('results'):
            print("\nTop Result:")
            top_result = data['results'][0]
            print(f"Title: {top_result.get('title')}")
            print(f"Authors: {', '.join(top_result.get('authors', []))}")
            print(f"Relevance Score: {top_result.get('relevance_score')}")
        
        return True
    except Exception as e:
        print(f"Advanced search failed: {str(e)}")
        return False

def test_interdisciplinary_search():
    """Test the interdisciplinary search endpoint"""
    print_header("Testing Interdisciplinary Search")
    
    try:
        response = requests.post(
            f"{API_BASE_URL}/interdisciplinary-search",
            json={
                "primary_discipline": "Quantum Computing",
                "secondary_disciplines": ["Machine Learning", "Cryptography"],
                "options": {
                    "max_results": 3,
                    "from_year": 2020
                }
            },
            timeout=TIMEOUT
        )
        response.raise_for_status()
        
        data = response.json()
        print(f"Status: {data.get('status')}")
        print(f"Response Time: {data.get('response_time', 0):.2f} seconds")
        print(f"Results: {len(data.get('results', []))} publications")
        
        if 'interdisciplinary_analysis' in data:
            print("\nInterdisciplinary Analysis:")
            analysis = data['interdisciplinary_analysis']
            print(f"Intersection Keywords: {', '.join(analysis.get('intersection_keywords', []))}")
        
        if 'interdisciplinary_synthesis' in data:
            print("\nInterdisciplinary Synthesis:")
            synthesis = data['interdisciplinary_synthesis']
            if 'knowledge_gaps' in synthesis:
                print(f"Knowledge Gaps: {', '.join(synthesis.get('knowledge_gaps', []))}")
        
        return True
    except Exception as e:
        print(f"Interdisciplinary search failed: {str(e)}")
        return False

def test_query_processing():
    """Test the query processing endpoint"""
    print_header("Testing Query Processing")
    
    query = "Recent advances in quantum error correction for superconducting qubits"
    
    try:
        response = requests.post(
            f"{API_BASE_URL}/process-query",
            json={"query": query},
            timeout=TIMEOUT
        )
        response.raise_for_status()
        
        data = response.json()
        print(f"Status: {data.get('status')}")
        print(f"Response Time: {data.get('response_time', 0):.2f} seconds")
        
        if 'structured_query' in data:
            print("\nStructured Query:")
            struct_query = data['structured_query']
            if 'research_areas' in struct_query:
                print(f"Research Areas: {', '.join(struct_query.get('research_areas', []))}")
            if 'expertise' in struct_query:
                print(f"Expertise: {', '.join(struct_query.get('expertise', []))}")
            if 'search_keywords' in struct_query:
                print(f"Search Keywords: {', '.join(struct_query.get('search_keywords', []))}")
        
        return True
    except Exception as e:
        print(f"Query processing failed: {str(e)}")
        return False

# Run all tests
def run_tests():
    """Run all API tests"""
    print_header("Starting API Server Tests")
    
    start_time = time.time()
    
    tests = [
        test_health_check,
        test_query_processing,
        test_simple_search,
        test_advanced_search,
        test_interdisciplinary_search
    ]
    
    results = []
    for test in tests:
        try:
            result = test()
            results.append(result)
        except KeyboardInterrupt:
            print("Tests interrupted by user.")
            sys.exit(1)
        except Exception as e:
            print(f"Test error: {str(e)}")
            results.append(False)
    
    # Print summary
    print_header("Test Results Summary")
    total_tests = len(tests)
    passed_tests = sum(results)
    failed_tests = total_tests - passed_tests
    
    print(f"Total Tests: {total_tests}")
    print(f"Passed: {passed_tests}")
    print(f"Failed: {failed_tests}")
    print(f"Success Rate: {(passed_tests / total_tests) * 100:.1f}%")
    print(f"Total Time: {time.time() - start_time:.2f} seconds")
    
    return failed_tests == 0

if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)