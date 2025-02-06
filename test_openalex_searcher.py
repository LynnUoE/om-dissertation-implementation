import unittest
from query_processor import QueryProcessor
from openalex_searcher import OpenAlexSearcher, create_searcher, ResearchResource
import logging
import json
from datetime import datetime

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class TestQueryProcessorOpenAlexIntegration(unittest.TestCase):
    def setUp(self):
        """Initialize test environment with necessary components"""
        self.api_key = "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"
        self.processor = QueryProcessor(api_key=self.api_key)
        self.searcher = create_searcher('s2231967@ed.ac.uk')
        
        # Enhanced test cases with more comprehensive coverage
        self.test_queries = [
            {
                "query": "Looking for experts in computer vision and deep learning for medical image analysis",
                "expected_expertise": ["computer vision", "deep learning", "medical image"],
                "min_citations": 1000
            },
            {
                "query": "Seeking collaboration in quantum computing and machine learning",
                "expected_expertise": ["quantum computing", "machine learning"],
                "min_citations": 500
            }
        ]

    def test_end_to_end_search(self):
        """Test the complete workflow from query processing to expert search"""
        logger.info("\nStarting end-to-end integration test")
        
        for test_case in self.test_queries:
            query = test_case["query"]
            expected_expertise = test_case["expected_expertise"]
            min_citations = test_case.get("min_citations")
            
            logger.info(f"\nTesting query: {query}")
            
            # Process query using QueryProcessor
            structured_query = self.processor.process_query(query)
            self.assertIsNotNone(structured_query)
            logger.info(f"\nProcessed query structure:\n{json.dumps(structured_query, indent=2)}")
            
            # Verify query processing results
            self._verify_query_processing(structured_query, expected_expertise)
            
            # Search for experts using enhanced searcher
            experts = self.searcher.search_experts(
                structured_query=structured_query,
                max_results=3,
                min_citations=min_citations
            )
            self.assertIsNotNone(experts)
            
            # Analyze and verify expert results
            self._analyze_expert_results(experts)

    def _verify_query_processing(self, structured_query, expected_expertise):
        """Verify the query processing results"""
        query_expertise = {exp.lower() for exp in structured_query.get('expertise', [])}
        query_areas = {area.lower() for area in structured_query.get('research_areas', [])}
        combined_expertise = query_expertise.union(query_areas)
        
        for expertise in expected_expertise:
            self.assertTrue(
                any(expertise.lower() in exp.lower() for exp in combined_expertise),
                f"Expected expertise '{expertise}' not found in processed query"
            )
        
        # Verify query structure
        required_fields = ['research_areas', 'expertise', 'search_keywords']
        for field in required_fields:
            self.assertIn(field, structured_query)

    def _analyze_expert_results(self, experts):
        """Analyze and verify expert search results"""
        logger.info(f"\nFound {len(experts)} experts")
        
        if not experts:
            logger.warning("No experts found for the query")
            return
            
        for idx, expert in enumerate(experts, 1):
            logger.info(f"\nExpert {idx}:")
            logger.info(f"Name: {expert['name']}")
            logger.info(f"Institutions: {', '.join(expert['institutions'])}")
            logger.info(f"Total Citations: {expert['citations']}")
            
            # Log top works
            if expert.get('works'):
                logger.info("\nTop works:")
                for work in expert['works'][:3]:
                    logger.info(
                        f"- {work.get('title')} "
                        f"(Citations: {work.get('citations')})"
                    )
            
            # Verify expert data structure
            self._verify_expert_structure(expert)

    def _verify_expert_structure(self, expert):
        """Verify the structure of expert data"""
        required_fields = ['name', 'institutions', 'works', 'citations', 'concepts']
        for field in required_fields:
            self.assertIn(field, expert)
            
        self.assertIsInstance(expert['citations'], int)
        self.assertIsInstance(expert['works'], list)
        self.assertIsInstance(expert['concepts'], list)

    def test_error_handling(self):
        """Test error handling scenarios"""
        logger.info("\nTesting error handling scenarios")
        
        test_cases = [
            ("Invalid query format", {'invalid': 'query'}),
            ("None query", None),
            ("Empty dictionary", {}),
            ("Malformed dictionary", {'research_areas': None}),
            ("Missing required fields", {'expertise': []})
        ]
        
        for case_name, invalid_query in test_cases:
            logger.info(f"\nTesting {case_name}")
            experts = self.searcher.search_experts(invalid_query)
            self.assertEqual(
                len(experts), 0,
                f"Expected empty result for {case_name}"
            )

    def test_expert_details(self):
        """Test retrieval of detailed expert information"""
        logger.info("\nTesting expert details retrieval")
        
        # First get some experts
        structured_query = self.processor.process_query(self.test_queries[0]['query'])
        experts = self.searcher.search_experts(structured_query, max_results=1)
        
        if experts:
            expert_id = experts[0]['id']
            logger.info(f"Retrieving details for expert ID: {expert_id}")
            
            details = self.searcher.get_expert_details(expert_id)
            self.assertIsNotNone(details)
            
            # Log expert details
            logger.info(f"\nExpert Details:")
            logger.info(f"Name: {details.get('display_name')}")
            logger.info(f"Citation Count: {details.get('cited_by_count')}")
            
            # Verify essential fields
            self.assertIn('display_name', details)
            self.assertIn('cited_by_count', details)

if __name__ == '__main__':
    unittest.main(verbosity=2)