import json
from types import SimpleNamespace

import pytest

import retrieval
from conftest import FakeOpenAlex, make_work
from literature_searcher import LiteratureSearcher
from openalex_client import OpenAlexResponse
from retrieval import (CrossEncoderReranker, EmbeddingReranker, MemoReranker, Reranker, create_reranker,
                       expand_by_citations, recall, rerank, title_key)
from tools import RERANK_POOL, ToolExecutor


class ListsOpenAlex:
    """Returns a different result list per (query, sort); records every call."""

    def __init__(self, lists, failing=()):
        self.lists = lists  # {(query, sort): [works]}
        self.failing = set(failing)
        self.calls = []

    def search_works(self, query="", **kwargs):
        self.calls.append({"query": query, **kwargs})
        prefix = "title_and_abstract.search:"
        if (kwargs.get("filter_string") or "").startswith(prefix):
            query = kwargs["filter_string"][len(prefix):]
        if query in self.failing:
            return OpenAlexResponse(500, {}, error="HTTP 500")
        return OpenAlexResponse(200, {"results": self.lists.get((query, kwargs.get("sort")), [])})


class ScoreByTitle(Reranker):
    """Fake reranker: score = position of the title's first word in a preference list."""
    name = "fake"

    def __init__(self, scores):
        self.scores = scores
        self.calls = []

    def score(self, query, docs):
        self.calls.append((query, docs))
        return [self.scores.get(d.split(".")[0], 0.0) for d in docs]


REL, CIT = retrieval.BY_RELEVANCE, retrieval.BY_CITATIONS


def test_title_key_merges_formatting_variants():
    assert title_key("Text-to-Text\\n Transformer") == title_key("Text‐to‐Text  Transformer") == "text to text transformer"
    assert title_key("Émergence") == "emergence"
    assert title_key("基于深度学习") == "基于深度学习"  # non-Latin titles are kept, not dropped
    assert title_key(None) == ""


def test_recall_fuses_lists_and_merges_duplicate_titles():
    a, b, c = make_work(1, "Alpha"), make_work(2, "Beta"), make_work(3, "Gamma")
    b_preprint = make_work(4, "BETA")
    client = ListsOpenAlex({
        ("q1", REL): [a, b],
        ("q1", CIT): [b_preprint, c],
        ("q2", REL): [b],
    })
    works = recall(client, ["q1", "q2", "q1", " "])

    assert len(client.calls) == 4  # duplicate and blank queries dropped; 2 queries x 2 sorts
    assert [w["title"] for w in works] == ["Beta", "Alpha", "Gamma"]  # Beta is in three lists
    assert works[0]["id"].endswith("W2")  # first copy kept
    assert works[0]["_rrf"] == pytest.approx(1 / 62 + 1 / 61 + 1 / 61)


def test_citation_sorted_recall_only_searches_titles_and_abstracts():
    client = ListsOpenAlex({})
    recall(client, ["graph nets, molecules: GNN|x"])
    by_sort = {c["sort"]: c for c in client.calls}
    assert by_sort[REL]["query"] == "graph nets, molecules: GNN|x"  # full-text search
    assert by_sort[CIT]["query"] == ""
    assert by_sort[CIT]["filter_string"] == "title_and_abstract.search:graph nets molecules GNN x"


def test_recall_passes_filters_to_every_search():
    client = ListsOpenAlex({})
    recall(client, ["q1", "q2"], from_year=2020, to_year=2023, min_citations=5, per_query=10)
    assert {c["sort"] for c in client.calls} == {REL, CIT}
    assert all(c["from_year"] == 2020 and c["to_year"] == 2023 and c["min_citations"] == 5
               and c["per_page"] == 10 for c in client.calls)


def test_recall_tolerates_partial_failure_but_not_total_failure():
    client = ListsOpenAlex({("ok", REL): [make_work(1)]}, failing={"bad"})
    assert len(recall(client, ["ok", "bad"])) == 1
    with pytest.raises(RuntimeError, match="All OpenAlex searches failed"):
        recall(ListsOpenAlex({}, failing={"bad"}), ["bad"])
    assert recall(client, []) == []


def cites(work, *refs):
    return {**work, "referenced_works": [f"https://openalex.org/W{r}" for r in refs]}


class IdsOpenAlex:
    """Answers ids.openalex filter requests from a dict of works."""

    def __init__(self, works, error=None):
        self.works = {w["id"].replace("https://openalex.org/", ""): w for w in works}
        self.error = error
        self.calls = []

    def search_works(self, query="", **kwargs):
        self.calls.append(kwargs)
        if self.error:
            return OpenAlexResponse(429, {}, error=self.error)
        ids = kwargs["filter_string"].removeprefix("ids.openalex:").split("|")
        return OpenAlexResponse(200, {"results": [self.works[i] for i in reversed(ids) if i in self.works]})


def test_citation_expansion_fetches_co_cited_papers():
    top = [cites(make_work(1, "A"), 90, 91, 92), cites(make_work(2, "B"), 90, 91, 3),
           cites(make_work(3, "C"), 90)]
    client = IdsOpenAlex([make_work(90, "Classic"), make_work(91, "Other classic")])
    new = expand_by_citations(client, top, min_count=2, from_year=2020)

    call = client.calls[0]
    assert set(call["filter_string"].removeprefix("ids.openalex:").split("|")) == {"W90", "W91"}  # W92 cited once, W3 known
    assert call["from_year"] == 2020 and call["per_page"] == 2
    assert [w["title"] for w in new] == ["Classic", "Other classic"]  # most co-cited first


def test_citation_expansion_skips_known_titles_and_survives_errors():
    top = [cites(make_work(1, "A"), 90), cites(make_work(2, "B"), 90)]
    assert expand_by_citations(IdsOpenAlex([make_work(90, "a")]), top) == []  # same title as W1
    assert expand_by_citations(IdsOpenAlex([], error="HTTP 429"), top) == []
    assert expand_by_citations(IdsOpenAlex([]), [make_work(1)]) == []  # nothing co-cited: no request


def test_memo_reranker_scores_each_document_once():
    inner = ScoreByTitle({"Alpha": 0.5, "Beta": 0.7})
    memo = MemoReranker(inner)
    assert memo.score("q", ["Alpha. x", "Beta. y"]) == [0.5, 0.7]
    assert memo.score("q", ["Beta. y", "Gamma. z", "Alpha. x"]) == [0.7, 0.0, 0.5]
    assert [docs for _, docs in inner.calls] == [["Alpha. x", "Beta. y"], ["Gamma. z"]]


def test_rerank_orders_by_reranker_score():
    works = [make_work(1, "Alpha"), make_work(2, "Beta"), make_work(3, "Gamma")]
    reranker = ScoreByTitle({"Alpha": 0.1, "Beta": 0.9, "Gamma": 0.5})
    ranked = rerank("query", works, reranker, top_k=2)
    assert [(w["title"], s) for w, s in ranked] == [("Beta", 0.9), ("Gamma", 0.5)]
    query, docs = reranker.calls[0]
    assert query == "query" and docs[0].startswith("Alpha. graph neural networks")  # title + abstract


def test_rerank_without_model_keeps_rrf_order_with_scores_in_unit_range():
    works = [{**make_work(1), "_rrf": 0.04}, {**make_work(2), "_rrf": 0.01}]
    assert [s for _, s in rerank("q", works, None)] == [1.0, 0.25]


def test_rerank_citation_prior():
    works = [make_work(1, "Alpha"), make_work(2, "Beta")]
    works[0]["cited_by_count"], works[1]["cited_by_count"] = 0, 1000
    ranked = rerank("q", works, ScoreByTitle({"Alpha": 0.6, "Beta": 0.5}), citation_weight=0.5)
    assert [w["title"] for w, _ in ranked] == ["Beta", "Alpha"]
    assert ranked[0][1] == pytest.approx(0.5 * 0.5 + 0.5 * 1.0)


def test_create_reranker_specs():
    assert create_reranker("none") is None and create_reranker(None) is None
    ce = create_reranker("cross-encoder:org/model")
    assert isinstance(ce, CrossEncoderReranker) and ce.model_name == "org/model" and ce._model is None  # lazy
    assert create_reranker("cross-encoder").model_name == retrieval.DEFAULT_CROSS_ENCODER
    assert create_reranker("embedding", llm_client=object()).model == retrieval.DEFAULT_EMBEDDING_MODEL
    with pytest.raises(ValueError):
        create_reranker("embedding")
    with pytest.raises(ValueError):
        create_reranker("bm25")


def test_embedding_reranker_cosine():
    vectors = {"query": [1.0, 0.0], "same": [2.0, 0.0], "orthogonal": [0.0, 1.0], "opposite": [-1.0, 0.0]}

    class FakeEmbeddings:
        def create(self, model, input):
            data = [SimpleNamespace(index=i, embedding=vectors[t]) for i, t in enumerate(input)]
            return SimpleNamespace(data=list(reversed(data)))  # API order isn't guaranteed

    reranker = EmbeddingReranker(SimpleNamespace(embeddings=FakeEmbeddings()), batch_size=2)
    assert reranker.score("query", ["same", "orthogonal", "opposite"]) == pytest.approx([1.0, 0.0, 0.0])


# -- LiteratureSearcher ------------------------------------------------------

STRUCTURED = {
    "research_areas": ["Chemistry"],
    "expertise": ["graph neural networks", "molecular property prediction"],
    "search_keywords": ["GNN"],
    "search_queries": ["graph neural networks molecules", "molecular property prediction"],
}


def make_searcher(openalex, strategy="multi_query", reranker=None, structured=None):
    searcher = LiteratureSearcher("test-key", "test@example.com", retrieval_strategy=strategy, reranker=reranker)
    searcher.openalex_client = openalex
    searcher.query_processor.process_query = lambda q: dict(structured or STRUCTURED)
    return searcher


def test_multi_query_search_reranks_candidates():
    works = [make_work(1, "Alpha"), make_work(2, "Beta"), make_work(3, "Gamma")]
    openalex = FakeOpenAlex(works)
    reranker = ScoreByTitle({"Alpha": 0.2, "Beta": 0.9, "Gamma": 0.6})
    result = make_searcher(openalex, reranker=reranker).search("GNNs for molecules", max_results=2)

    assert result["status"] == "success"
    assert [r["title"] for r in result["results"]] == ["Beta", "Gamma"]
    assert [r["relevance_score"] for r in result["results"]] == [0.9, 0.6]
    assert result["metadata"]["total_results"] == 3
    assert {c["query"] for c in openalex.calls if c["query"]} == set(STRUCTURED["search_queries"])
    assert reranker.calls[0][0] == "GNNs for molecules"  # reranked against the user's own words


def test_multi_query_citation_expansion_merges_cited_papers():
    works = [cites(make_work(1, "Alpha"), 90), cites(make_work(2, "Beta"), 90)]
    openalex = FakeOpenAlex(works)
    classic = make_work(90, "Classic")
    openalex.search_works = lambda query="", **kw: OpenAlexResponse(
        200, {"results": [classic] if "ids.openalex" in (kw.get("filter_string") or "") else works})
    reranker = ScoreByTitle({"Alpha": 0.5, "Beta": 0.4, "Classic": 0.9})
    searcher = make_searcher(openalex, reranker=reranker)
    searcher.citation_expansion = True
    result = searcher.search("q", max_results=2)

    assert [r["title"] for r in result["results"]] == ["Classic", "Alpha"]
    assert len(reranker.calls) == 2 and reranker.calls[1][1] == ["Classic. graph neural networks predict molecular properties"]


def test_multi_query_search_filters_before_reranking():
    works = [make_work(1, "Alpha"), make_work(2, "Beta")]
    works[1]["open_access"] = {"is_oa": False}
    reranker = ScoreByTitle({"Alpha": 0.1, "Beta": 0.9})
    result = make_searcher(FakeOpenAlex(works), reranker=reranker).search("q", open_access_only=True)
    assert [r["title"] for r in result["results"]] == ["Alpha"]


def test_multi_query_falls_back_to_extracted_topics():
    openalex = FakeOpenAlex()
    structured = {**STRUCTURED, "search_queries": []}
    make_searcher(openalex, structured=structured).search("q")
    assert {c["query"] for c in openalex.calls if c["query"]} == {"graph neural networks", "molecular property prediction",
                                                     "Chemistry"}


def test_multi_query_reports_openalex_failure():
    openalex = FakeOpenAlex()
    openalex.search_works = lambda query="", **kw: OpenAlexResponse(503, {}, error="HTTP 503")
    result = make_searcher(openalex).search("q")
    assert result["status"] == "error" and result["http_status"] == 502 and "HTTP 503" in result["message"]


def test_single_query_strategy_is_the_original_pipeline():
    openalex = FakeOpenAlex()
    result = make_searcher(openalex, strategy="single_query").search("q", max_results=2)
    assert result["status"] == "success" and len(result["results"]) == 2
    assert len(openalex.calls) == 1
    assert openalex.calls[0]["query"].startswith("Chemistry graph neural networks molecular property prediction GNN")


def test_unknown_strategy_rejected():
    with pytest.raises(ValueError):
        LiteratureSearcher("k", "e@example.com", retrieval_strategy="bm25")


# -- search_papers tool --------------------------------------------------------

def search_args(**overrides):
    args = {"query": "gnn", "from_year": None, "to_year": None, "min_citations": None,
            "sort": "relevance", "limit": 2}
    return json.dumps({**args, **overrides})


def test_search_papers_reranks_a_larger_pool():
    works = [make_work(1, "Alpha"), make_work(2, "Beta"), make_work(3, "Gamma")]
    openalex = FakeOpenAlex(works)
    reranker = ScoreByTitle({"Alpha": 0.1, "Beta": 0.5, "Gamma": 0.9})
    result = ToolExecutor(openalex, reranker=reranker).execute("search_papers", search_args())

    assert openalex.calls[0]["per_page"] == RERANK_POOL
    assert [p["title"] for p in result["papers"]] == ["Gamma", "Beta"]
    assert reranker.calls[0][0] == "gnn"


def test_search_papers_only_reranks_relevance_sort():
    openalex = FakeOpenAlex([make_work(1, "Alpha"), make_work(2, "Beta")])
    reranker = ScoreByTitle({"Alpha": 0.1, "Beta": 0.9})
    result = ToolExecutor(openalex, reranker=reranker).execute("search_papers", search_args(sort="citations"))
    assert openalex.calls[0]["per_page"] == 2 and not reranker.calls
    assert [p["title"] for p in result["papers"]] == ["Alpha", "Beta"]


def test_search_papers_only_grounds_papers_it_returned():
    works = [make_work(i, f"Paper {i}") for i in range(1, 6)]
    reranker = ScoreByTitle({f"Paper {i}": i / 10 for i in range(1, 6)})
    ex = ToolExecutor(FakeOpenAlex(works), reranker=reranker)
    result = ex.execute("search_papers", search_args(limit=2))
    assert [p["paper_id"] for p in result["papers"]] == ["W5", "W4"]
    assert set(ex.seen_papers) == {"W5", "W4"}  # the other three were never shown to the model


# -- semantic recall -----------------------------------------------------------

def test_client_semantic_search_params():
    from openalex_client import OpenAlexClient
    client = OpenAlexClient("test@example.com")
    captured = {}
    client._make_request = lambda endpoint, params=None, method="GET": captured.update(params) or None
    client.search_works("a long request " * 200, from_year=2020, min_citations=5, sort=CIT,
                        per_page=100, semantic=True)
    assert len(captured["search.semantic"]) == 2000 and "search" not in captured
    assert captured["per-page"] == 50 and "sort" not in captured
    assert captured["filter"] == "publication_year:2020-"  # no citation filter: unsupported


def test_recall_adds_semantic_channel_and_filters_citations():
    low, high = make_work(1, "Low"), make_work(2, "High")
    low["cited_by_count"], high["cited_by_count"] = 3, 50
    client = ListsOpenAlex({("q1", REL): [make_work(3, "Keyword")]})
    original = client.search_works

    def search_works(query="", semantic=False, **kwargs):
        if semantic:
            client.calls.append({"query": query, "semantic": True, **kwargs})
            return OpenAlexResponse(200, {"results": [low, high]})
        return original(query, **kwargs)
    client.search_works = search_works

    works = recall(client, ["q1"], min_citations=10, from_year=2021, semantic_query="the whole request")
    semantic_call = [c for c in client.calls if c.get("semantic")][0]
    assert semantic_call["query"] == "the whole request" and semantic_call["from_year"] == 2021
    assert {w["title"] for w in works} == {"Keyword", "High"}  # "Low" is under min_citations


def test_fuse_adds_lists_to_an_existing_pool():
    a, b = make_work(1, "Alpha"), make_work(2, "Beta")
    base = retrieval.fuse([[a, b]])
    fused = retrieval.fuse([[make_work(9, "BETA"), make_work(3, "Gamma")]], base=base)
    assert [w["title"] for w in fused] == ["Beta", "Alpha", "Gamma"]
    assert fused[0]["_rrf"] == pytest.approx(1 / 62 + 1 / 61)


def test_searcher_sends_the_request_to_semantic_search_when_enabled():
    openalex = FakeOpenAlex()
    semantic_queries = []
    original = openalex.search_works

    def search_works(query="", semantic=False, **kwargs):
        if semantic:
            semantic_queries.append(query)
        return original(query, **kwargs)
    openalex.search_works = search_works

    make_searcher(openalex).search("GNNs for molecules")
    assert semantic_queries == []
    searcher = make_searcher(openalex)
    searcher.semantic_recall = True
    searcher.search("GNNs for molecules")
    assert semantic_queries == ["GNNs for molecules"]


# -- semantic strategy ---------------------------------------------------------

def test_semantic_strategy_searches_by_meaning_then_expands():
    top = [cites(make_work(i, f"Recent {i}"), 90) for i in (1, 2)]
    classic = make_work(90, "Classic")
    calls = []

    class SemanticOpenAlex:
        def search_works(self, query="", semantic=False, **kwargs):
            calls.append({"query": query, "semantic": semantic, **kwargs})
            if semantic:
                return OpenAlexResponse(200, {"results": top})
            if "ids.openalex" in (kwargs.get("filter_string") or ""):
                return OpenAlexResponse(200, {"results": [classic]})
            return OpenAlexResponse(200, {"results": [make_work(50, "Keyword hit")]})

    reranker = ScoreByTitle({"Recent 1": 0.9, "Recent 2": 0.8, "Classic": 0.7})
    searcher = make_searcher(SemanticOpenAlex(), strategy="semantic", reranker=reranker)
    searcher.citation_expansion = True
    result = searcher.search("diffusion models for image generation", max_results=5)

    assert [c["semantic"] for c in calls] == [True, False]  # one semantic search, one expansion request
    assert calls[0]["query"] == "diffusion models for image generation"
    assert {r["title"] for r in result["results"]} == {"Recent 1", "Recent 2", "Classic"}
    assert result["metadata"]["recall"] == {"strategy": "semantic", "queries": [],
                                            "semantic_query": "diffusion models for image generation",
                                            "citation_expansion": True}


def test_multi_query_reports_its_keyword_queries():
    result = make_searcher(FakeOpenAlex(), strategy="multi_query").search("q")
    plan = result["metadata"]["recall"]
    assert plan["strategy"] == "multi_query" and plan["queries"] == STRUCTURED["search_queries"]
    assert plan["semantic_query"] is None and plan["citation_expansion"] is False


def test_factory_uses_strategy_defaults(monkeypatch):
    from literature_searcher import STRATEGY_DEFAULTS, create_literature_searcher
    monkeypatch.setattr("literature_searcher.create_reranker", lambda spec, llm_client=None: None)
    semantic = create_literature_searcher("k", "e@example.com")
    assert semantic.retrieval_strategy == "semantic"
    assert semantic.citation_weight == STRATEGY_DEFAULTS["semantic"]["citation_weight"] == 0.2
    assert semantic.citation_expansion is True
    keyword = create_literature_searcher("k", "e@example.com", retrieval_strategy="multi_query", citation_weight=0.3)
    assert keyword.citation_weight == 0.3 and keyword.citation_expansion is False
