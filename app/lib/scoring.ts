import {
  TRAITS,
  type Character,
  type CharacterData,
  type Question,
  type RankedMatch,
  type Trait,
  type TraitScores,
  type TraitStat,
  type UniverseMatch,
} from "./types";

/**
 * Scoring math. This MUST stay in sync with build/core/validate.py.
 * Matching uses cosine similarity on the OCEAN z-vector (pattern, not magnitude).
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

/**
 * Cosine similarity between two z-vectors, in [-1, 1] (1 = identical direction).
 *
 * We match on the *direction* of the OCEAN z-vector (the trait pattern), not its
 * magnitude. Plain Euclidean distance penalizes a character by ‖char‖², which made
 * the two characters nearest the cast centroid a "magnet" for any moderate respondent
 * (the Sugriva/Angad problem). Cosine drops that magnitude term entirely.
 */
export function cosineSimilarity(a: TraitScores, b: TraitScores): number {
  let dot = 0;
  let normA = 0;
  let normB = 0;
  for (const t of TRAITS) {
    dot += a[t] * b[t];
    normA += a[t] * a[t];
    normB += b[t] * b[t];
  }
  const denom = Math.sqrt(normA) * Math.sqrt(normB);
  return denom === 0 ? 0 : dot / denom;
}

/**
 * Rank every character by cosine similarity to the user's z-vector, closest-first.
 *
 * `similarity` is mapped to a friendly [0, 1] scale ((cos + 1) / 2) for display, and
 * `distance = 1 - cos` (lower = closer) is kept for any consumer that wants a distance.
 * Both are monotonic in the underlying cosine, so sort order is unaffected by the mapping.
 */
export function rankMatches(
  userZ: TraitScores,
  characters: Character[]
): RankedMatch[] {
  return characters
    .map((c) => {
      const cos = cosineSimilarity(userZ, c.z);
      return {
        name: c.name,
        blurb: c.blurb,
        distance: 1 - cos,
        similarity: (cos + 1) / 2,
        image: c.image,
      };
    })
    .sort((a, b) => a.distance - b.distance);
}

/**
 * The user's single best match in EACH franchise, sorted by similarity
 * descending (so one character per universe — N franchises → N entries).
 *
 * The raw 0-100 profile is franchise-agnostic, so we normalize it with each
 * franchise's own stats (exactly as if the user had taken that quiz) and take
 * that cast's closest character.
 *
 * Note: each franchise's z-space is cast-relative, so cross-franchise
 * similarities are "comparable enough" to order universes, not a rigorous
 * absolute metric.
 */
export function rankAcrossUniverses(
  raw: TraitScores,
  franchises: { id: string; name: string; data: CharacterData }[]
): UniverseMatch[] {
  const tops: UniverseMatch[] = [];
  for (const fr of franchises) {
    const z = rawToZ(raw, fr.data.stats);
    const best = rankMatches(z, fr.data.characters)[0];
    if (best) {
      tops.push({ ...best, franchise: fr.id, franchiseName: fr.name });
    }
  }
  return tops.sort((a, b) => b.similarity - a.similarity);
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
