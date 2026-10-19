#!/usr/bin/env python3
"""Check every scientific name in the label space against two nomenclators.

    python scripts/nomenclature_check.py            # all 244
    python scripts/nomenclature_check.py --hazard   # the 87 with a hazard

Writes `docs/nomenclature-check.csv`, worst first, and prints a summary.

Why this is a script and not a mycologist's job. Half of the review sheet
`docs/QA-toxicity-and-names.xlsx` asks "is this name current?", which is not
a judgement call -- it is a lookup against a nomenclator, and asking a
specialist to do 244 lookups by hand is how a review request gets declined.
What a specialist is needed for is the *toxicity* column and the handful of
rows where the two nomenclators disagree with each other. This narrows the
ask to those.

Why two sources rather than one. The GBIF backbone is what the image
fetcher resolves against (`ml/fungi_ml/data/sources.py`), so a name the
backbone treats as a synonym is a name that silently pulls a *different
fungus* into the training set -- that makes the backbone the operationally
load-bearing source. But the backbone is an assembled taxonomy with its own
merges, and this project has already been bitten by one: it treats
*Clitocybe dealbata* as a synonym of *C. rivulosa*. Species Fungorum Plus
is the fungal nomenclator those merges are supposed to come from, so
disagreement between the two is the signal worth a human's time.

Neither source is this project's authority. A row flagged here is a question
for the reviewer, not a change to make. Nothing in this script writes to the
taxonomy.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

ROOT = Path(__file__).resolve().parents[1]
TAXONOMY = ROOT / "data" / "taxonomy.seed.json"
OUT = ROOT / "docs" / "nomenclature-check.csv"

GBIF = "https://api.gbif.org/v1"

# The fungal nomenclator, as published through GBIF. Found with
# /dataset/search?q=Fungorum&type=CHECKLIST.
SPECIES_FUNGORUM = "bf3db7c9-5e5d-4fd0-bd5b-94539eaf9598"

# Deadliest first, matching every other artefact in docs/.
BAND = {"DEADLY": 0, "SERIOUS": 1, "TOXIC": 2, "NO_RECORDED_TOXICITY": 3, "UNKNOWN": 4}

# Worst first within a band. A name the two sources disagree about is ranked
# above a plain synonym: a synonym has an answer, a disagreement does not.
SEVERITY = {
    "PINNED_KEY_WRONG": 0,
    "SOURCES_DISAGREE": 1,
    "NO_MATCH": 2,
    "NOT_SPECIES_RANK": 3,
    "DOUBTFUL": 4,
    "SYNONYM": 5,
    "FUZZY_MATCH": 6,
    "SPELLING_DIFFERS": 7,
    "NOT_IN_NOMENCLATOR": 8,
    "OK": 9,
}


@dataclass
class Finding:
    key: str
    scientific_name: str
    toxicity: str
    flag: str = "OK"
    backbone_status: str = ""
    backbone_rank: str = ""
    backbone_accepted: str = ""
    backbone_key: str = ""
    nomenclator_status: str = ""
    nomenclator_accepted: str = ""
    pinned_key: str = ""
    pinned_resolves_to: str = ""
    note: str = ""
    notes: list[str] = field(default_factory=list)

    def sort_key(self) -> tuple[int, int, str]:
        return (SEVERITY.get(self.flag, 9), BAND.get(self.toxicity, 9), self.scientific_name)


def session() -> requests.Session:
    """A session that survives the connection resets GBIF hands out."""
    s = requests.Session()
    retry = Retry(
        total=6,
        backoff_factor=1.5,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=frozenset(["GET"]),
    )
    s.mount("https://", HTTPAdapter(max_retries=retry))
    return s


def get(s: requests.Session, path: str, **params) -> dict:
    """GET with one manual retry, because a reset is raised before Retry sees it."""
    url = f"{GBIF}{path}"
    for attempt in range(4):
        try:
            r = s.get(url, params=params, timeout=30)
            r.raise_for_status()
            return r.json()
        except (requests.ConnectionError, requests.Timeout, ValueError) as exc:
            if attempt == 3:
                raise
            time.sleep(2.0 * (attempt + 1))
            last = exc
    raise RuntimeError(f"unreachable: {last}")  # pragma: no cover


def canonical(name: str) -> str:
    """Genus plus epithet, dropping any authorship."""
    return " ".join(name.replace("(", " ").split()[:2]).strip()


def check_backbone(s: requests.Session, name: str, finding: Finding) -> None:
    """The source the image fetcher actually resolves against."""
    m = get(s, "/species/match", name=name, kingdom="Fungi", strict="false")
    match_type = (m.get("matchType") or "NONE").upper()
    status = (m.get("status") or "").upper()
    rank = (m.get("rank") or "").upper()

    finding.backbone_status = status
    finding.backbone_rank = rank
    finding.backbone_key = str(m.get("usageKey") or "")

    if match_type in ("NONE", ""):
        finding.flag = "NO_MATCH"
        finding.notes.append("the GBIF backbone has no match for this name at all")
        return

    if rank and rank != "SPECIES":
        finding.flag = "NOT_SPECIES_RANK"
        finding.notes.append(
            f"backbone matched at rank {rank}, not SPECIES -- the image "
            "fetcher refuses this, so the species has no training data"
        )
        return

    if match_type == "FUZZY":
        finding.flag = "FUZZY_MATCH"
        finding.notes.append(
            f"backbone matched FUZZY to {m.get('canonicalName')!r} -- fungal "
            "binomials differ by a letter or two between different species"
        )

    returned = canonical(m.get("canonicalName") or m.get("scientificName") or "")
    if returned and returned.lower() != canonical(name).lower():
        if finding.flag == "OK":
            finding.flag = "SPELLING_DIFFERS"
        finding.notes.append(f"backbone returned {returned!r} for {name!r}")

    if "SYNONYM" in status or m.get("synonym"):
        accepted_key = m.get("acceptedUsageKey")
        accepted = ""
        if accepted_key:
            u = get(s, f"/species/{accepted_key}")
            accepted = canonical(u.get("canonicalName") or u.get("scientificName") or "")
        finding.backbone_accepted = accepted
        if finding.flag in ("OK", "SPELLING_DIFFERS"):
            finding.flag = "SYNONYM"
        finding.notes.append(
            f"backbone treats this as a synonym of {accepted or '(unresolved)'}"
        )
    elif status == "DOUBTFUL":
        if finding.flag == "OK":
            finding.flag = "DOUBTFUL"
        finding.notes.append("backbone status is DOUBTFUL")


def check_nomenclator(s: requests.Session, name: str, finding: Finding) -> None:
    """Species Fungorum Plus: the fungal nomenclator, as a second opinion."""
    d = get(s, "/species", datasetKey=SPECIES_FUNGORUM, name=name, limit=20)
    rows = [r for r in d.get("results", []) if (r.get("rank") or "").upper() == "SPECIES"]
    if not rows:
        finding.nomenclator_status = "ABSENT"
        if finding.flag == "OK":
            finding.flag = "NOT_IN_NOMENCLATOR"
            finding.notes.append(
                "no species-rank record in Species Fungorum Plus under this name"
            )
        return

    # Prefer an accepted record if the nomenclator holds more than one.
    rows.sort(key=lambda r: 0 if (r.get("taxonomicStatus") or "").upper() == "ACCEPTED" else 1)
    row = rows[0]
    status = (row.get("taxonomicStatus") or "").upper()
    finding.nomenclator_status = status

    if status == "ACCEPTED":
        return

    accepted = canonical(row.get("accepted") or "")
    finding.nomenclator_accepted = accepted
    if accepted:
        finding.notes.append(f"nomenclator makes this a {status.lower()} of {accepted}")
    else:
        finding.notes.append(f"nomenclator status is {status}")
    if finding.flag in ("OK", "NOT_IN_NOMENCLATOR", "SPELLING_DIFFERS"):
        finding.flag = "SYNONYM"


def check_pinned_key(s: requests.Session, sp: dict, finding: Finding) -> None:
    """Verify a `gbif_key` set by hand still names the species it is pinned to.

    A pinned key is how the project overrides a refusal from
    `judge_match` -- *Helvella crispa*, whose name resolves to the Fungi
    kingdom at confidence 99. That override is the right fix and it also
    silences the check that caught the problem, so the key itself has to be
    verified: a pinned key pointing at the wrong taxon is the one failure in
    this whole file that nothing downstream could detect, because the images
    it fetches really are mushrooms.
    """
    key = sp.get("gbif_key")
    if not key:
        return
    finding.pinned_key = str(key)
    u = get(s, f"/species/{key}")
    rank = (u.get("rank") or "").upper()
    resolved = canonical(u.get("canonicalName") or u.get("scientificName") or "")
    finding.pinned_resolves_to = f"{resolved} ({rank})"

    if rank != "SPECIES" or resolved.lower() != canonical(finding.scientific_name).lower():
        finding.flag = "PINNED_KEY_WRONG"
        finding.notes.append(
            f"gbif_key {key} resolves to {resolved!r} at rank {rank}, not to "
            f"{canonical(finding.scientific_name)!r} at SPECIES -- images "
            "would be fetched under the wrong label"
        )
        return

    # The key is sound, so a complaint about the *name* is already handled.
    if finding.flag in ("NOT_SPECIES_RANK", "NO_MATCH", "FUZZY_MATCH", "SPELLING_DIFFERS"):
        finding.notes.append(
            f"handled: gbif_key {key} is pinned by hand and resolves correctly"
        )
        finding.flag = "OK"


def reconcile(finding: Finding) -> None:
    """Flag the rows where the two sources do not tell the same story.

    This is the only flag that genuinely needs a specialist. Everywhere else
    the sources agree and the answer is in the row.
    """
    bb = finding.backbone_accepted
    nm = finding.nomenclator_accepted
    if bb and nm and bb.lower() != nm.lower():
        finding.flag = "SOURCES_DISAGREE"
        finding.notes.append(
            f"backbone says synonym of {bb}; nomenclator says {nm}"
        )
        return
    # One source moves the name and the other keeps it.
    if bb and finding.nomenclator_status == "ACCEPTED":
        finding.flag = "SOURCES_DISAGREE"
        finding.notes.append(
            f"backbone merges this into {bb}, but the nomenclator still "
            "accepts the name as it stands"
        )
    elif nm and "SYNONYM" not in finding.backbone_status and finding.backbone_status == "ACCEPTED":
        finding.flag = "SOURCES_DISAGREE"
        finding.notes.append(
            f"nomenclator moves this to {nm}, but the backbone still accepts "
            "the name as it stands -- the image fetcher will use the backbone"
        )


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--hazard", action="store_true", help="only species carrying a hazard")
    ap.add_argument("--out", type=Path, default=OUT)
    args = ap.parse_args()

    data = json.loads(TAXONOMY.read_text())
    species = data["species"]
    if args.hazard:
        species = [sp for sp in species if sp["toxicity"] != "NO_RECORDED_TOXICITY"]

    s = session()
    findings: list[Finding] = []
    for i, sp in enumerate(species, 1):
        f = Finding(
            key=sp["key"],
            scientific_name=sp["scientific_name"],
            toxicity=sp["toxicity"],
        )
        try:
            check_backbone(s, f.scientific_name, f)
            check_nomenclator(s, f.scientific_name, f)
            reconcile(f)
            check_pinned_key(s, sp, f)
        except Exception as exc:  # network, not data
            f.flag = "NO_MATCH"
            f.notes.append(f"lookup failed: {type(exc).__name__}: {exc}")
        f.note = "; ".join(f.notes)
        findings.append(f)
        print(
            f"  [{i:3d}/{len(species)}] {f.scientific_name:<34} "
            f"{f.toxicity:<21} {f.flag}",
            flush=True,
        )

    findings.sort(key=Finding.sort_key)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(
            [
                "flag",
                "toxicity",
                "scientific_name",
                "key",
                "backbone_status",
                "backbone_rank",
                "backbone_accepted_name",
                "backbone_usage_key",
                "nomenclator_status",
                "nomenclator_accepted_name",
                "pinned_gbif_key",
                "pinned_key_resolves_to",
                "what_this_means",
                "REVIEWER_verdict",
                "REVIEWER_name_should_be",
                "REVIEWER_notes",
            ]
        )
        for f in findings:
            w.writerow(
                [
                    f.flag,
                    f.toxicity,
                    f.scientific_name,
                    f.key,
                    f.backbone_status,
                    f.backbone_rank,
                    f.backbone_accepted,
                    f.backbone_key,
                    f.nomenclator_status,
                    f.nomenclator_accepted,
                    f.pinned_key,
                    f.pinned_resolves_to,
                    f.note,
                    "",
                    "",
                    "",
                ]
            )

    counts: dict[str, int] = {}
    for f in findings:
        counts[f.flag] = counts.get(f.flag, 0) + 1

    print(f"\n{len(findings)} names checked against two nomenclators.\n")
    for flag in sorted(counts, key=lambda k: SEVERITY.get(k, 9)):
        print(f"  {flag:<20} {counts[flag]:>4}")

    needs_human = [f for f in findings if f.flag not in ("OK", "NOT_IN_NOMENCLATOR")]
    print(
        f"\n{len(needs_human)} of {len(findings)} rows need a human. "
        f"{counts.get('OK', 0)} are current under both sources and need nobody."
    )
    if needs_human:
        print("\nWorst first:\n")
        for f in needs_human:
            print(f"  {f.flag:<18} {f.toxicity:<21} {f.scientific_name}")
            print(f"    {f.note}")
    print(f"\nWritten: {args.out.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
