import json
from datetime import datetime, timezone

from sqlmodel import Session, select

from app.models.reports import Report, ReportSection, ReportSummary
from app.repositories.tables import ReportRow


def _report(row: ReportRow) -> Report:
    return Report(
        id=row.id, plot_id=row.plot_id, kind=row.kind, title=row.title, created_at=row.created_at,
        sections=[ReportSection(**s) for s in json.loads(row.sections_json)],
    )


class ReportRepository:
    def __init__(self, session: Session):
        self.session = session

    def save(self, plot_id: int, kind: str, title: str, sections: list[ReportSection]) -> Report:
        created_at = datetime.now(timezone.utc).replace(microsecond=0)
        row = ReportRow(
            plot_id=plot_id, kind=kind, title=title, created_at=created_at,
            sections_json=json.dumps([s.model_dump(mode="json") for s in sections],
                                     ensure_ascii=False),
        )
        self.session.add(row)
        self.session.commit()
        self.session.refresh(row)
        return _report(row)

    def list(self, plot_id: int | None = None) -> list[ReportSummary]:
        query = select(ReportRow).order_by(ReportRow.id.desc())
        if plot_id is not None:
            query = query.where(ReportRow.plot_id == plot_id)
        return [ReportSummary(id=r.id, plot_id=r.plot_id, kind=r.kind, title=r.title,
                              created_at=r.created_at) for r in self.session.exec(query)]

    def get(self, report_id: int) -> Report | None:
        row = self.session.get(ReportRow, report_id)
        return _report(row) if row else None
