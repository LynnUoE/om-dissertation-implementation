from typing import Dict, List, Optional, Union, Any
from datetime import datetime, timedelta
import logging
import json
from dataclasses import dataclass, field, asdict

# Import from project components
from openalex_client import create_client, OpenAlexClient
from query_processor import create_query_processor, QueryProcessor
from research_analyzer import create_analyzer, ResearchAnalyzer

@dataclass
class LiteratureSearchResult:
    """Data class for structured literature search results"""
    id: str
    title: str
    authors: List[str]
    publication_date: Optional[str] = None
    journal: Optional[str] = None
    abstract: Optional[str] = None
    doi: Optional[str] = None
    citations: int = 0
    open_access: bool = False
    type: str = "journal-article"
    topic_matches: Dict[str, float] = field(default_factory=dict)
    relevance_score: float = 0.0
    analysis: Optional[Dict[str, Any]] = None
    url: Optional[str] = None
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for API responses"""
        return asdict(self)

class LiteratureSearcher:
    """
    Literature search orchestrator that integrates query processing,
    OpenAlex API calls, and research analysis.
    """
    
    def __init__(
        self,
        openai_api_key: str,
        email_for_openalex: str,
        cache_duration: int = 24  # Cache duration in hours
    ):
        """
        Initialize the literature searcher
        
        Args:
            openai_api_key: API key for OpenAI
            email_for_openalex: Email for OpenAlex API identification
            cache_duration: Duration in hours to cache results
        """
        # Initialize components
        self.query_processor = create_query_processor(openai_api_key)
        self.openalex_client = create_client(email_for_openalex)
        self.research_analyzer = create_analyzer(openai_api_key)
        self.cache_duration = cache_duration
        
        # Setup result cache
        self.result_cache = {}
        
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
    
    def search(
        self, 
        query: str,
        max_results: int = 10,
        from_year: Optional[int] = None,
        to_year: Optional[int] = None,
        min_citations: Optional[int] = None,
        publication_types: Optional[List[str]] = None,
        open_access_only: bool = False,
        analyze_results: bool = True,
        min_relevance: float = 0.5
    ) -> Dict:
        """
        Perform a comprehensive literature search based on natural language query
        
        Args:
            query: Natural language query describing research interests
            max_results: Maximum number of results to return
            from_year: Earliest publication year to include
            to_year: Latest publication year to include
            min_citations: Minimum citation count
            publication_types: Types of publications to include
            open_access_only: Whether to return only open access publications
            analyze_results: Whether to perform research analysis on results
            min_relevance: Minimum relevance score for analyzed results
            
        Returns:
            Dictionary containing search results and metadata
        """
        try:
            # Check cache first
            cache_key = self._generate_cache_key(query, max_results, from_year, to_year, 
                                              min_citations, publication_types, open_access_only)
            cached_result = self._get_from_cache(cache_key)
            if cached_result:
                self.logger.info(f"Returning cached results for query: {query[:50]}...")
                return cached_result
            
            self.logger.info(f"Processing literature search for query: {query[:50]}...")
            
            # Process query to extract structured information
            query_start_time = datetime.now()
            structured_query = self.query_processor.process_query(query)
            query_processing_time = (datetime.now() - query_start_time).total_seconds()
            
            self.logger.info(f"Query processing completed in {query_processing_time:.2f}s")
            self.logger.info(f"Extracted {len(structured_query.get('research_areas', []))} research areas " +
                           f"and {len(structured_query.get('expertise', []))} expertise areas")
            
            # If we have no search terms, return empty results
            if (not structured_query.get('research_areas') and 
                not structured_query.get('expertise') and 
                not structured_query.get('search_keywords')):
                
                self.logger.warning("No search terms extracted from query")
                return {
                    'status': 'error',
                    'message': 'Could not extract search terms from query',
                    'original_query': query,
                    'structured_query': structured_query,
                    'results': [],
                    'metadata': {
                        'total_results': 0,
                        'processing_time': query_processing_time
                    }
                }
            
            # Determine time window based on query or defaults
            if not from_year and 'temporal_context' in structured_query:
                temporal_context = structured_query['temporal_context']
                from_year = self._extract_year_from_temporal_context(temporal_context)
            
            if not to_year:
                to_year = datetime.now().year
            
            # Prepare search parameters
            search_terms = self._extract_search_terms(structured_query)
            search_query = " ".join(search_terms)
            
            # Execute search query
            search_start_time = datetime.now()
            
            response = self.openalex_client.search_works(
                query=search_query,
                from_year=from_year,
                to_year=to_year,
                per_page=max_results * 3,  # Request more to filter later
                sort="cited_by_count:desc" if min_citations else "relevance_score:desc",
                min_citations=min_citations
            )
            
            search_time = (datetime.now() - search_start_time).total_seconds()
            self.logger.info(f"OpenAlex search completed in {search_time:.2f}s")
            
            if response.error:
                self.logger.error(f"OpenAlex API error: {response.error}")
                return {
                    'status': 'error',
                    'message': f'Error from OpenAlex API: {response.error}',
                    'original_query': query,
                    'structured_query': structured_query,
                    'results': [],
                    'metadata': {
                        'total_results': 0,
                        'processing_time': query_processing_time + search_time
                    }
                }
            
            # Process search results
            work_results = response.get_works()
            
            # Convert to LiteratureSearchResult objects
            literature_results = self._process_work_results(
                work_results,
                structured_query,
                publication_types,
                open_access_only
            )
            
            # Sort by relevance score and limit results
            literature_results.sort(key=lambda x: (x.relevance_score, x.citations), reverse=True)
            limited_results = literature_results[:max_results]
            
            # Perform research analysis if requested
            analysis_results = None
            synthesis = None
            methodology_analysis = None
            literature_summary = None
            
            if analyze_results and limited_results:
                analysis_start_time = datetime.now()
                
                # Convert to dictionary format for analyzer
                publications_for_analysis = [result.to_dict() for result in limited_results]
                
                # Analyze publications
                analyzed_publications = self.research_analyzer.analyze_publications(
                    publications=publications_for_analysis,
                    query_context=structured_query,
                    min_relevance=min_relevance,
                    max_publications=max_results
                )
                
                # Perform synthesis if we have enough analyzed publications
                if len(analyzed_publications) >= 2:
                    synthesis = self.research_analyzer.synthesize_analyses(
                        analyzed_results=analyzed_publications,
                        original_query=query
                    )
                    
                    methodology_analysis = self.research_analyzer.analyze_methodologies(
                        analyzed_results=analyzed_publications
                    )
                    
                    literature_summary = self.research_analyzer.generate_literature_summary(
                        analyzed_results=analyzed_publications,
                        synthesis=synthesis,
                        original_query=query
                    )
                
                # Add analysis to search results
                for result in limited_results:
                    for analyzed_pub in analyzed_publications:
                        if analyzed_pub['publication']['id'] == result.id:
                            result.analysis = analyzed_pub['analysis']
                            break
                
                analysis_time = (datetime.now() - analysis_start_time).total_seconds()
                self.logger.info(f"Research analysis completed in {analysis_time:.2f}s")
                
                analysis_results = {
                    'analyzed_publications': analyzed_publications,
                    'synthesis': synthesis,
                    'methodology_analysis': methodology_analysis,
                    'literature_summary': literature_summary
                }
            
            # Prepare result
            total_processing_time = (datetime.now() - query_start_time).total_seconds()
            result = {
                'status': 'success',
                'original_query': query,
                'structured_query': structured_query,
                'results': [result.to_dict() for result in limited_results],
                'metadata': {
                    'total_results': len(work_results),
                    'returned_results': len(limited_results),
                    'from_year': from_year,
                    'to_year': to_year,
                    'processing_time': total_processing_time
                }
            }
            
            # Add analysis results if available
            if analysis_results:
                result['analysis'] = analysis_results
            
            # Cache result
            self._add_to_cache(cache_key, result)
            
            return result
            
        except Exception as e:
            self.logger.error(f"Error in literature search: {str(e)}", exc_info=True)
            return {
                'status': 'error',
                'message': f'Error processing literature search: {str(e)}',
                'original_query': query,
                'results': [],
                'metadata': {
                    'total_results': 0,
                    'processing_time': -1
                }
            }
    
    def advanced_search(
        self,
        research_areas: List[str],
        specific_topics: List[str] = None,
        methodologies: List[str] = None,
        max_results: int = 10,
        from_year: Optional[int] = None,
        to_year: Optional[int] = None,
        analyze_results: bool = True
    ) -> Dict:
        """
        Perform an advanced search with explicit parameters instead of natural language query
        
        Args:
            research_areas: List of research areas or fields
            specific_topics: List of specific research topics
            methodologies: List of methodologies or techniques
            max_results: Maximum number of results to return
            from_year: Earliest publication year to include
            to_year: Latest publication year to include
            analyze_results: Whether to perform research analysis on results
            
        Returns:
            Dictionary containing search results and metadata
        """
        # Convert explicit parameters to structured query
        structured_query = {
            'research_areas': research_areas,
            'expertise': specific_topics or [],
            'search_keywords': methodologies or []
        }
        
        # Generate a natural language query for analysis purposes
        query_parts = []
        if research_areas:
            query_parts.append(f"Research in {', '.join(research_areas)}")
        if specific_topics:
            query_parts.append(f"focusing on {', '.join(specific_topics)}")
        if methodologies:
            query_parts.append(f"using {', '.join(methodologies)}")
        
        synthesized_query = " ".join(query_parts)
        
        # Delegate to the main search method
        return self.search(
            query=synthesized_query,
            max_results=max_results,
            from_year=from_year,
            to_year=to_year,
            analyze_results=analyze_results,
            min_relevance=0.0  # No minimum relevance since we're using explicit parameters
        )
    
    def get_publication_details(self, publication_id: str) -> Dict:
        """
        Get detailed information about a specific publication
        
        Args:
            publication_id: Identifier for the publication
            
        Returns:
            Dictionary with publication details
        """
        try:
            self.logger.info(f"Getting detailed information for publication {publication_id}")
            
            # If the ID doesn't have a proper prefix, check different formats
            if not (publication_id.startswith('W') or publication_id.startswith('https://openalex.org/')):
                # Try different possible formats
                possible_ids = [
                    publication_id,
                    f"W{publication_id}",
                    f"https://openalex.org/{publication_id}",
                    f"https://openalex.org/W{publication_id}"
                ]
                
                for possible_id in possible_ids:
                    response = self.openalex_client._make_request(f"works/{possible_id}")
                    if not response.error:
                        publication_id = possible_id
                        break
            
            # Get publication data
            response = self.openalex_client._make_request(f"works/{publication_id}")
            
            if response.error:
                self.logger.error(f"OpenAlex API error: {response.error}")
                return {
                    'status': 'error',
                    'message': f'Error retrieving publication details: {response.error}',
                    'publication_id': publication_id
                }
            
            # Extract publication data from response
            publication_data = response.data
            
            # Process publication data into a structured format
            publication = self._process_publication_data(publication_data)
            
            # Analyze the publication
            analysis = self.research_analyzer.analyze_publication(
                publication=publication.to_dict(),
                query_context={'research_areas': [], 'expertise': []}  # No specific query context
            )
            
            if analysis:
                analysis_dict = {
                    'primary_topics': analysis.primary_topics,
                    'key_findings': analysis.key_findings,
                    'methodology': analysis.methodology,
                    'practical_applications': analysis.practical_applications,
                    'technical_complexity': analysis.technical_complexity,
                    'citation_context': analysis.citation_context,
                    'knowledge_gaps': analysis.knowledge_gaps,
                    'temporal_context': analysis.temporal_context
                }
                publication.analysis = analysis_dict
            
            # Get related publications
            related_publications = self._get_related_publications(publication_data, max_related=3)
            
            return {
                'status': 'success',
                'publication': publication.to_dict(),
                'related_publications': related_publications
            }
            
        except Exception as e:
            self.logger.error(f"Error getting publication details: {str(e)}", exc_info=True)
            return {
                'status': 'error',
                'message': f'Error processing publication details: {str(e)}',
                'publication_id': publication_id
            }
    
    def interdisciplinary_search(
        self,
        primary_discipline: str,
        secondary_disciplines: List[str],
        max_results: int = 10,
        from_year: Optional[int] = None,
        recent_years: int = 5
    ) -> Dict:
        """
        Perform a specialized interdisciplinary search
        
        Args:
            primary_discipline: Main research discipline
            secondary_disciplines: Related disciplines to find intersections with
            max_results: Maximum number of results to return
            from_year: Earliest publication year to include
            recent_years: Number of recent years to include if from_year not specified
            
        Returns:
            Dictionary containing search results and metadata
        """
        try:
            self.logger.info(f"Performing interdisciplinary search for {primary_discipline} + {secondary_disciplines}")
            
            # Set default from_year if not provided
            if not from_year:
                from_year = datetime.now().year - recent_years
            
            to_year = datetime.now().year
            
            # Create a structured query
            structured_query = {
                'research_areas': [primary_discipline] + secondary_disciplines,
                'expertise': [],
                'search_keywords': []
            }
            
            # Create a specialized prompting approach for interdisciplinary search
            interdisciplinary_prompt = f"""
            Analyze research at the intersection of {primary_discipline} and {', '.join(secondary_disciplines)}.
            
            What keywords, methodologies, and research topics are found specifically at these intersections?
            
            YOU MUST PROVIDE YOUR RESPONSE AS A VALID JSON OBJECT with:
            - intersection_keywords: list of keywords specific to these disciplinary intersections
            - shared_methodologies: list of methodologies used across these disciplines
            - bridging_concepts: list of concepts that connect these fields
            - specialized_topics: list of research topics at these specific intersections
            
            Response (as JSON only):
            """
            
            # Get specialized interdisciplinary analysis
            response = self.query_processor.client.chat.completions.create(
                model="gpt-4o",
                messages=[{
                    "role": "user",
                    "content": interdisciplinary_prompt
                }],
                temperature=0.3,
                response_format={"type": "json_object"}
            )
            
            # Get response text
            analysis_text = response.choices[0].message.content
            
            # Parse the JSON response
            try:
                intersection_data = json.loads(analysis_text)
            except json.JSONDecodeError:
                # Try to extract JSON from text if direct parsing fails
                self.logger.warning("Failed to parse direct JSON response, attempting to extract JSON from text")
                intersection_data = self.query_processor.extract_json_from_text(analysis_text)
            
            # Enhance search terms with interdisciplinary insights
            intersection_keywords = intersection_data.get('intersection_keywords', [])
            bridging_concepts = intersection_data.get('bridging_concepts', [])
            
            # Add these to structured query
            structured_query['search_keywords'] = intersection_keywords + bridging_concepts
            
            # Execute the search
            combined_query = f"Research at the intersection of {primary_discipline} and {', '.join(secondary_disciplines)}"
            
            # Create specialized search query
            search_terms = []
            search_terms.append(f'"{primary_discipline}"')  # Primary discipline in quotes for exact match
            
            # Add secondary disciplines
            for discipline in secondary_disciplines:
                search_terms.append(f'"{discipline}"')  # Secondary disciplines in quotes
            
            # Add intersection keywords
            for keyword in intersection_keywords[:5]:  # Limit to top 5 to avoid dilution
                search_terms.append(keyword)
            
            # Join with AND operator
            search_query = " AND ".join(search_terms)
            
            # Execute search against OpenAlex
            response = self.openalex_client.search_works(
                query=search_query,
                from_year=from_year,
                to_year=to_year,
                per_page=max_results * 2,  # Request more to filter
                sort="relevance_score:desc"
            )
            
            if response.error:
                self.logger.error(f"OpenAlex API error: {response.error}")
                return {
                    'status': 'error',
                    'message': f'Error from OpenAlex API: {response.error}',
                    'query': combined_query,
                    'results': []
                }
            
            # Process work results
            work_results = response.get_works()
            
            # Convert to LiteratureSearchResult objects
            literature_results = self._process_work_results(
                work_results,
                structured_query
            )
            
            # Custom scoring for interdisciplinary relevance
            for result in literature_results:
                # Base score from standard processing
                base_score = result.relevance_score
                
                # Check for presence of primary discipline
                primary_present = primary_discipline.lower() in result.title.lower() or (result.abstract and primary_discipline.lower() in result.abstract.lower())
                
                # Count how many secondary disciplines are present
                secondary_count = sum(
                    1 for discipline in secondary_disciplines 
                    if discipline.lower() in result.title.lower() or (result.abstract and discipline.lower() in result.abstract.lower())
                )
                
                # Calculate interdisciplinary score
                if primary_present and secondary_count > 0:
                    # Boost based on coverage of disciplines
                    discipline_coverage = secondary_count / len(secondary_disciplines)
                    result.relevance_score = 0.5 + (0.3 * base_score) + (0.2 * discipline_coverage)
                else:
                    # Penalize if not covering both primary and at least one secondary
                    result.relevance_score = 0.3 * base_score
            
            # Sort by relevance score and limit results
            literature_results.sort(key=lambda x: x.relevance_score, reverse=True)
            limited_results = literature_results[:max_results]
            
            # Perform specialized analysis
            if limited_results:
                publications_for_analysis = [result.to_dict() for result in limited_results]
                
                analyzed_publications = self.research_analyzer.analyze_publications(
                    publications=publications_for_analysis,
                    query_context=structured_query,
                    min_relevance=0.3,  # Lower threshold for interdisciplinary work
                    max_publications=max_results
                )
                
                # Add analysis to search results
                for result in limited_results:
                    for analyzed_pub in analyzed_publications:
                        if analyzed_pub['publication']['id'] == result.id:
                            result.analysis = analyzed_pub['analysis']
                            break
                
                # Create interdisciplinary synthesis
                if len(analyzed_publications) >= 2:
                    interdisciplinary_synthesis = self._create_interdisciplinary_synthesis(
                        primary_discipline=primary_discipline,
                        secondary_disciplines=secondary_disciplines,
                        analyzed_publications=analyzed_publications,
                        intersection_data=intersection_data
                    )
                else:
                    interdisciplinary_synthesis = None
                
                return {
                    'status': 'success',
                    'primary_discipline': primary_discipline,
                    'secondary_disciplines': secondary_disciplines,
                    'interdisciplinary_analysis': intersection_data,
                    'results': [result.to_dict() for result in limited_results],
                    'interdisciplinary_synthesis': interdisciplinary_synthesis,
                    'query': combined_query
                }
            else:
                return {
                    'status': 'success',
                    'primary_discipline': primary_discipline,
                    'secondary_disciplines': secondary_disciplines,
                    'interdisciplinary_analysis': intersection_data,
                    'results': [],
                    'query': combined_query
                }
            
        except Exception as e:
            self.logger.error(f"Error in interdisciplinary search: {str(e)}", exc_info=True)
            return {
                'status': 'error',
                'message': f'Error processing interdisciplinary search: {str(e)}',
                'primary_discipline': primary_discipline,
                'secondary_disciplines': secondary_disciplines
            }
    
    def _process_work_results(
        self,
        work_results: List[Any],
        structured_query: Dict,
        publication_types: Optional[List[str]] = None,
        open_access_only: bool = False
    ) -> List[LiteratureSearchResult]:
        """
        Process work results from OpenAlex into structured literature results
        
        Args:
            work_results: Works from OpenAlex API
            structured_query: Structured query information
            publication_types: Types of publications to include
            open_access_only: Whether to include only open access publications
            
        Returns:
            List of LiteratureSearchResult objects
        """
        literature_results = []
        
        # Extract query terms for relevance scoring
        query_terms = set()
        for key in ['research_areas', 'expertise', 'search_keywords']:
            if key in structured_query:
                query_terms.update(term.lower() for term in structured_query[key])
        
        # Process each work
        for work in work_results:
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
            
            # Extract journal name
            journal = None  # This would come from work metadata in a real implementation
            
            # Create result
            result = LiteratureSearchResult(
                id=work.doi if work.doi else f"W{hash(work.title) & 0xffffffff}",
                title=work.title,
                authors=work.authors,
                publication_date=work.publication_date,
                journal=journal,
                abstract=work.abstract,
                doi=work.doi,
                citations=work.citations,
                open_access=is_open_access,
                type=work_type,
                topic_matches=topic_matches,
                relevance_score=relevance_score,
                url=f"https://doi.org/{work.doi}" if work.doi else None
            )
            
            literature_results.append(result)
        
        return literature_results
    
    def _process_publication_data(self, publication_data: Dict) -> LiteratureSearchResult:
        """
        Process detailed publication data from OpenAlex
        
        Args:
            publication_data: Raw publication data from OpenAlex
            
        Returns:
            LiteratureSearchResult object
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
        
        # Get DOI and URL
        doi = publication_data.get('doi')
        url = f"https://doi.org/{doi}" if doi else None
        
        return LiteratureSearchResult(
            id=publication_data.get('id', ''),
            title=publication_data.get('title', 'Untitled Publication'),
            abstract=publication_data.get('abstract', None),
            authors=authors,
            publication_date=publication_data.get('publication_date', None),
            journal=journal,
            citations=publication_data.get('cited_by_count', 0),
            doi=doi,
            open_access=is_open_access,
            type=pub_type,
            topic_matches=topic_matches,
            relevance_score=1.0,  # Default for direct lookups
            url=url
        )
    
    def _get_related_publications(
        self, 
        publication_data: Dict,
        max_related: int = 3
    ) -> List[Dict]:
        """
        Extract related publications from OpenAlex publication data
        
        Args:
            publication_data: Publication data from OpenAlex
            max_related: Maximum number of related publications to return
            
        Returns:
            List of related publication dictionaries
        """
        related_publications = []
        
        # In a real implementation, this would extract related publications
        # from the "related_works" field or make additional API calls
        
        # Simplified implementation for demonstration
        if 'related_works' in publication_data:
            for i, related_id in enumerate(publication_data['related_works']):
                if i >= max_related:
                    break
                    
                try:
                    response = self.openalex_client._make_request(f"works/{related_id}")
                    
                    if not response.error:
                        related_data = response.data
                        
                        related_publications.append({
                            'id': related_data.get('id', ''),
                            'title': related_data.get('title', 'Untitled Publication'),
                            'authors': [a.get('author', {}).get('display_name', '') 
                                        for a in related_data.get('authorships', [])[:3]],
                            'publication_date': related_data.get('publication_date', None),
                            'journal': related_data.get('primary_location', {}).get('source', {}).get('display_name', None)
                        })
                except Exception as e:
                    self.logger.error(f"Error fetching related publication: {str(e)}")
        
        return related_publications
    
    def _create_interdisciplinary_synthesis(
        self,
        primary_discipline: str,
        secondary_disciplines: List[str],
        analyzed_publications: List[Dict],
        intersection_data: Dict
    ) -> Dict:
        """
        Create a specialized synthesis for interdisciplinary results
        
        Args:
            primary_discipline: Primary research discipline
            secondary_disciplines: Secondary research disciplines
            analyzed_publications: List of analyzed publications
            intersection_data: Data about disciplinary intersections
            
        Returns:
            Dictionary containing interdisciplinary synthesis
        """
        try:
            # Extract key information from analyses
            methods_used = []
            findings = []
            topics = []
            
            for pub in analyzed_publications:
                analysis = pub['analysis']
                
                if 'methodology' in analysis:
                    methods_used.extend(analysis['methodology'])
                
                if 'key_findings' in analysis:
                    findings.extend(analysis['key_findings'])
                
                if 'primary_topics' in analysis:
                    topics.extend(analysis['primary_topics'])
            
            # Deduplicate
            methods_used = list(set(methods_used))
            findings = list(set(findings))
            topics = list(set(topics))
            
            # Create specialized synthesis prompt
            synthesis_prompt = f"""
            Create an interdisciplinary synthesis for research at the intersection of {primary_discipline} and {', '.join(secondary_disciplines)}.
            
            Consider these intersection keywords: {', '.join(intersection_data.get('intersection_keywords', []))}
            
            Methodologies observed: {', '.join(methods_used[:10])}
            
            Research topics observed: {', '.join(topics[:10])}
            
            Key findings observed: {', '.join(findings[:10])}
            
            YOU MUST PROVIDE YOUR RESPONSE AS A VALID JSON OBJECT with:
            - interdisciplinary_significance: description of why this intersection is important
            - conceptual_bridges: list of concepts that connect these disciplines
            - methodological_integration: explanation of how methods from different disciplines are combined
            - knowledge_gaps: list of areas needing further interdisciplinary research
            - future_directions: list of promising research avenues at this intersection
            
            Response (as JSON only):
            """
            
            # Get synthesis from LLM
            response = self.query_processor.client.chat.completions.create(
                model="gpt-4o",
                messages=[{
                    "role": "user",
                    "content": synthesis_prompt
                }],
                temperature=0.3,
                response_format={"type": "json_object"}
            )
            
            # Get response text
            synthesis_text = response.choices[0].message.content
            
            # Parse the JSON response
            try:
                synthesis_data = json.loads(synthesis_text)
            except json.JSONDecodeError:
                # Try to extract JSON from text if direct parsing fails
                self.logger.warning("Failed to parse direct JSON response, attempting to extract JSON from text")
                synthesis_data = self.query_processor.extract_json_from_text(synthesis_text)
            
            # Add metadata to synthesis
            synthesis_data['primary_discipline'] = primary_discipline
            synthesis_data['secondary_disciplines'] = secondary_disciplines
            synthesis_data['intersection_keywords'] = intersection_data.get('intersection_keywords', [])
            
            return synthesis_data
            
        except Exception as e:
            self.logger.error(f"Error creating interdisciplinary synthesis: {str(e)}")
            return {
                'error': str(e),
                'primary_discipline': primary_discipline,
                'secondary_disciplines': secondary_disciplines
            }
    
    def _extract_search_terms(self, structured_query: Dict) -> List[str]:
        """Extract and prioritize search terms from structured query"""
        search_terms = []
        
        # Add research areas (highest priority)
        if 'research_areas' in structured_query and structured_query['research_areas']:
            for area in structured_query['research_areas']:
                search_terms.append(area)
        
        # Add expertise areas
        if 'expertise' in structured_query and structured_query['expertise']:
            for expertise in structured_query['expertise']:
                search_terms.append(expertise)
        
        # Add search keywords
        if 'search_keywords' in structured_query and structured_query['search_keywords']:
            for keyword in structured_query['search_keywords']:
                search_terms.append(keyword)
        
        # Add expanded terms if available (lower priority)
        if 'expanded_terms' in structured_query:
            for original_term, expansions in structured_query['expanded_terms'].items():
                # Add a limited number of expanded terms to avoid query dilution
                for expansion in expansions[:2]:  # Only add top 2 expansions per term
                    search_terms.append(expansion)
        
        return search_terms
    
    def _calculate_relevance(
        self, 
        work: Any,
        query_terms: set
    ) -> tuple:
        """
        Calculate topic matches and relevance score
        
        Args:
            work: Work result from OpenAlex API
            query_terms: Set of query terms for matching
            
        Returns:
            Tuple of (topic_matches, relevance_score)
        """
        # Extract terms from title and abstract
        work_terms = self._extract_terms_from_work(work)
        
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
            
            # Include some citation weight in relevance
            citation_factor = min(1.0, (work.citations or 0) / 200)  # Scale citations
            relevance_score = 0.85 * relevance_score + 0.15 * citation_factor
        
        return topic_matches, relevance_score
    
    def _extract_terms_from_work(self, work: Any) -> set:
        """
        Extract meaningful terms from work title and abstract
        
        Args:
            work: Work result from OpenAlex API
            
        Returns:
            Set of extracted terms
        """
        terms = set()
        
        # Add title terms
        if work.title:
            terms.update(self._extract_terms(work.title))
        
        # Add abstract terms
        if work.abstract:
            terms.update(self._extract_terms(work.abstract))
        
        return terms
    
    def _extract_terms(self, text: str) -> set:
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
    
    def _determine_publication_type(self, work: Any) -> str:
        """
        Determine publication type from work metadata
        
        Args:
            work: Work result from OpenAlex API
            
        Returns:
            Publication type string
        """
        # Simplified implementation - in a real system, would use API metadata
        if not work.doi:
            return "preprint"
        
        # Additional logic would go here based on available metadata
        return "journal-article"
    
    def _determine_publication_type_from_data(self, publication_data: Dict) -> str:
        """
        Determine publication type from detailed publication data
        
        Args:
            publication_data: Publication data from OpenAlex
            
        Returns:
            Publication type string
        """
        # Check type field if available
        if 'type' in publication_data:
            type_value = publication_data.get('type')
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
        return "journal-article"  # Default
    
    def _extract_year_from_temporal_context(self, temporal_context: str) -> Optional[int]:
        """
        Extract a year value from temporal context phrase
        
        Args:
            temporal_context: String describing temporal context
            
        Returns:
            Year value or None
        """
        current_year = datetime.now().year
        
        # Look for "last X years" or "past X years" patterns
        import re
        last_years_match = re.search(r'(?:last|past|recent)\s+(\d+)\s+years?', temporal_context, re.IGNORECASE)
        if last_years_match:
            years_ago = int(last_years_match.group(1))
            return current_year - years_ago
        
        # Look for "since YYYY" pattern
        since_match = re.search(r'since\s+(\d{4})', temporal_context, re.IGNORECASE)
        if since_match:
            return int(since_match.group(1))
        
        # Look for specific year mentions
        year_match = re.search(r'\b(19\d{2}|20\d{2})\b', temporal_context)
        if year_match:
            return int(year_match.group(1))
        
        # Default to 5 years ago for "recent" and similar terms
        if any(term in temporal_context.lower() for term in ['recent', 'latest', 'current', 'new', 'modern']):
            return current_year - 5
        
        return None
    
    def _generate_cache_key(self, query: str, max_results: int, from_year: Optional[int],
                         to_year: Optional[int], min_citations: Optional[int],
                         publication_types: Optional[List[str]], open_access_only: bool) -> str:
        """Generate a cache key for a search query"""
        key_parts = [
            f"q={query}",
            f"max={max_results}",
            f"from={from_year or ''}",
            f"to={to_year or ''}",
            f"min_cite={min_citations or ''}",
            f"types={'-'.join(sorted(publication_types or []))}",
            f"oa={'yes' if open_access_only else 'no'}"
        ]
        
        return "|".join(key_parts)
    
    def _get_from_cache(self, cache_key: str) -> Optional[Dict]:
        """Get results from cache if available and not expired"""
        if cache_key in self.result_cache:
            cached_item = self.result_cache[cache_key]
            cached_time = cached_item.get('cached_at')
            
            if cached_time:
                # Check if cache is still valid
                cache_age = datetime.now() - datetime.fromisoformat(cached_time)
                if cache_age.total_seconds() < self.cache_duration * 3600:
                    return cached_item.get('result')
        
        return None
    
    def _add_to_cache(self, cache_key: str, result: Dict) -> None:
        """Add search result to cache"""
        cache_entry = {
            'result': result,
            'cached_at': datetime.now().isoformat()
        }
        
        self.result_cache[cache_key] = cache_entry
        
        # Simple cache size management (keep only the last 100 entries)
        if len(self.result_cache) > 100:
            # Remove oldest entries
            oldest_keys = sorted(
                self.result_cache.keys(),
                key=lambda k: datetime.fromisoformat(self.result_cache[k]['cached_at'])
            )[:10]  # Remove 10 oldest entries
            
            for key in oldest_keys:
                del self.result_cache[key]

def create_literature_searcher(openai_api_key: str, email_for_openalex: str) -> LiteratureSearcher:
    """Factory function to create a LiteratureSearcher instance"""
    return LiteratureSearcher(openai_api_key, email_for_openalex)