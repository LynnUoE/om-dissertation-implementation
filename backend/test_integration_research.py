import unittest
from query_processor import QueryProcessor
from openalex_searcher import OpenAlexSearcher, create_searcher
import logging
import json

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class TestQueryProcessorOpenAlexIntegration(unittest.TestCase):
    def setUp(self):
        # Update with your API key
        self.api_key = "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"
        self.processor = QueryProcessor(api_key=self.api_key)
        self.searcher = create_searcher('s2231967@ed.ac.uk')
        
        self.test_queries = [
            {
                "query": "Looking for experts in computer vision and deep learning for medical image analysis",
                "expected_expertise": ["computer vision", "deep learning", "medical image"]
            }
        ]

    def test_end_to_end_search(self):
        """Test the complete flow from query processing to expert search"""
        for test_case in self.test_queries:
            query = test_case["query"]
            expected_expertise = test_case["expected_expertise"]
            
            # Process query
            structured_query = self.processor.process_query(query)
            self.assertIsNotNone(structured_query)
            logger.info(f"Processed query: {json.dumps(structured_query, indent=2)}")
            
            # Verify expertise matches
            query_expertise = {exp.lower() for exp in structured_query.get('expertise', [])}
            query_areas = {area.lower() for area in structured_query.get('research_areas', [])}
            combined_expertise = query_expertise.union(query_areas)
            
            for expertise in expected_expertise:
                self.assertTrue(
                    any(expertise.lower() in exp for exp in combined_expertise),
                    f"Expected expertise '{expertise}' not found in processed query"
                )
            
            # Search for experts
            experts = self.searcher.search_experts(structured_query, max_results=3)
            self.assertIsNotNone(experts)
            logger.info(f"Found {len(experts)} experts")
            
            if experts:
                expert = experts[0]
                logger.info(f"Top expert: {expert['name']}")
                logger.info(f"Institution: {expert['institutions']}")
                logger.info(f"Citations: {expert['citations']}")
                
                # Verify expert data structure
                required_fields = ['name', 'institutions', 'works', 'citations', 'concepts']
                for field in required_fields:
                    self.assertIn(field, expert)

    def test_error_handling(self):
        """Test error cases"""
        # Test with invalid structured query
        invalid_query = {'invalid': 'query'}
        experts = self.searcher.search_experts(invalid_query)
        self.assertEqual(len(experts), 0)
        
        # Test with empty query
        experts = self.searcher.search_experts({})
        self.assertEqual(len(experts), 0)

if __name__ == '__main__':
    unittest.main(verbosity=2)