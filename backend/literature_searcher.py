from typing import Dict, List, Optional, Set, Tuple
from datetime import datetime
import logging
from dataclasses import dataclass, field

# Import from OpenAlexClient
from openalex_client import OpenAlexClient, create_client, WorkResult, OpenAlexResponse

@dataclass
class LiteratureResult:
    """Data class for literature search results with enhanced metadata"""
    id: str
    title: str
    abstract: Optional[str] = None
    authors: List[str] = field(default_factory=list)
    publication_date: Optional[str] = None
    journal: Optional[str] = None
    citations: int = 0
    doi: Optional[str] = None
    open_access: bool = False
    type: str = "journal-article"
    topic_matches: Dict[str, float] = field(default_factory=dict)
    relevance_score: float = 0.0
    
    def to_dict(self) -> Dict:
        """Convert to dictionary format for API responses"""
        return {
            "id": self.id,
            "title": self.title,
            "abstract": self.abstract,
            "authors": self.authors,
            "publication_date": self.publication_date,
            "journal": self.journal,
            "citations": self.citations,
            "doi": self.doi,
            "open_access": self.open_access,
            "type": self.type,
            "topic_matches": self.topic_matches,
            "relevance_score": self.relevance_score
        }

class LiteratureSearcher:
    """
    Literature search functionality using OpenAlex API
    
    This class provides methods to search for relevant literature
    based on research topics, keywords, and other criteria.
    """
    
    def __init__(self, email: str):
        """
        Initialize the LiteratureSearcher
        
        Args:
            email: Email for API identification (required by OpenAlex)
        """
        self.email = email
        self.client = create_client(email)
        
        # Configure logging
        self.logger = logging.getLogger('LiteratureSearcher')
        self.logger.setLevel(logging.INFO)
        
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
    
    def search_literature(
        self, 
        structured_query: Dict, 
        max_results: int = 20,
        from_year: Optional[int] = None,
        to_year: Optional[int] = None,
        min_citations: Optional[int] = None,
        publication_types: Optional[List[str]] = None,
        open_access_only: bool = False
    ) -> List[LiteratureResult]:
        """
        Search for literature based on research criteria
        
        Args:
            structured_query: Dictionary containing query parameters
                - research_areas: List of research fields
                - expertise: List of specific expertise areas (or topics)
                - search_keywords: Additional search terms
            max_results: Maximum number of results to return
            from_year: Earliest publication year to include
            to_year: Latest publication year to include
            min_citations: Minimum number of citations required
            publication_types: List of publication types to include
            open_access_only: Whether to include only open access publications
            
        Returns:
            List of LiteratureResult objects
        """
        self.logger.info(f"Searching for literature with criteria: {structured_query}")
        
        # Extract search terms from query
        search_terms = self._extract_search_terms(structured_query)
        search_query = " ".join(search_terms)
        
        if not search_query.strip():
            self.logger.warning("Empty search query, cannot proceed")
            return []
        
        # Search for works
        response = self.client.search_works(
            query=search_query,
            from_year=from_year,
            to_year=to_year,
            per_page=max_results,
            sort="relevance_score:desc",
            min_citations=min_citations
        )
        
        if response.error:
            self.logger.error(f"Error searching OpenAlex API: {response.error}")
            return []
            
        # Process works to create literature results
        results = self._process_search_results(
            response.get_works(),
            structured_query,
            publication_types,
            open_access_only
        )
        
        self.logger.info(f"Found {len(results)} publications for query")
        return results
    
    def get_publication_details(self, publication_id: str) -> Optional[Dict]:
        """
        Get detailed information about a specific publication
        
        Args:
            publication_id: Publication identifier
            
        Returns:
            Dictionary with publication details or None if not found
        """
        self.logger.info(f"Getting details for publication: {publication_id}")
        
        # Attempt to get work by ID if it's an OpenAlex ID
        if publication_id.startswith('https://openalex.org/') or publication_id.startswith('W'):
            try:
                # Extract OpenAlex ID from URL or prefix with W if it's just the ID
                if publication_id.startswith('https://openalex.org/'):
                    openalex_id = publication_id.split('/')[-1]
                else:
                    openalex_id = publication_id if publication_id.startswith('W') else f"W{publication_id}"
                
                # Make API request
                response = self.client._make_request(f"works/{openalex_id}")
                
                if response.error:
                    self.logger.error(f"Error fetching publication details: {response.error}")
                    return None
                
                # Process the publication details
                publication = self._process_publication_details(response.data)
                return publication.to_dict()
                
            except Exception as e:
                self.logger.error(f"Error processing publication details: {str(e)}")
                return None
        
        self.logger.warning(f"Publication ID {publication_id} is not an OpenAlex ID format")
        return None
    
    def get_similar_publications(
        self, 
        publication_id: str,
        max_results: int = 5
    ) -> List[Dict]:
        """
        Find publications similar to the specified publication
        
        Args:
            publication_id: Publication identifier
            max_results: Maximum number of similar publications to return
            
        Returns:
            List of similar publications
        """
        publication_details = self.get_publication_details(publication_id)
        
        if not publication_details:
            return []
            
        # Extract keywords and concepts
        keywords = []
        if "topic_matches" in publication_details:
            keywords.extend(publication_details["topic_matches"].keys())
            
        # Create a structured query from the publication info
        query = {
            "research_areas": keywords[:3],  # Use top 3 keywords as research areas
            "search_keywords": [publication_details.get("title", "")]
        }
        
        # Search for similar publications
        similar_publications = self.search_literature(
            query,
            max_results=max_results + 1  # Add 1 to filter out the original publication
        )
        
        # Filter out the original publication
        filtered_results = [
            pub.to_dict() for pub in similar_publications 
            if pub.id != publication_id
        ][:max_results]
        
        return filtered_results
    
    def search_by_keywords(
        self, 
        keywords: List[str],
        max_results: int = 20,
        from_year: Optional[int] = None,
        to_year: Optional[int] = None
    ) -> List[Dict]:
        """
        Search for publications by keywords
        
        Args:
            keywords: List of keywords
            max_results: Maximum number of publications to return
            from_year: Earliest publication year to include
            to_year: Latest publication year to include
            
        Returns:
            List of dictionaries with publication information
        """
        self.logger.info(f"Searching for publications by keywords: {keywords}")
        
        structured_query = {
            'research_areas': [],
            'expertise': [],
            'search_keywords': keywords
        }
        
        publications = self.search_literature(
            structured_query, 
            max_results=max_results,
            from_year=from_year,
            to_year=to_year
        )
        
        return [pub.to_dict() for pub in publications]
        
    def _extract_search_terms(self, structured_query: Dict) -> List[str]:
        """Extract search terms from structured query"""
        search_terms = []
        
        # Add research areas
        if 'research_areas' in structured_query:
            search_terms.extend(structured_query['research_areas'])
            
        # Add expertise areas (topics)
        if 'expertise' in structured_query:
            search_terms.extend(structured_query['expertise'])
            
        # Add search keywords
        if 'search_keywords' in structured_query:
            search_terms.extend(structured_query['search_keywords'])
        
        return search_terms
    
    def _process_search_results(
        self, 
        works: List[WorkResult],
        structured_query: Dict,
        publication_types: Optional[List[str]] = None,
        open_access_only: bool = False
    ) -> List[LiteratureResult]:
        """
        Process work results into literature results
        
        Args:
            works: List of works from OpenAlex API
            structured_query: Original query structure for relevance calculation
            publication_types: List of publication types to include
            open_access_only: Whether to include only open access publications
            
        Returns:
            List of LiteratureResult objects
        """
        results = []
        
        # Extract query terms for relevance scoring and topic matching
        query_terms = set()
        for key in ['research_areas', 'expertise', 'search_keywords']:
            if key in structured_query:
                query_terms.update(term.lower() for term in structured_query[key])
        
        # Process each work
        for work in works:
            # Skip if filtered by publication type
            work_type = self._determine_publication_type(work)
            if publication_types and work_type not in publication_types:
                continue
                
            # Skip if not open access and open access filter is active
            is_open_access = work.doi is not None  # Simplified check - can be enhanced
            if open_access_only and not is_open_access:
                continue
            
            # Generate topic matches and relevance score
            topic_matches, relevance_score = self._calculate_relevance(work, query_terms)
            
            # Create literature result
            result = LiteratureResult(
                id=work.doi if work.doi else f"W{hash(work.title) & 0xffffffff}",
                title=work.title,
                abstract=work.abstract,
                authors=work.authors,
                publication_date=work.publication_date,
                journal=self._extract_journal_name(work),
                citations=work.citations,
                doi=work.doi,
                open_access=is_open_access,
                type=work_type,
                topic_matches=topic_matches,
                relevance_score=relevance_score
            )
            
            results.append(result)
        
        # Sort by relevance score
        results.sort(key=lambda x: x.relevance_score, reverse=True)
        
        return results
    
    def _process_publication_details(self, publication_data: Dict) -> LiteratureResult:
        """
        Convert OpenAlex publication data to LiteratureResult format
        
        Args:
            publication_data: Publication data from OpenAlex API
            
        Returns:
            LiteratureResult object
        """
        # Extract authors
        authors = []
        for authorship in publication_data.get('authorships', []):
            if 'author' in authorship and 'display_name' in authorship['author']:
                authors.append(authorship['author']['display_name'])
        
        # Extract journal name
        journal = None
        if 'primary_location' in publication_data and publication_data['primary_location']:
            if 'source' in publication_data['primary_location']:
                journal = publication_data['primary_location']['source'].get('display_name')
        
        # Extract concepts for topic matches
        topic_matches = {}
        for concept in publication_data.get('concepts', []):
            if 'display_name' in concept and 'score' in concept:
                topic_matches[concept['display_name']] = concept['score']
        
        # Determine publication type
        pub_type = self._determine_publication_type_from_data(publication_data)
        
        # Check if open access
        is_open_access = publication_data.get('open_access', {}).get('is_oa', False)
        
        return LiteratureResult(
            id=publication_data.get('id', ''),
            title=publication_data.get('display_name', 'Untitled Publication'),
            abstract=publication_data.get('abstract', None),
            authors=authors,
            publication_date=publication_data.get('publication_date', None),
            journal=journal,
            citations=publication_data.get('cited_by_count', 0),
            doi=publication_data.get('doi', None),
            open_access=is_open_access,
            type=pub_type,
            topic_matches=topic_matches,
            relevance_score=1.0  # Default for direct lookups
        )
    
    def _calculate_relevance(
        self, 
        work: WorkResult,
        query_terms: Set[str]
    ) -> Tuple[Dict[str, float], float]:
        """
        Calculate topic matches and relevance score
        
        Args:
            work: Work result from OpenAlex API
            query_terms: Set of query terms for matching
            
        Returns:
            Tuple of (topic_matches, relevance_score)
        """
        # Extract terms from title and abstract
        work_terms = set()
        if work.title:
            work_terms.update(self._extract_terms(work.title))
        if work.abstract:
            work_terms.update(self._extract_terms(work.abstract))
        
        # Calculate topic matches
        topic_matches = {}
        
        for query_term in query_terms:
            best_match = 0.0
            for work_term in work_terms:
                # Calculate similarity between terms
                if query_term.lower() in work_term.lower():
                    similarity = len(query_term) / len(work_term)
                    best_match = max(best_match, similarity)
                elif work_term.lower() in query_term.lower():
                    similarity = len(work_term) / len(query_term)
                    best_match = max(best_match, similarity)
            
            if best_match > 0.5:  # Only include significant matches
                topic_matches[query_term] = best_match
        
        # Calculate overall relevance score
        relevance_score = 0.0
        if query_terms:
            matching_terms = sum(1 for term in work_terms if any(
                qt.lower() in term.lower() or term.lower() in qt.lower() for qt in query_terms
            ))
            relevance_score = min(1.0, matching_terms / len(query_terms) if query_terms else 0)
            
            # Boost by citation count (optional)
            citation_factor = min(1.0, (work.citations or 0) / 100)  # Scale citations
            relevance_score = 0.8 * relevance_score + 0.2 * citation_factor
        
        return topic_matches, relevance_score
    
    def _extract_terms(self, text: str) -> Set[str]:
        """
        Extract meaningful terms from text
        
        Args:
            text: Input text
            
        Returns:
            Set of extracted terms
        """
        if not text:
            return set()
            
        # Normalize text
        text = text.lower()
        
        # Extract n-grams (1, 2, and 3-grams)
        words = [w for w in text.split() if len(w) > 2]
        
        # Generate n-grams
        unigrams = set(words)
        bigrams = set(' '.join(words[i:i+2]) for i in range(len(words)-1))
        trigrams = set(' '.join(words[i:i+3]) for i in range(len(words)-2))
        
        # Combine all n-grams
        all_terms = unigrams.union(bigrams).union(trigrams)
        
        # Filter out common words and short terms
        stopwords = {
            'the', 'and', 'with', 'for', 'this', 'that', 'from', 'been',
            'have', 'has', 'not', 'are', 'were', 'was', 'being', 'been',
            'can', 'could', 'will', 'would', 'should', 'may', 'might'
        }
        
        filtered_terms = {
            t for t in all_terms 
            if len(t) > 3 and not all(w in stopwords for w in t.split())
        }
        
        return filtered_terms
    
    def _determine_publication_type(self, work: WorkResult) -> str:
        """Determine the publication type from work metadata"""
        # This is a simplified implementation - in a real system, 
        # you would use more metadata from the API response
        if not work.doi:
            return "preprint"
        
        journal_name = self._extract_journal_name(work)
        if "conference" in (journal_name or "").lower():
            return "conference-paper"
        elif "review" in (journal_name or "").lower():
            return "review"
        elif "book" in (journal_name or "").lower():
            return "book-chapter"
        else:
            return "journal-article"
    
    def _determine_publication_type_from_data(self, publication_data: Dict) -> str:
        """Determine publication type from detailed publication data"""
        # Check type field if available
        if 'type' in publication_data:
            type_value = publication_data['type']
            if type_value == 'journal-article':
                return 'journal-article'
            elif type_value == 'proceedings-article':
                return 'conference-paper'
            elif type_value == 'book-chapter':
                return 'book-chapter'
            elif type_value == 'review':
                return 'review'
            elif type_value == 'preprint':
                return 'preprint'
        
        # If no type or unknown type, make a best guess
        journal_name = None
        if 'primary_location' in publication_data and publication_data['primary_location']:
            if 'source' in publication_data['primary_location']:
                journal_name = publication_data['primary_location']['source'].get('display_name', '')
        
        if journal_name:
            if "conference" in journal_name.lower():
                return "conference-paper"
            elif "review" in journal_name.lower():
                return "review"
            elif "book" in journal_name.lower():
                return "book-chapter"
        
        return "journal-article"  # Default
    
    def _extract_journal_name(self, work: WorkResult) -> Optional[str]:
        """Extract journal name from work metadata (simplified)"""
        # This is a placeholder - in a real implementation, you would
        # extract this from the API response metadata
        return None

def create_literature_searcher(email: str) -> LiteratureSearcher:
    """Factory function to create a LiteratureSearcher instance"""
    return LiteratureSearcher(email)