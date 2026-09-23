#!/usr/bin/env python3
"""Drive the real thing, in a terminal.

    python scripts/demo.py

No GPU, no dataset, no network. Everything printed here is produced by the
same code the API serves; nothing is mocked and nothing is a transcript.

## The scenes hand their rankings in

Every ranking below is written into this file, the way the test suite writes
one. That keeps the demo honest about the stub, and it has a cost worth
knowing: the label space tripled on 2026-09-22 and this script's output did
not change by a character, because nothing here asks the taxonomy how big it
is. Scenes 7 and 8 were added for exactly that reason -- they exercise a pair
and a refusal that did not exist before the additions.

## What this can and cannot show

There is no trained classifier. The API's stub backend turns image pixels
into a deterministic ranking, which is enough to develop against and
meaningless as identification. So the scenes below hand the safety layer a
ranking directly, the way the tests do, and what you are watching is what the
app does *with* a ranking -- the refusals, the question it chooses, the way an
answer moves the mass.

That is the part worth demonstrating. It is also the part that is finished:
when a trained model replaces the stub, everything downstream of it is
already here.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "server"))
sys.path.insert(0, str(ROOT / "ml"))

from app.characters import CHARACTERS  # noqa: E402
from app.config import settings  # noqa: E402
from app.disclaimer import build as build_disclaimer  # noqa: E402
from app.evidence import entropy  # noqa: E402
from app.incidents import triage  # noqa: E402
from app.interrogation import InterrogationEngine  # noqa: E402
from app.ood import OodDetector, free_energy  # noqa: E402
from app.taxonomy_service import Toxicity  # noqa: E402
from app.safety import SafetyLayer  # noqa: E402
from app.taxonomy_service import TaxonomyService  # noqa: E402
from app.translate import default_translator  # noqa: E402

BOLD, DIM, RED, AMBER, GREEN, OFF = (
    "\033[1m", "\033[2m", "\033[31m", "\033[33m", "\033[32m", "\033[0m",
)


def answer(engine, ranked, character_key: str, option: str):
    """Apply an answer, refusing anything the API itself would reject.

    Writing this demo, I typed "I cut the mushroom off at the base" where the
    option is "I cut it off", and watched the engine grade it as a
    contradiction and move the death cap from 52% to 62%. The API validates
    answers against the catalogue (`/answer` returns 400), so a user could
    never do it -- but a script calling the engine directly can, and a demo
    that quietly shows the wrong thing is worse than one that crashes.
    """
    options = CHARACTERS[character_key].options
    if option not in options:
        raise SystemExit(
            f"{option!r} is not an option for {character_key!r}. Try: {options}"
        )
    return engine.apply_answer(ranked, character_key, option)


def rule(title: str) -> None:
    print(f"\n{BOLD}{'─' * 74}\n{title}\n{'─' * 74}{OFF}")


def say(assessment, taxonomy) -> None:
    colour = RED if assessment.deadly_in_play else (
        GREEN if assessment.verdict.value == "species" else AMBER
    )
    print(f"  {colour}{BOLD}{assessment.headline}{OFF}")
    if assessment.detail:
        print(f"  {DIM}{assessment.detail}{OFF}")
    for candidate in assessment.candidates[:4]:
        mark = RED + "  ✕" + OFF if candidate.toxicity == "DEADLY" else "   "
        print(
            f"  {mark} {candidate.confidence:5.1%}  {candidate.scientific_name:<30}"
            f" {DIM}{candidate.toxicity}{OFF}"
        )
    for warning in assessment.warnings:
        print(f"  {AMBER}! {warning}{OFF}")


def show_ranking(taxonomy, ranked, limit=4) -> None:
    for key, score in ranked[:limit]:
        species = taxonomy[key]
        mark = RED + "✕" + OFF if species.toxicity.value == "DEADLY" else " "
        print(f"    {mark} {score:6.1%}  {species.scientific_name}")


def main() -> int:
    taxonomy = TaxonomyService.load(settings.taxonomy_path)
    safety = SafetyLayer(taxonomy, confidence_threshold=0.80)
    engine = InterrogationEngine(taxonomy)

    deadly = [s for s in taxonomy.species.values() if s.toxicity is Toxicity.DEADLY]
    print(
        f"\n  {DIM}{len(taxonomy.species)} species  ·  {len(deadly)} that can kill  ·  "
        f"{len(taxonomy.dangerous_pairs())} lethal pairs{OFF}"
    )

    # ------------------------------------------------------------------
    rule("1. What a user agrees to before the app will do anything")
    disclaimer = build_disclaimer(
        model_loaded=False, calibrated=False, taxonomy_reviewed=False
    )
    print(f"  {BOLD}{disclaimer.heading}{OFF}   {DIM}version {disclaimer.version}{OFF}")
    for ack in disclaimer.acknowledgements:
        print(f"  {DIM}[ ]{OFF} {ack.statement}")
    print(
        f"\n  {DIM}The last three are here because /health currently reports "
        f"model_loaded,\n  calibrated and taxonomy_reviewed all false. Train a "
        f"model and that\n  statement disappears, the version changes, and every "
        f"user is asked again.{OFF}"
    )

    # ------------------------------------------------------------------
    rule("2. A confident, ordinary answer")
    say(safety.assess([("hydnum-repandum", 0.93), ("cantharellus-cibarius", 0.05)]), taxonomy)
    print(
        f"\n  {DIM}Note what the best case looks like: 93%, a named species, and "
        f"still\n  'Not assessed as safe'. There is no edible category to be "
        f"promoted into.{OFF}"
    )

    # ------------------------------------------------------------------
    rule("3. The same photograph, if a death cap is in the frame")
    ranked = [("amanita-phalloides", 0.52), ("agaricus-campestris", 0.41), ("lepista-nuda", 0.07)]
    say(safety.assess(ranked), taxonomy)
    print(
        f"\n  {DIM}A competitor returns 'Field Mushroom, 87%' here. This refuses "
        f"to choose,\n  names both, and goes looking for the character that "
        f"separates them.{OFF}"
    )

    # ------------------------------------------------------------------
    rule("4. The question it asks, and why that one")
    questions = engine.next_questions(ranked, limit=3)
    for i, question in enumerate(questions, 1):
        character = question.character
        print(f"  {BOLD}{i}. {character.prompt}{OFF}")
        print(f"     {DIM}{character.how}{OFF}")
        print(
            f"     {DIM}worth {question.expected_information_gain:.2f} bits"
            f"   ·   {', '.join(character.options)}{OFF}"
        )
        if question.resolves_dangerous_pair and character.safety_note:
            print(f"     {AMBER}{character.safety_note}{OFF}")
    print(
        f"\n  {DIM}Chosen by simulating every possible answer through the real\n"
        f"  re-weighting, so it cannot ask something its own update would "
        f"ignore.{OFF}"
    )

    # ------------------------------------------------------------------
    rule("5. Answering it")
    print(f"  {BOLD}Before{OFF}   entropy {entropy([s for _, s in ranked]):.2f} bits")
    show_ranking(taxonomy, ranked)

    answered = answer(engine, ranked, "volva", "Clear cup or sac")
    print(f"\n  {DIM}User digs up the stem base and finds a sac.{OFF}")
    print(f"  {BOLD}After{OFF}    entropy {entropy([s for _, s in answered]):.2f} bits")
    show_ranking(taxonomy, answered)
    say(safety.assess(answered), taxonomy)

    # ------------------------------------------------------------------
    rule("6. The commonest field mistake")
    print(f"  {DIM}Same question. This time the user cut the stem at ground level.{OFF}")
    cut = answer(engine, ranked, "volva", "I cut it off")
    show_ranking(taxonomy, cut)
    print(
        f"\n  {DIM}Identical to the input, to the last decimal. That is the point:"
        f"\n  'I cut it off' is a fact about the user, not about the mushroom."
        f"\n\n  Scored as a state it reads as 'no volva', which contradicts the "
        f"death cap\n  and agrees with the field mushroom -- so the single "
        f"commonest reason a\n  forager cannot see a volva would push the deadly "
        f"candidate down. Measured\n  before the fix: 0.50 to 0.355.{OFF}"
    )

    # ------------------------------------------------------------------
    rule("7. A sentence, instead of eight questions")
    sentence = ("small brown mushroom, tuft on a rotten stump, "
                "ring on the stem, no smell")
    translator = default_translator()
    translated = translator.translate(sentence)

    print(f'  {BOLD}"{sentence}"{OFF}\n')
    print(f"  {DIM}translated by: {translated.backend}{OFF}")
    for key, value in translated.field_notes.items():
        label = CHARACTERS[key].label if key in CHARACTERS else key
        print(f"    {label:<26} {GREEN}{value}{OFF}")
    if translated.not_understood:
        print(f"    {DIM}could not place: "
              f"{', '.join(repr(p) for p in translated.not_understood)}{OFF}")

    # Those notes are ordinary field notes, so they go through the ordinary
    # engine. Nothing about the answer is special because a translator
    # produced it.
    described = [("galerina-marginata", 0.34), ("kuehneromyces-mutabilis", 0.33),
                 ("flammulina-velutipes", 0.33)]
    for key, value in translated.field_notes.items():
        described = answer(engine, described, key, value)
    print()
    show_ranking(taxonomy, described, limit=3)
    print(
        f"  {DIM}Nothing moved, and nothing should have. Every one of those "
        f"answers is\n  either consistent with all three or undescribed for "
        f"all three -- they are\n  three tufted brown mushrooms on a stump. A "
        f"consistent answer never\n  boosts; the sentence has described the "
        f"ambiguity, not resolved it.{OFF}"
    )
    say(safety.assess(described), taxonomy)

    print(f"\n  {BOLD}\"...and the spore print was white\"{OFF}")
    more = translator.translate("and the spore print was white")
    for key, value in more.field_notes.items():
        label = CHARACTERS[key].label if key in CHARACTERS else key
        print(f"    {label:<26} {GREEN}{value}{OFF}")
        described = answer(engine, described, key, value)
    print()
    show_ranking(taxonomy, described, limit=3)
    say(safety.assess(described), taxonomy)
    top = described[0][1]
    print(
        f"  {DIM}That one bites, because it contradicts. Both brown-spored "
        f"species are\n  pushed down -- the funeral bell by less than the "
        f"woodtuft, because the\n  deadly tier's floor holds it up. Still a "
        f"refusal at {top:.0%}.{OFF}"
    )

    print(
        f"\n  {DIM}The schema it answers in has no field for a species. Not a "
        f"discouraged\n  one -- there is nowhere to put the string. Asked to "
        f'identify something\n  outright it returns nothing at all:{OFF}'
    )
    refused = translator.translate("I think it is a death cap")
    print(f"    {DIM}\"I think it is a death cap\"  ->  "
          f"{refused.field_notes or '{}'}{OFF}")
    print(
        f"\n  {DIM}Every enum in that schema is read from the character "
        f"catalogue at call\n  time, so a state that is not an option cannot "
        f"be produced -- the same\n  guarantee the worksheet importer enforces "
        f"by refusing the row, moved one\n  step earlier. It is validated again "
        f"here anyway: `strict` is a promise\n  from the API, and this is a "
        f"safety path.{OFF}"
    )

    # ------------------------------------------------------------------
    rule("8. A pair that did not exist yesterday")
    print(
        f"  {DIM}A stump in January. Velvet shank fruits on broadleaf wood in the "
        f"cold,\n  and so does the funeral bell -- same stump, same weather, same "
        f"tawny cap\n  in a tuft. The pair only exists because the velvet shank was "
        f"added by\n  how often it is recorded.{OFF}\n"
    )
    winter = [("flammulina-velutipes", 0.58), ("galerina-marginata", 0.34),
              ("kuehneromyces-mutabilis", 0.08)]
    say(safety.assess(winter), taxonomy)

    print(f"\n  {DIM}The user does the print. It comes back white.{OFF}")
    printed = answer(engine, winter, "spore_print_colour", "White or cream")
    show_ranking(taxonomy, printed, limit=3)
    print(f"  {DIM}Still refusing at 74%. Rust brown would have been the "
          f"funeral bell.{OFF}")

    # ------------------------------------------------------------------
    rule("9. Two species it will never separate, and says so")
    crepidotus = [("crepidotus-variabilis", 0.47), ("crepidotus-cesatii", 0.44),
                  ("crepidotus-mollis", 0.09)]
    say(safety.assess(crepidotus), taxonomy)
    print(
        f"\n  {DIM}These two are separated by spore shape under a microscope and "
        f"by\n  nothing else. They are in the label space because they are recorded "
        f"in\n  their thousands, and a species the model has never seen gets forced "
        f"into\n  the nearest one it knows.\n\n  So the honest outcome is the genus "
        f"and a refusal, which is what it gives.\n  Adding species by frequency buys "
        f"coverage and costs precision; this is\n  what paying that is supposed to "
        f"look like.{OFF}"
    )

    # ------------------------------------------------------------------
    rule("10. Something it has never seen")
    import math

    known = [2.0, 8.5, 1.5, 0.5]        # a confident, in-distribution logit vector
    shifted = [v - 6.0 for v in known]  # the same shape, every logit six lower
    detector = OodDetector(threshold=-4.0)

    for label, logits in (("a mushroom it knows", known), ("a photograph of a dog", shifted)):
        softmax_top = math.exp(max(logits)) / sum(math.exp(v) for v in logits)
        verdict = detector.assess(free_energy(logits))
        text = "OUT OF SCOPE" if verdict.out_of_distribution else "in scope"
        colour = AMBER if verdict.out_of_distribution else GREEN
        print(
            f"  {label:<24} softmax top-1 {softmax_top:.4f}   "
            f"free energy {verdict.energy:+.2f}   {colour}{text}{OFF}"
        )
    print(
        f"\n  {DIM}Identical softmax to four decimal places. Softmax depends only "
        f"on the\n  differences between logits, so it cannot see that the network "
        f"recognised\n  nothing. Free energy keeps the magnitude.{OFF}"
    )

    # ------------------------------------------------------------------
    rule("11. Reading a spore print off a photograph")
    print(
        f"  {DIM}The one part of this that is finished end to end, because it "
        f"needs no\n  model: real colour science on real pixels. The user "
        f"photographs the print\n  on a half-white card and marks two "
        f"rectangles.{OFF}\n"
    )
    from PIL import Image  # noqa: PLC0415
    from app.spore_print import REFERENCE_CHART, read_from_photograph  # noqa: PLC0415

    def card(deposit, white=(243, 243, 243)):
        image = Image.new("RGB", (400, 200), white)
        image.paste(Image.new("RGB", (200, 200), deposit), (0, 0))
        return image

    left, right = (0.05, 0.2, 0.35, 0.6), (0.6, 0.2, 0.35, 0.6)
    warm = lambda c, k: tuple(int(min(255, v * m * 0.75)) for v, m in zip(c, k))
    tungsten = (1.25, 1.0, 0.75)
    white_pink = tuple(
        (a + b) // 2
        for a, b in zip(REFERENCE_CHART["White or cream"], REFERENCE_CHART["Pink"])
    )

    scenes = [
        ("a white print, daylight", card(REFERENCE_CHART["White or cream"])),
        ("the same print, tungsten bulb",
         card(warm(REFERENCE_CHART["White or cream"], tungsten), warm((243, 243, 243), tungsten))),
        ("a chocolate-brown print", card(REFERENCE_CHART["Chocolate or purple-brown"])),
        ("between white and pink", card(white_pink)),
        ("they photographed a blue thing", card((20, 40, 220))),
    ]
    for label, image in scenes:
        reading = read_from_photograph(image, left, right)
        if reading.confident:
            print(f"  {label:<32} {GREEN}{reading.option}{OFF}")
        else:
            print(f"  {label:<32} {AMBER}declines{OFF}  {DIM}{reading.reason}{OFF}")
    print(
        f"\n  {DIM}The white/pink boundary is the one that matters: it is what "
        f"separates an\n  Amanita from a young Agaricus. Landing between them, "
        f"it refuses rather\n  than picking a side -- and a confident reading is "
        f"still only a suggestion\n  beside the manual list. The person picks.{OFF}"
    )

    # ------------------------------------------------------------------
    rule("12. Telling it that it was wrong")
    scenarios = [
        (
            "'It said field mushroom. It was a death cap.'",
            dict(verdict="species", reported_candidates=["agaricus-campestris"],
                 believed_species_key="amanita-phalloides",
                 anyone_ate_it=False, anyone_unwell=False),
        ),
        (
            "'You warned me off. It was obviously a field mushroom.'",
            dict(verdict="dangerous_group",
                 reported_candidates=["amanita-phalloides", "agaricus-campestris"],
                 believed_species_key="agaricus-campestris",
                 anyone_ate_it=False, anyone_unwell=False),
        ),
        (
            "'Wrong russula.'",
            dict(verdict="species", reported_candidates=["lepista-nuda"],
                 believed_species_key="boletus-edulis",
                 anyone_ate_it=False, anyone_unwell=False),
        ),
        (
            "'My son ate one.'",
            dict(verdict="species", reported_candidates=["lepista-nuda"],
                 believed_species_key=None,
                 anyone_ate_it=True, anyone_unwell=False),
        ),
    ]
    for description, kwargs in scenarios:
        severity = triage(taxonomy=taxonomy, **kwargs)
        colour = RED if severity.value in ("medical", "dangerous_miss") else AMBER
        print(f"  {description:<56} {colour}{severity.value}{OFF}")
    print(
        f"\n  {DIM}Graded from the taxonomy, not from the wording. The last one "
        f"stops being\n  a bug report: the form turns into the emergency page "
        f"before anything sends.{OFF}"
    )

    # ------------------------------------------------------------------
    rule("What is not being demonstrated")
    print(
        "  There is no trained model. Every ranking above was handed in, the way\n"
        "  the tests hand one in. What you have seen is the layer that sits on top\n"
        "  of a classifier, and none of it gets easier or harder when the real one\n"
        "  arrives.\n"
    )
    print(f"  {DIM}The taxonomy behind it is unreviewed. See docs/REVIEW.md.{OFF}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
