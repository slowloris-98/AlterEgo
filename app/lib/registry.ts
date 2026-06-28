import fs from "node:fs";
import path from "node:path";
import type {
  CharacterData,
  Franchise,
  FranchiseMeta,
  Quiz,
} from "./types";

/**
 * Server-only. Discovers personality tests by scanning `data/<id>/` for folders
 * that contain meta.json + quiz.json + characters.json. Dropping in a new data
 * folder makes a new test appear with no code changes.
 */

const DATA_DIR = path.join(process.cwd(), "data");

function readJson<T>(filePath: string): T {
  return JSON.parse(fs.readFileSync(filePath, "utf-8")) as T;
}

function isFranchiseDir(id: string): boolean {
  const dir = path.join(DATA_DIR, id);
  if (!fs.existsSync(dir) || !fs.statSync(dir).isDirectory()) return false;
  return (
    fs.existsSync(path.join(dir, "meta.json")) &&
    fs.existsSync(path.join(dir, "quiz.json")) &&
    fs.existsSync(path.join(dir, "characters.json"))
  );
}

/** Lightweight list for the landing page — meta only. */
export function listFranchises(): FranchiseMeta[] {
  if (!fs.existsSync(DATA_DIR)) return [];
  return fs
    .readdirSync(DATA_DIR)
    .filter(isFranchiseDir)
    .map((id) => readJson<FranchiseMeta>(path.join(DATA_DIR, id, "meta.json")))
    .sort((a, b) => a.display_name.localeCompare(b.display_name));
}

/** Full franchise payload (meta + quiz + character data). Null if unknown. */
export function loadFranchise(id: string): Franchise | null {
  // Guard against path traversal; only accept simple ids.
  if (!/^[a-z0-9_-]+$/i.test(id) || !isFranchiseDir(id)) return null;
  const dir = path.join(DATA_DIR, id);
  return {
    meta: readJson<FranchiseMeta>(path.join(dir, "meta.json")),
    quiz: readJson<Quiz>(path.join(dir, "quiz.json")),
    data: readJson<CharacterData>(path.join(dir, "characters.json")),
  };
}
