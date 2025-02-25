# expert_searcher.py
from typing import Dict, List, Optional, Set, Tuple
from datetime import datetime
import logging
from dataclasses import dataclass, field

# Import from OpenAlexClient
from openalex_client import OpenAlexClient, create_client, WorkResult, OpenAlexResponse

@dataclass
class ResearchExpert:
    """Data class for researcher expertise information"""
    id: str
    name: str
    institution: Optional[str] = None
    citation_count: int = 0
    works_count: int = 0
    expertise_areas: Set[str] = field(default_factory=set)
    top_works: List[Dict] = field(default_factory=list)
    h_index: Optional[int] = None
    recent_years: Set[int] = field(default_factory=set)
    relevance_score: float = 0.0
    
    def to_dict(self) -> Dict:
        """Convert to dictionary format for API responses"""
        return {
            "id": self.id,
            "name": self.name,
            "institution": self.institution,
            "citation_count": self.citation_count,
            "works_count": self.works_count,
            "expertise_areas": list(self.expertise_areas),
            "top_works": self.top_works[:5],  # Limit to top 5 works
            "h_index": self.h_index,
            "recent_years": sorted(list(self.recent_years), reverse=True),
            "relevance_score": self.relevance_score
        }

class ExpertSearcher:
    """
    Expert researcher search functionality using OpenAlex API
    
    This class provides methods to search for researcher expertise
    based on research topics, disciplines, and other criteria.
    It uses the OpenAlexClient for robust API interactions.
    """
    
    def __init__(self, email: str):
        """
        Initialize the ExpertSearcher
        
        Args:
            email: Email for API identification (required by OpenAlex)
        """
        self.email = email
        self.client = create_client(email)
        
        # Configure logging
        self.logger = logging.getLogger('ExpertSearcher')
        self.logger.setLevel(logging.INFO)
        
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
    
    def search_experts(
        self, 
        structured_query: Dict, 
        max_results: int = 20,
        recent_years: int = 5,
        min_works: int = 3
    ) -> List[ResearchExpert]:
        """
        Search for experts based on research criteria
        
        Args:
            structured_query: Dictionary containing query parameters
                - research_areas: List of research fields
                - expertise: List of specific expertise areas
                - search_keywords: Additional search terms
            max_results: Maximum number of experts to return
            recent_years: Number of recent years to consider for active researchers
            min_works: Minimum number of works required
            
        Returns:
            List of ResearchExpert objects
        """
        self.logger.info(f"Searching for experts with criteria: {structured_query}")
        
        # Extract search terms from query
        search_terms = self._extract_search_terms(structured_query)
        search_query = " ".join(search_terms)
        
        if not search_query.strip():
            self.logger.warning("Empty search query, cannot proceed")
            return []
        
        # Current year for recency filtering
        current_year = datetime.now().year
        from_year = current_year - recent_years
        
        # Search for works first - we'll extract authors from these
        response = self.client.search_works(
            query=search_query,
            from_year=from_year,
            to_year=current_year,
            per_page=100,  # Get more works to find more unique authors
            sort="cited_by_count:desc"
        )
        
        if response.error:
            self.logger.error(f"Error searching OpenAlex API: {response.error}")
            return []
            
        # Process works to extract experts
        experts = self._extract_experts_from_works(
            response.get_works(),
            structured_query,
            min_works
        )
        
        # Sort by citation count and limit results
        sorted_experts = sorted(
            experts.values(),
            key=lambda x: (x.relevance_score, x.citation_count),
            reverse=True
        )
        
        self.logger.info(f"Found {len(sorted_experts)} experts for query")
        return sorted_experts[:max_results]
    
    def get_expert_details(self, expert_id: str) -> Optional[Dict]:
        """
        Get detailed information about a specific expert
        
        Args:
            expert_id: Expert identifier
            
        Returns:
            Dictionary with expert details or None if not found
        """
        self.logger.info(f"Getting details for expert: {expert_id}")
        
        # Attempt to get researcher by ID if it's an OpenAlex ID
        if expert_id.startswith('https://openalex.org/'):
            try:
                # Extract OpenAlex ID from URL
                openalex_id = expert_id.split('/')[-1]
                
                # Make API request
                response = self.client._make_request(f"authors/{openalex_id}")
                
                if response.error:
                    self.logger.error(f"Error fetching expert details: {response.error}")
                    return None
                
                # Convert to ResearchExpert format
                return self._convert_api_author_to_expert(response.data).to_dict()
                
            except Exception as e:
                self.logger.error(f"Error processing expert details: {str(e)}")
                return None
        
        # For non-OpenAlex IDs, we'll need to search by name
        self.logger.warning(f"Expert ID {expert_id} is not an OpenAlex ID format")
        return None
    
    def search_by_disciplines(
        self, 
        disciplines: List[str],
        max_results: int = 20,
        min_citations: int = 100
    ) -> List[Dict]:
        """
        Search for experts by research disciplines
        
        Args:
            disciplines: List of research disciplines
            max_results: Maximum number of experts to return
            min_citations: Minimum number of citations required
            
        Returns:
            List of dictionaries with expert information
        """
        self.logger.info(f"Searching for experts by disciplines: {disciplines}")
        
        structured_query = {
            'research_areas': disciplines,
            'expertise': [],
            'search_keywords': []
        }
        
        experts = self.search_experts(
            structured_query, 
            max_results=max_results,
            min_works=5  # Higher threshold for discipline search
        )
        
        # Filter by minimum citations
        filtered_experts = [
            e for e in experts 
            if e.citation_count >= min_citations
        ]
        
        self.logger.info(f"Found {len(filtered_experts)} experts with min {min_citations} citations")
        return [e.to_dict() for e in filtered_experts]
    
    def search_multidisciplinary(
        self,
        primary_discipline: str,
        secondary_disciplines: List[str],
        max_results: int = 10,
        require_all: bool = False
    ) -> List[Dict]:
        """
        Search for experts working across multiple disciplines
        
        Args:
            primary_discipline: Main research discipline
            secondary_disciplines: Additional disciplines of interest
            max_results: Maximum number of experts to return
            require_all: If True, experts must match all disciplines
            
        Returns:
            List of dictionaries with expert information
        """
        self.logger.info(
            f"Searching for multidisciplinary experts: primary={primary_discipline}, "
            f"secondary={secondary_disciplines}, require_all={require_all}"
        )
        
        # First search for primary discipline experts
        primary_experts = self.search_experts(
            {'research_areas': [primary_discipline]},
            max_results=max_results * 2  # Get more for filtering
        )
        
        if not primary_experts:
            self.logger.warning(f"No experts found for primary discipline: {primary_discipline}")
            return []
        
        # Filter experts based on secondary disciplines
        filtered_experts = []
        
        for expert in primary_experts:
            # Check if expert has expertise in secondary disciplines
            matches = [
                any(sd.lower() in area.lower() for area in expert.expertise_areas)
                for sd in secondary_disciplines
            ]
            
            if require_all and all(matches):
                # Expert matches all secondary disciplines
                expert.relevance_score = 1.0
                filtered_experts.append(expert)
            elif not require_all and any(matches):
                # Expert matches at least one secondary discipline
                expert.relevance_score = sum(matches) / len(secondary_disciplines)
                filtered_experts.append(expert)
        
        # Sort by relevance score and limit results
        sorted_experts = sorted(
            filtered_experts,
            key=lambda x: x.relevance_score,
            reverse=True
        )
        
        self.logger.info(f"Found {len(sorted_experts)} multidisciplinary experts")
        return [e.to_dict() for e in sorted_experts[:max_results]]
        
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
    
    def _extract_experts_from_works(
        self, 
        works: List[WorkResult],
        structured_query: Dict,
        min_works: int
    ) -> Dict[str, ResearchExpert]:
        """
        Extract expert information from work results
        
        Args:
            works: List of works from OpenAlex API
            structured_query: Original query structure for relevance calculation
            min_works: Minimum number of works to include an expert
            
        Returns:
            Dictionary mapping expert IDs to ResearchExpert objects
        """
        experts = {}
        author_works = {}
        
        # Extract query terms for relevance scoring
        query_terms = set()
        for key in ['research_areas', 'expertise', 'search_keywords']:
            if key in structured_query:
                query_terms.update(term.lower() for term in structured_query[key])
        
        # Process each work to extract authors and their expertise
        for work in works:
            # Skip works without authors
            if not work.authors:
                continue
            
            # Extract publication year
            pub_year = None
            if work.publication_date:
                try:
                    pub_year = int(work.publication_date.split('-')[0])
                except (ValueError, IndexError):
                    pass
            
            # Generate concept terms from title and abstract
            concepts = set()
            if work.title:
                concepts.update(self._extract_terms(work.title))
            if work.abstract:
                concepts.update(self._extract_terms(work.abstract))
            
            # Calculate relevance based on query terms
            relevance = 0.0
            if query_terms:
                matching_terms = sum(1 for term in concepts if any(
                    qt in term for qt in query_terms
                ))
                relevance = min(1.0, matching_terms / len(query_terms) if query_terms else 0)
            
            # Process each author
            for author_name in work.authors:
                # Create a unique ID for the author
                author_id = f"author:{author_name.lower().replace(' ', '_')}"
                
                # Track works by this author
                if author_id not in author_works:
                    author_works[author_id] = []
                
                author_works[author_id].append({
                    'title': work.title,
                    'publication_date': work.publication_date,
                    'year': pub_year,
                    'citations': work.citations,
                    'concepts': list(concepts),
                    'relevance': relevance
                })
                
                # Update or create expert record
                if author_id not in experts:
                    experts[author_id] = ResearchExpert(
                        id=author_id,
                        name=author_name,
                        institution=None,  # Will be filled later if available
                        citation_count=work.citations,
                        works_count=1,
                        expertise_areas=concepts,
                        relevance_score=relevance
                    )
                else:
                    expert = experts[author_id]
                    expert.citation_count += work.citations
                    expert.works_count += 1
                    expert.expertise_areas.update(concepts)
                    expert.relevance_score = max(expert.relevance_score, relevance)
                
                # Add publication year to recent years
                if pub_year:
                    experts[author_id].recent_years.add(pub_year)
        
        # Filter experts with fewer than min_works
        filtered_experts = {
            aid: expert 
            for aid, expert in experts.items() 
            if expert.works_count >= min_works
        }
        
        # Add top works to each expert
        for aid, expert in filtered_experts.items():
            # Sort works by citations
            sorted_works = sorted(
                author_works[aid],
                key=lambda w: w['citations'],
                reverse=True
            )
            expert.top_works = sorted_works[:5]  # Keep top 5 works
        
        return filtered_experts
    
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
    
    def _convert_api_author_to_expert(self, author_data: Dict) -> ResearchExpert:
        """
        Convert OpenAlex author data to ResearchExpert format
        
        Args:
            author_data: Author data from OpenAlex API
            
        Returns:
            ResearchExpert object
        """
        # Extract institution if available
        institution = None
        if 'last_known_institution' in author_data and author_data['last_known_institution']:
            institution = author_data['last_known_institution'].get('display_name')
        
        # Extract expertise areas from concepts
        expertise_areas = set()
        for concept in author_data.get('x_concepts', []):
            expertise_areas.add(concept.get('display_name', '').lower())
        
        # Create expert object
        expert = ResearchExpert(
            id=author_data.get('id', ''),
            name=author_data.get('display_name', ''),
            institution=institution,
            citation_count=author_data.get('cited_by_count', 0),
            works_count=author_data.get('works_count', 0),
            expertise_areas=expertise_areas,
            h_index=author_data.get('h_index', None),
            relevance_score=1.0  # Default for direct lookups
        )
        
        return expert

def create_expert_searcher(email: str) -> ExpertSearcher:
    """Factory function to create an ExpertSearcher instance"""
    return ExpertSearcher(email)