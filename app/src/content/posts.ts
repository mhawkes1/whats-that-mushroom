/**
 * The Learn posts, bundled with the app.
 *
 * **Why these live in the repo and not on a website.** Every claim this
 * project makes about a species exists in exactly one place and is
 * generated from it -- the ebook's field data comes from the taxonomy
 * rather than being hand-copied, and the walkthrough is a recording of
 * real responses rather than a reimplementation of the safety layer. Two
 * hand-kept copies of one fact drift, silently. A blog would be a third
 * copy that nothing generates and no test reads.
 *
 * In here they are diffed, reviewed and SCANNED: `content.test.ts` runs
 * rule 1 over every word in both directions, the same rule that
 * `test_no_user_facing_path_makes_an_inedibility_claim` runs over the
 * safety layer. That test has twice been found covering one surface and
 * missing another -- it never read `disclaimer.py`, where a soft
 * edibility verdict survived the September purge, and it never read
 * `scripts/try_it.py`. This surface is covered from its first day.
 *
 * They are also bundled rather than fetched. A wood is where the network
 * is not, which is the same reason the emergency screen is the one
 * hardcoded, offline, ungated string in the app.
 *
 * **What a post may say.** These four state facts about how the APP
 * behaves -- what a refusal means, which answers contradict which
 * candidates -- and naming a species in service of that is fine, because
 * it describes this app rather than making a new field-guide claim. A
 * post that tells somebody how to tell two mushrooms apart in the field
 * is a mycological claim, and those wait for the review that
 * `taxonomy_reviewed: false` is blocking on. Do not add one before then.
 */

export type Block =
  | { kind: 'heading'; text: string }
  | { kind: 'p'; text: string }
  | { kind: 'bullet'; text: string }
  | { kind: 'aside'; text: string };

export interface Post {
  slug: string;
  title: string;
  /** One sentence, shown on the card. */
  standfirst: string;
  blocks: Block[];
}

export const POSTS: Post[] = [
  {
    slug: 'why-i-refuse',
    title: 'Why I will not always answer',
    standfirst:
      'Most identification apps answer every time. This one does not, and the refusals are the point.',
    blocks: [
      {
        kind: 'p',
        text:
          'An app that answers every question looks more useful than one that does not. It is easy to build, too: you take the most likely species and you print it. The reason this app will not do that is that the cost of the two mistakes is not the same. Being told nothing wastes a walk. Being told the wrong name can cost a liver.',
      },
      {
        kind: 'p',
        text:
          'So there are several things I can say, and only one of them is a species.',
      },
      { kind: 'heading', text: 'I think this is a particular species' },
      {
        kind: 'p',
        text:
          'The most confident answer I have. It still is not a confirmation: nobody has checked it, and the percentage beside it is my own estimate of how often I am right about photographs like these. It is not a vote, and no expert has seen your mushroom.',
      },
      { kind: 'heading', text: 'This is a group I cannot split' },
      {
        kind: 'p',
        text:
          'Sometimes the genus is clear and the species is not. I will say so rather than pick the common one, because the common one is what a guess looks like when it is wrong.',
      },
      { kind: 'heading', text: 'Two of these can be confused and one is dangerous' },
      {
        kind: 'p',
        text:
          'This is the refusal that matters most. When the candidates include a pair that are mistaken for one another, and one of the pair can kill, I name neither — even if one of them is well ahead. Naming the safer one is the single most dangerous thing an identification app can do, because it is right most of the time and catastrophic the rest.',
      },
      {
        kind: 'aside',
        text:
          'Answering the follow-up questions can lift this refusal. Sometimes it cannot: a few pairs need a microscope, and no photograph and no question will separate them.',
      },
      { kind: 'heading', text: 'I am not sure what this is' },
      {
        kind: 'p',
        text:
          'No candidate is strong enough to be worth printing. Better framing, the underside of the cap, or the base of the stem will often change this. Sometimes nothing will.',
      },
      { kind: 'heading', text: 'This may not be something I know' },
      {
        kind: 'p',
        text:
          'I was trained on a few hundred British species. There are thousands. When a photograph does not look like anything I was taught, I would rather say so than hand you the nearest thing I happen to have a name for.',
      },
      { kind: 'heading', text: 'What a refusal is not' },
      {
        kind: 'p',
        text:
          'It is not a bug, and it is not me being broken or slow. It is the one behaviour that separates this from an app that is confidently wrong twice a week. The counter on the home screen shows how often it happens, deliberately.',
      },
    ],
  },

  {
    slug: 'what-the-percentages-mean',
    title: 'What the percentages mean',
    standfirst:
      'The number beside a species is not the chance that I am right, and the small ones matter far more than they look.',
    blocks: [
      {
        kind: 'p',
        text:
          'Every photograph gets a score for every species I know, and those scores add up to one. What you see is the top few out of several hundred, so the percentages on your screen will not add up to 100. The rest is spread thinly over everything I did not think was worth showing you.',
      },
      { kind: 'heading', text: 'What a percentage is not' },
      {
        kind: 'p',
        text:
          'It is not a vote, and it is not a second opinion. Nobody has looked at your mushroom. It is one model’s score, produced by something that has only ever seen photographs, and it carries no more authority than that.',
      },
      { kind: 'heading', text: 'What it is, once it has been checked' },
      {
        kind: 'p',
        text:
          'A percentage is honest when it matches how often I turn out to be right. If I say 70% on a thousand photographs and I am right on about seven hundred of them, then the number means what it says. Making that true is a separate step from training: the model is tested against photographs it was never shown, and its numbers are stretched or squeezed until they line up with reality. That step is the whole difference between a confidence and a number that merely looks like one.',
      },
      { kind: 'heading', text: 'Right now, it has not been checked' },
      {
        kind: 'p',
        text:
          'Where that is the case I say so on the result itself, every time, rather than letting you find out later. Treat the ordering as real and the numbers as rough. The species at the top is still the one I think most likely; it is the distance between 60% and 80% that you should not read much into yet.',
      },
      { kind: 'heading', text: 'Why a small number can still stop me' },
      {
        kind: 'p',
        text:
          'This is the one worth remembering. If the species that can kill hold even 1% of the score between them, I show the full warning — at any position in the list, including places too far down for you to see. Rounding a one-in-a-hundred chance of a lethal mushroom down to nothing is the single piece of arithmetic this app will not do.',
      },
      {
        kind: 'aside',
        text:
          'So a dangerous species sitting at 1% is not me being twitchy. It is the one number on the screen whose size is not the point.',
      },
      { kind: 'heading', text: 'Why the leader can be well ahead and I still will not name it' },
      {
        kind: 'p',
        text:
          'A species can lead on 57% and get no name from me, because something that can kill is holding 24% behind it. The question I am answering is not whether the leader is ahead of the others. It is whether anything dangerous is still in play.',
      },
      { kind: 'heading', text: 'Why I sometimes name nothing at all' },
      {
        kind: 'p',
        text:
          'There is a bar, and it is set so that when I do commit to a species I am right about 95 times in 100. Below the bar I decline and ask for more instead. That is why refusals are common rather than rare: the bar is where it is on purpose, and dropping it would buy you more names at the price of more wrong ones.',
      },
      { kind: 'heading', text: 'What moves a percentage' },
      {
        kind: 'p',
        text:
          'Answering a question — but not in the way most people expect. Telling me something that matches a species does not push it up. It pushes down every species that cannot show what you described, and whatever is left rises because the rest fell. That is also why a guessed answer is not free, which is its own piece further on.',
      },
    ],
  },

  {
    slug: 'photographing-a-mushroom',
    title: 'Photographing a mushroom',
    standfirst:
      'Most of what I get wrong, I get wrong because the answer was in a part of the mushroom nobody photographed.',
    blocks: [
      {
        kind: 'p',
        text:
          'I cannot see what you did not photograph, and the parts people leave out are the parts that carry the answer. This is the single biggest thing you can change about how well I do.',
      },
      { kind: 'heading', text: 'Lever the whole thing out' },
      {
        kind: 'p',
        text:
          'Do not cut the stem. The base is where a sac, a bulb or a sudden swelling would show, and those are among the few features that separate things that otherwise look identical from above. A knife through the stem removes the evidence before anyone has read it. Push a finger or a stick into the soil beside it and lift.',
      },
      {
        kind: 'aside',
        text:
          'Cutting the base off is the commonest field mistake there is, and I am built to notice it: if you tell me you cut it, I treat that as "I could not look" rather than as "there was nothing there".',
      },
      { kind: 'heading', text: 'Three views, not one' },
      { kind: 'bullet', text: 'The cap, from above, filling the frame.' },
      {
        kind: 'bullet',
        text:
          'The side, so the stem, any ring and the shape of the base are all visible at once.',
      },
      {
        kind: 'bullet',
        text:
          'The underside — gills, pores or spines, and how they meet the stem.',
      },
      {
        kind: 'p',
        text:
          'Each view rules out things the others cannot. Only the first is required, and the other two are where most of the gain is. I average what the views tell me rather than taking the best one, so a clear photograph will not vouch for a set that is otherwise unreadable.',
      },
      { kind: 'heading', text: 'Daylight, not a torch or a flash' },
      {
        kind: 'p',
        text:
          'Colour separates species that are otherwise the same shape, and it is the least reliable thing in any photograph. Indoor light, a flash or a phone torch will all shift it. Shade on a bright day is better than direct sun, which blows out a pale cap into featureless white.',
      },
      { kind: 'heading', text: 'Give it something to be the size of' },
      {
        kind: 'p',
        text:
          'A coin, a key, your hand in the frame. Scale is invisible in a close-up, and a thumbnail-sized mushroom and a dinner-plate-sized one can look the same on a screen.',
      },
      { kind: 'heading', text: 'Photograph where it was growing' },
      {
        kind: 'p',
        text:
          'On wood or on soil, under what sort of tree, alone or in a troop. Habitat is one of the questions I will ask you, and it is far easier to answer from a photograph taken at the time than from memory on the sofa.',
      },
    ],
  },

  {
    slug: 'spore-prints',
    title: 'Spore prints, and why I ask for twelve hours',
    standfirst:
      'The slowest thing I will ever ask you to do, and one of the few that a photograph genuinely cannot replace.',
    blocks: [
      {
        kind: 'p',
        text:
          'A spore print is the colour of the dust a cap drops when you leave it face down overnight. It is one of a very small number of characters that separate species a camera cannot, because the colour comes from the spores themselves rather than from the surface of a mushroom that has been rained on, bleached by sun or handled.',
      },
      { kind: 'heading', text: 'How to take one' },
      {
        kind: 'bullet',
        text:
          'Cut the cap from the stem and set it gills, pores or spines down.',
      },
      {
        kind: 'bullet',
        text:
          'Put it on paper that is half white and half black, or on two pieces side by side. A white print is invisible on white paper and a dark one is invisible on black, and you cannot know in advance which you are getting.',
      },
      {
        kind: 'bullet',
        text:
          'Cover it with a bowl or a glass so it does not dry out, and leave it somewhere still.',
      },
      { kind: 'bullet', text: 'Give it between two and twelve hours.' },
      { kind: 'heading', text: 'Why the timer works the way it does' },
      {
        kind: 'p',
        text:
          'The wait is far longer than anyone keeps an app open, so there is no countdown to watch. I store the time you started and work it out whenever you come back. Close the app, let the phone die, start it a day later — the print is on the kitchen table either way, and so is the record of when you began.',
      },
      { kind: 'heading', text: 'Photographing the result' },
      {
        kind: 'p',
        text:
          'I can read a photographed print against a colour chart. You mark the patch of deposit and a patch of the bare paper beside it, and I compare the two — the paper matters, because a kitchen bulb shifts both and only the difference between them is stable.',
      },
      {
        kind: 'aside',
        text:
          'What comes back is a suggestion beside the list, never an answer filled in for you. A spore colour is one of the strongest pieces of evidence in the whole app, and something that strong should be a person looking at a deposit and deciding, not a camera guessing at one.',
      },
    ],
  },

  {
    slug: 'answers-that-mislead-me',
    title: 'Three answers that mislead me',
    standfirst:
      'When I ask a question, a wrong answer does not simply fail to help. It can push me away from the one species you most needed me to consider.',
    blocks: [
      {
        kind: 'p',
        text:
          'Here is the mechanism, because it explains all three. An answer that matches a candidate never promotes it — evidence in this app eliminates, it cannot manufacture confidence. What an answer does is contradict every candidate that does not list what you said. So a guess does not cost you nothing. It quietly removes candidates, and if one of those was the dangerous one, the warning goes with it.',
      },
      {
        kind: 'p',
        text:
          'These three are the ones where that is most likely to happen, measured against what the deadly species I know about actually declare.',
      },
      { kind: 'heading', text: 'The ring' },
      {
        kind: 'p',
        text:
          'A ring is the collar of tissue left on the stem by the veil that covered the young gills. The trap is that it does not last. It withers to a faint smudge, and heavy rain washes it off altogether — which is exactly the weather in which somebody looks at a bare stem and answers "no ring".',
      },
      {
        kind: 'p',
        text:
          'Answering "cobwebby fibres" rules out four of the deadly species in my label space at once, and "no ring" rules out two. Look for a faint zone, a different texture or a line of debris stuck to the stem before you decide there was never anything there.',
      },
      { kind: 'heading', text: 'The surface of the cap' },
      {
        kind: 'p',
        text:
          'Weather again. A cap that is dry and smooth in its own right looks slimy and greasy after rain, and "slimy or greasy" contradicts five deadly species in one answer. If it has been wet, say what the cap is like rather than what the rain has made of it — or skip the question.',
      },
      { kind: 'heading', text: 'Habitat' },
      {
        kind: 'p',
        text:
          'Three of the deadly species I know list only "no trees nearby" and "mixed broadleaf", and two more split along conifer against broadleaf. So standing in mixed woodland and naming the single nearest tree can contradict three of them in one tap. If several kinds of tree are around you, "mixed broadleaf" is the honest answer and not the vague one.',
      },
      { kind: 'heading', text: 'The most useful button on the screen' },
      {
        kind: 'p',
        text:
          'Every question carries "I can’t tell / skip this", and it is there precisely so that none of the above has to be guessed at. Skipping costs me a little information. Guessing can cost me the right answer. Use it freely — it is the control that keeps this honest, not an admission of anything.',
      },
    ],
  },
];

export const postBySlug = (slug: string): Post | undefined =>
  POSTS.find((p) => p.slug === slug);
