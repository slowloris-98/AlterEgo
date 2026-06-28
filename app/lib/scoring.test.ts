/**
 * Scoring parity check: feeds the build-generated answer keys through the
 * TypeScript scoring pipeline and asserts the closest match is the intended
 * character. This proves lib/scoring.ts agrees with build/core/validate.py.
 *
 * Run: npm test   (from the app/ directory)
 */
import fs from "node:fs";
import path from "node:path";
import { scoreAnswers } from "./scoring";
import type { CharacterData, Quiz } from "./types";

const dataDir = path.join(process.cwd(), "data", "got");
const buildOut = path.join(
  process.cwd(),
  "..",
  "build",
  "franchises",
  "got",
  "out"
);

const quiz = JSON.parse(
  fs.readFileSync(path.join(dataDir, "quiz.json"), "utf-8")
) as Quiz;
const data = JSON.parse(
  fs.readFileSync(path.join(dataDir, "characters.json"), "utf-8")
) as CharacterData;
const keys = JSON.parse(
  fs.readFileSync(path.join(buildOut, "answer_keys.json"), "utf-8")
) as { keys: { name: string; answers: Record<string, number> }[] };

let pass = 0;
let fail = 0;

for (const key of keys.keys) {
  const { ranked } = scoreAnswers(key.answers, quiz.questions, data);
  const top = ranked[0].name;
  if (top === key.name) {
    pass++;
  } else {
    fail++;
    console.error(`  ✗ ${key.name} → matched ${top}`);
  }
}

console.log(`\nScoring parity: ${pass}/${pass + fail} answer keys matched.`);

if (fail > 0) {
  console.error(
    `FAIL: ${fail} answer key(s) did not resolve to their character.`
  );
  process.exit(1);
} else {
  console.log("PASS: scoring.ts matches the build-generated answer keys.");
}
