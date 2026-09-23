"""Tests for dataset acquisition.

The resolver tests are the important ones. GBIF's occurrence search is
inclusive of descendants, so accepting a genus-rank taxon key does not fetch
nothing -- it fetches the whole genus under one species label, and the counts
look healthy the whole way down. Nothing downstream can detect it: the images
really are mushrooms, they are just the wrong ones.

Everything here runs offline against a stub session.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fungi_ml.data.sources import (  # noqa: E402
    MIN_MATCH_CONFIDENCE,
    RESEARCH_GRADE,
    UnresolvedDeadlySpecies,
    _licence_accepted,
    _research_grade,
    build_manifest,
    judge_match,
    load_quotas,
    resolve_label_space,
    resolve_species,
    SpeciesQuota,
)

ROOT = Path(__file__).resolve().parents[2]


def match_payload(**overrides) -> dict:
    payload = {
        "usageKey": 2536892,
        "scientificName": "Amanita phalloides (Vaill. ex Fr.) Link",
        "canonicalName": "Amanita phalloides",
        "rank": "SPECIES",
        "status": "ACCEPTED",
        "confidence": 99,
        "matchType": "EXACT",
        "synonym": False,
    }
    payload.update(overrides)
    return payload


class StubResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


class StubSession:
    """Answers /species/match from a name->payload table and records calls."""

    def __init__(self, table=None, pages=None):
        self.table = table or {}
        self.pages = list(pages or [])
        self.calls: list[dict] = []

    def get(self, url, params=None, timeout=None):
        self.calls.append({"url": url, "params": params})
        if url.endswith("/species/match"):
            name = params["name"]
            if name not in self.table:
                return StubResponse({"matchType": "NONE", "confidence": 0})
            return StubResponse(self.table[name])
        if self.pages:
            return StubResponse(self.pages.pop(0))
        return StubResponse({"results": [], "endOfRecords": True})


# --- the refusal that matters ------------------------------------------------


def test_a_genus_rank_match_is_refused():
    """The failure that would file every death cap in Britain as a blusher."""
    verdict = judge_match(
        "Amanita rubescens", match_payload(rank="GENUS", canonicalName="Amanita", usageKey=2526057)
    )
    assert not verdict.accepted
    assert verdict.usage_key is None
    assert "GENUS" in verdict.reason


@pytest.mark.parametrize("rank", ["GENUS", "FAMILY", "ORDER", "KINGDOM", None])
def test_no_rank_above_species_ever_yields_a_key(rank):
    verdict = judge_match("Amanita phalloides", match_payload(rank=rank))
    assert not verdict.accepted
    assert verdict.usage_key is None


def test_a_fuzzy_match_is_refused_even_at_species_rank():
    """Fungal binomials differ by a letter or two across different species."""
    verdict = judge_match(
        "Amanita citrina", match_payload(matchType="FUZZY", canonicalName="Amanita vittadinii")
    )
    assert not verdict.accepted
    assert "FUZZY" in verdict.reason


def test_a_low_confidence_match_is_refused():
    verdict = judge_match(
        "Amanita phalloides", match_payload(confidence=MIN_MATCH_CONFIDENCE - 1)
    )
    assert not verdict.accepted


def test_no_match_is_refused_without_raising():
    verdict = judge_match("Amanita nonexistentia", {"matchType": "NONE", "confidence": 0})
    assert not verdict.accepted
    assert verdict.usage_key is None


def test_an_exact_species_match_is_accepted():
    verdict = judge_match("Amanita phalloides", match_payload())
    assert verdict.accepted
    assert verdict.usage_key == 2536892


def test_a_synonym_is_accepted_and_the_rename_is_recorded():
    """The backbone moves species between genera faster than field guides do."""
    verdict = judge_match(
        "Lepista nuda",
        match_payload(canonicalName="Clitocybe nuda", synonym=True, usageKey=1234),
    )
    assert verdict.accepted
    assert verdict.usage_key == 1234
    assert "Clitocybe nuda" in verdict.reason


def test_a_refused_match_still_reports_what_gbif_said():
    """A caller that only sees None cannot tell 'never heard of it' from 'wrong rank'."""
    verdict = judge_match("Amanita rubescens", match_payload(rank="GENUS"))
    assert verdict.rank == "GENUS"
    assert verdict.match_type == "EXACT"
    assert verdict.confidence == 99


def test_a_network_failure_is_a_refusal_not_an_exception():
    class Failing:
        def get(self, *a, **k):
            raise requests.ConnectionError("no route to host")

    verdict = resolve_species("Amanita phalloides", Failing())
    assert not verdict.accepted
    assert verdict.usage_key is None


# --- licences ----------------------------------------------------------------


@pytest.mark.parametrize(
    "raw",
    [
        "CC0_1_0",
        "CC_BY_4_0",
        "http://creativecommons.org/licenses/by/4.0/",
        "http://creativecommons.org/publicdomain/zero/1.0/",
    ],
)
def test_open_licences_are_accepted(raw):
    assert _licence_accepted(raw)


@pytest.mark.parametrize(
    "raw",
    [
        None,
        "",
        "UNSPECIFIED",
        "http://creativecommons.org/licenses/by-nd/4.0/",
        "http://creativecommons.org/licenses/by-nc-nd/4.0/",
        "All rights reserved",
    ],
)
def test_closed_or_unstated_licences_are_refused(raw):
    """An absent licence is refused: unknown terms are not permissive terms."""
    assert not _licence_accepted(raw)


# --- research grade ----------------------------------------------------------


def test_only_research_grade_observations_are_kept():
    assert _research_grade({"identificationVerificationStatus": RESEARCH_GRADE})
    assert not _research_grade({"identificationVerificationStatus": "Needs ID"})
    assert not _research_grade({})


# --- the manifest ------------------------------------------------------------


def occurrence(key: int, n_images: int = 1, **overrides) -> dict:
    occ = {
        "key": key,
        "license": "CC_BY_4_0",
        "identificationVerificationStatus": RESEARCH_GRADE,
        "decimalLatitude": 52.7,
        "decimalLongitude": -2.75,
        "month": 10,
        "year": 2024,
        "countryCode": "GB",
        "rightsHolder": "someone",
        "media": [{"identifier": f"https://img.example/{key}-{i}.jpg"} for i in range(n_images)],
    }
    occ.update(overrides)
    return occ


def build(occurrences, target=100, tmp_path=None, **kwargs):
    quota = SpeciesQuota(
        key="amanita-phalloides", scientific_name="Amanita phalloides", gbif_key=1, target=target
    )
    session = StubSession(pages=[{"results": occurrences, "endOfRecords": True}])
    return build_manifest(
        [quota],
        tmp_path / "m.parquet",
        sleep_between_pages=0.0,
        **kwargs,
    ), session


def test_manifest_drops_unlicensed_and_unverified_records(tmp_path, monkeypatch):
    import fungi_ml.data.sources as sources

    monkeypatch.setattr(sources, "_session", lambda: StubSession(
        pages=[{
            "results": [
                occurrence(1),
                occurrence(2, license="http://creativecommons.org/licenses/by-nd/4.0/"),
                occurrence(3, identificationVerificationStatus="Needs ID"),
            ],
            "endOfRecords": True,
        }]
    ))
    frame, _ = build([], tmp_path=tmp_path)
    assert set(frame["observation_id"]) == {"1"}


def test_one_observation_cannot_eat_the_whole_quota(tmp_path, monkeypatch):
    """A quota is counted in images; the split is counted in observations."""
    import fungi_ml.data.sources as sources

    monkeypatch.setattr(sources, "_session", lambda: StubSession(
        pages=[{"results": [occurrence(i, n_images=30) for i in range(1, 6)], "endOfRecords": True}]
    ))
    frame, _ = build([], target=20, tmp_path=tmp_path, max_images_per_observation=4)
    per_obs = frame.groupby("observation_id").size()
    assert per_obs.max() <= 4
    assert len(per_obs) >= 5


def test_manifest_carries_the_observation_id_the_splitter_needs(tmp_path, monkeypatch):
    import fungi_ml.data.sources as sources

    monkeypatch.setattr(sources, "_session", lambda: StubSession(
        pages=[{"results": [occurrence(7, n_images=3)], "endOfRecords": True}]
    ))
    frame, _ = build([], tmp_path=tmp_path)
    assert list(frame["observation_id"]) == ["7", "7", "7"]
    assert frame["species_key"].unique().tolist() == ["amanita-phalloides"]


# --- the label space ---------------------------------------------------------


def seed_taxonomy(tmp_path: Path, species) -> Path:
    path = tmp_path / "taxonomy.json"
    path.write_text(json.dumps({"species": species}), encoding="utf-8")
    return path


def test_an_unresolved_deadly_species_stops_the_build(tmp_path):
    """A species the model cannot name is one the app cannot warn about."""
    path = seed_taxonomy(
        tmp_path,
        [
            {
                "key": "amanita-phalloides",
                "scientific_name": "Amanita phalloides",
                "toxicity": "DEADLY",
                "gbif_key": None,
            }
        ],
    )
    session = StubSession({"Amanita phalloides": match_payload(rank="GENUS")})
    with pytest.raises(UnresolvedDeadlySpecies) as exc:
        load_quotas(path, 100, session=session)
    assert "Amanita phalloides" in str(exc.value)


def test_an_unresolved_ordinary_species_is_dropped_not_fatal(tmp_path):
    path = seed_taxonomy(
        tmp_path,
        [
            {
                "key": "unknown-thing",
                "scientific_name": "Nonexistus fabricatus",
                "toxicity": "INEDIBLE",
                "gbif_key": None,
            },
            {
                "key": "amanita-phalloides",
                "scientific_name": "Amanita phalloides",
                "toxicity": "DEADLY",
                "gbif_key": None,
            },
        ],
    )
    session = StubSession({"Amanita phalloides": match_payload()})
    quotas = load_quotas(path, 100, session=session)
    assert [q.key for q in quotas] == ["amanita-phalloides"]


def test_a_declared_key_is_used_without_asking_gbif(tmp_path):
    path = seed_taxonomy(
        tmp_path,
        [
            {
                "key": "amanita-phalloides",
                "scientific_name": "Amanita phalloides",
                "toxicity": "DEADLY",
                "gbif_key": 2536892,
            }
        ],
    )
    session = StubSession()
    quotas = load_quotas(path, 100, session=session)
    assert quotas[0].gbif_key == 2536892
    assert session.calls == []


def test_resolution_is_cached_and_readable(tmp_path):
    path = seed_taxonomy(
        tmp_path,
        [
            {
                "key": "amanita-phalloides",
                "scientific_name": "Amanita phalloides",
                "toxicity": "DEADLY",
                "gbif_key": None,
            },
            {
                "key": "unknown-thing",
                "scientific_name": "Nonexistus fabricatus",
                "toxicity": "INEDIBLE",
                "gbif_key": None,
            },
        ],
    )
    cache = tmp_path / "gbif-keys.json"
    session = StubSession({"Amanita phalloides": match_payload()})
    resolve_label_space(path, session=session, cache_path=cache, sleep_between=0.0)

    assert session.calls, "first pass should have asked GBIF"
    written = json.loads(cache.read_text())
    by_name = {m["scientific_name"]: m for m in written["matches"]}
    # The refusal is recorded with its reason, which is the point of the file.
    assert by_name["Nonexistus fabricatus"]["accepted"] is False
    assert by_name["Nonexistus fabricatus"]["reason"]

    again = StubSession()
    matches = resolve_label_space(path, session=again, cache_path=cache, sleep_between=0.0)
    assert again.calls == [], "second pass should have reused the cache"
    assert {m.scientific_name for m in matches if m.accepted} == {"Amanita phalloides"}


def test_every_deadly_species_in_the_real_taxonomy_is_still_unresolved(tmp_path):
    """Guards the claim that no GBIF key has been set by hand yet.

    If this fails, keys have been added -- which is progress, not a fault.
    Update the test to pin the reviewed ones instead of deleting it.
    """
    raw = json.loads((ROOT / "data" / "taxonomy.seed.json").read_text(encoding="utf-8"))
    declared = [s["scientific_name"] for s in raw["species"] if s.get("gbif_key") is not None]
    assert declared == []
