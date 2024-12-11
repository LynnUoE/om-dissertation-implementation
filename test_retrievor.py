import unittest
from query_processor import QueryProcessor
from resource_retriever import ResearcherSearch
import json

class TestResearcherSearch(unittest.TestCase):
    def setUp(self):
        """Set up test fixtures before each test method."""
        # Replace with your actual OpenAI API key
        self.api_key = "your-actual-openai-api-key-here"
        self.query_processor = QueryProcessor(api_key=self.api_key)
        self.researcher_search = ResearcherSearch()
        
        self.sample_query = """
        Looking for collaborators in quantum computing with expertise in 
        quantum error correction and superconducting qubits for a joint 
        research project on quantum machine learning.
        """

    def test_researcher_search_integration(self):
        """Test the full integration of query processing and researcher search"""
        print("\nTest 1: Full Integration Test")
        print("-" * 50)
        
        # Process the query
        print("Input Query:", self.sample_query.strip())
        query_result = self.query_processor.process_query(self.sample_query)
        
        if query_result:
            print("\nStructured Query Result:")
            print(json.dumps(query_result, indent=2))
            
            # Search for researchers
            researchers = self.researcher_search.search_researchers(query_result)
            
            print(f"\nFound {len(researchers)} researchers")
            for i, researcher in enumerate(researchers[:3], 1):
                print(f"\nResearcher {i}:")
                print(f"Name: {researcher['name']}")
                print(f"Works Count: {researcher['works_count']}")
                print(f"Citations: {researcher['cited_by_count']}")
                if researcher['institutions']:
                    print(f"Institution: {researcher['institutions'][0]}")
                if researcher['concepts']:
                    print("Top Concepts:", [c['name'] for c in researcher['concepts']])
            
            self.assertIsNotNone(researchers)
            self.assertTrue(len(researchers) > 0)
        else:
            print("Error: Query processing failed. Please check your OpenAI API key.")
            self.skipTest("Query processing failed")

    def test_researcher_details(self):
        """Test fetching detailed researcher information"""
        print("\nTest 2: Researcher Details Test")
        print("-" * 50)
        
        # Using a known quantum computing researcher ID
        researcher_id = "A2057960269"  # Updated to a valid OpenAlex ID
        
        print(f"Fetching details for researcher ID: {researcher_id}")
        details = self.researcher_search.get_researcher_details(researcher_id)
        
        if details:
            print("\nResearcher Details:")
            print(json.dumps(details, indent=2))
            
            self.assertIsNotNone(details)
            self.assertTrue('name' in details)
            self.assertTrue('works_count' in details)
        else:
            print(f"Error: Could not fetch details for researcher ID: {researcher_id}")
            self.fail("Failed to fetch researcher details")

if __name__ == '__main__':
    unittest.main(verbosity=2)