import unittest
from unittest.mock import Mock, patch
from datetime import datetime
import requests

from openalex_searcher import OpenAlexSearcher, ResearchResource, create_searcher

class TestOpenAlexSearcher(unittest.TestCase):
    def setUp(self):
        """Set up test fixtures before each test method."""
        self.searcher = create_searcher('s2231967@ed.ac.uk')
        
        # Sample test data
        self.sample_structured_query = {
            'research_areas': ['machine learning', 'artificial intelligence'],
            'expertise': ['deep learning', 'neural networks'],
            'search_keywords': ['computer vision'],
            'collaboration_type': 'research project',
            'requirements': ['python programming']
        }
        
        self.sample_openalex_response = {
            'results': [{
                'title': 'Deep Learning Advances in Computer Vision',
                'authorships': [
                    {
                        'author': {'display_name': 'John Doe'},
                        'institutions': [{'display_name': 'Stanford University'}]
                    },
                    {
                        'author': {'display_name': 'Jane Smith'},
                        'institutions': []
                    }
                ],
                'publication_date': '2023-01-15',
                'doi': '10.1234/example.doi',
                'cited_by_count': 150,
                'concepts': [
                    {'display_name': 'Machine Learning'},
                    {'display_name': 'Computer Vision'}
                ],
                'type': 'journal-article',
                'abstract': 'A study on deep learning applications in computer vision.'
            }],
            'meta': {
                'count': 1,
                'page': 1,
                'per_page': 50
            }
        }

    def test_initialization(self):
        """Test proper initialization of OpenAlexSearcher."""
        self.assertEqual(
            self.searcher.headers['User-Agent'],
            'ResearchMatcher (s2231967@ed.ac.uk)'
        )
        self.assertIsInstance(self.searcher.session, requests.Session)

    def test_construct_query(self):
        """Test query string construction from structured query."""
        query_string = self.searcher._construct_query(self.sample_structured_query)
        
        # Verify all search terms are included
        search_terms = [
            'machine learning',
            'artificial intelligence',
            'computer vision',
            'deep learning',
            'neural networks'
        ]
        for term in search_terms:
            self.assertIn(f'"{term}"', query_string)
        
        # Verify year range is included
        current_year = datetime.now().year
        self.assertIn(
            f'publication_year:{current_year-5}-{current_year}',
            query_string
        )

    @patch('requests.Session.get')
    def test_search_success(self, mock_get):
        """Test successful API search with mock response."""
        # Setup mock response
        mock_response = Mock()
        mock_response.json.return_value = self.sample_openalex_response
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        # Perform search
        results = self.searcher.search(self.sample_structured_query, max_results=1)
        
        # Verify results
        self.assertEqual(len(results), 1)
        result = results[0]
        self.assertIsInstance(result, ResearchResource)
        self.assertEqual(result.title, 'Deep Learning Advances in Computer Vision')
        self.assertEqual(result.authors, ['John Doe', 'Jane Smith'])
        self.assertEqual(result.institution, 'Stanford University')
        self.assertEqual(result.citations_count, 150)

    @patch('requests.Session.get')
    def test_search_error_handling(self, mock_get):
        """Test error handling during API search."""
        mock_get.side_effect = requests.exceptions.RequestException('API Error')
        
        results = self.searcher.search(self.sample_structured_query)
        self.assertEqual(results, [])

    def test_filter_results(self):
        """Test filtering of search results."""
        test_resources = [
            ResearchResource(
                title='Paper 1',
                authors=['Author 1'],
                publication_date='2023-01-01',
                doi='10.1234/1',
                citations_count=100,
                concepts=['Machine Learning', 'AI'],
                institution='University 1',
                publication_type='journal-article',
                abstract='Abstract 1'
            ),
            ResearchResource(
                title='Paper 2',
                authors=['Author 2'],
                publication_date='2023-01-02',
                doi='10.1234/2',
                citations_count=5,
                concepts=['Computer Vision'],
                institution='University 2',
                publication_type='journal-article',
                abstract='Abstract 2'
            )
        ]

        # Test citation filter
        filtered = self.searcher.filter_results(test_resources, min_citations=50)
        self.assertEqual(len(filtered), 1)
        self.assertEqual(filtered[0].title, 'Paper 1')

        # Test concept filter
        filtered = self.searcher.filter_results(
            test_resources,
            required_concepts=['Machine Learning']
        )
        self.assertEqual(len(filtered), 1)
        self.assertEqual(filtered[0].title, 'Paper 1')

    def test_parse_response(self):
        """Test parsing of API response into ResearchResource object."""
        result = self.searcher._parse_response(
            self.sample_openalex_response['results'][0]
        )
        
        self.assertIsInstance(result, ResearchResource)
        self.assertEqual(result.title, 'Deep Learning Advances in Computer Vision')
        self.assertEqual(len(result.authors), 2)
        self.assertEqual(result.doi, '10.1234/example.doi')
        self.assertEqual(result.citations_count, 150)
        self.assertEqual(len(result.concepts), 2)
        self.assertEqual(result.institution, 'Stanford University')
        self.assertEqual(result.publication_type, 'journal-article')

if __name__ == '__main__':
    unittest.main()