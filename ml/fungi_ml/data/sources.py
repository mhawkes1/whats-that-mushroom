"""Dataset acquisition.

Two supported sources, both openly licensed:

  GBIF   -- occurrence records with media, filtered to research-grade
            iNaturalist observations. Gives us geolocation and date, which
            the model consumes as auxiliary inputs.
  DF20   -- the Danish Fungi 2020 benchmark. Expert-verified, which makes it
            the cleaner signal, but Denmark-biased.

Nothing here downloads images at import time. Call `build_manifest` to emit a
parquet manifest, then `fetch_images` to materialise it. Keeping the two
steps apart means a failed download resumes rather than restarting.
"""

from __future__ import annotations

import concurrent.futures
import hashlib
import io
import json
import logging
import time
from dataclasses import dataclass
from pathlib import Path

import pandas as pd
import requests
from PIL import Image

log = logging.getLogger(__name__)

GBIF_API = "https://api.gbif.org/v1"
INATURALIST_DATASET_KEY = "50c9509d-22c7-4a22-a47d-8c48425ef4a7"

# Licences we will redistribute a derived model from. Deliberately excludes
# ND (no-derivatives) and anything unstated.
ACCEPTED_LICENCES = {
    "CC0_1_0",
    "CC_BY_4_0",
    "CC_BY_NC_4_0",
}


USER_AGENT = "whats-that-mushroom/0.1 (dataset builder; +https://github.com/mhawkes1)"

# GBIF republishes iNaturalist records at several verification levels. Only
# research-grade observations have had a second identifier agree, and an
# unverified one is a stranger's guess -- exactly the kind of label this
# project exists to distrust.
RESEARCH_GRADE = "Research Grade"


def _session() -> requests.Session:
    session = requests.Session()
    session.headers["User-Agent"] = USER_AGENT
    return session


@dataclass
class SpeciesQuota:
    key: str
    scientific_name: str
    gbif_key: int
    target: int


# A match below this confidence is not trusted without a human looking at it.
# GBIF reports confidence 0-100; an exact hit on a well-known binomial scores
# in the high 90s.
MIN_MATCH_CONFIDENCE = 95

# Match types GBIF may return. Only EXACT is auto-accepted. FUZZY corrects
# spelling, and fungal binomials differ by a letter or two across genuinely
# different species, so a fuzzy hit is a question for a human, not a result.
AUTO_ACCEPTED_MATCH_TYPES = frozenset({"EXACT"})


@dataclass(frozen=True)
class TaxonMatch:
    """What GBIF said when asked about one of our species, and whether we believe it.

    Kept as a record rather than collapsed to an integer because the
    interesting cases are the refusals, and a caller that only sees `None`
    cannot tell a species GBIF has never heard of from one it answered at the
    wrong rank.
    """

    scientific_name: str
    usage_key: int | None = None
    matched_name: str | None = None
    rank: str | None = None
    match_type: str | None = None
    confidence: int | None = None
    status: str | None = None
    synonym: bool = False
    accepted: bool = False
    reason: str = ""

    def as_record(self) -> dict:
        return {
            "scientific_name": self.scientific_name,
            "usage_key": self.usage_key,
            "matched_name": self.matched_name,
            "rank": self.rank,
            "match_type": self.match_type,
            "confidence": self.confidence,
            "status": self.status,
            "synonym": self.synonym,
            "accepted": self.accepted,
            "reason": self.reason,
        }


def judge_match(scientific_name: str, payload: dict) -> TaxonMatch:
    """Decide whether a GBIF match may be used to download images for a species.

    This is the whole safety argument of the fetcher, so it is a pure
    function of the payload and tested without a network.

    The refusal that matters is `rank != SPECIES`. GBIF's occurrence search
    is inclusive of descendants, so a genus-rank `usageKey` does not fetch
    nothing -- it fetches *the entire genus* under one species label. A
    failed match on `Amanita rubescens` that fell back to `Amanita` would
    file every death cap in Britain as a blusher, and nothing downstream
    would notice: the counts would look healthy and the images would look
    like mushrooms.
    """
    match_type = payload.get("matchType")
    rank = payload.get("rank")
    key = payload.get("usageKey")
    matched = payload.get("canonicalName") or payload.get("scientificName")
    confidence = payload.get("confidence")
    common = {
        "scientific_name": scientific_name,
        "usage_key": key,
        "matched_name": matched,
        "rank": rank,
        "match_type": match_type,
        "confidence": confidence,
        "status": payload.get("status"),
        "synonym": bool(payload.get("synonym")),
    }

    def refuse(reason: str) -> TaxonMatch:
        return TaxonMatch(**{**common, "usage_key": None, "accepted": False, "reason": reason})

    if match_type in (None, "NONE"):
        return refuse("GBIF has no match for this name")
    if rank != "SPECIES":
        return refuse(
            f"matched at rank {rank!r}, not SPECIES -- that key would fetch the whole {rank.lower() if rank else 'clade'}"
        )
    if key is None:
        return refuse("match carried no usageKey")
    if match_type not in AUTO_ACCEPTED_MATCH_TYPES:
        return refuse(f"match type {match_type!r} needs a human to confirm the species")
    if confidence is not None and confidence < MIN_MATCH_CONFIDENCE:
        return refuse(f"confidence {confidence} is below {MIN_MATCH_CONFIDENCE}")

    reason = "exact match"
    if common["synonym"]:
        # Legitimate and common -- the backbone moves species between genera
        # faster than field guides do. Worth recording, because the manifest
        # will carry our name and the images will have been filed under GBIF's.
        reason = f"exact match to {matched}, which GBIF treats as the accepted name"
    return TaxonMatch(**{**common, "usage_key": int(key), "accepted": True, "reason": reason})


def resolve_species(scientific_name: str, session: requests.Session) -> TaxonMatch:
    """Ask GBIF for a taxon key, and judge the answer before returning it."""
    try:
        resp = session.get(
            f"{GBIF_API}/species/match",
            params={"name": scientific_name, "kingdom": "Fungi", "strict": "false"},
            timeout=30,
        )
        resp.raise_for_status()
        payload = resp.json()
    except requests.RequestException as exc:
        return TaxonMatch(scientific_name=scientific_name, reason=f"GBIF request failed: {exc}")

    match = judge_match(scientific_name, payload)
    if not match.accepted:
        log.warning("Refused GBIF match for %s: %s", scientific_name, match.reason)
    return match


def _licence_accepted(raw: str | None) -> bool:
    """Normalise a GBIF licence value and test it against the allow-list.

    GBIF returns either an enum ("CC_BY_4_0") or a Creative Commons URL
    ("http://creativecommons.org/licenses/by-nc/4.0/") depending on which
    route served the record. An absent licence is rejected: we cannot
    redistribute a model derived from images whose terms are unknown.
    """
    if not raw:
        return False
    if raw in ACCEPTED_LICENCES:
        return True
    if "creativecommons.org" not in raw:
        return False
    parts = [p for p in raw.rstrip("/").split("/") if p]
    if len(parts) < 2:
        return False
    version, code = parts[-1], parts[-2]
    if code == "zero":
        code, version = "cc0", "1.0"
    normalised = f"{'CC0' if code == 'cc0' else 'CC_' + code.upper().replace('-', '_')}_{version.replace('.', '_')}"
    return normalised in ACCEPTED_LICENCES


def _research_grade(occ: dict) -> bool:
    """Keep only observations a second identifier has agreed with.

    GBIF's iNaturalist dataset is *mostly* research-grade, which is why the
    old docstring could claim this filter without anyone noticing it was
    absent. Mostly is not a filter.
    """
    return occ.get("identificationVerificationStatus") == RESEARCH_GRADE


def _occurrence_page(
    session: requests.Session, taxon_key: int, offset: int, limit: int, country: str | None
) -> dict:
    params = {
        "taxonKey": taxon_key,
        "datasetKey": INATURALIST_DATASET_KEY,
        "mediaType": "StillImage",
        "hasCoordinate": "true",
        "occurrenceStatus": "PRESENT",
        "limit": limit,
        "offset": offset,
    }
    if country:
        params["country"] = country
    resp = session.get(f"{GBIF_API}/occurrence/search", params=params, timeout=60)
    resp.raise_for_status()
    return resp.json()


def build_manifest(
    quotas: list[SpeciesQuota],
    out_path: str | Path,
    country: str | None = None,
    page_size: int = 300,
    sleep_between_pages: float = 0.2,
    max_images_per_observation: int = 4,
) -> pd.DataFrame:
    """Page the GBIF occurrence API and emit one row per usable image.

    The manifest carries the auxiliary features the model conditions on --
    month, latitude, longitude -- alongside the image URL. `observation_id`
    groups images of the same fruiting body so the splitter can keep them
    together.
    """
    session = _session()

    rows: list[dict] = []
    for quota in quotas:
        collected = 0
        offset = 0
        by_observation: dict[str, list[str]] = {}
        while collected < quota.target:
            try:
                page = _occurrence_page(
                    session, quota.gbif_key, offset, page_size, country
                )
            except requests.RequestException as exc:
                log.error("GBIF page failed for %s at offset %d: %s", quota.key, offset, exc)
                break

            results = page.get("results", [])
            if not results:
                break

            for occ in results:
                if not _licence_accepted(occ.get("license")):
                    continue
                if not _research_grade(occ):
                    continue
                observation_id = str(occ.get("key"))

                for media in occ.get("media", []):
                    url = media.get("identifier")
                    if not url:
                        continue
                    taken = by_observation.setdefault(observation_id, [])
                    if len(taken) >= max_images_per_observation:
                        break
                    rows.append(
                        {
                            "species_key": quota.key,
                            "scientific_name": quota.scientific_name,
                            "gbif_key": quota.gbif_key,
                            "observation_id": observation_id,
                            "image_url": url,
                            "licence": occ.get("license"),
                            "rights_holder": occ.get("rightsHolder"),
                            "latitude": occ.get("decimalLatitude"),
                            "longitude": occ.get("decimalLongitude"),
                            "month": occ.get("month"),
                            "year": occ.get("year"),
                            "country_code": occ.get("countryCode"),
                            "identification_verified": occ.get("identificationVerificationStatus"),
                        }
                    )
                    taken.append(url)
                    collected += 1
                    if collected >= quota.target:
                        break
                if collected >= quota.target:
                    break

            offset += page_size
            if page.get("endOfRecords"):
                break
            time.sleep(sleep_between_pages)

        log.info(
            "%s: %d images across %d observations",
            quota.key,
            collected,
            len(by_observation),
        )

    frame = pd.DataFrame(rows)
    if frame.empty:
        raise RuntimeError("Manifest is empty -- check taxon keys and network access.")

    frame = frame.drop_duplicates(subset=["image_url"])
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_parquet(out_path, index=False)
    log.info("Wrote %d rows to %s", len(frame), out_path)
    return frame


def _local_path(image_root: Path, species_key: str, url: str) -> Path:
    digest = hashlib.sha1(url.encode("utf-8")).hexdigest()[:16]
    return image_root / species_key / f"{digest}.jpg"


def _fetch_one(
    session: requests.Session, row: dict, image_root: Path, max_edge: int
) -> tuple[str, str | None]:
    dest = _local_path(image_root, row["species_key"], row["image_url"])
    if dest.exists():
        return row["image_url"], str(dest)

    try:
        resp = session.get(row["image_url"], timeout=45)
        resp.raise_for_status()
        img = Image.open(io.BytesIO(resp.content))
        img = img.convert("RGB")
        # Downscale on ingest. Full-resolution iNaturalist images are far
        # larger than any input size we train at, and storing them wastes
        # both disk and dataloader time.
        if max(img.size) > max_edge:
            scale = max_edge / max(img.size)
            img = img.resize(
                (round(img.width * scale), round(img.height * scale)),
                Image.Resampling.LANCZOS,
            )
        dest.parent.mkdir(parents=True, exist_ok=True)
        img.save(dest, "JPEG", quality=92)
        return row["image_url"], str(dest)
    except Exception as exc:  # noqa: BLE001 - one bad image must not stop the run
        log.debug("Failed %s: %s", row["image_url"], exc)
        return row["image_url"], None


def fetch_images(
    manifest: pd.DataFrame,
    image_root: str | Path,
    max_edge: int = 800,
    workers: int = 16,
) -> pd.DataFrame:
    """Download every image in the manifest, returning it with a `path` column.

    Rows whose download failed are dropped. Re-running is cheap because
    existing files are detected and skipped.
    """
    image_root = Path(image_root)
    image_root.mkdir(parents=True, exist_ok=True)

    session = _session()

    records = manifest.to_dict("records")
    resolved: dict[str, str | None] = {}

    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [
            pool.submit(_fetch_one, session, row, image_root, max_edge) for row in records
        ]
        for i, fut in enumerate(concurrent.futures.as_completed(futures), 1):
            url, path = fut.result()
            resolved[url] = path
            if i % 500 == 0:
                log.info("fetched %d/%d", i, len(futures))

    manifest = manifest.copy()
    manifest["path"] = manifest["image_url"].map(resolved)
    ok = manifest[manifest["path"].notna()].reset_index(drop=True)
    log.info("Retained %d of %d images", len(ok), len(manifest))
    return ok


class UnresolvedDeadlySpecies(RuntimeError):
    """Raised when a species that can kill could not be resolved to a taxon key.

    Dropping it is not a smaller dataset, it is a hole in the safety layer:
    a species the model cannot name is one the app cannot warn about, and
    every lookalike edge pointing at it goes slack. The build stops so a
    human decides, rather than discovering it in the model card.
    """


def resolve_label_space(
    taxonomy_path: str | Path,
    session: requests.Session | None = None,
    cache_path: str | Path | None = None,
    sleep_between: float = 0.1,
) -> list[TaxonMatch]:
    """Resolve every species in the taxonomy, reusing a cache of past answers.

    The cache is a plain JSON file meant to be read: resolution is the step
    where a name silently becomes the wrong fungus, and the only defence
    against that is somebody looking at the refusals.
    """
    raw = json.loads(Path(taxonomy_path).read_text(encoding="utf-8"))
    cached: dict[str, dict] = {}
    cache_path = Path(cache_path) if cache_path else None
    if cache_path and cache_path.exists():
        cached = {
            r["scientific_name"]: r
            for r in json.loads(cache_path.read_text(encoding="utf-8"))["matches"]
        }

    session = session or _session()
    matches: list[TaxonMatch] = []
    for entry in raw["species"]:
        name = entry["scientific_name"]
        declared = entry.get("gbif_key")
        if declared is not None:
            matches.append(
                TaxonMatch(
                    scientific_name=name,
                    usage_key=int(declared),
                    matched_name=name,
                    rank="SPECIES",
                    match_type="DECLARED",
                    accepted=True,
                    reason="gbif_key set in the taxonomy",
                )
            )
            continue
        if name in cached:
            matches.append(TaxonMatch(**cached[name]))
            continue
        matches.append(resolve_species(name, session))
        time.sleep(sleep_between)

    if cache_path:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(
            json.dumps(
                {
                    "note": (
                        "Resolved GBIF taxon keys. Refused entries are listed with "
                        "the reason; fix them by setting gbif_key on the species in "
                        "data/taxonomy.seed.json after checking the key by hand."
                    ),
                    "matches": [m.as_record() for m in matches],
                },
                indent=2,
            ),
            encoding="utf-8",
        )
    return matches


def load_quotas(
    taxonomy_path: str | Path,
    target_per_species: int,
    session: requests.Session | None = None,
    cache_path: str | Path | None = None,
    allow_unresolved_deadly: bool = False,
) -> list[SpeciesQuota]:
    """Build download quotas from the seed taxonomy, resolving GBIF keys.

    Species GBIF would not confirm are dropped, loudly. If one of them can
    kill, the build stops instead -- see `UnresolvedDeadlySpecies`.
    """
    raw = json.loads(Path(taxonomy_path).read_text(encoding="utf-8"))
    toxicity = {e["scientific_name"]: e.get("toxicity") for e in raw["species"]}
    by_name = {e["scientific_name"]: e for e in raw["species"]}

    matches = resolve_label_space(taxonomy_path, session=session, cache_path=cache_path)

    quotas: list[SpeciesQuota] = []
    refused: list[TaxonMatch] = []
    for match in matches:
        if not match.accepted or match.usage_key is None:
            refused.append(match)
            continue
        entry = by_name[match.scientific_name]
        quotas.append(
            SpeciesQuota(
                key=entry["key"],
                scientific_name=match.scientific_name,
                gbif_key=match.usage_key,
                target=target_per_species,
            )
        )

    if refused:
        log.warning("Dropped %d species GBIF would not confirm:", len(refused))
        for match in refused:
            log.warning("  %-40s %s", match.scientific_name, match.reason)

    lethal = [m for m in refused if toxicity.get(m.scientific_name) == "DEADLY"]
    if lethal and not allow_unresolved_deadly:
        names = ", ".join(f"{m.scientific_name} ({m.reason})" for m in lethal)
        raise UnresolvedDeadlySpecies(
            f"{len(lethal)} DEADLY species could not be resolved: {names}. "
            "Set gbif_key by hand in data/taxonomy.seed.json, or pass "
            "allow_unresolved_deadly=True having decided the app may not name them."
        )

    log.info("Resolved %d of %d species", len(quotas), len(matches))
    return quotas
