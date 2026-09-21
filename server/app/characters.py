"""The character catalogue: how to ask a user for diagnostic evidence.

This is the heart of what makes the app different. A classifier narrows the
field; this turns the remaining ambiguity into a question a non-expert can
actually answer, with instructions for how to answer it.

Each character carries:
  prompt       -- the question, in plain language
  how          -- how to obtain the observation, including what to be careful of
  options      -- discrete answers, or None for a free photograph
  safety_note  -- shown when the character is being asked because a deadly
                  species is in play
  effort       -- "instant", "minutes", or "hours", so the UI can order the
                  cheap questions first
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Character:
    key: str
    label: str
    prompt: str
    how: str
    effort: str = "instant"
    options: tuple[str, ...] = ()
    safety_note: str = ""
    requires_photo: bool = False
    # Options that report a failed observation rather than a state of the
    # mushroom. "I cut it off" says nothing about whether there was a volva;
    # it says the user destroyed the evidence. Treating that as a state would
    # let it contradict a species that does have one -- and the species with
    # volvas are the ones that kill people, missed in exactly this way.
    #
    # `evidence.py` gives these a likelihood of 1.0, the same as a character
    # nobody has described: no information, so nothing moves.
    uninformative_options: tuple[str, ...] = ()


CHARACTERS: dict[str, Character] = {
    "volva": Character(
        key="volva",
        label="Base of the stem",
        prompt="Dig up the very base of the stem. Is there a cup or bag around it?",
        how=(
            "Do not cut the mushroom at ground level. Lever the whole thing out with "
            "a knife or your fingers so the base comes up intact, then brush off the "
            "soil. You are looking for a sac, cup or rim of tissue around the bottom."
        ),
        effort="minutes",
        options=("Clear cup or sac", "Swollen but no cup", "Neither", "I cut it off"),
        uninformative_options=("I cut it off",),
        safety_note=(
            "This is the single most important check in mushroom foraging. The sac at "
            "the base is the mark of Amanita, the genus responsible for most fatal "
            "poisonings. It is often buried and is routinely cut off and missed."
        ),
        requires_photo=True,
    ),
    "ring": Character(
        key="ring",
        label="Ring on the stem",
        prompt="Is there a ring or skirt of tissue on the stem?",
        how="Look partway up the stem for a collar, skirt or a distinct zone of fibres.",
        options=("Firm skirt-like ring", "Cobwebby fibres", "Faint zone only", "No ring"),
    ),
    "spore_print_colour": Character(
        key="spore_print_colour",
        label="Spore print",
        prompt="What colour is the spore print?",
        how=(
            "Cut the cap off and lay it gills-down on paper that is half white and half "
            "black, cover it with a bowl, and leave it for two to twelve hours. The "
            "colour of the powder that falls is the spore print."
        ),
        effort="hours",
        options=(
            "White or cream", "Pink", "Rust or cinnamon brown",
            "Chocolate or purple-brown", "Black", "Olive or yellow",
        ),
        safety_note=(
            "Spore print colour is the most decisive test available without a "
            "microscope, and it separates several deadly species from their edible "
            "lookalikes. It takes hours, and it is worth the wait."
        ),
        requires_photo=True,
    ),
    "gill_type": Character(
        key="gill_type",
        label="Underside of the cap",
        prompt="What is under the cap?",
        how="Turn the mushroom over and photograph the underside straight on.",
        options=(
            "Blade-like gills", "Blunt forking ridges", "Pores or tubes",
            "Spines or teeth", "Smooth or wrinkled",
        ),
        requires_photo=True,
    ),
    "gill_attachment": Character(
        key="gill_attachment",
        label="How the gills meet the stem",
        prompt="How do the gills meet the stem?",
        how=(
            "Slice the mushroom in half from cap to base and look at the cut face. "
            "Photograph the cut surface."
        ),
        effort="minutes",
        options=(
            "Running down the stem", "Squarely attached",
            "Notched just before the stem", "Free, not touching the stem",
        ),
        safety_note=(
            "Gill attachment separates the deadly Clitocybe species, whose gills run "
            "down the stem, from the Fairy Ring Champignon, whose gills do not."
        ),
        requires_photo=True,
    ),
    "gill_colour": Character(
        key="gill_colour",
        label="Gill colour",
        prompt="What colour are the gills right now?",
        how="Describe the colour of the gills themselves, not the cap.",
        options=("White", "Pink", "Brown", "Chocolate or black", "Yellow or green", "Grey"),
        safety_note=(
            "Gills that stay pure white at every age are a warning sign in a "
            "ringed, white-stemmed mushroom."
        ),
    ),
    "bruising_reaction": Character(
        key="bruising_reaction",
        label="Bruising",
        prompt="Does it change colour when cut or rubbed?",
        how=(
            "Cut the mushroom in half lengthways, including the very base of the stem, "
            "and rub the cap edge. Wait a full two minutes and watch for a change."
        ),
        effort="minutes",
        options=(
            "Yellow, especially at the stem base", "Red or pink", "Blue",
            "Green", "Brown", "No change",
        ),
        safety_note=(
            "Chrome-yellow staining at the base of the stem marks the Yellow Stainer, "
            "the commonest cause of mushroom poisoning in Britain."
        ),
        requires_photo=True,
    ),
    "substrate": Character(
        key="substrate",
        label="What it is growing on",
        prompt="What is it growing on or out of?",
        how=(
            "Look at what the base actually emerges from, not just what is nearby. "
            "Buried wood and roots count as wood."
        ),
        options=(
            "Soil or leaf litter", "Dead wood or a stump", "A living tree",
            "Grass or lawn", "Dung", "Moss",
        ),
        safety_note=(
            "Several deadly species grow in clusters on dead wood, exactly where "
            "foragers look for edible woodland species."
        ),
    ),
    "habitat": Character(
        key="habitat",
        label="Surroundings",
        prompt="What trees are within about ten metres?",
        how=(
            "Many fungi partner with one kind of tree and grow nowhere else, so this "
            "narrows the possibilities sharply."
        ),
        options=(
            "Oak", "Beech", "Birch", "Pine or spruce", "Mixed broadleaf",
            "No trees nearby",
        ),
    ),
    "smell": Character(
        key="smell",
        label="Smell",
        prompt="What does it smell like?",
        how="Break a piece and smell it immediately, close up.",
        options=(
            "Pleasantly mushroomy", "Aniseed or almond", "Apricot or fruity",
            "Fresh bread dough", "Radish", "Raw potato or earthy",
            "Ink or chemicals", "Rotting or foul", "Nothing much",
        ),
        safety_note=(
            "A phenolic or inky smell, strongest at the stem base, is a reliable "
            "warning sign in white Agaricus species."
        ),
    ),
    "cap_surface": Character(
        key="cap_surface",
        label="Cap surface",
        prompt="What is the cap surface like?",
        how="Photograph the cap from directly above in even light.",
        options=(
            "Smooth and dry", "Slimy or greasy", "Scaly", "Fibrous",
            "Velvety", "Pitted or honeycombed", "Brain-like or folded",
        ),
        requires_photo=True,
    ),
    "interior_structure": Character(
        key="interior_structure",
        label="Inside",
        prompt="Cut it in half from top to bottom. What does the inside look like?",
        how=(
            "Slice vertically through the whole thing, including the base, and "
            "photograph the cut face."
        ),
        effort="minutes",
        options=(
            "Completely hollow", "Chambered or cottony", "Solid and pure white",
            "Solid and dark", "Shows a developing cap and gills",
        ),
        safety_note=(
            "Sectioning is how you tell a puffball from an Amanita button. A puffball "
            "is uniformly white inside; an Amanita button shows a developing mushroom."
        ),
        requires_photo=True,
    ),
    "stipe_surface": Character(
        key="stipe_surface",
        label="Stem surface",
        prompt="What does the stem look like below the ring?",
        how="Photograph the full length of the stem.",
        options=(
            "Snakeskin-patterned", "Scaly or shaggy", "Smooth",
            "Netted or with a raised mesh", "Fibrous",
        ),
        requires_photo=True,
    ),
    "stipe_base": Character(
        key="stipe_base",
        label="Shape of the stem base",
        prompt="What shape is the very bottom of the stem?",
        how="Lever the whole mushroom out of the ground and clean off the soil.",
        effort="minutes",
        options=("Abruptly bulbous", "Tapering", "Even", "Rooting deeply"),
        requires_photo=True,
    ),
    "pore_colour": Character(
        key="pore_colour",
        label="Pore colour",
        prompt="What colour are the pores underneath?",
        how="Photograph the underside of the cap.",
        options=("White or cream", "Yellow", "Olive", "Red or orange", "Pink"),
        safety_note="Red pores on a bolete are a standing warning sign.",
        requires_photo=True,
    ),
    "cortina": Character(
        key="cortina",
        label="Cobwebby veil",
        prompt="Is there a cobwebby veil between the cap edge and the stem?",
        how=(
            "Look at a young specimen. The veil is fine, like spider silk, and "
            "often leaves a rusty band on the stem once it collapses."
        ),
        options=("Yes, cobwebby", "No", "Can't tell"),
        uninformative_options=("Can't tell",),
        safety_note=(
            "A cortina places a mushroom in or near Cortinarius, a genus containing "
            "species that destroy the kidneys weeks after being eaten."
        ),
    ),
    "taste": Character(
        key="taste",
        label="Taste",
        prompt="Touch a tiny piece to your tongue. Is it mild, bitter or burning?",
        how=(
            "Only for a mushroom already narrowed to a group where this is safe. "
            "Touch a crumb to the tip of your tongue, wait thirty seconds, then spit "
            "it out entirely. Never swallow."
        ),
        effort="minutes",
        options=("Mild", "Bitter", "Burning or peppery"),
        safety_note=(
            "The app will not ask for this while any deadly species remains a "
            "candidate. Amatoxins are tasteless and a taste test cannot detect them."
        ),
    ),
    "latex_colour": Character(
        key="latex_colour",
        label="Milk",
        prompt="Does it leak milk when the gills are scratched? What colour?",
        how="Scratch the gills and watch for droplets for about a minute.",
        options=("White", "Orange or carrot", "Yellow", "No milk"),
    ),
    "gill_texture": Character(
        key="gill_texture",
        label="Gill texture",
        prompt="Are the gills brittle or flexible?",
        how="Run a finger sideways across the gills.",
        options=("Brittle, shattering like chalk", "Flexible and greasy", "Soft"),
    ),
    "gill_spacing": Character(
        key="gill_spacing",
        label="Gill spacing",
        prompt="Are the gills crowded together or well spaced?",
        how="Photograph the underside straight on.",
        options=("Crowded", "Well spaced"),
        requires_photo=True,
    ),
    "growth_form": Character(
        key="growth_form",
        label="Growth habit",
        prompt="How is it growing?",
        how="Step back and photograph the whole group in place.",
        options=("Singly", "Scattered", "In a tight cluster", "In a ring", "As a bracket"),
        requires_photo=True,
    ),
    "cap_colour": Character(
        key="cap_colour",
        label="Cap colour",
        prompt="What colour is the cap?",
        how="Photograph from above in natural light, avoiding deep shade.",
        options=(
            "White or cream", "Yellow", "Orange", "Red", "Brown",
            "Olive or greenish", "Grey", "Purple",
        ),
        requires_photo=True,
    ),
    "season": Character(
        key="season",
        label="Time of year",
        prompt="When did you find it?",
        how="The month alone rules out a great many species.",
        options=("Spring", "Summer", "Autumn", "Winter"),
    ),
    "cap_margin": Character(
        key="cap_margin",
        label="Cap edge",
        prompt="What is the edge of the cap like?",
        how="Photograph the cap from the side.",
        options=("Strongly inrolled", "Shaggy or woolly", "Straight", "Upturned"),
        requires_photo=True,
    ),
    "flesh_colour": Character(
        key="flesh_colour",
        label="Flesh colour",
        prompt="What colour is the flesh inside?",
        how="Cut it open and look immediately, then again after two minutes.",
        options=("White", "Orange", "Red", "Yellow", "Brown"),
        requires_photo=True,
    ),
    "hymenium_type": Character(
        key="hymenium_type",
        label="Spore surface",
        prompt="What carries the spores underneath?",
        how="Photograph the underside close up.",
        options=("Gills", "Pores", "Spines", "Smooth surface", "Ridges"),
        requires_photo=True,
    ),
    "stipe_presence": Character(
        key="stipe_presence",
        label="Stem",
        prompt="Is there a stem, and where does it join the cap?",
        how="Photograph the mushroom from the side.",
        options=("Central stem", "Off-centre stem", "Stem at the side", "No stem"),
        requires_photo=True,
    ),
    "stipe_texture": Character(
        key="stipe_texture",
        label="Stem texture",
        prompt="Is the stem tough or brittle?",
        how="Try to bend it, then snap it.",
        options=("Tough and pliable, springs back", "Snaps cleanly like chalk", "Soft"),
    ),
    "skin_thickness": Character(
        key="skin_thickness",
        label="Skin thickness",
        prompt="How thick is the outer skin?",
        how="Cut through the outer wall and look at the cut edge.",
        options=("Thin, like paper", "Thick and rubbery"),
        requires_photo=True,
    ),
    "cap_attachment": Character(
        key="cap_attachment",
        label="How the cap joins the stem",
        prompt="Is the cap fused to the stem along its length, or only at the top?",
        how="Cut lengthways through cap and stem together and photograph the cut face.",
        effort="minutes",
        options=("Fused along its length", "Attached only at the top", "Free, like a skirt"),
        safety_note=(
            "This separates a true morel from the false morels and thimble morels "
            "that grow alongside it."
        ),
        requires_photo=True,
    ),
    "cap_shape": Character(
        key="cap_shape",
        label="Cap shape",
        prompt="What shape is the cap?",
        how="Photograph from the side.",
        options=("Domed", "Flat", "Funnel-shaped", "Cylindrical", "Conical", "Irregular"),
        requires_photo=True,
    ),
    "cap_cuticle": Character(
        key="cap_cuticle",
        label="Cap skin",
        prompt="Does the skin peel off the cap easily?",
        how="Lift the skin at the cap edge with a fingernail and pull towards the centre.",
        options=("Peels easily, most of the way", "Peels a little at the edge", "Will not peel"),
    ),
    "deliquescence": Character(
        key="deliquescence",
        label="Dissolving",
        prompt="Is the cap dissolving into black liquid at the edge?",
        how="Look at the cap margin on an older specimen.",
        options=("Yes", "No"),
    ),
    "texture": Character(
        key="texture",
        label="Texture",
        prompt="What does it feel like?",
        how="Press it between your fingers.",
        options=("Gelatinous and rubbery", "Firm and fleshy", "Woody", "Soft and fragile"),
    ),
    "size": Character(
        key="size",
        label="Size",
        prompt="How wide is the cap?",
        how="Measure across the widest point, or photograph it beside a coin.",
        options=("Under 2 cm", "2-5 cm", "5-10 cm", "10-20 cm", "Over 20 cm"),
    ),
}


def get_character(key: str) -> Character | None:
    return CHARACTERS.get(key)


EFFORT_ORDER = {"instant": 0, "minutes": 1, "hours": 2}


def order_by_effort(keys: list[str]) -> list[str]:
    """Cheap questions first, so the user is not sent to make a spore print
    when looking at the stem base would have settled it."""
    return sorted(
        [k for k in keys if k in CHARACTERS],
        key=lambda k: EFFORT_ORDER.get(CHARACTERS[k].effort, 1),
    )


# The characters offered on the capture form, before any question is asked.
#
# Deliberately short. The catalogue holds 35 characters and a form listing all
# of them would be abandoned halfway; these are the ones a person standing
# over a mushroom can answer without instruction, plus spore print for the
# minority who already have one. Everything else stays with the interrogation
# engine, which asks for it only when it would actually settle something.
#
# Order is the order they are shown: where you found it, then what it looks
# like, then the two that need a closer look.
FIELD_NOTE_CHARACTERS: tuple[str, ...] = (
    "habitat",
    "substrate",
    "growth_form",
    "cap_colour",
    "gill_colour",
    "ring",
    "smell",
    "spore_print_colour",
)


def field_note_characters() -> list[Character]:
    """The capture-form characters, in display order."""
    return [CHARACTERS[key] for key in FIELD_NOTE_CHARACTERS if key in CHARACTERS]
