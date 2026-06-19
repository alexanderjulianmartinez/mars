"""Repository — the only persistence API the rest of Mars uses.

Translates between Pydantic domain models and ORM rows. Keeping this boundary
thin means the engine/CLI never see SQLAlchemy.
"""

from __future__ import annotations

from mars.models import AgentRun, ContextPackage, EvalRun
from mars.storage.db import Database
from mars.storage.orm import AgentRunRow, ContextPackageRow, EvalRunRow


class Repository:
    def __init__(self, db: Database) -> None:
        self._db = db

    # -- writes ----------------------------------------------------------- #

    def save_context_package(self, pkg: ContextPackage) -> None:
        with self._db.session() as s:
            s.merge(
                ContextPackageRow(
                    id=pkg.id,
                    profile=pkg.profile,
                    version=pkg.version,
                    payload=pkg.model_dump(mode="json"),
                )
            )
            s.commit()

    def save_agent_run(self, run: AgentRun) -> None:
        with self._db.session() as s:
            s.merge(
                AgentRunRow(
                    id=run.id,
                    agent=run.agent,
                    model=run.model,
                    payload=run.model_dump(mode="json"),
                )
            )
            s.commit()

    def save_eval_run(self, run: EvalRun) -> None:
        with self._db.session() as s:
            s.merge(
                EvalRunRow(
                    id=run.id,
                    suite_id=run.suite_id,
                    case_id=run.case_id,
                    agent=run.agent,
                    model=run.model,
                    score=run.score,
                    status=run.status.value,
                    created_at=run.created_at,
                    payload=run.model_dump(mode="json"),
                )
            )
            s.commit()

    # -- reads ------------------------------------------------------------ #

    def get_eval_run(self, run_id: str) -> EvalRun | None:
        with self._db.session() as s:
            row = s.get(EvalRunRow, run_id)
            return EvalRun.model_validate(row.payload) if row else None

    def get_agent_run(self, run_id: str) -> AgentRun | None:
        with self._db.session() as s:
            row = s.get(AgentRunRow, run_id)
            return AgentRun.model_validate(row.payload) if row else None

    def get_context_package(self, pkg_id: str) -> ContextPackage | None:
        with self._db.session() as s:
            row = s.get(ContextPackageRow, pkg_id)
            return ContextPackage.model_validate(row.payload) if row else None

    def list_eval_runs(
        self,
        *,
        suite_id: str | None = None,
        case_id: str | None = None,
        agent: str | None = None,
    ) -> list[EvalRun]:
        with self._db.session() as s:
            q = s.query(EvalRunRow)
            if suite_id:
                q = q.filter(EvalRunRow.suite_id == suite_id)
            if case_id:
                q = q.filter(EvalRunRow.case_id == case_id)
            if agent:
                q = q.filter(EvalRunRow.agent == agent)
            q = q.order_by(EvalRunRow.created_at.desc())
            return [EvalRun.model_validate(r.payload) for r in q.all()]

    def latest_eval_run(
        self, *, suite_id: str, case_id: str, agent: str, before: str | None = None
    ) -> EvalRun | None:
        """Most recent run for a (suite, case, agent), optionally excluding ``before``.

        Used to find the baseline a current run is compared against.
        """
        runs = self.list_eval_runs(suite_id=suite_id, case_id=case_id, agent=agent)
        for run in runs:
            if before is not None and run.id == before:
                continue
            return run
        return None
