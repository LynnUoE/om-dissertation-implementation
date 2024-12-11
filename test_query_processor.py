import unittest
from query_processor import QueryProcessor
import json

class TestQueryProcessor(unittest.TestCase):
    def setUp(self):
        self.api_key = "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"
        self.processor = QueryProcessor(api_key=self.api_key)
        
        self.sample_query = """
        Looking for collaborators in quantum computing with expertise in 
        quantum error correction and superconducting qubits for a joint 
        research project on quantum machine learning.
        """

    def test_live_api_query(self):
        """Test the actual API call with a real query and display results"""
        print("\nProcessing query:", self.sample_query)
        print("\n" + "="*50)
        
        result = self.processor.process_query(self.sample_query)
        
        print("\nQuery Analysis Results:")
        print("="*50)
        if result:
            print(json.dumps(result, indent=2))
        else:
            print("No results obtained from the query")
            
        print("="*50 + "\n")
        
        self.assertIsNotNone(result)
        self.assertTrue('research_areas' in result)
        self.assertTrue('expertise' in result)
        
    def test_preprocess_query(self):
        messy_query = "QUANTUM    computing Research!!!"
        expected_clean = "quantum computing research"
        result = self.processor.preprocess_query(messy_query)
        self.assertEqual(result, expected_clean)

if __name__ == '__main__':
    unittest.main(verbosity=2)