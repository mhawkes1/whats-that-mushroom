"""The Learn card photographs, and the tag that nearly shipped sideways.

`scripts/build_learn_images.py` turns Martin's originals into the five
cards the app bundles. The originals are not in the repository -- they are
24 MP files on his machine -- so anything baked in wrongly here is
permanent unless he runs the ingest again, which is why the ingest step is
in the script rather than in somebody's shell history.
"""

from __future__ import annotations

import pathlib
import re

from PIL import Image

ROOT = pathlib.Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "build_learn_images.py"
SRC = ROOT / "docs" / "design" / "learn"
CARDS = ROOT / "app" / "assets" / "learn"


def _card_names() -> list[str]:
    body = SCRIPT.read_text(encoding="utf-8")
    block = body[body.index("CARDS: dict[str, tuple[str, float]] = {"):]
    block = block[: block.index("}")]
    return re.findall(r'"([a-z-]+)":\s*\(', block)


def _sources() -> list[str]:
    body = SCRIPT.read_text(encoding="utf-8")
    block = body[body.index("CARDS: dict[str, tuple[str, float]] = {"):]
    block = block[: block.index("}")]
    return sorted(set(re.findall(r'\(\s*"([a-z-]+)"\s*,', block)))


def test_the_build_applies_exif_orientation_before_anything_else():
    """The one that shipped a sideways card for a day.

    Two of the six frames carry `Orientation: 8` -- stored 6000x4000
    landscape, meant to be shown 4000x6000 portrait. `Image.open().size`
    reports what is STORED, so downscaling and stripping metadata without
    reading the tag bakes in a 90-degree rotation. The scarlet elf cups
    went out that way on 2026-11-21 and nothing caught it, because leaf
    litter has no horizon.

    Read from the source rather than exercised, for the same reason the
    connection-pool test is: the guard is that the call is THERE, on both
    paths, and a round trip through a fixture would pass on an upright
    fixture whatever the code did.
    """
    body = SCRIPT.read_text(encoding="utf-8")
    assert "ImageOps.exif_transpose" in body, (
        "orientation must be applied, or a portrait photograph ships sideways"
    )
    # Both the ingest and the crop go through it.
    assert body.count("upright(") >= 3, (
        "every read of a photograph goes through `upright`, not Image.open"
    )
    assert "Image.open(SRC /" not in body, (
        "a direct open in the crop path skips the orientation tag"
    )


def test_every_card_has_a_source_and_every_source_is_used():
    missing = [s for s in _sources() if not (SRC / f"{s}.jpg").exists()]
    assert not missing, f"no committed source for {missing}"

    spare = sorted(p.stem for p in SRC.glob("*.jpg") if p.stem not in _sources())
    assert not spare, f"committed sources nothing builds from: {spare} -- delete or use"


def test_every_card_is_built_and_is_the_shape_the_screens_expect():
    # 780x585 is 4:3 at the 390pt reference card width. The screens set a
    # real height of 256 to match; a card of another shape means `cover`
    # starts cropping again, which is how the stems came off.
    for name in _card_names():
        path = CARDS / f"{name}.jpg"
        assert path.exists(), f"{path.name} is missing -- run build_learn_images.py"
        with Image.open(path) as im:
            assert im.size == (780, 585), f"{path.name} is {im.size}, expected (780, 585)"
            assert not im.getexif(), f"{path.name} carries EXIF"


def test_the_sources_are_stored_upright():
    """Portrait sources must be taller than they are wide, on disk.

    The ingest applies the orientation tag and then writes a fresh image,
    so a correctly ingested portrait frame is portrait in the file. This
    catches a source re-added by hand from an original without the ingest
    -- which is exactly what happened, and the only visible symptom was a
    card that looked a bit odd.
    """
    shapes = {p.stem: Image.open(p).size for p in SRC.glob("*.jpg")}
    assert shapes, "no committed sources"
    for stem, (w, h) in shapes.items():
        assert max(w, h) <= 2000, f"{stem}.jpg is {w}x{h}; sources are 2000px on the long edge"
    # The two that are portrait after their orientation tag is honoured.
    for stem in ("amanita", "elfcups"):
        w, h = shapes[stem]
        assert h > w, (
            f"{stem}.jpg is stored {w}x{h} -- landscape. It is a PORTRAIT frame; "
            "it was ingested without ImageOps.exif_transpose and is rotated 90 degrees."
        )
