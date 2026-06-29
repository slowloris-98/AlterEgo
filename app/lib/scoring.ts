import {
  TRAITS,
  type Character,
  type CharacterData,
  type Question,
  type RankedMatch,
  type Trait,
  type TraitScores,
  type TraitStat,
} from "./types";

/**
 * Scoring math. This MUST stay in sync with build/core/validate.py (lines 35-77).
 * Any change here should be mirrored there, and vice versa.
 */

/** Quiz answers ({qid: value}) → raw OCEAN scores on a 0-100 scale. */
export function answersToRaw(
  answers: Record<string, number>,
  questions: Question[]
): TraitScores {
  const traitValues: Record<Trait, number[]> = {
    openness: [],
    conscientiousness: [],
    extraversion: [],
    agreeableness: [],
    neuroticism: [],
  };

  const qMap = new Map(questions.map((q) => [q.id, q]));

  for (const [qid, value] of Object.entries(answers)) {
    const q = qMap.get(qid);
    if (!q) continue;
    const v = q.reverse ? 6 - value : value;
    traitValues[q.trait].push(v);
  }

  const raw = {} as TraitScores;
  for (const trait of TRAITS) {
    const vals = traitValues[trait];
    if (vals.length > 0) {
      const avg = vals.reduce((a, b) => a + b, 0) / vals.length;
      raw[trait] = ((avg - 1) / 4) * 100; // 1-5 Likert → 0-100
    } else {
      raw[trait] = 50;
    }
  }
  return raw;
}

/** Project raw scores onto the cast's z-scale using the stats block. */
export function rawToZ(
  raw: TraitScores,
  stats: Record<Trait, TraitStat>
): TraitScores {
  const z = {} as TraitScores;
  for (const trait of TRAITS) {
    z[trait] = (raw[trait] - stats[trait].mean) / stats[trait].std;
  }
  return z;
}

export function euclidean(a: TraitScores, b: TraitScores): number {
  let sum = 0;
  for (const t of TRAITS) {
    const d = a[t] - b[t];
    sum += d * d;
  }
  return Math.sqrt(sum);
}

/**
 * Distance from the user's z-vector to every character, sorted closest-first.
 * Friendly similarity = 1 / (1 + distance).
 */
export function rankMatches(
  userZ: TraitScores,
  characters: Character[]
): RankedMatch[] {
  return characters
    .map((c) => {
      const distance = euclidean(userZ, c.z);
      return {
        name: c.name,
        blurb: c.blurb,
        distance,
        similarity: 1 / (1 + distance),
        image: c.image,
      };
    })
    .sort((a, b) => a.distance - b.distance);
}

/** Full pipeline: answers → raw → z → ranked matches. */
export function scoreAnswers(
  answers: Record<string, number>,
  questions: Question[],
  data: CharacterData
): { raw: TraitScores; ranked: RankedMatch[] } {
  const raw = answersToRaw(answers, questions);
  const z = rawToZ(raw, data.stats);
  const ranked = rankMatches(z, data.characters);
  return { raw, ranked };
}
