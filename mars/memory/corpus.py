"""Labeled memory corpus + seeding for Salience Memory v1 (issue #7).

Real Cortex assigns its own UUID to each memory on ``add_memory``, so gold labels
cannot be authored ahead of time against fixed ids. Instead we author a corpus
with *stable keys* + relevance flags, **seed** it into Cortex (capturing the
assigned ids), and emit a gold-label file keyed to those real ids. The retrieval
experiment then measures against real Cortex retrieval.

The corpus is deliberately built so salience can help: relevant memories carry
high importance but only moderate keyword overlap, while distractors have heavy
keyword overlap but low importance.

Seeding is a live, opt-in step (it writes to the shared Cortex project). All the
pure logic here is testable with a fake Cortex.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

import yaml

CORPUS_DIR = Path(__file__).resolve().parents[2] / "experiments" / "corpus"


@dataclass
class CorpusMemory:
    key: str
    content: str
    type: str = "note"
    importance: float = 0.5
    relevant: bool = False
    target: bool = False


@dataclass
class CorpusQuery:
    text: str
    memories: list[CorpusMemory]


@dataclass
class Corpus:
    name: str
    project: str
    queries: list[CorpusQuery] = field(default_factory=list)

    def query_texts(self) -> list[str]:
        return [q.text for q in self.queries]

    @property
    def n_memories(self) -> int:
        return sum(len(q.memories) for q in self.queries)


def load_corpus(name: str, corpus_dir: Path | None = None) -> Corpus:
    path = (corpus_dir or CORPUS_DIR) / f"{name}.corpus.yaml"
    data = yaml.safe_load(path.read_text())
    queries = [
        CorpusQuery(
            text=q["query"],
            memories=[
                CorpusMemory(
                    key=m["key"],
                    content=m["content"].strip(),
                    type=m.get("type", "note"),
                    importance=float(m.get("importance", 0.5)),
                    relevant=bool(m.get("relevant", False)),
                    target=bool(m.get("target", False)),
                )
                for m in q.get("memories", [])
            ],
        )
        for q in data.get("queries", [])
    ]
    return Corpus(name=name, project=data.get("project", "mars"), queries=queries)


def seed_corpus(cortex, corpus: Corpus) -> tuple[dict[str, dict], dict[str, str]]:
    """Seed the corpus into Cortex; return (gold_map, key->id).

    ``cortex`` must expose ``add_memory(project, mem_type, content, importance,
    summary) -> id``. Gold map: ``query_text -> {"relevant": set[id], "target": id}``.
    """
    gold: dict[str, dict] = {}
    key_to_id: dict[str, str] = {}
    for q in corpus.queries:
        relevant: set[str] = set()
        target: str | None = None
        for m in q.memories:
            mid = cortex.add_memory(
                corpus.project, m.type, m.content, importance=m.importance, summary=m.key
            )
            key_to_id[m.key] = mid
            if m.relevant:
                relevant.add(mid)
            if m.target:
                target = mid
        gold[q.text] = {"relevant": relevant, "target": target}
    return gold, key_to_id


def gold_path(name: str, corpus_dir: Path | None = None) -> Path:
    return (corpus_dir or CORPUS_DIR) / f"{name}.gold.json"


def save_gold(gold_map: dict[str, dict], name: str, corpus_dir: Path | None = None) -> Path:
    path = gold_path(name, corpus_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    serializable = {
        q: {"relevant": sorted(v["relevant"]), "target": v["target"]} for q, v in gold_map.items()
    }
    path.write_text(json.dumps(serializable, indent=2))
    return path


def load_gold(name: str, corpus_dir: Path | None = None) -> dict[str, dict] | None:
    path = gold_path(name, corpus_dir)
    if not path.is_file():
        return None
    raw = json.loads(path.read_text())
    return {q: {"relevant": set(v.get("relevant", [])), "target": v.get("target")} for q, v in raw.items()}
