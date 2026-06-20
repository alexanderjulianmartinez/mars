#!/usr/bin/env python3
"""Deterministic authoring tool for the expanded Salience Memory benchmark.

Emits ``salience-memory-v1-expanded.corpus.yaml``: ~30 realistic software-
engineering scenarios across six domains, each with ~20 memories spanning the
six categories (target / relevant / distractor / stale / contradictory /
low_confidence). Content is hand-authored per scenario; counts are topped up with
*grounded* padding (built from each scenario's own keywords, never random
filler) so the corpus is large enough that recall@5 can no longer saturate.

Run:  python experiments/corpus/generate_expanded.py
This is one-shot corpus tooling, not runtime infrastructure. The committed YAML
is the artifact; the generator exists so the corpus is reproducible + auditable.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from pathlib import Path

import yaml

OUT = Path(__file__).resolve().parent / "salience-memory-v1-expanded.corpus.yaml"
SEED = 1729

# Target counts per category per query (hand content is padded up to these).
TARGET_DISTRACTORS = 7
TARGET_STALE = 3
TARGET_LOWCONF = 3

# (importance, novelty, urgency, confidence) ranges per category.
RANGES = {
    "target": ((0.85, 1.0), (0.6, 0.95), (0.5, 0.95), (0.85, 1.0)),
    "relevant": ((0.5, 0.85), (0.4, 0.8), (0.3, 0.8), (0.7, 0.95)),
    "distractor": ((0.05, 0.25), (0.2, 0.6), (0.1, 0.5), (0.5, 0.9)),
    "stale": ((0.1, 0.3), (0.05, 0.25), (0.05, 0.3), (0.5, 0.8)),
    "contradictory": ((0.2, 0.7), (0.3, 0.7), (0.3, 0.8), (0.3, 0.6)),
    "low_confidence": ((0.2, 0.5), (0.3, 0.7), (0.2, 0.6), (0.1, 0.4)),
}


@dataclass
class Scenario:
    slug: str
    domain: str
    query: str
    keywords: list[str]
    targets: list[str]
    relevants: list[str]
    distractors: list[str]
    stale: list[str] = field(default_factory=list)
    contradictory: list[str] = field(default_factory=list)
    low_confidence: list[str] = field(default_factory=list)


def _pad_distractors(s: Scenario, n: int) -> list[str]:
    out = list(s.distractors)
    kws = s.keywords
    i = 0
    while len(out) < n:
        kw = kws[i % len(kws)]
        alt = kws[(i + 1) % len(kws)]
        out.append(
            f"A separate change to {kw} touched the same area but addressed "
            f"{alt} rather than the question of how to {s.query[:48].lower()}."
        )
        i += 1
    return out[:n]


def _pad_stale(s: Scenario, n: int) -> list[str]:
    out = list(s.stale)
    kws = s.keywords
    i = 0
    while len(out) < n:
        kw = kws[i % len(kws)]
        out.append(
            f"[archived] The earlier {kw} approach was the accepted answer before "
            f"the last replatform; it has since been superseded and should not be relied on."
        )
        i += 1
    return out[:n]


def _pad_lowconf(s: Scenario, n: int) -> list[str]:
    out = list(s.low_confidence)
    kws = s.keywords
    i = 0
    while len(out) < n:
        kw = kws[i % len(kws)]
        out.append(
            f"Unverified note: someone suggested {kw} might be relevant here, but it was "
            f"never confirmed and no owner stands behind it."
        )
        i += 1
    return out[:n]


def build_corpus(scenarios: list[Scenario]) -> dict:
    rng = random.Random(SEED)

    def signals(category: str) -> dict:
        (imp, nov, urg, conf) = RANGES[category]
        return {
            "importance": round(rng.uniform(*imp), 3),
            "novelty": round(rng.uniform(*nov), 3),
            "urgency": round(rng.uniform(*urg), 3),
            "confidence": round(rng.uniform(*conf), 3),
        }

    queries = []
    for s in scenarios:
        members: list[tuple[str, str, str]] = []  # (category, id, content)
        buckets = {
            "target": s.targets,
            "relevant": s.relevants,
            "distractor": _pad_distractors(s, TARGET_DISTRACTORS),
            "stale": _pad_stale(s, TARGET_STALE),
            "contradictory": s.contradictory,
            "low_confidence": _pad_lowconf(s, TARGET_LOWCONF),
        }
        for category, contents in buckets.items():
            for i, content in enumerate(contents):
                mid = f"{s.slug}-{category}-{i}"
                members.append((category, mid, " ".join(content.split())))

        memories = []
        target_ids, relevant_ids = [], []
        for category, mid, content in members:
            memories.append({"id": mid, "content": content, "category": category, **signals(category)})
            if category == "target":
                target_ids.append(mid)
            elif category == "relevant":
                relevant_ids.append(mid)

        queries.append({
            "query": s.query,
            "domain": s.domain,
            "target_memories": target_ids,
            "relevant_memories": relevant_ids,
            "memories": memories,
        })

    return {"project": "mars", "name": "salience-memory-v1-expanded", "queries": queries}


def main() -> None:
    from scenarios_data import SCENARIOS  # local import; data lives next door

    corpus = build_corpus(SCENARIOS)
    OUT.write_text(yaml.safe_dump(corpus, sort_keys=False, width=100, allow_unicode=True))
    n_mem = sum(len(q["memories"]) for q in corpus["queries"])
    print(f"Wrote {OUT.name}: {len(corpus['queries'])} queries, {n_mem} memories")


if __name__ == "__main__":
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parent))
    main()
