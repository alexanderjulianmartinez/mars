"""Freeze + verification for Salience Memory Benchmark v1.0.0.

These tests guard the frozen research artifact: the manifest must exist, its
hash must match the on-disk corpus, the corpus must validate, the version must
be pinned at 1.0.0, the recorded stats must hold, and ``verify-frozen`` must
*fail* if the corpus drifts from the frozen hash.
"""

from pathlib import Path

import pytest
from typer.testing import CliRunner

from mars.cli import app
from mars.memory.benchmark_manifest import (
    BenchmarkManifest,
    corpus_path_for,
    corpus_sha256,
    load_manifest,
    manifest_path_for,
    verify_frozen,
)

BENCHMARK_ID = "salience-memory-benchmark-v1"
CORPUS_NAME = "salience-memory-v1-expanded"
EXPECTED_SHA = "a464085c3daa64c97d2764c47f8758931b2a51c2adc1e143fcfc98d9faa74d59"
EXPECTED_CATEGORY_COUNTS = {
    "target": 30,
    "relevant": 102,
    "distractor": 210,
    "stale": 90,
    "contradictory": 30,
    "low_confidence": 90,
}

runner = CliRunner()


def test_manifest_exists_and_is_pinned():
    manifest = load_manifest(BENCHMARK_ID)
    assert isinstance(manifest, BenchmarkManifest)
    assert manifest.version == "1.0.0"
    assert manifest.corpus_name == CORPUS_NAME
    assert manifest.corpus_sha256 == EXPECTED_SHA


def test_manifest_hash_matches_corpus():
    path = corpus_path_for(CORPUS_NAME)
    assert corpus_sha256(path) == EXPECTED_SHA


def test_manifest_records_expected_stats():
    manifest = load_manifest(BENCHMARK_ID)
    assert manifest.query_count == 30
    assert manifest.memory_count == 552
    assert manifest.category_counts == EXPECTED_CATEGORY_COUNTS


def test_verify_frozen_passes_on_current_corpus():
    result = verify_frozen(BENCHMARK_ID)
    assert result.ok, result.failures()
    assert result.hash_matches
    assert result.validation_errors == []
    assert result.stats_mismatches == []
    assert result.corpus is not None
    assert result.corpus.n_queries == 30
    assert result.corpus.n_memories == 552


def test_verify_frozen_fails_on_hash_mismatch(tmp_path: Path):
    """A mutated corpus (changed bytes) must fail verification."""
    src_dir = corpus_path_for(CORPUS_NAME).parent
    # Copy manifest + corpus into a temp dir, then tamper with the corpus.
    manifest_src = manifest_path_for(BENCHMARK_ID)
    assert manifest_src is not None
    (tmp_path / manifest_src.name).write_bytes(manifest_src.read_bytes())
    corpus_src = corpus_path_for(CORPUS_NAME)
    tampered = corpus_src.read_text() + "\n# tamper\n"
    (tmp_path / corpus_src.name).write_text(tampered)

    result = verify_frozen(BENCHMARK_ID, corpus_dir=tmp_path)
    assert not result.ok
    assert not result.hash_matches
    assert any("SHA256 changed" in r for r in result.failures())


def test_cli_corpus_hash_prints_frozen_digest():
    res = runner.invoke(
        app,
        ["corpus", "hash", str(corpus_path_for(CORPUS_NAME))],
    )
    assert res.exit_code == 0, res.stdout
    assert EXPECTED_SHA in res.stdout


def test_cli_verify_frozen_succeeds():
    res = runner.invoke(app, ["corpus", "verify-frozen", BENCHMARK_ID])
    assert res.exit_code == 0, res.stdout
    assert "frozen & verified" in res.stdout
    assert "1.0.0" in res.stdout


def test_cli_verify_frozen_unknown_id_fails():
    res = runner.invoke(app, ["corpus", "verify-frozen", "nope"])
    assert res.exit_code == 1
