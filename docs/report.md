# LitFinder: Evaluating and Improving LLM-Powered Literature Search

**English** | [简体中文](report.zh-CN.md)

*Technical report, September 2026. It covers the work in pull requests #1-#14. Every number comes from the benchmark in [`eval/`](../eval/), and can be recomputed from the committed runs and labels with `python eval/run_eval.py --score-only`.*

## Summary

LitFinder finds academic papers for a research request written in plain language, using the [OpenAlex](https://openalex.org) catalog of 300M+ works. This report measures how well different retrieval designs work and explains the choices behind the current defaults.

- **The original pipeline often found little.** It joined every term an LLM extracted into one 50+ word keyword query. OpenAlex requires nearly every term to match, so a request like "speculative decoding for LLM inference" returned no papers, and only 1 of 159 hand-picked foundational papers was found.
- **Reranking brought the biggest gain.** Short focused queries plus a 22M-parameter cross-encoder raised nDCG@10 from **0.55 to 0.92** (p < 0.001). The cross-encoder was as good as one 25 times larger.
- **Topical relevance and foundational papers trade off.** The better a design matches the topic, the more it crowds out older landmark papers whose wording differs from the request. A small citation prior and citation expansion recover most of them.
- **The current default is OpenAlex semantic search, plus citation expansion, plus the reranker.**
  - nDCG@10 of **0.947**, which beats the tuned keyword pipeline (p = 0.02).
  - Foundational-paper recall is similar to the keyword pipeline's.
  - It needs **2 OpenAlex requests per search instead of 10**; the cost per search drops from about US$0.015 to about US$0.0014.
- **Cheap LLMs are enough where the LLM does little.** gpt-4o-mini matches gpt-4o for query analysis at 1/16 of the cost.
- **Testing cheap models exposed a tool-design bug in the agent.** After fixing it, the gpt-4o-mini agent went from 0.20 to 0.56 nDCG@10.
- **gpt-4o-mini is now the agent's default.** Over two runs it matches gpt-4o (nDCG@10 0.567 vs 0.577, p = 0.62), and its reasons are as faithful to the papers' abstracts (94% vs 95% fully supported), at 1/11 of the cost. The one error all three models made, reversing a paper's finding, came from the search tool cutting abstracts at 600 characters; longer abstracts, a grounding prompt and a title check removed it at no loss in relevance.
- **The evaluation work also surfaced production bugs.** Two missing request timeouts could hang a search for hours, a reranker crashed under concurrent calls, and the OpenAlex client froze for five hours when its billing budget ran out.

| | nDCG@10 | Canonical R@20 | Latency | Cost per search |
|---|---|---|---|---|
| Original pipeline | 0.550 | 0.006 | 4.5 s | ~US$0.006 |
| **Current default** | **0.949** | **0.347** | **4.7 s** | **~US$0.0014** |

## 1. The system

LitFinder has three ways to search:

- **Pipeline search** (`POST /api/search`). An LLM reads the request, the backend retrieves candidates from OpenAlex, and a reranker orders them. This is the path this report optimizes.
- **Agent search** (`POST /api/agent-search`). An LLM plans the search itself through function calling, with four tools: `search_papers`, `get_paper`, `search_authors` and `get_author_papers`. It returns ranked papers with a reason for each, and it can only cite IDs that a tool actually returned.
- **MCP server.** The same four tools are exposed over the Model Context Protocol for hosts such as Claude Code and Claude Desktop.

The work went in stages, each measured before and after:

| Stage | What changed | PRs |
|---|---|---|
| 1 | Local setup; data-quality fixes | #1, #2 |
| 2 | Agent search (function calling) and Structured Outputs | #3 |
| 3 | MCP server | #4, #5 |
| 4 | Focused keyword queries + cross-encoder reranking; the benchmark | #6 |
| 5 | Frontend redesign; Docker | #7, #8 |
| 6 | OpenAlex semantic search + citation expansion becomes the default | #9 |
| 7 | gpt-4o-mini for query analysis; agent search-tool fix; LLM timeouts | #10, #11 |

## 2. How the evaluation works

**Queries.** There are 32 natural-language research requests (`eval/queries.jsonl`). About two thirds are machine-learning topics; the rest come from biology, medicine, materials science, climate and social science. One request carries a date constraint ("published since 2023").

**Canonical papers.** Each query has 4-5 foundational papers picked by hand, 159 in total, such as DDPM for diffusion models or FedAvg for federated learning. Each paper was looked up in OpenAlex, and every copy was recorded, since preprint and published versions are often separate records. The canonical papers give a judge-free check of whether a system finds the classics.

**Relevance labels.** Every paper that any system returned in its top 20 was labelled (pooling, as in TREC):

- **Judge:** `gpt-4.1` at temperature 0, which is not the model under test.
- **Input:** the title and abstract of each paper, one pair per call.
- **Grades:** 2 = highly relevant, 1 = partially relevant, 0 = not relevant.
- **Size:** 3,994 labels in total: 2,524 highly relevant, 912 partially relevant and 558 not relevant.

**Metrics:**

- **nDCG@10:** graded ranking quality of the top 10.
- **Recall@20:** the share of all highly relevant papers found for the query that appear in the top 20. The denominator grows as more systems are labelled, so compare Recall@20 only within one results table.
- **Canonical R@20:** the share of the hand-picked papers in the top 20.

Significance comes from a paired randomization test over the 32 queries (10,000 permutations).

**Fair comparisons.** Systems that differ in one stage share the cached output of every other stage. For example, all reranker variants rerank the same cached candidate pool, and all pipeline variants share one LLM analysis per query unless the LLM itself is what's being compared.

**Checking the judge.**

- **Canonical papers:** of the 159, the judge graded 147 highly relevant, 11 partially relevant and 1 not relevant.
- **Cheaper judges:** all labels were re-graded with cheaper models and compared with the gpt-4.1 labels.

| Judge | Exact agreement | Weighted κ | Rank correlation of systems (Kendall τ, nDCG@10) |
|---|---|---|---|
| gpt-4.1-mini | 85% | 0.86 | 0.84 |
| gpt-4.1-nano | 66% | 0.71 | 0.82 |

gpt-4.1-mini leaves every conclusion in this report unchanged at about 1/5 of the labelling cost. gpt-4.1-nano grades too strictly: it downgraded 591 of the papers gpt-4.1 rated highly relevant.

## 3. Results

The full table of 31 systems is in [`eval/results.md`](../eval/results.md).

### 3.1 Why the original pipeline failed

The original design asked an LLM for research areas, topics, keywords and expansions, then joined all of them into a single OpenAlex query. OpenAlex keyword search behaves close to "every term must match", so these long queries matched few papers, sometimes none. The remaining results were ranked by a term-overlap heuristic; in the queries inspected by hand, it scored almost every result between 0.94 and 1.00, so it barely ranked them.

The result was nDCG@10 0.550 and canonical recall 0.006. Five queries returned fewer than 10 papers, one of them none at all.

### 3.2 Focused queries and reranking

The first redesign asks the LLM for 3-5 short queries of 2-6 terms. Each query runs as a full-text search sorted by relevance and as a search sorted by citations. The results (about 180 unique candidates) are merged with reciprocal rank fusion and reranked against the user's original request.

| Reranker (same candidate pool) | nDCG@10 | Latency |
|---|---|---|
| None (fusion order only) | 0.731 | 5.5 s |
| OpenAI `text-embedding-3-small` | 0.932 | 6.6 s |
| `ms-marco-MiniLM-L-6-v2` cross-encoder (22M) | 0.924 | 6.1 s |
| `bge-reranker-base` (278M) | 0.907 | 9.3 s |
| `bge-reranker-v2-m3` (568M) | 0.942 | 18.0 s |

Focused queries alone help (0.55 → 0.73), but reranking is where the gain is (→ 0.92, p < 0.001). The rerankers are close to one another: MiniLM vs bge-v2-m3 gives p = 0.27, and MiniLM vs embeddings gives p = 0.61. MiniLM runs locally, needs no API call and is three times faster than bge-v2-m3, so it became the default.

### 3.3 The trade-off: topical relevance vs foundational papers

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="figures/tradeoff-dark.svg">
  <img alt="Scatter plot of nDCG@10 against canonical recall@20 for each system. The original pipeline sits at the bottom left. Keyword and semantic pipelines with a reranker sit near the top; semantic search alone is high on nDCG but low on canonical recall. The default is at nDCG 0.95 and canonical recall 0.34. Agent variants sit around nDCG 0.53-0.60." src="figures/tradeoff-light.svg">
</picture>

Two experiments on the keyword pipeline showed the same pattern.

**1. Citation-sorted searches on titles and abstracts only.** In the first version, the searches sorted by citations matched full text. They returned famous papers that merely mention the terms, such as the R language and AlphaFold for a diffusion-models query. Matching titles and abstracts instead raised Recall@20 (0.206 → 0.225, p = 0.021) but *lowered* canonical recall (0.347 → 0.234, p = 0.003). Off-topic famous papers were easy for the reranker to discard. Recent papers whose titles closely match the query were not, and they pushed out older classics whose wording differs, such as "Denoising Diffusion Probabilistic Models" for "diffusion models for high-quality image generation".

**2. A citation prior.** A citation prior blends a log-scaled citation count into the final score:

| Citation prior weight | nDCG@10 | Canonical R@20 |
|---|---|---|
| 0 | 0.924 | 0.234 |
| 0.1 | 0.893 | 0.391 |
| 0.2 | 0.875 | 0.411 |
| 0.3 | 0.855 | 0.411 |

At 0.1, canonical recall rises by 16 points (p = 0.001), while the nDCG change is not significant (p = 0.14). Above 0.1, nDCG keeps falling but canonical recall stops improving.

**Citation expansion made no difference here.** It adds papers that several of the top candidates cite (nDCG unchanged, p = 0.25 on canonical recall), because the keyword pool already contained most classics that the reranker could rank.

### 3.4 Semantic search

In February 2026 OpenAlex added semantic search: every work's title and abstract is embedded (GTE-Large, 1,024 dimensions), and a query matches by meaning. It returns at most 50 results per request.

| Recall design (all with MiniLM) | nDCG@10 | Recall@20 | Canonical R@20 | OpenAlex requests |
|---|---|---|---|---|
| Keyword queries + 10% prior | 0.893 | 0.212 | 0.391 | 10 |
| … + a semantic channel | 0.898 | 0.219 | 0.397 | 11 |
| Semantic search alone (OpenAlex's order, no reranker) | 0.950 | 0.244 | 0.106 | 1 |
| Semantic search + 10% prior | 0.969 | 0.246 | 0.106 | 1 |
| Semantic search + citation expansion + 10% prior | 0.956 | 0.244 | 0.309 | 2 |
| **Semantic search + citation expansion + 20% prior (default)** | **0.947** | **0.244** | **0.341** | **2** |

Semantic search is the extreme end of the trade-off. It is the most topically relevant design measured, with nDCG@10 0.95 without any reranking, but only 19 of the 159 canonical papers appear anywhere in its results. Citation expansion fixes exactly this: the recent matches cite the classics, so fetching the papers they cite most often brings canonical recall from 0.11 back to 0.31 (p < 0.001), and a 20% prior brings it to 0.34.

Compared with the keyword pipeline with a semantic channel, the default is better on:

- **nDCG@10:** 0.947 vs 0.898, p = 0.02.
- **Recall@20:** p < 0.001.
- **Latency:** 1.5 s faster.
- **Cost:** a tenth of the OpenAlex requests.

Canonical recall is 0.34 vs 0.40, a difference that is not significant (p = 0.36).

### 3.5 Choosing the LLM for query analysis

With semantic recall, the LLM no longer writes search queries; it only extracts constraints such as a date range.

| Query analysis model | nDCG@10 | Canonical R@20 | LLM cost per search |
|---|---|---|---|
| gpt-4o | 0.947 | 0.341 | ~US$0.0046 (estimated) |
| gpt-4.1-mini | 0.949 | 0.347 | US$0.00077 |
| **gpt-4o-mini (default)** | **0.949** | **0.347** | **US$0.00028** |

All three models read "since 2023" correctly, and retrieval is identical within noise (p = 0.50). gpt-4o-mini became the default for this step (`QUERY_LLM_MODEL`).

### 3.6 Agent search

The agent plans every search, so the model matters much more there. The first runs with cheaper models looked like this:

| Agent model | nDCG@10 |
|---|---|
| gpt-4o | 0.625 |
| gpt-4.1-mini | 0.515 |
| gpt-4o-mini | 0.200 |

The traces explained the gpt-4o-mini result:

- **Unrequested filters.** It added date and citation filters nobody asked for, and sorted by "recent".
- **A full-text search behind non-relevance sorts.** The tool's date and citation sorts searched full text, which is the same trap as in §3.3. It returned the newest papers that mention the terms, such as brand design and battery materials for a diffusion-models query.
- **Invented reasons.** The model then wrote plausible reasons for those papers.

The fix has two parts:

- **Tool.** Date- and citation-sorted searches match titles and abstracts only.
- **Prompt.** It forbids unrequested filters and off-topic picks, and requires reasons grounded in the abstract.

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="figures/agent-fix-dark.svg">
  <img alt="Dumbbell chart of agent nDCG@10 before and after the search-tool fix: gpt-4o 0.63 to 0.60, gpt-4.1-mini 0.51 to 0.53, gpt-4o-mini 0.20 to 0.56." src="figures/agent-fix-light.svg">
</picture>

| Agent model (after the fix) | nDCG@10 | Canonical R@20 | LLM cost per search | Latency |
|---|---|---|---|---|
| gpt-4o | 0.604 | 0.269 | US$0.027 | 12.2 s |
| gpt-4.1-mini | 0.532 | 0.206 | US$0.0050 | 5.6 s |
| gpt-4o-mini (now the default, §3.7) | 0.557 | 0.269 | US$0.0021 | 6.3 s |

What the fixed runs show:

- **gpt-4o-mini recovered.** It went from 0.20 to 0.56 (p < 0.001), and is now within noise of gpt-4o (p = 0.085) at 1/13 of the cost.
- **The other two models were unaffected** within noise (p ≈ 0.5).
- **gpt-4.1-mini is the weakest agent** and is significantly worse than gpt-4o (p = 0.011), even though it matches gpt-4o-mini at query analysis.

**The agent scores below the pipeline** (0.60 vs 0.95 nDCG@10). This is partly by design: it recommends about 5 papers after about 2 tool calls, while nDCG@10 rewards a full top 10. Its strengths are explanations, researcher recommendations and multi-part questions, which nDCG does not measure. §3.7 checks the explanations.

### 3.7 Are the agent's reasons faithful?

Each paper the agent recommends comes with a one-sentence reason. A wrong reason can mislead more than a missing paper, because users may trust it without reading the paper. To check them, the three fixed agents were run a second time with their reasons saved, and gpt-4.1 compared every reason with the paper's title and abstract ([`eval/faithfulness.py`](../eval/faithfulness.py)):

- **Supported:** every claim about the paper is stated in or directly implied by the title or abstract.
- **Partially supported:** the main claim holds, but the reason adds a detail the abstract doesn't mention or overstates something.
- **Unsupported:** a key claim is missing from the abstract or contradicts it.

Whether the paper fits the request is not judged here; nDCG already measures that. Papers whose OpenAlex record has no abstract, or only a one-line teaser under 100 characters, can't be checked and are counted separately.

| Agent model | Reasons checked | Supported | Partially supported | Unsupported | No usable abstract |
|---|---|---|---|---|---|
| gpt-4o | 127 | 95% | 3% | 2% | 16 |
| gpt-4o-mini | 134 | 94% | 3% | 3% | 23 |
| gpt-4.1-mini | 116 | 91% | 4% | 4% | 15 |

All three models are close. Reading the 11 unsupported reasons one by one, they fall into four kinds:

| Kind | gpt-4o | gpt-4o-mini | gpt-4.1-mini | Example |
|---|---|---|---|---|
| Reversed a finding | 1 | 1 | 1 | All three said *Towards Evaluating the Robustness of Neural Networks* shows that defensive distillation works. The abstract quotes that earlier claim, then shows it doesn't hold. |
| Stretched a link to the request | 1 | 2 | 2 | LLaMA and PaLM described as related to mixture-of-experts; PaLM's abstract says it is a dense model. |
| Added a detail from outside the abstract | 0 | 0 | 1 | A survey of LLM agents described as covering tool use, which its abstract doesn't mention (it may be true of the full paper). |
| OpenAlex data error, not the agent's fault | 0 | 1 | 1 | FlashAttention's record carries another paper's abstract; REST's abstract field holds only its authors and venue. |

The second run also measures how much the agent varies between runs of the same model:

| Agent model | nDCG@10, run 1 | Run 2 | Mean | Top-10 overlap between runs | LLM cost per search (mean) |
|---|---|---|---|---|---|
| gpt-4o | 0.604 | 0.549 | 0.577 | 68% | US$0.024 |
| gpt-4o-mini | 0.557 | 0.576 | 0.567 | 74% | US$0.0021 |
| gpt-4.1-mini | 0.532 | 0.531 | 0.531 | 84% | US$0.0055 |

What this shows:

- **Run-to-run noise is as large as the model gap.** gpt-4o's two runs differ by 0.055 (p = 0.06), more than its first-run lead over gpt-4o-mini (0.047). Averaged over both runs, the gap is 0.01 (p = 0.62), and gpt-4o-mini finds slightly more foundational papers (canonical R@20 0.263 vs 0.244).
- **gpt-4.1-mini is still the weakest agent**, significantly below gpt-4o on the two-run mean (p = 0.035), and the fewest of its reasons are fully supported (91%).
- **The agent now defaults to gpt-4o-mini** (`AGENT_LLM_MODEL`), at 1/11 of gpt-4o's cost. Reading notes still use `LLM_MODEL`.
- **The error worth fixing next is the reversed finding.** All three models made it on the same paper, so a bigger model doesn't prevent it. The abstract quotes an earlier claim before refuting it, and the models repeat the quoted claim (see §3.8).

### 3.8 Fixing the reversed finding

The reversed finding came from the search tool, not the models. Search results showed only the first 600 characters of each abstract to keep the context small. That cut 96% of abstracts (the median is 1,314 characters), and in this paper the sentence "In this paper, we demonstrate that defensive distillation does not significantly increase the robustness" starts at character 588. The models saw the earlier claim and never saw the refutation.

Two changes, each evaluated on all 32 queries with gpt-4o-mini:

- **v3: longer abstracts and a grounding prompt.** Search results show up to 1,500 characters (67% of abstracts in full). The prompt says abstracts often describe earlier work before the paper's own contribution, that reasons must describe what the paper itself proposes or finds, and that a paper whose link to the request can't be stated from its abstract should be left out.
- **v4: a title check.** v3's longer context caused a new error: three reasons were attached to the wrong paper (e.g. a reason about RegNeRF on Mip-NeRF 360). The final answer now names each paper's title before its ID and reason, and grounding checks that the title matches the ID. A mismatched reason moves to the paper whose title it names, or is dropped.

| gpt-4o-mini agent | nDCG@10 | Canonical R@20 | Supported | Unsupported | Reversed findings | Reasons on the wrong paper | LLM cost per search |
|---|---|---|---|---|---|---|---|
| v2 (runs 1 and 2) | 0.557 / 0.576 | 0.269 / 0.256 | 94% | 3% | 1 | 0 | US$0.0021 |
| v3: longer abstracts + prompt | 0.586 | 0.256 | 91% | 4% | 0 | 3 | US$0.0022 |
| **v4: + title check (default)** | **0.601** | **0.275** | **94%** | **3%** | **0** | **0** | **US$0.0026** |

What this shows:

- **Both targeted errors are gone.** The reversed finding didn't recur, and v4 now describes that paper correctly ("critiques the effectiveness of defensive distillation ... introduces new attack strategies").
- **Writing the title first did the work.** The title check never fired in v4's 159 recommendations, so the mismatches stopped because the model anchors each reason to the title it has just written. The check remains as a safety net.
- **No loss in retrieval**, at about 20% more tokens from the longer abstracts. The nDCG@10 gain over v2 is within run-to-run noise (p = 0.26 against v2's second run; v4 was run once).
- **What remains.** v4's 4 unsupported reasons are 2 stretched links (e.g. MobileNets described as related to knowledge distillation) and 2 details the abstract doesn't state. The unsupported rate (3%) is the same as before; with about 140 reasons per run, changes of a few reasons are noise.

## 4. Cost per search

Prices are OpenAI and OpenAlex list prices in September 2026: gpt-4o US$2.50/US$10, gpt-4o-mini US$0.15/US$0.60 per million input/output tokens; an OpenAlex search costs US$0.001, a list/filter request US$0.0001, and a single-work lookup is free.

| Design | OpenAlex requests | OpenAlex cost | LLM cost | Total | nDCG@10 |
|---|---|---|---|---|---|
| Original pipeline (gpt-4o) | 1 | US$0.001 | ~US$0.0046 | ~US$0.006 | 0.550 |
| Keyword pipeline + MiniLM + prior (gpt-4o) | 10 | US$0.010 | ~US$0.0046 | ~US$0.015 | 0.893 |
| **Default: semantic + expansion + MiniLM (gpt-4o-mini)** | **2** | **US$0.0011** | **US$0.0003** | **~US$0.0014** | **0.949** |
| Agent, gpt-4o | ≤2 | ≤US$0.002 | US$0.027 | ~US$0.029 | 0.604 |
| **Agent (default), gpt-4o-mini** | ≤5 | ≤US$0.005 | US$0.0026 | ≤US$0.008 | 0.601 |

For the agent, the OpenAlex column is an upper bound: it counts every tool call, and some calls are free single-paper lookups (the eval doesn't separate them).

**Free budget.** OpenAlex's free budget of US$1 per day per API key covers about 900 default searches, compared with about 90 for the keyword pipeline. The reranker runs locally at no cost.

**Cost of the benchmark itself.**

- **OpenAI:** on the order of US$10 over the whole project, mostly for gpt-4.1 labelling.
- **OpenAlex:** about 2,000 requests, spread over several days because of the daily budget.
- **Re-running:** with gpt-4.1-mini as the judge, a full re-run's labelling would cost under US$1.

## 5. Engineering findings

Several problems only showed up because the evaluation ran thousands of real requests:

| Finding | Effect | Fix |
|---|---|---|
| OpenAlex returns HTTP 429 with `Retry-After` = seconds until the daily budget resets | The client slept for ~5 hours | Waits over 30 s fail fast with the reset time (#6) |
| No timeout on OpenAlex requests | A stalled connection hung an eval run overnight | (5 s connect, 30 s read) timeout, then retry (#9) |
| OpenAI SDK default timeout of 10 min × 7 attempts | One stalled call could hang an agent search for over an hour | 60 s per-request timeout (#11) |
| Cross-encoder called from parallel agent tool calls on Apple's GPU | The whole process crashed | The reranker serializes its calls with a lock (#6) |
| Low-tier OpenAI key (30k tokens/min) | Agent searches failed on 429 | 6 retries with exponential backoff (#6) |
| Agent tool's date/citation sorts searched full text | Off-topic results with invented reasons | Title/abstract matching and a stricter prompt (#11) |
| A date range in the request ("since 2023") was dropped | Date constraints ignored | Schema and prompt route dates to the filter (#6) |
| OpenAlex data errors | The LoRA paper is stored under the wrong title; DDPM and FlashAttention carry another paper's abstract; some abstracts are one-line teasers or just the author list; some titles contain a literal `\n`; preprint and published copies are separate records | Canonical papers matched by DOI where needed; title normalization merges duplicates (#6); the faithfulness check skips abstracts under 100 characters (#13) |
| Paper IDs were title hashes when a paper had no DOI | The details page opened the wrong paper or a 404 | Real OpenAlex IDs throughout (#6) |

## 6. Limitations

- **LLM labels.** The judge is not a human annotator. The canonical papers and the cheaper-judge comparison support it, but individual labels can be wrong.
- **Pool bias.** Papers no evaluated system retrieved are never labelled, so Recall@20 is relative to what the systems found together.
- **Small query set.** 32 queries, most in machine learning. Differences of a few nDCG points are within noise; the p-values are reported for that reason.
- **Few runs per system.** The LLM steps and OpenAlex's live index are not deterministic. Pipeline systems were run once; the agents were run twice, and one agent's nDCG@10 moved by 0.055 between runs.
- **Unequal comparison with the agent.** The agent returns fewer papers than the metrics reward.
- **Faithfulness is checked against the abstract only**, by an LLM. A reason that is true of the full paper but not stated in its abstract counts as unsupported, and OpenAlex's abstracts are sometimes wrong.
- **Estimated gpt-4o costs.** Where gpt-4o runs predate token logging, their costs are estimated from the same prompts' measured token counts.

## 7. Future work

- **Stretched links in agent reasons.** About 3% of reasons still claim a connection the abstract doesn't support. Checking each reason against its abstract before returning it (a cheap model, one call per search) would catch these, at the cost of one more LLM call.
- **Agentic RAG.**
  - Give the agent the default pipeline as a tool.
  - Decompose multi-part questions and check whether the evidence covers every part.
  - Generate cited literature reviews with per-claim verification, and extend the benchmark with citation-precision and faithfulness metrics.
- **Recall beyond 50 semantic results.** A self-hosted index over an OpenAlex snapshot subset, with BM25 and dense retrieval, would remove the per-request cost and the 50-result cap.

## Appendix: reproducing the results

```bash
pip install -r requirements.txt -r requirements-dev.txt
python eval/run_eval.py --score-only        # recompute every metric from the committed runs and labels
python eval/run_eval.py --systems semantic+minilm+cite0.2+expand@gpt-4o-mini   # re-run one system (needs API keys)
python eval/judge_agreement.py --model gpt-4.1-mini                            # judge agreement study
python eval/faithfulness.py --systems agent-v2.run2 agent-v2@gpt-4o-mini.run2   # reason faithfulness
python docs/figures/make_figures.py        # redraw the figures (needs matplotlib)
```

System names in `eval/results.md` read as `<recall>+<reranker>+<options>@<model>`:

- **Recall:** `single_query` is the original; `multi_query_v1` and `multi_query` are the keyword designs (`_v1` matches full text for citation-sorted searches); `semantic` is semantic search.
- **Options:** `citeX` is a citation prior of weight X; `expand` is citation expansion.
- **Agents:** `agent-v2` is the agent after the tool fix; `.run2` is its second run, which also saved reasons; `agent-v3` adds longer abstracts and the grounding prompt, and `agent-v4` the title check (§3.8).
