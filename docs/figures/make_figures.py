"""
Draw the report's figures from the saved eval runs and labels, in a light and
a dark version (GitHub picks one with <picture>).

    pip install matplotlib
    python docs/figures/make_figures.py
    python docs/figures/make_figures.py --png /tmp/preview   # also write PNG previews
"""
import os
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path[:0] = [os.path.join(ROOT, "eval"), os.path.join(ROOT, "backend")]
from common import QRELS_PATH, QUERIES_PATH, RUNS_DIR, read_jsonl  # noqa: E402
from metrics import canonical_recall_at_k, mean, ndcg_at_k  # noqa: E402

OUT = os.path.dirname(os.path.abspath(__file__))

# Reference palette (validated: first three categorical slots, all pairs, both modes)
THEMES = {
    "light": {"surface": "#fcfcfb", "text": "#0b0b0b", "text2": "#52514e", "muted": "#8a8984", "grid": "#e8e7e3",
              "series": ["#2a78d6", "#eb6834", "#1baf7a"]},
    "dark": {"surface": "#1a1a19", "text": "#ffffff", "text2": "#c3c2b7", "muted": "#8f8e87", "grid": "#33332f",
             "series": ["#3987e5", "#d95926", "#199e70"]},
}

# (system, label shown next to the point or None, label offset in points)
FAMILIES = [
    ("Keyword queries + reranker", "o", [
        ("multi_query", "Keyword queries, no reranker", (8, -4)),
        ("multi_query+minilm", "+ MiniLM", (8, -9)),
        ("multi_query+bge-m3", None, (0, 0)),
        ("multi_query+minilm+cite0.1", None, (0, 0)),
        ("multi_query+minilm+cite0.2", "+ MiniLM + 10-30%\n   citation prior", (12, -6)),
        ("multi_query+minilm+cite0.3", None, (0, 0)),
        ("multi_query+semantic+minilm+cite0.1", None, (0, 0)),
    ]),
    ("Semantic search + reranker", "s", [
        ("semantic", "Semantic search alone", (9, -1)),
        ("semantic+minilm+cite0.1", None, (0, 0)),
        ("semantic+minilm+cite0.1+expand", None, (0, 0)),
        ("semantic+minilm+cite0.2+expand", "Default: + citation expansion\n+ 20% citation prior", (10, 2)),
    ]),
    ("Agent (fixed tools)", "^", [
        ("agent-v2", "gpt-4o", (8, 4)),
        ("agent-v2@gpt-4o-mini", "gpt-4o-mini", (8, -10)),
        ("agent-v2@gpt-4.1-mini", "gpt-4.1-mini", (-70, -12)),
    ]),
]


def load():
    qrels = {}
    for r in read_jsonl(QRELS_PATH):
        qrels.setdefault(r["qid"], {})[r["key"]] = r["grade"]
    queries = read_jsonl(QUERIES_PATH)

    def score(system):
        runs = {r["qid"]: [x["key"] for x in r["results"]] for r in read_jsonl(os.path.join(RUNS_DIR, f"{system}.jsonl"))}
        return (mean(ndcg_at_k(runs[q["id"]], qrels[q["id"]], 10) for q in queries),
                mean(canonical_recall_at_k(runs[q["id"]], q["canonical"], 20) for q in queries))
    return score


def style_axes(ax, t):
    ax.set_facecolor(t["surface"])
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(t["grid"])
    ax.tick_params(colors=t["text2"], labelsize=9, length=0, pad=6)
    ax.grid(True, color=t["grid"], linewidth=0.8)
    ax.set_axisbelow(True)


def tradeoff(score, mode):
    t = THEMES[mode]
    fig, ax = plt.subplots(figsize=(8.4, 5.4), dpi=100)
    fig.patch.set_facecolor(t["surface"])
    style_axes(ax, t)

    x, y = score("single_query")[1], score("single_query")[0]
    ax.scatter([x], [y], s=70, marker="D", color=t["muted"], edgecolors=t["surface"], linewidths=2, zorder=3,
               label="Original pipeline (one long query)")
    ax.annotate("Original pipeline", (x, y), xytext=(8, -3), textcoords="offset points",
                color=t["text2"], fontsize=9, va="center")

    for (family, marker, systems), color in zip(FAMILIES, t["series"]):
        points = [(s, label, offset, *score(s)) for s, label, offset in systems]
        ax.scatter([p[4] for p in points], [p[3] for p in points], s=70, marker=marker, color=color,
                   edgecolors=t["surface"], linewidths=2, zorder=3, label=family)
        for s, label, offset, ndcg, canon in points:
            if label:
                bold = s == "semantic+minilm+cite0.2+expand"
                ax.annotate(label, (canon, ndcg), xytext=offset, textcoords="offset points",
                            color=t["text"] if bold else t["text2"], fontsize=9,
                            fontweight="bold" if bold else "normal", va="center")

    ax.set_xlabel("Canonical recall@20  (share of hand-picked foundational papers found)", color=t["text2"], fontsize=10)
    ax.set_ylabel("nDCG@10  (topical relevance)", color=t["text2"], fontsize=10)
    ax.set_xlim(-0.02, 0.62)
    ax.set_ylim(0.45, 1.0)
    fig.suptitle("Topical relevance vs foundational papers, 32 queries", x=0.07, ha="left",
                 color=t["text"], fontsize=13, fontweight="bold")
    legend = ax.legend(loc="lower right", frameon=False, fontsize=9, labelcolor=t["text2"])
    for handle in legend.legend_handles:
        handle.set_edgecolor(t["surface"])
    fig.tight_layout(rect=(0, 0, 1, 0.96))
    save(fig, f"tradeoff-{mode}", t)
    plt.close(fig)


def agent_fix(score, mode):
    t = THEMES[mode]
    models = [("gpt-4o", "agent", "agent-v2"), ("gpt-4.1-mini", "agent@gpt-4.1-mini", "agent-v2@gpt-4.1-mini"),
              ("gpt-4o-mini", "agent@gpt-4o-mini", "agent-v2@gpt-4o-mini")]
    fig, ax = plt.subplots(figsize=(8.4, 3.4), dpi=100)
    fig.patch.set_facecolor(t["surface"])
    style_axes(ax, t)
    ax.grid(True, axis="x", color=t["grid"], linewidth=0.8)
    ax.grid(False, axis="y")

    before_c, after_c = t["muted"], t["series"][0]
    for i, (name, before, after) in enumerate(models):
        b, a = score(before)[0], score(after)[0]
        ax.plot([b, a], [i, i], color=t["grid"], linewidth=2, zorder=1, solid_capstyle="round")
        ax.scatter([b], [i], s=80, color=before_c, edgecolors=t["surface"], linewidths=2, zorder=3,
                   label="Before the fix" if i == 0 else None)
        ax.scatter([a], [i], s=80, color=after_c, edgecolors=t["surface"], linewidths=2, zorder=3,
                   label="After the fix" if i == 0 else None)
        # Before-values below the dot and after-values above, so close pairs don't collide
        ax.annotate(f"{b:.2f}", (b, i), xytext=(0, -16), textcoords="offset points", ha="center",
                    color=t["text2"], fontsize=9)
        ax.annotate(f"{a:.2f}", (a, i), xytext=(0, 11), textcoords="offset points", ha="center",
                    color=t["text"], fontsize=9, fontweight="bold")

    ax.set_yticks(range(len(models)), [m[0] for m in models])
    ax.tick_params(axis="y", labelsize=10, colors=t["text"])
    ax.set_ylim(-0.6, len(models) - 0.4)
    ax.invert_yaxis()  # gpt-4o, the default, on top
    ax.set_xlim(0.1, 0.75)
    ax.set_xlabel("nDCG@10", color=t["text2"], fontsize=10)
    fig.suptitle("Agent search before and after the search-tool fix", x=0.07, ha="left",
                 color=t["text"], fontsize=13, fontweight="bold")
    ax.legend(loc="lower left", bbox_to_anchor=(0, 1.0), frameon=False, fontsize=9, labelcolor=t["text2"], ncol=2)
    fig.tight_layout(rect=(0, 0, 1, 0.93))
    save(fig, f"agent-fix-{mode}", t)
    plt.close(fig)


PNG_DIR = None


def save(fig, name, t):
    fig.savefig(os.path.join(OUT, f"{name}.svg"), facecolor=t["surface"])
    if PNG_DIR:
        fig.savefig(os.path.join(PNG_DIR, f"{name}.png"), facecolor=t["surface"], dpi=120)


def main():
    global PNG_DIR
    if "--png" in sys.argv:
        PNG_DIR = sys.argv[sys.argv.index("--png") + 1]
        os.makedirs(PNG_DIR, exist_ok=True)
    plt.rcParams["font.family"] = ["Helvetica", "Arial", "DejaVu Sans"]
    plt.rcParams["svg.fonttype"] = "none"  # Keep text as text
    score = load()
    for mode in THEMES:
        tradeoff(score, mode)
        agent_fix(score, mode)
    print("Wrote", sorted(f for f in os.listdir(OUT) if f.endswith(".svg")))


if __name__ == "__main__":
    main()
