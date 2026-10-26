"""Reports of a suspected misidentification.

The route exists because an app that tells people it might be wrong owes them
somewhere to say that it was. Without one, the only evidence of a dangerous
failure is a poisoning someone else hears about.

## What a report is, and is not

A report is evidence for a human reviewer. It is never applied to the taxonomy
automatically, and nothing in this module writes to `data/taxonomy.seed.json`.
A user who is confident the app was wrong may themselves be wrong, and the
data they would be correcting is the data every other user's warnings are
derived from. `docs/INCIDENTS.md` documents who acts on these and how.

## Triage is derived, not claimed

`severity` is computed here from the taxonomy, not taken from the reporter.
What matters is not how serious the user felt the error was but what the
error *was*: an app that failed to warn about a species that can kill is a
different class of defect from one that named the wrong russula, and the
difference is knowable from the toxicity of the species they say it actually
was.

## A report is not a triage channel

If someone says they ate it, or that anyone is unwell, this stops being a bug
report. The response carries the emergency guidance and the client shows that
instead of a confirmation -- an incident form that files a medical emergency
as a ticket and thanks the user for their feedback is worse than no form.

The client makes the same check before it submits, so the guidance does not
depend on the request succeeding. Duplicating it is deliberate: the network is
exactly what fails in a wood.

## No photographs, yet

The photograph is the most useful thing a report could carry and it is not
accepted. Storing users' images raises retention and consent questions that
the legal review in `docs/SAFETY.md` is blocking on, and quietly beginning to
collect them ahead of that review is the wrong order to do this in. What is
stored is what the app itself said, which is enough to know which pair of
species confused it.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path

from .taxonomy_service import TaxonomyService, Toxicity

MAX_FREE_TEXT = 4000


class Severity(str, Enum):
    """What kind of defect a report describes.

    Ordered by what it costs to leave unfixed, which is the same ordering the
    risk matrix uses and not the same as how loud the report is.
    """

    # Someone ate it, or someone is unwell. Not a defect report at all.
    MEDICAL = "medical"
    # The app did not warn, and the species reported can kill or seriously harm.
    DANGEROUS_MISS = "dangerous_miss"
    # The app warned about something lethal and the reporter says it was not.
    # Lower priority, never zero: warnings nobody believes protect nobody.
    DANGEROUS_FALSE_ALARM = "dangerous_false_alarm"
    ORDINARY = "ordinary"


EMERGENCY_GUIDANCE = (
    "If anyone has eaten a wild mushroom and may be unwell, treat this as "
    "urgent. In the UK call 999, or NHS 111 if it is not an emergency. Take "
    "the mushroom, or what is left of it, with you -- a photograph is a poor "
    "substitute for the specimen. Do not wait for symptoms: amatoxin "
    "poisoning has a latent period of six to twenty-four hours and early "
    "treatment substantially improves the outcome."
)


@dataclass
class IncidentReport:
    """One report, as stored."""

    incident_id: str
    received_at: str
    severity: str

    # What the app said. Sent by the client from its own observation log, so a
    # report stays actionable after the server has forgotten the observation.
    observation_id: str | None
    verdict: str | None
    reported_candidates: list[str]
    model_version: str | None
    calibrated: bool | None

    # What the reporter says.
    believed_species: str | None
    believed_species_key: str | None
    account: str
    anyone_ate_it: bool
    anyone_unwell: bool
    contact: str | None = None

    notes: dict = field(default_factory=dict)


def triage(
    *,
    taxonomy: TaxonomyService,
    verdict: str | None,
    reported_candidates: list[str],
    believed_species_key: str | None,
    anyone_ate_it: bool,
    anyone_unwell: bool,
) -> Severity:
    """Classify a report from what it describes, not from how it is worded."""
    if anyone_ate_it or anyone_unwell:
        return Severity.MEDICAL

    believed = taxonomy.get(believed_species_key) if believed_species_key else None
    believed_is_dangerous = believed is not None and believed.toxicity in (
        Toxicity.DEADLY,
        Toxicity.SERIOUS,
    )

    warned = verdict == "dangerous_group" or any(
        (species := taxonomy.get(key)) is not None
        and species.toxicity in (Toxicity.DEADLY, Toxicity.SERIOUS)
        for key in reported_candidates
    )

    if believed_is_dangerous and not warned:
        # The failure the whole app is built to avoid.
        return Severity.DANGEROUS_MISS
    if warned and believed is not None and not believed_is_dangerous:
        return Severity.DANGEROUS_FALSE_ALARM
    return Severity.ORDINARY


def build_report(
    *,
    taxonomy: TaxonomyService,
    observation_id: str | None,
    verdict: str | None,
    reported_candidates: list[str],
    model_version: str | None,
    calibrated: bool | None,
    believed_species_key: str | None,
    account: str,
    anyone_ate_it: bool,
    anyone_unwell: bool,
    contact: str | None,
    now: datetime | None = None,
) -> IncidentReport:
    believed = taxonomy.get(believed_species_key) if believed_species_key else None
    severity = triage(
        taxonomy=taxonomy,
        verdict=verdict,
        reported_candidates=reported_candidates,
        believed_species_key=believed_species_key,
        anyone_ate_it=anyone_ate_it,
        anyone_unwell=anyone_unwell,
    )
    return IncidentReport(
        incident_id=uuid.uuid4().hex,
        received_at=(now or datetime.now(timezone.utc)).isoformat(),
        severity=severity.value,
        observation_id=observation_id,
        verdict=verdict,
        reported_candidates=list(reported_candidates),
        model_version=model_version,
        calibrated=calibrated,
        believed_species=believed.scientific_name if believed else None,
        believed_species_key=believed_species_key,
        account=account[:MAX_FREE_TEXT],
        anyone_ate_it=anyone_ate_it,
        anyone_unwell=anyone_unwell,
        contact=(contact.strip()[:200] or None) if contact else None,
    )


class Outcome(str, Enum):
    """What happened to a report, in the reporter's words rather than ours.

    Deliberately short and deliberately blunt. A reporter who took the
    trouble to tell us the app was wrong is owed an answer that says whether
    it was, not a status page that says "in progress" forever.

    There is no "wontfix". If a report is not acted on, the honest value is
    `NO_CHANGE` plus a reason a person wrote, and the reason is what the
    reporter reads.
    """

    RECEIVED = "received"
    INVESTIGATING = "investigating"
    # The app was wrong and the data or the model changed because of it.
    FIXED = "fixed"
    # The app was wrong and we have not fixed it yet. Still an admission.
    CONFIRMED_NOT_YET_FIXED = "confirmed_not_yet_fixed"
    # We could not tell. Not the same as "you were wrong".
    COULD_NOT_DETERMINE = "could_not_determine"
    # We looked and think the app was right. Says so plainly.
    NO_CHANGE = "no_change"


# Terminal outcomes. A report that has reached one of these is answered.
CLOSED_OUTCOMES = frozenset(
    {Outcome.FIXED, Outcome.CONFIRMED_NOT_YET_FIXED,
     Outcome.COULD_NOT_DETERMINE, Outcome.NO_CHANGE}
)

# What a reporter is told when the report was a medical one. A person who
# said somebody had eaten something is never shown a ticket state: see
# `docs/INCIDENTS.md`, and the note on the confirmation text that
# deliberately does not thank anyone for their feedback.
MEDICAL_STATUS_TEXT = (
    "This report said that someone had eaten a wild mushroom or was unwell. "
    "It is not being tracked as a defect, and nothing here is a substitute "
    "for medical advice."
)


@dataclass
class IncidentUpdate:
    """A responder's note on a report, appended rather than written over.

    The log is append-only because a log that can be edited is not evidence,
    and that applies to the *outcome* as much as to the report: a status
    silently changed from "fixed" to "no change" would be exactly the record
    nobody could trust. So an update is a new line, the current status is a
    fold over every line for an id, and the whole history stays readable.
    """

    incident_id: str
    recorded_at: str
    outcome: str
    # Written for the reporter to read, so it must not name another report,
    # another user, or anything internal.
    public_note: str
    # Written for us.
    internal_note: str = ""
    responder: str = ""
    record_type: str = "update"


@dataclass
class IncidentStatus:
    """What a reporter is allowed to see about their own report.

    Note what is absent: their own free-text account, their contact details,
    the species they named, and everything the app said. All of that is in
    the report and none of it is here.

    The id is unguessable (uuid4), but it is also the kind of thing people
    paste into forums, so this is written on the assumption that whoever
    holds the id is not necessarily the person who filed it. Nothing here
    identifies anybody or discloses anything they did not already know.
    """

    incident_id: str
    received_at: str
    outcome: str
    public_note: str
    closed: bool
    medical: bool = False


def status_for(
    report: IncidentReport, updates: list[IncidentUpdate]
) -> IncidentStatus:
    """Fold a report and its updates into the one thing a reporter sees."""
    if report.severity == Severity.MEDICAL.value:
        # Not a defect report, so not a defect status.
        return IncidentStatus(
            incident_id=report.incident_id,
            received_at=report.received_at,
            outcome=Outcome.RECEIVED.value,
            public_note=MEDICAL_STATUS_TEXT,
            closed=True,
            medical=True,
        )

    mine = [u for u in updates if u.incident_id == report.incident_id]
    if not mine:
        return IncidentStatus(
            incident_id=report.incident_id,
            received_at=report.received_at,
            outcome=Outcome.RECEIVED.value,
            public_note=(
                "Recorded and waiting for a person to read it. Nothing is "
                "changed automatically."
            ),
            closed=False,
        )

    latest = sorted(mine, key=lambda u: u.recorded_at)[-1]
    return IncidentStatus(
        incident_id=report.incident_id,
        received_at=report.received_at,
        outcome=latest.outcome,
        public_note=latest.public_note,
        closed=Outcome(latest.outcome) in CLOSED_OUTCOMES,
    )


class IncidentStore:
    """Append-only JSON lines.

    Append-only because an incident log that can be edited is not evidence.
    A flat file because a report is written rarely and read by a person, and
    a database here would be infrastructure standing in for a process.
    """

    def __init__(self, path: Path):
        self.path = path

    def append(self, report: IncidentReport) -> IncidentReport:
        self._write(asdict(report))
        return report

    def append_update(self, update: IncidentUpdate) -> IncidentUpdate:
        """Record an outcome. Appended, never written over the report."""
        self._write(asdict(update))
        return update

    def _write(self, record: dict) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")

    def _lines(self) -> list[dict]:
        if not self.path.exists():
            return []
        return [
            json.loads(line)
            for line in self.path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]

    def all(self) -> list[IncidentReport]:
        """Reports only.

        Updates share the file, so they are filtered out by `record_type`.
        Reports written before updates existed have no such key, which is
        why the test is for the update marker rather than for a report one
        -- an older line must keep reading as a report.
        """
        return [
            IncidentReport(**row)
            for row in self._lines()
            if row.get("record_type") != "update"
        ]

    def updates(self) -> list[IncidentUpdate]:
        return [
            IncidentUpdate(**row)
            for row in self._lines()
            if row.get("record_type") == "update"
        ]

    def status(self, incident_id: str) -> IncidentStatus | None:
        """What the reporter is shown, or None if no such report exists."""
        report = next(
            (r for r in self.all() if r.incident_id == incident_id), None
        )
        if report is None:
            return None
        return status_for(report, self.updates())
