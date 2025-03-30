# article_searcher.py
from typing import Dict, List, Optional, Set
from datetime import datetime
import logging
from dataclasses import dataclass, field

# Import from OpenAlexClient
from openalex_client import OpenAlexClient, create_client, WorkResult, OpenAlexResponse

@dataclass
class ResearchArticle:
    """Data class for research article information"""
    id: str
    title: str
    authors: List[str]
    publication_date: str
    journal: Optional[str] = None
    citation_count: int = 0
    abstract: Optional[str] = None
    keywords: Set[str] = field(default_factory=set)
    relevance_score: float = 0.0
    
    def to_dict(self) -> Dict:
        """Convert to dictionary format for API responses"""
        return {
            "id": self.id,
            "title": self.title,
            "authors": self.authors,
            "publication_date": self.publication_date,
            "journal": self.journal,
            "citation_count": self.citation_count,
            "abstract": self.abstract,
            "keywords": list(self.keywords),
            "relevance_score": self.relevance_score
        }

class ArticleSearcher:
    """
    Research article search functionality using OpenAlex API
    
    This class provides methods to search for research articles
    based on research topics, disciplines, and other criteria.
    It uses the OpenAlexClient for robust API interactions.
    """
    
    def __init__(self, email: str):
        """
        Initialize the ArticleSearcher
        
        Args:
            email: Email for API identification (required by OpenAlex)
        """
        self.email = email
        self.client = create_client(email)
        
        # Configure logging
        self.logger = logging.getLogger('ArticleSearcher')
        self.logger.setLevel(logging.INFO)
        
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
    
    def search_articles(
        self, 
        structured_query: Dict, 
        max_results: int = 20,
        recent_years: int = 5,
        min_citations: int = 0
    ) -> List[ResearchArticle]:
        """
        Search for articles based on research criteria
        
        Args:
            structured_query: Dictionary containing query parameters
                - research_areas: List of research fields
                - expertise: List of specific expertise areas
                - search_keywords: Additional search terms
            max_results: Maximum number of articles to return
            recent_years: Number of recent years to consider
            min_citations: Minimum number of citations required
            
        Returns:
            List of ResearchArticle objects
        """
        self.logger.info(f"Searching for articles with criteria: {structured_query}")
        
        # Extract search terms from query
        search_terms = self._extract_search_terms(structured_query)
        search_query = " ".join(search_terms)
        
        if not search_query.strip():
            self.logger.warning("Empty search query, cannot proceed")
            return []
        
        # Current year for recency filtering
        current_year = datetime.now().year
        from_year = current_year - recent_years
        
        # Search for works
        response = self.client.search_works(
            query=search_query,
            from_year=from_year,
            to_year=current_year,
            per_page=max_results,
            sort="cited_by_count:desc",
            min_citations=min_citations
        )
        
        if response.error:
            self.logger.error(f"Error searching OpenAlex API: {response.error}")
            return []
            
        # Process works to extract article information
        articles = self._convert_works_to_articles(
            response.get_works(),
            structured_query
        )
        
        # Sort by relevance score and limit results
        sorted_articles = sorted(
            articles,
            key=lambda x: (x.relevance_score, x.citation_count),
            reverse=True
        )
        
        self.logger.info(f"Found {len(sorted_articles)} articles for query")
        return sorted_articles[:max_results]
    
    def get_article_details(self, article_id: str) -> Optional[Dict]:
        """
        Get detailed information about a specific article
        
        Args:
            article_id: Article identifier
            
        Returns:
            Dictionary with article details or None if not found
        """
        self.logger.info(f"Getting details for article: {article_id}")
        
        # Attempt to get work by ID if it's an OpenAlex ID
        if article_id.startswith('https://openalex.org/'):
            try:
                # Extract OpenAlex ID from URL
                openalex_id = article_id.split('/')[-1]
                
                # Make API request
                response = self.client._make_request(f"works/{openalex_id}")
                
                if response.error:
                    self.logger.error(f"Error fetching article details: {response.error}")
                    return None
                
                # Convert to ResearchArticle format
                work = WorkResult.from_api_response(response.data)
                return self._convert_work_to_article(work, {}).to_dict()
                
            except Exception as e:
                self.logger.error(f"Error processing article details: {str(e)}")
                return None
        
        # For non-OpenAlex IDs, we'll need to search by title
        self.logger.warning(f"Article ID {article_id} is not an OpenAlex ID format")
        return None
    
    def search_by_disciplines(
        self, 
        disciplines: List[str],
        max_results: int = 20,
        min_citations: int = 10,
        recent_years: int = 5
    ) -> List[Dict]:
        """
        Search for articles by research disciplines
        
        Args:
            disciplines: List of research disciplines
            max_results: Maximum number of articles to return
            min_citations: Minimum number of citations required
            recent_years: Number of recent years to consider
            
        Returns:
            List of dictionaries with article information
        """
        self.logger.info(f"Searching for articles by disciplines: {disciplines}")
        
        structured_query = {
            'research_areas': disciplines,
            'expertise': [],
            'search_keywords': []
        }
        
        articles = self.search_articles(
            structured_query, 
            max_results=max_results,
            min_citations=min_citations,
            recent_years=recent_years
        )
        
        self.logger.info(f"Found {len(articles)} articles for disciplines")
        return [a.to_dict() for a in articles]
    
    def search_multidisciplinary(
        self,
        primary_discipline: str,
        secondary_disciplines: List[str],
        max_results: int = 10,
        recent_years: int = 5
    ) -> List[Dict]:
        """
        Search for articles spanning multiple disciplines
        
        Args:
            primary_discipline: Main research discipline
            secondary_disciplines: Additional disciplines of interest
            max_results: Maximum number of articles to return
            recent_years: Number of recent years to consider
            
        Returns:
            List of dictionaries with article information
        """
        self.logger.info(
            f"Searching for multidisciplinary articles: primary={primary_discipline}, "
            f"secondary={secondary_disciplines}"
        )
        
        # Combine all disciplines for the search
        all_disciplines = [primary_discipline] + secondary_disciplines
        structured_query = {
            'research_areas': all_disciplines,
            'expertise': [],
            'search_keywords': []
        }
        
        # Get articles matching any of the disciplines
        articles = self.search_articles(
            structured_query,
            max_results=max_results * 2,  # Get more for filtering
            recent_years=recent_years
        )
        
        if not articles:
            self.logger.warning(f"No articles found for disciplines")
            return []
        
        # Calculate multidisciplinary relevance
        for article in articles:
            # Check how many disciplines are covered in the article
            keyword_text = ' '.join(article.keywords).lower()
            title_abstract = (article.title + ' ' + (article.abstract or '')).lower()
            
            # Count matches for each discipline
            primary_match = primary_discipline.lower() in keyword_text or primary_discipline.lower() in title_abstract
            secondary_matches = sum(
                1 for sd in secondary_disciplines 
                if sd.lower() in keyword_text or sd.lower() in title_abstract
            )
            
            # Calculate relevance score based on discipline coverage
            # Articles must match primary discipline and at least one secondary
            if primary_match and secondary_matches > 0:
                # Normalize score by number of secondary disciplines
                article.relevance_score = 0.5 + (secondary_matches / len(secondary_disciplines)) * 0.5
            else:
                article.relevance_score = 0.0
        
        # Filter and sort by relevance
        filtered_articles = [a for a in articles if a.relevance_score > 0]
        sorted_articles = sorted(
            filtered_articles,
            key=lambda x: (x.relevance_score, x.citation_count),
            reverse=True
        )
        
        self.logger.info(f"Found {len(sorted_articles)} multidisciplinary articles")
        return [a.to_dict() for a in sorted_articles[:max_results]]
        
    def _extract_search_terms(self, structured_query: Dict) -> List[str]:
        """Extract search terms from structured query"""
        search_terms = []
        
        # Add research areas
        if 'research_areas' in structured_query:
            search_terms.extend(structured_query['research_areas'])
            
        # Add expertise areas
        if 'expertise' in structured_query:
            search_terms.extend(structured_query['expertise'])
            
        # Add search keywords
        if 'search_keywords' in structured_query:
            search_terms.extend(structured_query['search_keywords'])
        
        return search_terms
    
    def _convert_works_to_articles(
        self, 
        works: List[WorkResult],
        structured_query: Dict
    ) -> List[ResearchArticle]:
        """
        Convert work results to research articles with relevance scoring
        
        Args:
            works: List of works from OpenAlex API
            structured_query: Original query structure for relevance calculation
            
        Returns:
            List of ResearchArticle objects
        """
        articles = []
        
        # Extract query terms for relevance scoring
        query_terms = set()
        for key in ['research_areas', 'expertise', 'search_keywords']:
            if key in structured_query:
                query_terms.update(term.lower() for term in structured_query[key])
        
        # Process each work to create article objects
        for work in works:
            article = self._convert_work_to_article(work, query_terms)
            articles.append(article)
        
        return articles
    
    def _convert_work_to_article(
        self, 
        work: WorkResult, 
        query_terms: Set[str]
    ) -> ResearchArticle:
        """
        Convert a single work to a research article with relevance scoring
        
        Args:
            work: Work result from OpenAlex API
            query_terms: Set of query terms for relevance calculation
            
        Returns:
            ResearchArticle object
        """
        # Extract keywords from title and abstract
        keywords = set()
        if work.title:
            keywords.update(self._extract_terms(work.title))
        if work.abstract:
            keywords.update(self._extract_terms(work.abstract))
        
        # Calculate relevance based on query terms
        relevance = 0.0
        if query_terms:
            matching_terms = sum(1 for term in keywords if any(
                qt in term for qt in query_terms
            ))
            relevance = min(1.0, matching_terms / len(query_terms) if query_terms else 0)
        
        # Create article object
        article = ResearchArticle(
            id=f"https://doi.org/{work.doi}" if work.doi else f"article:{hash(work.title)}",
            title=work.title,
            authors=work.authors,
            publication_date=work.publication_date,
            citation_count=work.citations,
            abstract=work.abstract,
            keywords=keywords,
            relevance_score=relevance
        )
        
        return article
    
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

def create_article_searcher(email: str) -> ArticleSearcher:
    """Factory function to create an ArticleSearcher instance"""
    return ArticleSearcher(email)