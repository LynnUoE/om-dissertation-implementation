# Retrieval Evaluation

A small benchmark for comparing LitFinder's retrieval strategies. Results are in [results.md](results.md).

## Query set

[queries.jsonl](queries.jsonl) holds 32 natural-language research requests. About two thirds are machine-learning topics and the rest come from biology, medicine, materials science, climate and social science. One query includes a date constraint ("published since 2023").

Each query lists 4-5 **canonical papers** picked by hand: well-known papers that anyone reviewing the topic would expect to find, such as DDPM for diffusion models or FedAvg for federated learning. [resolve_canonical.py](resolve_canonical.py) looks each one up in OpenAlex and stores every work with the same title, since OpenAlex often lists a preprint and the published version separately. Two papers are matched by DOI: OpenAlex stores the LoRA paper under the wrong title, and one title search failed on "U.S.".

## Relevance labels

The canonical papers alone would undercount relevant results: a query about federated learning has hundreds of relevant papers, not five. So every paper that any system returns in its top 20 is labelled (**pooling**, as in TREC):

- **Judge:** `gpt-4.1` at temperature 0, with the rubric in [judge.py](judge.py). It is a different model from the one under test (`gpt-4o` by default).
- **Input:** each (query, paper) pair is judged on its own from the title, year and abstract.
- **Grades:** 2 = highly relevant (belongs in a short reading list on the topic), 1 = partially relevant, 0 = not relevant.

Labels are saved in [qrels.jsonl](qrels.jsonl) with the judge's one-sentence reason. Existing labels are never re-judged, so adding a system only labels the papers it newly finds.

Papers are matched by normalized title rather than OpenAlex ID, so a preprint and its published version count as the same paper.

### Can a cheaper judge be used?

[judge_agreement.py](judge_agreement.py) re-labels every pair with another model and compares it with the `gpt-4.1` labels (about 96% of pairs were re-labelled; the rest hit rate limits):

| Judge | Exact agreement | Weighted κ | Kendall τ of system ranking (nDCG@10 / Recall@20) | Relative cost |
|---|---|---|---|---|
| `gpt-4.1-mini` | 85% | 0.86 | 0.84 / 0.87 | ~1/5 |
| `gpt-4.1-nano` | 66% | 0.71 | 0.82 / 0.79 | ~1/20 |

`gpt-4.1-mini` is a reasonable judge for day-to-day iteration: it is a little stricter, but every conclusion in the results holds with its labels. `gpt-4.1-nano` downgrades many highly relevant papers (591 of 1,570) and lowers every system's nDCG@10 by about 0.12. Don't mix judges in one report, since their grading scales differ.

```bash
python eval/judge_agreement.py --model gpt-4.1-mini
python eval/run_eval.py --judge-model gpt-4.1-mini    # label new papers with it
```

## Metrics

| Metric | Meaning |
|---|---|
| nDCG@10 | Ranking quality of the top 10 with graded gains (2^grade − 1), normalized by the best possible ranking of all labelled papers for the query |
| P@10 | Share of the top 10 slots holding a paper graded ≥ 1 (empty slots count as misses) |
| Recall@20 | Share of all papers graded 2 for the query (across every system) that appear in the top 20 |
| Canonical R@20 | Share of the hand-picked canonical papers in the top 20; doesn't depend on the LLM judge |
| p | Paired randomization test on per-query nDCG@10 against the `single_query` baseline |

## Fair comparisons

- All pipeline systems share one cached LLM query analysis per query, so they differ only in retrieval.
- Systems with the same recall version rerank the same cached candidate pool, so they differ only in the reranker, the citation prior and expansion. The semantic search results are cached once per query; `multi_query+semantic` pools fuse them with the keyword pool exactly as `recall()` does.
- Reported latency covers the whole search (LLM analysis + OpenAlex + reranking), with reranker models loaded beforehand.

## Limitations

- **LLM labels.** The judge is not a human annotator. Spot checks look reasonable, and the canonical papers are a judge-free check, but individual labels can be wrong.
- **Pool bias.** Papers that no system retrieved are never labelled, so Recall@20 is relative to what the evaluated systems found together.
- **Small query set.** With 32 queries, differences of a few nDCG points are within noise; check the p-values.
- **The agent returns fewer results.** It usually recommends 5-10 papers, which caps its P@10 and Recall@20. nDCG@10 is the fairest comparison with the pipelines.
- **Nondeterminism.** The LLM steps are not fully deterministic, and OpenAlex's index changes over time, so reruns won't match exactly.

## Running it

```bash
python eval/run_eval.py                           # run every system, label new papers, write results.md
python eval/run_eval.py --systems multi_query+bge-base --queries q01 q02
python eval/run_eval.py --score-only              # recompute metrics from saved runs and labels
```

Runs are saved in `runs/`. Cached LLM analyses, candidate pools and paper texts are saved in `.cache/`, which is not committed.

**Cost of a full run from scratch:**

- **OpenAI:** about US$6, mostly labelling with `gpt-4.1` (about US$4) and the two agent systems (about US$1.5). With `gpt-4.1-mini` as the judge, labelling costs under US$1.
- **OpenAlex:** about 1,100 searches. OpenAlex bills every search against a daily budget; the free budget with an API key is about 1,000 searches a day. Runs resume where they stopped, and runs that hit an OpenAlex error are not saved.
