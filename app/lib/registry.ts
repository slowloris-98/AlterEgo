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
const CHARACTER_ART_DIR = path.join(process.cwd(), "public", "art", "characters");
const IMAGE_EXTENSIONS = [".jpg", ".jpeg", ".png", ".webp", ".avif"];

function readJson<T>(filePath: string): T {
  return JSON.parse(fs.readFileSync(filePath, "utf-8")) as T;
}

/** Character name → filename-safe slug ("Harry Potter" → "harry-potter"). */
function slugify(name: string): string {
  return name
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");
}

/**
 * Look for a character image at public/art/characters/<id>/<slug>.<ext> for any supported
 * extension. Returns the public URL, or undefined if no file is present.
 */
function findCharacterImage(franchiseId: string, name: string): string | undefined {
  const slug = slugify(name);
  for (const ext of IMAGE_EXTENSIONS) {
    const file = path.join(CHARACTER_ART_DIR, franchiseId, `${slug}${ext}`);
    if (fs.existsSync(file)) {
      return `/art/characters/${franchiseId}/${slug}${ext}`;
    }
  }
  return undefined;
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
  const data = readJson<CharacterData>(path.join(dir, "characters.json"));
  // Attach a character image URL where a file exists (decoupled from the regenerated JSON).
  for (const c of data.characters) {
    c.image = findCharacterImage(id, c.name);
  }
  return {
    meta: readJson<FranchiseMeta>(path.join(dir, "meta.json")),
    quiz: readJson<Quiz>(path.join(dir, "quiz.json")),
    data,
  };
}
