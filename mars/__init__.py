"""Mars — continuous evaluation for AI software engineering agents.

Mars is the evaluation layer of a three-part system:

    Cortex  -> context generation
    AutoDev -> agent execution
    Mars    -> evaluation, scoring, regression detection, reporting

Mars never generates context or executes engineering tasks itself. It consumes
:class:`~mars.providers.base.CortexProvider` and
:class:`~mars.providers.base.AutoDevProvider` and measures the outcomes.
"""

__version__ = "0.1.0"
