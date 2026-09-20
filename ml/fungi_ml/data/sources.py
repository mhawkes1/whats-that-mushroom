"""Dataset acquisition.

Two supported sources, both openly licensed:

  GBIF   -- occurrence records with media, filtered to research-grade
            iNaturalist observations. Gives us geolocation, date and often
            substrate, which the model consumes as auxiliary inputs.
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


@dataclass
class SpeciesQuota:
    key: str
    scientific_name: str
    gbif_key: int
    target: int


def resolve_gbif_key(scientific_name: str, session: requests.Session) -> int | None:
    """Look up the GBIF backbone taxon key for a scientific name."""
    resp = session.get(
        f"{GBIF_API}/species/match",
        params={"name": scientific_name, "kingdom": "Fungi", "strict": "false"},
        timeout=30,
    )
    resp.raise_for_status()
    payload = resp.json()
    if payload.get("matchType") == "NONE":
        log.warning("No GBIF match for %s", scientific_name)
        return None
    if payload.get("rank") != "SPECIES":
        log.warning(
            "GBIF matched %s at rank %s, not SPECIES", scientific_name, payload.get("rank")
        )
    return payload.get("usageKey")


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
) -> pd.DataFrame:
    """Page the GBIF occurrence API and emit one row per usable image.

    The manifest carries the auxiliary features the model conditions on --
    month, latitude, longitude -- alongside the image URL. `observation_id`
    groups images of the same fruiting body so the splitter can keep them
    together.
    """
    session = requests.Session()
    session.headers["User-Agent"] = "whats-that-mushroom/0.1 (dataset builder; +https://github.com/mhawkes1)"

    rows: list[dict] = []
    for quota in quotas:
        collected = 0
        offset = 0
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

                for media in occ.get("media", []):
                    url = media.get("identifier")
                    if not url:
                        continue
                    rows.append(
                        {
                            "species_key": quota.key,
                            "scientific_name": quota.scientific_name,
                            "gbif_key": quota.gbif_key,
                            "observation_id": str(occ.get("key")),
                            "image_url": url,
                            "licence": occ.get("license"),
                            "rights_holder": occ.get("rightsHolder"),
                            "latitude": occ.get("decimalLatitude"),
                            "longitude": occ.get("decimalLongitude"),
                            "month": occ.get("month"),
                            "year": occ.get("year"),
                            "country_code": occ.get("countryCode"),
                            "substrate": occ.get("substrate"),
                            "identification_verified": occ.get("identificationVerificationStatus"),
                        }
                    )
                    collected += 1
                    if collected >= quota.target:
                        break
                if collected >= quota.target:
                    break

            offset += page_size
            if page.get("endOfRecords"):
                break
            time.sleep(sleep_between_pages)

        log.info("%s: %d images queued", quota.key, collected)

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

    session = requests.Session()
    session.headers["User-Agent"] = "whats-that-mushroom/0.1 (dataset builder; +https://github.com/mhawkes1)"

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


def load_quotas(
    taxonomy_path: str | Path, target_per_species: int, resolve_missing: bool = True
) -> list[SpeciesQuota]:
    """Build download quotas from the seed taxonomy, resolving GBIF keys."""
    raw = json.loads(Path(taxonomy_path).read_text(encoding="utf-8"))
    session = requests.Session()
    session.headers["User-Agent"] = "whats-that-mushroom/0.1 (dataset builder; +https://github.com/mhawkes1)"

    quotas: list[SpeciesQuota] = []
    for entry in raw["species"]:
        gbif_key = entry.get("gbif_key")
        if gbif_key is None and resolve_missing:
            gbif_key = resolve_gbif_key(entry["scientific_name"], session)
            time.sleep(0.1)
        if gbif_key is None:
            log.warning("Skipping %s -- no GBIF key", entry["key"])
            continue
        quotas.append(
            SpeciesQuota(
                key=entry["key"],
                scientific_name=entry["scientific_name"],
                gbif_key=int(gbif_key),
                target=target_per_species,
            )
        )
    return quotas
