export const TRAITS = [
  "openness",
  "conscientiousness",
  "extraversion",
  "agreeableness",
  "neuroticism",
] as const;

export type Trait = (typeof TRAITS)[number];

export type TraitScores = Record<Trait, number>;

export interface QuizOption {
  label: string;
  value: number;
}

export interface Question {
  id: string;
  text: string;
  trait: Trait;
  reverse: boolean;
  options: QuizOption[];
}

export interface Quiz {
  franchise: string;
  questions: Question[];
}

export interface Character {
  name: string;
  raw: TraitScores;
  z: TraitScores;
  blurb: string;
  /** Resolved at load time from public/art/characters/<id>/<slug>.<ext>, if a file exists. */
  image?: string;
  /**
   * When true, the character is excluded from matching and display. Their data
   * (raw/z/blurb/art) is retained so they can be un-hidden by removing this flag —
   * no rescoring required. Filtered out in loadFranchise (registry.ts).
   */
  hidden?: boolean;
}

export interface TraitStat {
  mean: number;
  std: number;
}

export interface CharacterData {
  franchise: string;
  stats: Record<Trait, TraitStat>;
  characters: Character[];
}

export interface FranchiseMeta {
  id: string;
  display_name: string;
  tagline?: string;
  description?: string;
  theme?: string;
  /** Optional card art shown behind the franchise card on the landing page. */
  image?: string;
}

export interface Franchise {
  meta: FranchiseMeta;
  quiz: Quiz;
  data: CharacterData;
}

/** A single character's closeness to the user's answers. */
export interface RankedMatch {
  name: string;
  blurb: string;
  distance: number;
  similarity: number;
  /** Character image URL, present only when a file exists for this character. */
  image?: string;
}

/** A character match tagged with its source franchise, for cross-universe ranking. */
export interface UniverseMatch extends RankedMatch {
  /** Franchise id, e.g. "breakingbad". */
  franchise: string;
  /** Franchise display name, e.g. "Breaking Bad". */
  franchiseName: string;
}

/** What the /api/match endpoint returns to the client. */
export interface MatchResult {
  franchise: string;
  match: RankedMatch;
  runnersUp: RankedMatch[];
  /** Top characters across ALL franchises, ranked by similarity descending. */
  acrossUniverses: UniverseMatch[];
  /** User's OCEAN scores on a 0-100 scale. */
  traits: TraitScores;
  /** Matched character's raw OCEAN scores (0-100), for radar comparison. */
  matchTraits: TraitScores;
  /** Id of the logged quiz_logs row, used to attach later feedback. */
  logId?: string | null;
}
