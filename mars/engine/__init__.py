"""The Mars evaluation engine.

:class:`~mars.engine.runner.EvalRunner` orchestrates the pipeline (context ->
agent -> tests -> score -> persist). :mod:`mars.engine.regression` compares a
run against its baseline.
"""

from mars.engine.regression import RegressionReport, detect_regression
from mars.engine.runner import EvalRunner

__all__ = ["EvalRunner", "detect_regression", "RegressionReport"]
