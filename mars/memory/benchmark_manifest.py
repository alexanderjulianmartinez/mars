"""Freeze + verification tooling for versioned benchmark corpora.

A *manifest* pins a benchmark corpus to a content hash so it can be cited as a
stable research artifact. The first frozen artifact is **Salience Memory
Benchmark v1.0.0** (``salience-memory-benchmark-v1``), backing Experiments 1-5
of the Salience & Attention Systems work.

This module is pure data + verification (no Cortex, no paid APIs): it computes
the corpus SHA256, loads the manifest, and reports whether the on-disk corpus
still matches the frozen hash. Freezing policy lives in
``docs/SALIENCE_MEMORY_BENCHMARK_V1.md``.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

import yaml

from mars.memory.expanded_corpus import (
    CORPUS_DIR,
    ExpandedCorpus,
    load_expanded_corpus,
    validate_corpus,
)


def corpus_sha256(path: Path) -> str:
    """Return the SHA256 hex digest of a corpus file's raw bytes."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def corpus_path_for(name: str, corpus_dir: Path | None = None) -> Path:
    """Resolve the on-disk path for a corpus ``name``."""
    return (corpus_dir or CORPUS_DIR) / f"{name}.corpus.yaml"


@dataclass
class BenchmarkManifest:
    """A loaded benchmark manifest (the frozen reference record)."""

    benchmark_id: str
    version: str
    corpus_path: str
    corpus_sha256: str
    query_count: int
    memory_count: int
    category_counts: dict[str, int]
    raw: dict

    @property
    def corpus_name(self) -> str:
        """The corpus ``name`` (filename stem without ``.corpus.yaml``)."""
        return Path(self.corpus_path).name.replace(".corpus.yaml", "")


def manifest_path_for(benchmark_id: str, corpus_dir: Path | None = None) -> Path | None:
    """Find the ``*.manifest.yaml`` whose ``benchmark_id`` matches, if any."""
    directory = corpus_dir or CORPUS_DIR
    for path in sorted(directory.glob("*.manifest.yaml")):
        data = yaml.safe_load(path.read_text()) or {}
        if data.get("benchmark_id") == benchmark_id:
            return path
    return None


def load_manifest(benchmark_id: str, corpus_dir: Path | None = None) -> BenchmarkManifest:
    """Load the manifest for ``benchmark_id``; raise ``FileNotFoundError`` if absent."""
    path = manifest_path_for(benchmark_id, corpus_dir)
    if path is None:
        raise FileNotFoundError(f"no manifest with benchmark_id {benchmark_id!r}")
    data = yaml.safe_load(path.read_text()) or {}
    return BenchmarkManifest(
        benchmark_id=data["benchmark_id"],
        version=str(data["version"]),
        corpus_path=data["corpus_path"],
        corpus_sha256=data["corpus_sha256"],
        query_count=int(data["query_count"]),
        memory_count=int(data["memory_count"]),
        category_counts=dict(data.get("category_counts", {})),
        raw=data,
    )


@dataclass
class FreezeVerification:
    """Result of verifying a frozen benchmark against its on-disk corpus."""

    benchmark_id: str
    version: str
    corpus_name: str
    expected_sha256: str
    actual_sha256: str
    validation_errors: list[str]
    stats_mismatches: list[str]
    corpus: ExpandedCorpus | None

    @property
    def hash_matches(self) -> bool:
        return self.expected_sha256 == self.actual_sha256

    @property
    def ok(self) -> bool:
        return self.hash_matches and not self.validation_errors and not self.stats_mismatches

    def failures(self) -> list[str]:
        """Human-readable reasons the freeze check failed (empty if OK)."""
        reasons: list[str] = []
        if not self.hash_matches:
            reasons.append(
                f"corpus SHA256 changed: manifest={self.expected_sha256} "
                f"actual={self.actual_sha256}"
            )
        reasons.extend(f"validation: {e}" for e in self.validation_errors)
        reasons.extend(f"stats: {m}" for m in self.stats_mismatches)
        return reasons


def verify_frozen(benchmark_id: str, corpus_dir: Path | None = None) -> FreezeVerification:
    """Verify a frozen benchmark: recompute the corpus hash, validate it, and
    confirm the manifest's recorded stats still hold.

    Raises ``FileNotFoundError`` if the manifest or corpus is missing.
    """
    manifest = load_manifest(benchmark_id, corpus_dir)
    path = corpus_path_for(manifest.corpus_name, corpus_dir)
    if not path.exists():
        raise FileNotFoundError(f"corpus file missing: {path}")

    actual_sha = corpus_sha256(path)
    corpus = load_expanded_corpus(manifest.corpus_name, corpus_dir)
    validation_errors = validate_corpus(corpus)

    stats_mismatches: list[str] = []
    if corpus.n_queries != manifest.query_count:
        stats_mismatches.append(
            f"query_count {corpus.n_queries} != manifest {manifest.query_count}"
        )
    if corpus.n_memories != manifest.memory_count:
        stats_mismatches.append(
            f"memory_count {corpus.n_memories} != manifest {manifest.memory_count}"
        )
    actual_cats = corpus.category_counts()
    for cat, expected in manifest.category_counts.items():
        if actual_cats.get(cat, 0) != expected:
            stats_mismatches.append(
                f"category {cat} {actual_cats.get(cat, 0)} != manifest {expected}"
            )

    return FreezeVerification(
        benchmark_id=manifest.benchmark_id,
        version=manifest.version,
        corpus_name=manifest.corpus_name,
        expected_sha256=manifest.corpus_sha256,
        actual_sha256=actual_sha,
        validation_errors=validation_errors,
        stats_mismatches=stats_mismatches,
        corpus=corpus,
    )
