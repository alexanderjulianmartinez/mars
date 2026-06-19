"""Render EvalRuns as Markdown (Jinja2) or JSON."""

from __future__ import annotations

import json
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from mars.engine.regression import RegressionReport
from mars.models import EvalRun

_TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"
_env = Environment(
    loader=FileSystemLoader(str(_TEMPLATES_DIR)),
    autoescape=select_autoescape(enabled_extensions=()),
    trim_blocks=True,
    lstrip_blocks=True,
)


def render_markdown(run: EvalRun, regression: RegressionReport | None = None) -> str:
    template = _env.get_template("report.md.j2")
    return template.render(run=run, regression=regression)


def render_json(run: EvalRun, regression: RegressionReport | None = None) -> str:
    data = run.model_dump(mode="json")
    if regression is not None:
        data["regression"] = {
            "has_regression": regression.has_regression,
            "warnings": regression.warnings,
            "score_delta": regression.score_delta,
            "runtime_delta_ms": regression.runtime_delta_ms,
            "cost_delta_usd": regression.cost_delta_usd,
        }
    return json.dumps(data, indent=2)
