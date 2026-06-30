/**
 * Scoring regression checks for every franchise:
 *
 *  1. Parity — feeds the build-generated answer keys through the TypeScript scoring
 *     pipeline and asserts each key's closest match is the intended character. This
 *     proves lib/scoring.ts agrees with build/core/validate.py and that no character's
 *     self-match regressed under the cosine-similarity matching.
 *
 *  2. No-magnet — runs a batch of deterministic random respondents through the pipeline
 *     and asserts no single character attracts >40% of them. This is the automated guard
 *     against the Euclidean "centroid magnet" that funnelled moderate users into the one
 *     or two characters nearest the cast average.
 *
 * Run: npm test   (from the app/ directory)
 */
import fs from "node:fs";
import path from "node:path";
import { scoreAnswers } from "./scoring";
import type { CharacterData, Quiz } from "./types";

const FRANCHISES = ["breakingbad", "friends", "got", "hp", "ramayana"];
const MAGNET_THRESHOLD = 0.4; // flag if one character attracts >40% of random respondents
const SIM_N = 20000;

interface AnswerKey {
  name: string;
  answers: Record<string, number>;
}

function load(franchise: string) {
  const dataDir = path.join(process.cwd(), "data", franchise);
  const buildOut = path.join(
    process.cwd(),
    "..",
    "build",
    "franchises",
    franchise,
    "out"
  );
  const quiz = JSON.parse(
    fs.readFileSync(path.join(dataDir, "quiz.json"), "utf-8")
  ) as Quiz;
  const data = JSON.parse(
    fs.readFileSync(path.join(dataDir, "characters.json"), "utf-8")
  ) as CharacterData;
  // Mirror loadFranchise (registry.ts): hidden characters are excluded from matching.
  const hidden = new Set(
    data.characters.filter((c) => c.hidden).map((c) => c.name)
  );
  data.characters = data.characters.filter((c) => !c.hidden);
  const keys = (
    JSON.parse(
      fs.readFileSync(path.join(buildOut, "answer_keys.json"), "utf-8")
    ) as { keys: AnswerKey[] }
  ).keys;
  return { quiz, data, keys, hidden };
}

/** Deterministic PRNG (mulberry32) so the no-magnet check is reproducible. */
function mulberry32(seed: number): () => number {
  let a = seed;
  return () => {
    a |= 0;
    a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

let pass = 0;
let fail = 0;

for (const franchise of FRANCHISES) {
  const { quiz, data, keys, hidden } = load(franchise);

  // 1. Parity: every answer key resolves to its own character.
  for (const key of keys) {
    // A hidden character can never be matched; their answer key isn't expected to resolve.
    if (hidden.has(key.name)) continue;
    const { ranked } = scoreAnswers(key.answers, quiz.questions, data);
    const top = ranked[0].name;
    if (top === key.name) {
      pass++;
    } else {
      fail++;
      console.error(`  ✗ [${franchise}] ${key.name} → matched ${top}`);
    }
  }

  // 2. No-magnet: no character should dominate random respondents.
  const rng = mulberry32(0xC0FFEE);
  const counts = new Map<string, number>();
  for (let i = 0; i < SIM_N; i++) {
    const answers: Record<string, number> = {};
    for (const q of quiz.questions) {
      answers[q.id] = 1 + Math.floor(rng() * 5); // 1..5
    }
    const { ranked } = scoreAnswers(answers, quiz.questions, data);
    const name = ranked[0].name;
    counts.set(name, (counts.get(name) ?? 0) + 1);
  }
  let topName = "";
  let topCount = 0;
  for (const [name, count] of counts) {
    if (count > topCount) {
      topCount = count;
      topName = name;
    }
  }
  const topShare = topCount / SIM_N;
  if (topShare > MAGNET_THRESHOLD) {
    fail++;
    console.error(
      `  ✗ [${franchise}] magnet: ${topName} attracts ${(topShare * 100).toFixed(0)}% of random respondents`
    );
  } else {
    pass++;
  }
}

console.log(`\nScoring checks: ${pass}/${pass + fail} passed.`);

if (fail > 0) {
  console.error(`FAIL: ${fail} check(s) failed.`);
  process.exit(1);
} else {
  console.log(
    "PASS: all franchises match their answer keys and show no magnet character."
  );
}
