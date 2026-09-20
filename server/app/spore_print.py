"""Spore print colour matching.

A spore print is the most decisive test available to a forager without a
microscope, and it is the one the interrogation engine asks for when a lethal
ambiguity turns on it. Until now the app could ask for a spore print and then
offer six words to choose between. This module is the other half: it takes
what the user photographed and tells them which of those six it looks like.

The photograph is taken against the half-white, half-black card the
instructions already ask for. The white half is a known neutral, so it doubles
as a white-balance reference -- kitchen lighting runs anywhere from 2700K
tungsten to overcast daylight, and an uncorrected "white or cream" under a
warm bulb measures as distinctly cream, which is a different answer.

The caller samples two patches and sends their mean sRGB values. All the
judgement lives here, on the server, for two reasons:

  * The six answer strings are defined in `characters.py`. A second copy in
    the client would drift, and the drift would be silent -- the client would
    submit an answer string `/answer` does not recognise.
  * Deciding whether a match may be asserted at all is a safety decision, and
    safety decisions belong where the tests are.

## Why this refuses so readily

Spore print colour separates deadly species from edible lookalikes: white for
*Amanita*, chocolate-brown for a mature *Agaricus*. A confident wrong answer
in the reassuring direction is the exact failure this project exists to avoid,
and a phone camera pointed at a thin dust deposit under domestic lighting is
not a colorimeter.

So the match is a suggestion, never a submission. `confident` is false
whenever the reference card is unusable, whenever two colours are too close to
call, and whenever nothing on the chart fits. In every one of those cases the
user picks from the list by eye, unaided -- which is exactly where they were
before this module existed, so refusing costs them nothing.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

# The chart. Keys are the `spore_print_colour` options from `characters.py`
# verbatim, because the matched key is submitted straight back to `/answer`.
#
# These sRGB values are approximations of a spore deposit viewed on white
# paper, not measured colorimetry, and they carry the same review status as
# the rest of the reference data: unreviewed. See `docs/REVIEW.md`.
REFERENCE_CHART: dict[str, tuple[int, int, int]] = {
    "White or cream": (245, 240, 228),
    "Pink": (226, 186, 180),
    "Rust or cinnamon brown": (166, 104, 56),
    "Chocolate or purple-brown": (88, 62, 58),
    "Black": (38, 35, 34),
    "Olive or yellow": (170, 160, 80),
}

# What the card's white half should render as in a well-exposed photograph.
# The correction scales the sample so the card lands here, which normalises
# exposure and colour cast in one step -- both matter, because a chart match
# is a distance in a space that includes lightness. Correcting only the cast
# leaves a dimly-lit white print reading as mid-grey, which matches nothing.
REFERENCE_WHITE_LEVEL = 243.0

# A white card that measures darker than this was photographed too dim to
# correct from; the correction would amplify sensor noise into a hue.
MIN_WHITE_LEVEL = 60.0

# A white card at or near saturation has been clipped. The true value is
# unknowable -- any channel that hit 255 may have been far brighter -- so the
# ratio between channels is no longer a white-balance reference.
MAX_WHITE_LEVEL = 250.0

# The largest channel imbalance we will correct. Beyond this the light is so
# strongly coloured (sodium street lighting, a phone torch through a shade)
# that correction is guesswork.
MAX_WHITE_CAST = 1.8

# Perceptual distance, CIEDE2000. Roughly: under 1 is invisible, 2-3 is a
# noticeable difference, over 5 reads as a different colour.
#
# `AMBIGUOUS_MARGIN` is how much closer the winner must be than the runner-up
# before we will name it. It is set wide on purpose: the chart's own closest
# pair is white-to-pink, which is precisely the distinction that matters when
# an Amanita is in play.
AMBIGUOUS_MARGIN = 6.0

# Nothing on the chart is a plausible spore colour beyond this. Usually means
# the sampled patch was the card, a shadow, or the tabletop.
MAX_DISTANCE = 30.0


@dataclass(frozen=True)
class ColourMatch:
    """One chart entry and how far the sample sat from it."""

    option: str
    distance: float


@dataclass(frozen=True)
class SporePrintReading:
    """The outcome of a match attempt.

    `confident` is the only field a caller should branch on. When it is false
    the ranking is still returned -- it is useful for ordering the manual
    picker -- but it must not be presented as an answer.
    """

    confident: bool
    reason: str
    ranked: list[ColourMatch]
    corrected_rgb: tuple[int, int, int] | None

    @property
    def option(self) -> str | None:
        """The matched option, or None when no match may be asserted."""
        return self.ranked[0].option if self.confident and self.ranked else None


def _srgb_to_linear(channel: float) -> float:
    c = channel / 255.0
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def _linear_to_xyz(r: float, g: float, b: float) -> tuple[float, float, float]:
    # sRGB primaries, D65 white point.
    return (
        r * 0.4124564 + g * 0.3575761 + b * 0.1804375,
        r * 0.2126729 + g * 0.7151522 + b * 0.0721750,
        r * 0.0193339 + g * 0.1191920 + b * 0.9503041,
    )


def rgb_to_lab(rgb: tuple[float, float, float]) -> tuple[float, float, float]:
    """sRGB (0-255) to CIELAB under D65.

    Lab is used rather than RGB because RGB distance does not track what the
    eye sees: two browns a user would call the same colour can sit further
    apart in RGB than white does from pink.
    """
    r, g, b = (_srgb_to_linear(c) for c in rgb)
    x, y, z = _linear_to_xyz(r, g, b)

    # D65 reference white.
    x, y, z = x / 0.95047, y / 1.00000, z / 1.08883

    def f(t: float) -> float:
        return t ** (1 / 3) if t > 216 / 24389 else (841 / 108) * t + 4 / 29

    fx, fy, fz = f(x), f(y), f(z)
    return (116 * fy - 16, 500 * (fx - fy), 200 * (fy - fz))


def ciede2000(lab1: tuple[float, float, float], lab2: tuple[float, float, float]) -> float:
    """CIEDE2000 colour difference.

    The 1976 formula is simpler but badly overstates differences among
    near-neutral colours -- which is most of this chart, and which would make
    white, cream and pale pink look further apart than they are. Overstating
    the gap there would let an ambiguous reading pass as a confident one.
    """
    L1, a1, b1 = lab1
    L2, a2, b2 = lab2

    C1 = math.hypot(a1, b1)
    C2 = math.hypot(a2, b2)
    C_bar = (C1 + C2) / 2

    G = 0.5 * (1 - math.sqrt(C_bar**7 / (C_bar**7 + 25**7))) if C_bar > 0 else 0.5
    a1p, a2p = (1 + G) * a1, (1 + G) * a2

    C1p, C2p = math.hypot(a1p, b1), math.hypot(a2p, b2)
    h1p = math.degrees(math.atan2(b1, a1p)) % 360 if (a1p or b1) else 0.0
    h2p = math.degrees(math.atan2(b2, a2p)) % 360 if (a2p or b2) else 0.0

    dLp = L2 - L1
    dCp = C2p - C1p

    if C1p * C2p == 0:
        dhp = 0.0
    elif abs(h2p - h1p) <= 180:
        dhp = h2p - h1p
    elif h2p - h1p > 180:
        dhp = h2p - h1p - 360
    else:
        dhp = h2p - h1p + 360
    dHp = 2 * math.sqrt(C1p * C2p) * math.sin(math.radians(dhp / 2))

    Lp_bar = (L1 + L2) / 2
    Cp_bar = (C1p + C2p) / 2

    if C1p * C2p == 0:
        hp_bar = h1p + h2p
    elif abs(h1p - h2p) <= 180:
        hp_bar = (h1p + h2p) / 2
    elif h1p + h2p < 360:
        hp_bar = (h1p + h2p + 360) / 2
    else:
        hp_bar = (h1p + h2p - 360) / 2

    T = (
        1
        - 0.17 * math.cos(math.radians(hp_bar - 30))
        + 0.24 * math.cos(math.radians(2 * hp_bar))
        + 0.32 * math.cos(math.radians(3 * hp_bar + 6))
        - 0.20 * math.cos(math.radians(4 * hp_bar - 63))
    )

    d_theta = 30 * math.exp(-(((hp_bar - 275) / 25) ** 2))
    R_C = 2 * math.sqrt(Cp_bar**7 / (Cp_bar**7 + 25**7)) if Cp_bar > 0 else 0.0
    S_L = 1 + (0.015 * (Lp_bar - 50) ** 2) / math.sqrt(20 + (Lp_bar - 50) ** 2)
    S_C = 1 + 0.045 * Cp_bar
    S_H = 1 + 0.015 * Cp_bar * T
    R_T = -math.sin(math.radians(2 * d_theta)) * R_C

    return math.sqrt(
        (dLp / S_L) ** 2
        + (dCp / S_C) ** 2
        + (dHp / S_H) ** 2
        + R_T * (dCp / S_C) * (dHp / S_H)
    )


def white_balance(
    sample: tuple[float, float, float], white: tuple[float, float, float]
) -> tuple[int, int, int]:
    """Scale a sample so the reference card renders as a known white.

    A von Kries-style per-channel correction. The card is known to be white
    paper, so whatever imbalance it shows is the light rather than the
    subject, and whatever brightness it shows is the exposure. Mapping the
    card onto `REFERENCE_WHITE_LEVEL` divides out both at once.

    Normalising brightness as well as hue is what makes a photograph taken in
    a dim kitchen comparable with one taken by a window. Without it the same
    print matches a different chart entry depending on the exposure, which is
    the sort of quietly inconsistent behaviour a user would never spot.
    """
    corrected = []
    for channel, reference in zip(sample, white):
        gain = REFERENCE_WHITE_LEVEL / reference if reference > 0 else 1.0
        corrected.append(int(round(min(255.0, max(0.0, channel * gain)))))
    return (corrected[0], corrected[1], corrected[2])


def _reject(reason: str, corrected: tuple[int, int, int] | None = None) -> SporePrintReading:
    return SporePrintReading(
        confident=False, reason=reason, ranked=[], corrected_rgb=corrected
    )


def rank_against_chart(rgb: tuple[float, float, float]) -> list[ColourMatch]:
    """Every chart entry, nearest first."""
    lab = rgb_to_lab(rgb)
    matches = [
        ColourMatch(option=option, distance=ciede2000(lab, rgb_to_lab(reference)))
        for option, reference in REFERENCE_CHART.items()
    ]
    return sorted(matches, key=lambda m: m.distance)


def match_spore_print(
    sample_rgb: tuple[float, float, float],
    white_rgb: tuple[float, float, float],
) -> SporePrintReading:
    """Match a sampled spore deposit against the chart, or decline to.

    `sample_rgb` is the mean colour of the deposit; `white_rgb` the mean of the
    card's white half. Both are sRGB 0-255 as the camera recorded them, with no
    correction applied.
    """
    for name, value in (("sample", sample_rgb), ("white reference", white_rgb)):
        if len(value) != 3 or any(not math.isfinite(c) or c < 0 or c > 255 for c in value):
            return _reject(f"The {name} colour is not a usable RGB value.")

    white_level = sum(white_rgb) / 3
    if white_level < MIN_WHITE_LEVEL:
        return _reject(
            "The white card came out too dark to judge colour from. Take it "
            "again somewhere brighter -- daylight near a window is ideal."
        )
    if white_level > MAX_WHITE_LEVEL:
        return _reject(
            "The white card is overexposed, so its true colour is lost and the "
            "print's colour cannot be corrected. Take it again with less light "
            "or lower exposure."
        )

    lo, hi = min(white_rgb), max(white_rgb)
    if lo <= 0 or hi / lo > MAX_WHITE_CAST:
        return _reject(
            "The light is too strongly coloured to correct for. Try again in "
            "daylight rather than under a coloured or very warm lamp."
        )

    corrected = white_balance(sample_rgb, white_rgb)
    ranked = rank_against_chart(corrected)
    best, runner_up = ranked[0], ranked[1]

    if best.distance > MAX_DISTANCE:
        return _reject(
            "That colour does not match anything on the chart. Check you "
            "photographed the spore deposit itself, not the card or the cap.",
            corrected,
        )

    if runner_up.distance - best.distance < AMBIGUOUS_MARGIN:
        return SporePrintReading(
            confident=False,
            reason=(
                f"This sits between {best.option.lower()} and "
                f"{runner_up.option.lower()}, and the two are too close to call "
                f"from a photograph. Compare it against the chart yourself."
            ),
            ranked=ranked,
            corrected_rgb=corrected,
        )

    return SporePrintReading(
        confident=True,
        reason=(
            f"Closest match on the chart is {best.option.lower()}. "
            f"Check it against the swatch before you accept it."
        ),
        ranked=ranked,
        corrected_rgb=corrected,
    )
