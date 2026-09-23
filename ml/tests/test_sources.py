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
    CollidingTaxonKeys,
    INATURALIST_DATASET_KEY,
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


def test_a_synonym_follows_its_accepted_key():
    """A synonym key does not return fewer occurrences -- often it returns none.

    Real case: Inocybe erubescens, DEADLY, matched EXACT at confidence 100
    to usageKey 2527939, which has 0 occurrences. Its acceptedUsageKey
    10776858 (Inosperma erubescens) has 82. Taking the match at face value
    would have dropped a deadly species out of the label space silently,
    because the name resolved perfectly and nothing downstream counts
    images per species until it is too late.
    """
    verdict = judge_match(
        "Inocybe erubescens",
        match_payload(
            usageKey=2527939, acceptedUsageKey=10776858, status="SYNONYM",
            canonicalName="Inocybe erubescens", genus="Inosperma",
        ),
    )
    assert verdict.accepted
    assert verdict.usage_key == 10776858, "must follow to the accepted usage"
    assert verdict.synonym
    assert "10776858" in verdict.reason


def test_a_synonym_with_nowhere_to_follow_is_refused():
    verdict = judge_match(
        "Something obsoletum", match_payload(status="SYNONYM", acceptedUsageKey=None)
    )
    assert not verdict.accepted
    assert verdict.usage_key is None


def test_image_source_any_lifts_the_dataset_restriction(tmp_path):
    """The ivory funnels have zero iNaturalist images and 1,300 elsewhere.

    So `image_source: "any"` drops the datasetKey filter for that species
    alone. Every other species keeps it, because the research-grade
    property comes from iNaturalist's publication policy and widening
    trades it away.
    """
    path = seed_taxonomy(
        tmp_path,
        [
            {"key": "clitocybe-rivulosa", "scientific_name": "Clitocybe rivulosa",
             "toxicity": "DEADLY", "gbif_key": 2531052, "image_source": "any"},
            {"key": "amanita-phalloides", "scientific_name": "Amanita phalloides",
             "toxicity": "DEADLY", "gbif_key": 5240325},
        ],
    )
    quotas = {q.key: q for q in load_quotas(path, 100, session=StubSession())}
    assert quotas["clitocybe-rivulosa"].dataset_key is None
    assert quotas["amanita-phalloides"].dataset_key == INATURALIST_DATASET_KEY


def test_an_unknown_image_source_is_refused(tmp_path):
    path = seed_taxonomy(
        tmp_path,
        [{"key": "x", "scientific_name": "Amanita phalloides", "toxicity": "DEADLY",
          "gbif_key": 1, "image_source": "flickr"}],
    )
    with pytest.raises(ValueError, match="flickr"):
        load_quotas(path, 100, session=StubSession())


def test_the_manifest_records_which_dataset_each_image_came_from(tmp_path, monkeypatch):
    """Provenance has to survive into the manifest, or the widening is invisible."""
    import fungi_ml.data.sources as sources

    monkeypatch.setattr(sources, "_session", lambda: StubSession(
        pages=[{"results": [occurrence(1, datasetKey="abc-123")], "endOfRecords": True}]
    ))
    frame, _ = build([], tmp_path=tmp_path)
    assert frame["dataset_key"].tolist() == ["abc-123"]


def test_two_species_may_not_claim_the_same_taxon(tmp_path):
    """Following synonyms can merge two of our species onto one key.

    GBIF treats Clitocybe dealbata as a synonym of C. rivulosa, and this
    taxonomy carries both as DEADLY species. Downloaded together they would
    file every image under both labels -- silent label noise the
    risk-weighted objective cannot see.
    """
    path = seed_taxonomy(
        tmp_path,
        [
            {"key": "clitocybe-dealbata", "scientific_name": "Clitocybe dealbata",
             "toxicity": "DEADLY", "gbif_key": None},
            {"key": "clitocybe-rivulosa", "scientific_name": "Clitocybe rivulosa",
             "toxicity": "DEADLY", "gbif_key": None},
        ],
    )
    session = StubSession({
        "Clitocybe dealbata": match_payload(
            usageKey=2531056, acceptedUsageKey=2531052, status="SYNONYM",
            canonicalName="Clitocybe dealbata"),
        "Clitocybe rivulosa": match_payload(
            usageKey=2531052, canonicalName="Clitocybe rivulosa"),
    })
    with pytest.raises(CollidingTaxonKeys) as exc:
        load_quotas(path, 100, session=session)
    assert "2531052" in str(exc.value)


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
        # The forms the live API actually returns. Every one of 300 real
        # records sampled carried the /legalcode suffix, which the original
        # positional parser read as version="legalcode" and rejected -- so
        # the fetcher would have refused every image in the dataset and
        # blamed the network. These three are not hypothetical variants;
        # they are the whole population.
        "http://creativecommons.org/licenses/by-nc/4.0/legalcode",
        "http://creativecommons.org/licenses/by/4.0/legalcode",
        "http://creativecommons.org/publicdomain/zero/1.0/legalcode",
        "https://creativecommons.org/licenses/by/4.0/deed.en",
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
        "http://creativecommons.org/licenses/by-nd/4.0/legalcode",
        "http://creativecommons.org/licenses/by-nc-nd/4.0/legalcode",
        "All rights reserved",
    ],
)
def test_closed_or_unstated_licences_are_refused(raw):
    """An absent licence is refused: unknown terms are not permissive terms."""
    assert not _licence_accepted(raw)


# --- research grade ----------------------------------------------------------


def test_a_record_with_no_verification_field_is_kept():
    """The live API omits the field entirely, on 300 of 300 records sampled.

    An earlier version of this required it to equal "Research Grade", which
    would have discarded the whole dataset while looking like quality
    control. Absence is not rejection: the research-grade property comes
    from iNaturalist's publication policy, not from anything this code can
    check.
    """
    assert _research_grade({})
    assert _research_grade({"identificationVerificationStatus": None})


def test_an_explicitly_lower_grade_is_rejected():
    assert not _research_grade({"identificationVerificationStatus": "Needs ID"})
    assert not _research_grade({"identificationVerificationStatus": "casual"})
    assert _research_grade({"identificationVerificationStatus": RESEARCH_GRADE})


# --- the manifest ------------------------------------------------------------


def occurrence(key: int, n_images: int = 1, **overrides) -> dict:
    occ = {
        "key": key,
        # Shaped like the live API: licence URL with /legalcode, and no
        # identificationVerificationStatus field at all.
        "license": "http://creativecommons.org/licenses/by-nc/4.0/legalcode",
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
                occurrence(2, license="http://creativecommons.org/licenses/by-nd/4.0/legalcode"),
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
                "toxicity": "NO_RECORDED_TOXICITY",
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
                "toxicity": "NO_RECORDED_TOXICITY",
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


# Keys set by hand, with the reason. A hand-set key skips GBIF's matcher
# entirely, so each one is a claim somebody has to stand behind.
HAND_SET_KEYS = {
    # /species/match falls back to the Fungi KINGDOM -- four authorships,
    # three DOUBTFUL.
    "Helvella crispa": 2554614,
    # Pinned to their own usage rather than following acceptedUsageKey,
    # because following it would collide two label-space species onto one
    # taxon. Martin's decision, 2026-09-23: keep them separate.
    "Clitocybe dealbata": 2531056,   # GBIF: synonym of C. rivulosa
    "Inocybe lilacina": 3331644,     # GBIF: synonym of I. geophylla
}


def test_hand_set_gbif_keys_are_the_expected_ones(tmp_path):
    """A hand-set key bypasses every check in `judge_match`.

    So the set of them is pinned here rather than left to drift. Adding one
    means adding it above with the reason it could not be resolved.
    """
    raw = json.loads((ROOT / "data" / "taxonomy.seed.json").read_text(encoding="utf-8"))
    declared = {
        s["scientific_name"]: s["gbif_key"]
        for s in raw["species"]
        if s.get("gbif_key") is not None
    }
    assert declared == HAND_SET_KEYS


def test_a_species_losing_every_image_is_reported_loudly(tmp_path, caplog):
    """A silent download failure leaves a healthy-looking manifest.

    On the first live run the ivory funnels lost 24 of 24 images, because
    their photographs live on svampe.databasen.org, mushroomobserver.org
    and artsobservasjoner.no rather than the iNaturalist CDN, and the
    sandbox allowed only the latter. The run printed "Retained 59 of 83"
    and carried on. Two DEADLY species had silently left the dataset.
    """
    import logging

    import pandas as pd

    from fungi_ml.data.sources import fetch_images

    manifest = pd.DataFrame(
        [
            {"species_key": "gone", "image_url": "https://blocked.example/a.jpg"},
            {"species_key": "gone", "image_url": "https://blocked.example/b.jpg"},
        ]
    )
    with caplog.at_level(logging.WARNING):
        kept = fetch_images(manifest, tmp_path / "img", workers=2)

    assert kept.empty
    text = caplog.text
    assert "blocked.example" in text, "must name the host that failed"
    assert "gone" in text, "must name the species that vanished"
    assert any(r.levelno >= logging.ERROR for r in caplog.records), (
        "a species losing every image is an error, not a warning"
    )


def test_a_transient_page_failure_is_retried(monkeypatch):
    """One reset must not cost a species its whole quota.

    Observed live: Agaricus arvensis -- the horse mushroom, and a death cap
    lookalike -- hit a ConnectionResetError at offset 0. The paging loop
    caught it, broke, kept the nothing it had collected, and the run
    carried on to the next species.
    """
    import fungi_ml.data.sources as sources

    monkeypatch.setattr(sources.time, "sleep", lambda _: None)
    calls = {"n": 0}

    class Flaky:
        def get(self, url, params=None, timeout=None):
            calls["n"] += 1
            if calls["n"] < 3:
                raise requests.ConnectionError("Connection reset by peer")
            return StubResponse({"results": [], "endOfRecords": True})

    page = sources._occurrence_page(Flaky(), 1, 0, 300, None)
    assert page["endOfRecords"] is True
    assert calls["n"] == 3, "should have retried twice before succeeding"


def test_paging_gives_up_after_the_retry_budget(monkeypatch):
    import fungi_ml.data.sources as sources

    monkeypatch.setattr(sources.time, "sleep", lambda _: None)
    calls = {"n": 0}

    class Dead:
        def get(self, *a, **k):
            calls["n"] += 1
            raise requests.ConnectionError("down")

    with pytest.raises(requests.RequestException):
        sources._occurrence_page(Dead(), 1, 0, 300, None)
    assert calls["n"] == sources.PAGE_RETRIES


def test_a_species_cut_short_by_gbif_is_reported(tmp_path, monkeypatch, caplog):
    """A truncated species looks identical to a rare one in the manifest."""
    import logging

    import fungi_ml.data.sources as sources

    monkeypatch.setattr(sources.time, "sleep", lambda _: None)

    class HalfDead:
        """Serves one good page for the first species, then dies."""

        def __init__(self):
            self.served = 0

        def get(self, url, params=None, timeout=None):
            if params.get("taxonKey") == 1 and self.served == 0:
                self.served += 1
                return StubResponse(
                    {"results": [occurrence(1, n_images=2)], "endOfRecords": True}
                )
            raise requests.ConnectionError("down")

    monkeypatch.setattr(sources, "_session", HalfDead)
    quotas = [
        SpeciesQuota(key="fine", scientific_name="A b", gbif_key=1, target=50),
        SpeciesQuota(key="cut-short", scientific_name="C d", gbif_key=2, target=50),
    ]
    with caplog.at_level(logging.ERROR):
        sources.build_manifest(quotas, tmp_path / "m.parquet", sleep_between_pages=0.0)

    assert "cut-short" in caplog.text
    assert "did NOT reach their quota" in caplog.text
