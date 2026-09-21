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


class IncidentStore:
    """Append-only JSON lines.

    Append-only because an incident log that can be edited is not evidence.
    A flat file because a report is written rarely and read by a person, and
    a database here would be infrastructure standing in for a process.
    """

    def __init__(self, path: Path):
        self.path = path

    def append(self, report: IncidentReport) -> IncidentReport:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(asdict(report), ensure_ascii=False) + "\n")
        return report

    def all(self) -> list[IncidentReport]:
        if not self.path.exists():
            return []
        out: list[IncidentReport] = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                out.append(IncidentReport(**json.loads(line)))
        return out
