import unittest
from unittest.mock import Mock, patch, MagicMock
import json
from datetime import datetime
from typing import Dict, List

# Import the class to test
from expert_searcher import ExpertSearcher, ResearchExpert, create_expert_searcher
from openalex_client import OpenAlexResponse, WorkResult


class TestExpertSearcher(unittest.TestCase):
    """Unit tests for the ExpertSearcher class"""

    def setUp(self):
        """Set up test environment before each test"""
        self.email = "test@example.com"
        self.searcher = ExpertSearcher(self.email)
        
        # Sample query data
        self.sample_query = {
            "research_areas": ["machine learning", "artificial intelligence"],
            "expertise": ["deep learning", "neural networks"],
            "search_keywords": ["computer vision"]
        }
        
        # Sample work results
        self.sample_works = [
            WorkResult(
                title="Deep Learning Applications in Computer Vision",
                publication_date="2023-05-15",
                citations=120,
                doi="10.1234/example.123",
                authors=["John Smith", "Jane Doe"],
                abstract="This paper explores applications of deep neural networks in computer vision tasks."
            ),
            WorkResult(
                title="Transformer Models for Natural Language Processing",
                publication_date="2022-08-10",
                citations=85,
                doi="10.1234/example.456",
                authors=["Jane Doe", "Michael Johnson"],
                abstract="We present advancements in transformer architectures for NLP tasks."
            ),
            WorkResult(
                title="Reinforcement Learning in Robotics",
                publication_date="2023-02-20",
                citations=45,
                doi="10.1234/example.789",
                authors=["Michael Johnson", "Sarah Williams"],
                abstract="This study applies reinforcement learning algorithms to robotic control systems."
            )
        ]

    def test_initialization(self):
        """Test that the ExpertSearcher initializes correctly"""
        self.assertEqual(self.searcher.email, self.email)
        self.assertIsNotNone(self.searcher.client)
        self.assertIsNotNone(self.searcher.logger)

    def test_extract_search_terms(self):
        """Test extraction of search terms from structured query"""
        search_terms = self.searcher._extract_search_terms(self.sample_query)
        
        # Check that all terms are extracted
        expected_terms = [
            "machine learning", "artificial intelligence", 
            "deep learning", "neural networks", 
            "computer vision"
        ]
        
        self.assertEqual(len(search_terms), len(expected_terms))
        for term in expected_terms:
            self.assertIn(term, search_terms)

    def test_extract_terms_from_text(self):
        """Test term extraction from text content"""
        text = "Deep learning models have shown significant improvements in computer vision applications"
        terms = self.searcher._extract_terms(text)
        
        # Check that meaningful terms are extracted
        self.assertIn("deep learning", terms)
        self.assertIn("computer vision", terms)
        
        # Check that common words are filtered out
        self.assertNotIn("have", terms)
        self.assertNotIn("shown", terms)

    @patch('expert_searcher.create_client')
    def test_search_experts_empty_query(self, mock_create_client):
        """Test behavior with empty query"""
        empty_query = {"research_areas": [], "expertise": [], "search_keywords": []}
        
        experts = self.searcher.search_experts(empty_query)
        self.assertEqual(len(experts), 0)
        
        # Verify the client's search_works was not called
        mock_client = mock_create_client.return_value
        mock_client.search_works.assert_not_called()

    @patch('openalex_client.OpenAlexClient.search_works')
    def test_search_experts_api_error(self, mock_search_works):
        """Test handling of API errors"""
        # Mock API error response
        error_response = OpenAlexResponse(
            status_code=500,
            data={},
            error="API Error",
            meta=None
        )
        mock_search_works.return_value = error_response
        
        # Call the method
        experts = self.searcher.search_experts(self.sample_query)
        
        # Verify result
        self.assertEqual(len(experts), 0)
        mock_search_works.assert_called_once()

    @patch('openalex_client.OpenAlexResponse.get_works')
    @patch('openalex_client.OpenAlexClient.search_works')
    def test_search_experts_success(self, mock_search_works, mock_get_works):
        """Test successful expert search"""
        # Mock successful response
        success_response = MagicMock()
        success_response.error = None
        mock_search_works.return_value = success_response
        
        # Mock work results
        mock_get_works.return_value = self.sample_works
        
        # Call the method
        experts = self.searcher.search_experts(self.sample_query, max_results=3, min_works=1)
        
        # Verify results
        self.assertGreater(len(experts), 0)
        
        # Check that experts were extracted from the works
        expected_authors = {"John Smith", "Jane Doe", "Michael Johnson", "Sarah Williams"}
        found_authors = {expert.name for expert in experts}
        
        # At least some of the expected authors should be found
        self.assertTrue(any(author in found_authors for author in expected_authors))
        
        # Check expert properties
        for expert in experts:
            self.assertIsInstance(expert, ResearchExpert)
            self.assertTrue(hasattr(expert, 'name'))
            self.assertTrue(hasattr(expert, 'citation_count'))
            self.assertTrue(hasattr(expert, 'works_count'))
            self.assertTrue(hasattr(expert, 'expertise_areas'))
            self.assertTrue(hasattr(expert, 'top_works'))

    def test_extract_experts_from_works(self):
        """Test extraction of experts from work results"""
        experts = self.searcher._extract_experts_from_works(
            self.sample_works,
            self.sample_query,
            min_works=1
        )
        
        # Check that experts were extracted from works
        self.assertGreater(len(experts), 0)
        
        # Check that Jane Doe (appears in multiple works) has higher works_count
        jane_id = None
        for expert_id, expert in experts.items():
            if expert.name == "Jane Doe":
                jane_id = expert_id
                break
                
        if jane_id:
            self.assertEqual(experts[jane_id].works_count, 2)
            
        # Check that citation counts are accumulated correctly
        for expert_id, expert in experts.items():
            if expert.name == "Jane Doe":
                # Jane appears in works with 120 and 85 citations
                self.assertEqual(expert.citation_count, 205)

    @patch('expert_searcher.ExpertSearcher.search_experts')
    def test_search_multidisciplinary(self, mock_search_experts):
        """Test multidisciplinary search functionality"""
        # Create mock experts
        experts = [
            ResearchExpert(
                id="1",
                name="Expert 1",
                institution="University A",
                citation_count=200,
                works_count=15,
                expertise_areas={"artificial intelligence", "machine learning", "healthcare"},
                top_works=[{"title": "AI in Healthcare", "citations": 100}],
                relevance_score=0.9
            ),
            ResearchExpert(
                id="2",
                name="Expert 2",
                institution="University B",
                citation_count=150,
                works_count=10,
                expertise_areas={"artificial intelligence", "robotics"},
                top_works=[{"title": "AI in Robotics", "citations": 80}],
                relevance_score=0.7
            )
        ]
        mock_search_experts.return_value = experts
        
        # Call multidisciplinary search
        results = self.searcher.search_multidisciplinary(
            "artificial intelligence",
            ["healthcare", "medicine"],
            require_all=False
        )
        
        # Verify results
        self.assertEqual(len(results), 1)  # Only Expert 1 matches the secondary discipline
        self.assertEqual(results[0]["name"], "Expert 1")

    @patch('expert_searcher.ExpertSearcher.search_experts')
    def test_search_by_disciplines(self, mock_search_experts):
        """Test discipline-based search functionality"""
        # Create mock experts
        experts = [
            ResearchExpert(
                id="1",
                name="Expert 1",
                institution="University A",
                citation_count=200,
                works_count=15,
                expertise_areas={"climate change", "sustainability"},
                top_works=[{"title": "Climate Change Impact", "citations": 100}],
                relevance_score=0.9
            ),
            ResearchExpert(
                id="2",
                name="Expert 2",
                institution="University B",
                citation_count=50,  # Below min_citations threshold
                works_count=10,
                expertise_areas={"climate change", "ecology"},
                top_works=[{"title": "Ecology Studies", "citations": 30}],
                relevance_score=0.7
            )
        ]
        mock_search_experts.return_value = experts
        
        # Call discipline search with min_citations filter
        results = self.searcher.search_by_disciplines(
            ["climate change", "sustainability"],
            min_citations=100
        )
        
        # Verify results
        self.assertEqual(len(results), 1)  # Only Expert 1 meets citation threshold
        self.assertEqual(results[0]["name"], "Expert 1")

    def test_create_expert_searcher(self):
        """Test factory function to create ExpertSearcher"""
        searcher = create_expert_searcher(self.email)
        self.assertIsInstance(searcher, ExpertSearcher)
        self.assertEqual(searcher.email, self.email)


if __name__ == "__main__":
    unittest.main()