# Incident process

What happens to a report that the app got something wrong.

`docs/SAFETY.md` lists an incident route as blocking for public release, and
names two halves: a way for users to report a suspected misidentification, and
a documented process for acting on it. This is the second half. The first is
`POST /incident` and `app/src/screens/ReportScreen.tsx`.

## The shape of it

A report arrives carrying what the app said — the verdict, the candidates it
offered, the model version, whether calibration was fitted — and what the
reporter says it actually was. The record of what the app said is sent by the
client from its own observation log rather than looked up server-side, so a
report stays actionable long after the server has forgotten the observation,
and so it names the model that produced the answer rather than whichever one
is running when someone opens the report.

Reports append to `data/incidents.jsonl`. Append-only, because a log that can
be edited in place is not evidence.

## A report is never applied automatically

Nothing in `server/app/incidents.py` writes to `data/taxonomy.seed.json`, and
nothing should. A reporter confident the app was wrong may themselves be
wrong, and the data they would be correcting is what every other user's
warnings are derived from. A report is evidence for a human. There is a test
pinning this.

## Triage

`severity` is computed from the taxonomy, not taken from the reporter. What
matters is not how strongly the report is worded but what class of failure it
describes.

| Severity | What it means | Response |
| --- | --- | --- |
| `medical` | Someone ate it, or anyone is unwell | Not a defect report. See below. |
| `dangerous_miss` | The reporter names a DEADLY or SERIOUS species; the app warned about nothing | Same day. This is the failure the app exists to prevent. |
| `dangerous_false_alarm` | The app warned; the reporter says it was ordinary | Within the week. |
| `ordinary` | Everything else | Batched. |

`dangerous_false_alarm` is deliberately not dismissed as harmless. The whole
design leans on the user believing a warning when they see one, and a warning
nobody believes protects nobody. A run of them against the same pair means
the pair is drawn too wide, which is a data question, not a model one.

## Acting on each severity

### `medical`

This is not an engineering ticket and must never be queued as one. The client
detects it before submitting anything and turns the form into the emergency
guidance; the server's reply carries the same guidance and the confirmation
text deliberately does not thank the user for their feedback.

Operationally: nothing is owed to the codebase here and everything is owed to
the person. If a contact address was left, and only then, a human replies with
the emergency information again and nothing else — no questions about the
photograph, no request for the specimen, nothing that reads as a support
thread while someone is waiting on a liver function test.

The report still matters afterwards. Once the person is safe, it is the most
important thing in the log.

### `dangerous_miss`

Work it the same day, in this order.

1. **Reproduce.** The report names the model version. If it is not the current
   one, check the current one first: it may already be fixed, and it may be
   worse.
2. **Is the species in the label space at all?** If not, this is an
   out-of-distribution failure, not a classification one, and belongs to
   `server/app/ood.py` and the energy threshold — not to the taxonomy.
3. **Is the pair in the lookalike graph?** A missing edge is the most common
   cause and the cheapest fix, and it changes behaviour immediately: a
   dangerous pair makes the app refuse rather than choose.
4. **Are the separating characters described for both halves?** Both. A pair
   described on the deadly side only lets evidence move mass away from the
   lethal candidate and never toward it — see the note in `CLAUDE.md`.
5. Only then consider the model. A missed dangerous species is a
   risk-weighted error, and the risk matrix already weights it; a run of them
   against one pair is a training-data problem, usually too few images of the
   safe half.

Any change to the taxonomy that comes out of this goes through the worksheet
(`scripts/character_states.py`), not by hand-editing the JSON, and is flagged
for the mycological review like everything else in there.

### `dangerous_false_alarm`

Check whether the lookalike edge is real before loosening anything. Widening
a dangerous pair is cheap and narrowing one is not: the cost of a false alarm
is a wasted trip and the cost of the other error is a liver transplant. If the
edge is real and the app is simply unable to separate the two, that is the app
working, and the answer is a better question in the interrogation engine, not
a removed warning.

### `ordinary`

Batched, and read in bulk rather than one at a time. The value here is in the
pattern: twenty reports confusing the same two species says something no
single report does.

## What is not collected

**Photographs.** They are the most useful thing a report could carry and the
route does not accept them. Storing users' images raises retention and consent
questions that the legal review in `docs/SAFETY.md` is also blocking on, and
beginning to collect them before that review is the wrong order. What is
stored is what the app itself said, which is enough to know which two species
were confused.

**Anything identifying, unless offered.** The contact field is optional, is
capped, and the form says the report is just as useful without it. No location
is sent: the observation log holds coordinates on the device and they stay
there.

## Rate limiting

`POST /incident` is the only unauthenticated write route the service has, so
it is rate limited per client: `server/app/ratelimit.py`, five reports an
hour by default (`WTM_INCIDENT_RATE_LIMIT`, `WTM_INCIDENT_RATE_WINDOW_SECONDS`).

**A report declaring that someone ate it, or that anyone is unwell, is never
limited.** Not counted, not refused, and not charged against the ordinary
quota either, so a genuine emergency cannot lock the reporter out of filing
the defect report afterwards. Someone whose child has eaten something may
submit repeatedly, from a bad signal, in a panic; every one of those lands.
A flood of medical reports costs a large file. The other error costs
something this project will not trade away. Six tests pin it.

A refusal returns 429 with `Retry-After`, and its message names the way
through — a frightened person must not be left believing the route is shut.

Two things about it are deliberately modest, and should be read as decisions
rather than oversights:

- **The counter is in memory**, so it is per-process and resets on restart.
  That is sufficient for the single-process deployment this is, and it is
  not a Redis dependency standing in for a decision nobody has made. Run
  more than one worker and the limit silently becomes `n_workers x limit`;
  move it to a shared store at that point rather than lowering the number.
- **`X-Forwarded-For` is ignored** unless `WTM_TRUST_FORWARDED_FOR` is set.
  The header is caller-supplied, so honouring it by default would hand
  anyone a fresh quota per request while reading, in the config, as
  protection. Enable it only behind a proxy that overwrites the header.

## Before launch

- [ ] A named person on the rota for `medical` and `dangerous_miss`, with a
      real response time rather than this document's aspiration. **This is
      the one that cannot be written in code.** `dangerous_miss` says "same
      day" above; until somebody's name is against it, that is a sentence
      rather than a commitment, and the app should not be in public hands
      with an unattended report queue.
- [x] Authentication or rate limiting in front of `POST /incident`. Done —
      see above. Authentication was not added: the route must work for
      somebody who has just installed the app and has no account, and the
      medical exemption has to hold for a stranger.
- [ ] A retention period for `data/incidents.jsonl`, decided with the legal
      review rather than before it.
- [ ] A way to tell a reporter what happened to their report, where they left
      a contact address. Blocked on the first item: there is nobody to send
      it from yet.
