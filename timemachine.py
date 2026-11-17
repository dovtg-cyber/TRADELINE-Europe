"""Legal Time Machine: what was the legal status of an act on a given date.

The five dates are kept apart on purpose: adoption, publication, entry into force, application, end of application.
A date that is not stored is never invented. The result carries warnings and, on a sunset boundary,
asks for human review instead of guessing. Standard library only.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Optional
from .verification import SourceVersion

NOT_YET_PUBLISHED = "not_yet_published"
PUBLISHED_NOT_IN_FORCE = "published_not_in_force"
IN_FORCE_NOT_APPLICABLE = "in_force_not_applicable"
APPLICABLE = "applicable"
BOUNDARY_CHECK = "applicable_boundary_check"
CEASED = "ceased"
UNKNOWN = "unknown"


@dataclass
class Status:
    state: str
    version: Optional[SourceVersion] = None
    warnings: list[str] = field(default_factory=list)

    @property
    def relied_on(self) -> bool:
        """Only an applicable state may support a mandatory statement. A boundary date needs a human decision."""
        return self.state == APPLICABLE


def entry_into_force_default(published_on: date, days: int = 20) -> date:
    """The usual EU rule: 'the twentieth day following publication'. A COMPUTED value, not a stored fact.
    Always compare with the date EUR-Lex records for the act."""
    return published_on + timedelta(days=days)


def act_status(versions: list[SourceVersion], d: date) -> Status:
    vs = sorted(versions, key=lambda v: v.version_from)
    if not vs:
        return Status(UNKNOWN, None, ["no_versions_in_knowledge_base"])
    v = next((x for x in vs if x.in_force_on(d)), None)
    if v is None:
        if d < vs[0].version_from:
            pub = vs[0].published_on
            if pub is None:
                return Status(UNKNOWN, None, ["no_version_covers_date", "publication_date_unknown"])
            return Status(PUBLISHED_NOT_IN_FORCE if d >= pub else NOT_YET_PUBLISHED, None, [])
        last = vs[-1]
        if last.version_to is not None and d > last.version_to:
            return Status(CEASED, last, [])
        return Status(UNKNOWN, None, ["gap_between_versions"])
    warn: list[str] = []
    if v.entered_into_force is None:
        warn.append("entry_into_force_unknown")
    if v.published_on is None:
        warn.append("publication_date_unknown")
    if v.entered_into_force is not None and d < v.entered_into_force:
        return Status(PUBLISHED_NOT_IN_FORCE if (v.published_on is None or d >= v.published_on) else NOT_YET_PUBLISHED, v, warn)
    if v.applies_from is not None and d < v.applies_from:
        return Status(IN_FORCE_NOT_APPLICABLE, v, warn)
    if v.ceases_on is not None:
        if d > v.ceases_on:
            return Status(CEASED, v, warn)
        if d == v.ceases_on:
            warn.append("sunset_date_boundary: texts saying 'until <date>' are ambiguous; a specialist must confirm whether the date is inclusive")
            return Status(BOUNDARY_CHECK, v, warn)
    return Status(APPLICABLE, v, warn)
