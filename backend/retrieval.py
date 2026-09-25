"""
Retrieval: recall candidates from OpenAlex, then rerank them against the
user's original request.

OpenAlex keyword search matches (nearly) every query term, so one long query
built from many extracted keywords returns few or no results. The pipeline
search strategies (see LiteratureSearcher) combine these steps instead:

  1. Recall, one of:
     - semantic (default): the user's whole request goes to OpenAlex's
       semantic (embedding) search, which matches meaning rather than words.
     - multi_query: each focused keyword query (2-6 terms) runs twice, in
       parallel: a full-text search sorted by relevance and a title/abstract
       search sorted by citations (a full-text search sorted by citations
       mostly returns famous papers that merely mention the terms). A semantic
       search can be added as one more channel.
     Result lists are merged with reciprocal rank fusion (RRF).
  2. Citation expansion (snowballing; on for semantic): foundational papers are
     often missing from the matches but cited by many of them. Papers cited by
     several of the top-ranked candidates are fetched in one request.
  3. Rerank: score each candidate's title + abstract against the request with a
     cross-encoder or an embedding model, blended with a citation prior.

Rerankers are selected with a spec string (see create_reranker):
  "none"                   keep the RRF order
  "embedding[:model]"      cosine similarity of embeddings (OpenAI-compatible API)
  "cross-encoder[:model]"  local cross-encoder via sentence-transformers
"""
import logging
import math
import re
import threading
import unicodedata
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, List, Optional, Sequence, Tuple

from openalex_client import OpenAlexClient, reconstruct_abstract

logger = logging.getLogger("retrieval")

RRF_K = 60
DOC_CHARS = 1200  # Title + abstract characters given to a reranker
DEFAULT_EMBEDDING_MODEL = "text-embedding-3-small"
# 22M parameters; as accurate as bge-reranker-v2-m3 (568M) on eval/ and 3x faster
DEFAULT_CROSS_ENCODER = "cross-encoder/ms-marco-MiniLM-L-6-v2"
BY_RELEVANCE = "relevance_score:desc"
BY_CITATIONS = "cited_by_count:desc"
# (sort, searched field) pairs run for every focused query
RECALL_SEARCHES = ((BY_RELEVANCE, "fulltext"), (BY_CITATIONS, "title_abstract"))
SEMANTIC_RESULTS = 50  # OpenAlex's maximum for semantic search


def title_key(title: Optional[str]) -> str:
    """
    Normalized title. OpenAlex often lists a preprint and its published
    version as separate works with the same title; this key merges them.
    """
    text = (title or "").replace("\\n", " ")  # Some OpenAlex titles contain a literal "\n"
    text = "".join(c for c in unicodedata.normalize("NFKD", text) if not unicodedata.combining(c))
    return " ".join(re.sub(r"[\W_]+", " ", text.lower()).split())


def paper_text(work: Dict, max_chars: int = DOC_CHARS) -> str:
    """Title and abstract of a raw OpenAlex work, as reranker input."""
    title = (work.get("title") or "").strip()
    abstract = reconstruct_abstract(work.get("abstract_inverted_index")) or ""
    text = f"{title}. {abstract}" if abstract else title
    return text[:max_chars]


# ---------------------------------------------------------------------------
# Stage 1: recall
# ---------------------------------------------------------------------------

def recall(
    client: OpenAlexClient,
    queries: Sequence[str],
    from_year: Optional[int] = None,
    to_year: Optional[int] = None,
    min_citations: Optional[int] = None,
    per_query: int = 25,
    searches: Sequence[Tuple[str, str]] = RECALL_SEARCHES,
    semantic_query: Optional[str] = None,
    max_workers: int = 6,
) -> List[Dict]:
    """
    Run every (query, sort, field) search in parallel and merge the results.
    field is "fulltext" (OpenAlex's default search) or "title_abstract".
    semantic_query, if given, adds one semantic search (e.g. the user's whole
    request); its results get the same year and citation filters.

    Returns unique raw OpenAlex works ordered by RRF score, each with an added
    "_rrf" field. Raises RuntimeError if every search failed.
    """
    queries = [q.strip() for q in dict.fromkeys(queries) if q and q.strip()]
    searches = [(q, sort, field) for q in queries for sort, field in searches]
    if semantic_query and semantic_query.strip():
        searches.append((semantic_query.strip(), None, "semantic"))
    if not searches:
        return []

    def run(search: Tuple[str, Optional[str], str]):
        query, sort, field = search
        if field == "semantic":
            return client.search_works(query=query, from_year=from_year, to_year=to_year,
                                       per_page=SEMANTIC_RESULTS, semantic=True)
        if field == "title_abstract":
            kwargs = {"query": "", "filter_string": f"title_and_abstract.search:{_filter_value(query)}"}
        else:
            kwargs = {"query": query}
        return client.search_works(from_year=from_year, to_year=to_year, min_citations=min_citations,
                                   sort=sort, per_page=per_query, **kwargs)

    with ThreadPoolExecutor(max_workers=min(max_workers, len(searches))) as pool:
        responses = list(pool.map(run, searches))

    errors = [r.error for r in responses if r.error]
    if len(errors) == len(responses):
        raise RuntimeError(f"All OpenAlex searches failed: {errors[0]}")

    lists = []
    for (query, sort, field), response in zip(searches, responses):
        if response.error:
            logger.warning(f"Search '{query}' ({sort}, {field}) failed: {response.error}")
            continue
        works = [w for w in (response.data or {}).get("results") or [] if w]
        if field == "semantic" and min_citations:  # Semantic search can't filter by citations
            works = [w for w in works if (w.get("cited_by_count") or 0) >= min_citations]
        lists.append(works)
    return fuse(lists)


def fuse(result_lists: Sequence[List[Dict]], base: Optional[List[Dict]] = None) -> List[Dict]:
    """
    Merge ranked lists of works with reciprocal rank fusion. Works with the
    same title (preprint + published version) are merged, keeping the first
    copy seen. `base` is an already fused list (with "_rrf" scores) to add the
    new lists to. Returns works ordered by RRF score, each with "_rrf".
    """
    works: Dict[str, Dict] = {}   # title key -> work
    scores: Dict[str, float] = {}
    for work in base or []:
        key = title_key(work.get("title"))
        if key:
            works.setdefault(key, work)
            scores[key] = scores.get(key, 0.0) + work.get("_rrf", 0.0)
    for results in result_lists:
        for rank, work in enumerate(results, start=1):
            key = title_key((work or {}).get("title"))
            if not key:
                continue
            works.setdefault(key, work)
            scores[key] = scores.get(key, 0.0) + 1.0 / (RRF_K + rank)

    ordered = sorted(works, key=lambda k: scores[k], reverse=True)
    return [{**works[k], "_rrf": scores[k]} for k in ordered]


def expand_by_citations(
    client: OpenAlexClient,
    ranked_works: List[Dict],
    top_n: int = 20,
    min_count: int = 2,
    max_new: int = 25,
    from_year: Optional[int] = None,
    to_year: Optional[int] = None,
    min_citations: Optional[int] = None,
) -> List[Dict]:
    """
    Fetch papers cited by at least `min_count` of the `top_n` best candidates
    (OpenAlex search results include each work's referenced_works), most
    co-cited first. Uses one OpenAlex request and applies the same filters as
    recall. Returns only works not already in `ranked_works`; on failure it
    logs a warning and returns [] so the search still succeeds.
    """
    known_ids = {w.get("id") for w in ranked_works}
    known_keys = {title_key(w.get("title")) for w in ranked_works}
    counts = Counter(ref for w in ranked_works[:top_n] for ref in set(w.get("referenced_works") or []))
    ids = [ref for ref, n in counts.most_common() if n >= min_count and ref not in known_ids][:max_new]
    if not ids:
        return []

    short_ids = [i.replace("https://openalex.org/", "") for i in ids]
    response = client.search_works(query="", filter_string="ids.openalex:" + "|".join(short_ids),
                                   from_year=from_year, to_year=to_year, min_citations=min_citations,
                                   per_page=len(short_ids))
    if response.error:
        logger.warning(f"Citation expansion failed: {response.error}")
        return []
    order = {i: n for n, i in enumerate(ids)}
    new = [w for w in (response.data or {}).get("results") or []
           if w and title_key(w.get("title")) and title_key(w.get("title")) not in known_keys]
    return sorted(new, key=lambda w: order.get(w.get("id"), len(order)))


def _filter_value(query: str) -> str:
    """OpenAlex filter values can't contain the filter syntax characters , | :"""
    return " ".join(re.sub(r"[,|:]", " ", query).split())


# ---------------------------------------------------------------------------
# Stage 2: rerank
# ---------------------------------------------------------------------------

class Reranker:
    """Scores documents against a query; higher is more relevant, in [0, 1]."""
    name = "none"

    def score(self, query: str, docs: List[str]) -> List[float]:
        raise NotImplementedError


class EmbeddingReranker(Reranker):
    """Cosine similarity between query and document embeddings."""

    def __init__(self, client, model: str = DEFAULT_EMBEDDING_MODEL, batch_size: int = 256):
        self.client = client  # OpenAI or OpenAI-compatible client
        self.model = model
        self.batch_size = batch_size
        self.name = f"embedding:{model}"

    def _embed(self, texts: List[str]) -> List[List[float]]:
        vectors = []
        for i in range(0, len(texts), self.batch_size):
            response = self.client.embeddings.create(model=self.model, input=texts[i:i + self.batch_size])
            vectors.extend(d.embedding for d in sorted(response.data, key=lambda d: d.index))
        return vectors

    def score(self, query: str, docs: List[str]) -> List[float]:
        if not docs:
            return []
        query_vec, *doc_vecs = self._embed([query] + docs)
        return [max(0.0, _cosine(query_vec, v)) for v in doc_vecs]


class CrossEncoderReranker(Reranker):
    """
    A cross-encoder reads the query and document together, which ranks more
    accurately than comparing separate embeddings. Runs locally; the model is
    downloaded from Hugging Face on first use.
    """

    def __init__(self, model: str = DEFAULT_CROSS_ENCODER, batch_size: int = 16, max_length: int = 512):
        self.model_name = model
        self.batch_size = batch_size
        self.max_length = max_length
        self.name = f"cross-encoder:{model}"
        self._model = None
        # The agent runs tool calls in parallel and Flask serves requests on threads, but a
        # model on a GPU (e.g. Apple's MPS) crashes the process if used by two threads at once
        self._lock = threading.Lock()

    def _load(self):
        if self._model is None:
            try:
                from sentence_transformers import CrossEncoder
            except ImportError as e:
                raise RuntimeError(
                    "The cross-encoder reranker needs sentence-transformers: pip install -r requirements.txt"
                ) from e
            logger.info(f"Loading cross-encoder {self.model_name}")
            self._model = CrossEncoder(self.model_name, max_length=self.max_length)
        return self._model

    def score(self, query: str, docs: List[str]) -> List[float]:
        if not docs:
            return []
        import torch
        with self._lock:
            # Some models output raw logits (e.g. ms-marco-MiniLM); a sigmoid maps every model into [0, 1]
            scores = self._load().predict([(query, d) for d in docs], batch_size=self.batch_size,
                                          activation_fn=torch.nn.Sigmoid(), show_progress_bar=False)
        return [float(s) for s in scores]


class MemoReranker(Reranker):
    """Remembers scores by document text, so reranking a grown pool only scores the new documents."""

    def __init__(self, inner: Reranker):
        self.inner = inner
        self.name = inner.name
        self._scores: Dict[Tuple[str, str], float] = {}

    def score(self, query: str, docs: List[str]) -> List[float]:
        todo = list(dict.fromkeys(d for d in docs if (query, d) not in self._scores))
        for doc, value in zip(todo, self.inner.score(query, todo) if todo else []):
            self._scores[(query, doc)] = value
        return [self._scores[(query, d)] for d in docs]


def create_reranker(spec: Optional[str], llm_client=None) -> Optional[Reranker]:
    """
    Build a reranker from a spec string such as "cross-encoder:BAAI/bge-reranker-base".
    Returns None for "none" (keep recall order).
    """
    spec = (spec or "none").strip()
    kind, _, model = spec.partition(":")
    if kind == "none":
        return None
    if kind == "embedding":
        if llm_client is None:
            raise ValueError("The embedding reranker needs an OpenAI-compatible client")
        return EmbeddingReranker(llm_client, model or DEFAULT_EMBEDDING_MODEL)
    if kind == "cross-encoder":
        return CrossEncoderReranker(model or DEFAULT_CROSS_ENCODER)
    raise ValueError(f"Unknown reranker '{spec}' (use none, embedding[:model] or cross-encoder[:model])")


def rerank(
    query: str,
    works: List[Dict],
    reranker: Optional[Reranker],
    top_k: Optional[int] = None,
    citation_weight: float = 0.0,
) -> List[Tuple[Dict, float]]:
    """
    Order works by relevance to `query`. Returns (work, score) pairs, best first,
    with scores in [0, 1].

    Without a reranker, works keep their recall (RRF) order and the score is
    the RRF score relative to the best candidate. citation_weight blends in a
    log-scaled citation prior: score = (1 - w) * relevance + w * prior.
    """
    if not works:
        return []
    if reranker is None:
        best = max(w.get("_rrf", 0.0) for w in works) or 1.0
        relevance = [w.get("_rrf", 0.0) / best for w in works]
    else:
        relevance = reranker.score(query, [paper_text(w) for w in works])

    if citation_weight:
        max_log = max(math.log1p(w.get("cited_by_count") or 0) for w in works) or 1.0
        prior = [math.log1p(w.get("cited_by_count") or 0) / max_log for w in works]
        relevance = [(1 - citation_weight) * r + citation_weight * p for r, p in zip(relevance, prior)]

    # Stable sort keeps recall order for ties
    ranked = sorted(zip(works, relevance), key=lambda pair: pair[1], reverse=True)
    return ranked[:top_k] if top_k else ranked


def _cosine(a: List[float], b: List[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm = math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b))
    return dot / norm if norm else 0.0
