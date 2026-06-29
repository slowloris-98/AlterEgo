import crypto from "node:crypto";
import { getSupabase } from "./db";
import type { RankedMatch, TraitScores } from "./types";

/**
 * Anonymous logging of each submission for later distribution analysis.
 * Identity is a salted SHA-256 hash of the IP — no raw PII is stored.
 */

/** Best-effort client IP from proxy headers (Vercel sets x-forwarded-for). */
export function getClientIp(headers: Headers): string | null {
  const fwd = headers.get("x-forwarded-for");
  if (fwd) return fwd.split(",")[0].trim();
  return headers.get("x-real-ip");
}

function hashIp(ip: string | null): string | null {
  if (!ip) return null;
  const salt = process.env.IP_HASH_SALT ?? "";
  return crypto.createHash("sha256").update(ip + salt).digest("hex");
}

export interface SubmissionLog {
  franchise: string;
  answers: Record<string, number>;
  traitScores: TraitScores;
  match: RankedMatch;
  runnersUp: RankedMatch[];
  ip: string | null;
}

/**
 * Insert one quiz_logs row and return its id (used to attach later feedback).
 * Silently no-ops and returns null when Supabase is unconfigured or on error.
 */
export async function logSubmission(
  entry: SubmissionLog
): Promise<string | null> {
  const supabase = getSupabase();
  if (!supabase) return null;

  try {
    const { data, error } = await supabase
      .from("quiz_logs")
      .insert({
        franchise: entry.franchise,
        answers: entry.answers,
        trait_scores: entry.traitScores,
        match: entry.match.name,
        runners_up: entry.runnersUp.map((r) => ({
          name: r.name,
          distance: r.distance,
          similarity: r.similarity,
        })),
        distance: entry.match.distance,
        ip_hash: hashIp(entry.ip),
      })
      .select("id")
      .single();
    if (error) {
      console.error("quiz_logs insert failed:", error.message);
      return null;
    }
    return (data?.id as string) ?? null;
  } catch (err) {
    console.error("quiz_logs insert threw:", err);
    return null;
  }
}

export interface FeedbackUpdate {
  rating?: "up" | "down";
  feedbackText?: string;
}

/**
 * Attach a rating and/or free-text feedback to an existing quiz_logs row.
 * Best-effort: no-ops when Supabase is unconfigured, never throws.
 */
export async function updateFeedback(
  logId: string,
  feedback: FeedbackUpdate
): Promise<void> {
  const supabase = getSupabase();
  if (!supabase) return;

  const patch: Record<string, string> = {};
  if (feedback.rating) patch.rating = feedback.rating;
  if (feedback.feedbackText) patch.feedback_text = feedback.feedbackText;
  if (Object.keys(patch).length === 0) return;

  try {
    const { error } = await supabase
      .from("quiz_logs")
      .update(patch)
      .eq("id", logId);
    if (error) console.error("quiz_logs feedback update failed:", error.message);
  } catch (err) {
    console.error("quiz_logs feedback update threw:", err);
  }
}
