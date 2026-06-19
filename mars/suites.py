"""Load benchmark suites from YAML definitions.

A suite file lists its cases inline. The loader injects ``suite_id`` into each
case so authors don't have to repeat it.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from mars.models import EvalCase, EvalSuite

DEFAULT_SUITES_DIR = Path(__file__).resolve().parent.parent / "suites"


def load_suite_file(path: Path) -> EvalSuite:
    data = yaml.safe_load(path.read_text())
    if not isinstance(data, dict):
        raise ValueError(f"{path}: suite file must be a mapping")
    suite_id = data["id"]
    cases = [
        EvalCase.model_validate({"suite_id": suite_id, **case})
        for case in data.get("cases", [])
    ]
    return EvalSuite(
        id=suite_id,
        name=data.get("name", suite_id),
        description=data.get("description", ""),
        tags=data.get("tags", []),
        cases=cases,
    )


def load_suites(suites_dir: Path | None = None) -> dict[str, EvalSuite]:
    """Load every ``*.yaml`` suite under ``suites_dir`` keyed by suite id."""
    directory = suites_dir or DEFAULT_SUITES_DIR
    suites: dict[str, EvalSuite] = {}
    for path in sorted(directory.glob("*.yaml")):
        suite = load_suite_file(path)
        suites[suite.id] = suite
    return suites


def load_suite(suite_id: str, suites_dir: Path | None = None) -> EvalSuite:
    suites = load_suites(suites_dir)
    if suite_id not in suites:
        raise KeyError(f"suite {suite_id!r} not found in {suites_dir or DEFAULT_SUITES_DIR}")
    return suites[suite_id]
