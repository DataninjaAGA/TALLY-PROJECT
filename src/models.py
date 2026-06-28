from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date


@dataclass
class TallyTask:
    task_card: str
    description: str
    man_hours: str = ""
    work_order: str = ""
    status: str = ""
    logbook_pg: str = ""
    remark: str = ""
    source_row: int | None = None


@dataclass
class TallyDocument:
    register: str
    station: str
    tally_date: date | None
    flight: str = ""
    arrival: str = ""
    departure: str = ""
    tasks: list[TallyTask] = field(default_factory=list)

    @property
    def filename(self) -> str:
        safe = self.register.replace("/", "-").replace("\\", "-").strip()
        return f"{safe} T.pdf"
