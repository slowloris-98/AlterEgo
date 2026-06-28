# Harry Potter quiz keying (the psychometric backbone)

`out/quiz.json` is a Harry Potter-themed re-skin of the public-domain **IPIP-50** Big-Five markers
(https://ipip.ori.org). The wording is themed; the **trait + keying below are fixed and must never
drift**. This is the contract `validate.py` (and the runtime `lib/scoring.ts`) score against. It is
identical to the GoT and Friends keying — only the scenarios change.

## Rules
- 25 questions, exactly 5 per OCEAN trait, ids `q1`–`q25`.
- Each question offers 5 options with `value` 5→1 (so every trait can reach both extremes).
- `reverse = true` when the source IPIP item is minus-keyed; scoring applies `6 − value`.
- **Neuroticism inversion:** IPIP's factor is *Emotional Stability*. Emotional-stability-positive
  items ("relaxed", "seldom blue") are tagged `trait: neuroticism` with `reverse: true`.
- **Authoring rule:** options are written around the source item's *own pole* — strongest agreement
  with the source statement = value 5. Direction is then handled by `reverse` at scoring time.
- Theme is decoration only: the trait is set by this table, not by how a scenario feels.

## Locked table

| id | trait | IPIP source item | reverse |
|----|-------|------------------|---------|
| q1  | openness | Am full of ideas | false |
| q2  | openness | Have a vivid imagination | false |
| q3  | openness | Am quick to understand things | false |
| q4  | openness | Am not interested in abstract ideas | true |
| q5  | openness | Do not have a good imagination | true |
| q6  | conscientiousness | Am always prepared | false |
| q7  | conscientiousness | Pay attention to details | false |
| q8  | conscientiousness | Like order | false |
| q9  | conscientiousness | Make a mess of things | true |
| q10 | conscientiousness | Shirk my duties | true |
| q11 | extraversion | Am the life of the party | false |
| q12 | extraversion | Start conversations | false |
| q13 | extraversion | Don't mind being the center of attention | false |
| q14 | extraversion | Keep in the background | true |
| q15 | extraversion | Am quiet around strangers | true |
| q16 | agreeableness | Sympathize with others' feelings | false |
| q17 | agreeableness | Take time out for others | false |
| q18 | agreeableness | Make people feel at ease | false |
| q19 | agreeableness | Insult people | true |
| q20 | agreeableness | Am not really interested in others | true |
| q21 | neuroticism | Get stressed out easily | false |
| q22 | neuroticism | Worry about things | false |
| q23 | neuroticism | Have frequent mood swings | false |
| q24 | neuroticism | Am relaxed most of the time (Emotional Stability) | true |
| q25 | neuroticism | Seldom feel blue (Emotional Stability) | true |

Shared 25-slot template across franchises (GoT/Friends/HP) per spec §14 — re-theme the wording,
keep trait + reverse identical.
