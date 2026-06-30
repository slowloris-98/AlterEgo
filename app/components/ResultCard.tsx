"use client";

import { useState } from "react";
import { TRAITS, type MatchResult } from "@/lib/types";
import RadarChart from "./RadarChart";

const TRAIT_LABELS: Record<string, string> = {
  openness: "Openness",
  conscientiousness: "Conscientiousness",
  extraversion: "Extraversion",
  agreeableness: "Agreeableness",
  neuroticism: "Neuroticism",
};

function pct(n: number): string {
  return `${Math.round(n * 100)}%`;
}

/** First letters of the first two name words ("Harry Potter" → "HP"). */
function initials(name: string): string {
  return name
    .split(/\s+/)
    .slice(0, 2)
    .map((w) => w[0]?.toUpperCase() ?? "")
    .join("");
}

/**
 * Circular character portrait for the closest match. Falls back to a themed
 * initials disc when no image is set or the image fails to load.
 */
function MatchAvatar({ name, image }: { name: string; image?: string }) {
  const [failed, setFailed] = useState(false);
  const showImage = image && !failed;

  return (
    <div className="mx-auto mb-3 h-28 w-28">
      {showImage ? (
        // eslint-disable-next-line @next/next/no-img-element
        <img
          src={image}
          alt={name}
          className="h-28 w-28 rounded-full border-2 border-accent/50 object-cover shadow-lg"
          onError={() => setFailed(true)}
        />
      ) : (
        <div
          className="flex h-28 w-28 items-center justify-center rounded-full border-2 border-accent/40 bg-accent/15 text-3xl font-bold text-accent shadow-lg"
          aria-label={name}
        >
          {initials(name)}
        </div>
      )}
    </div>
  );
}

/** Records a thumbs rating and/or free-text feedback against the quiz_logs row. */
async function sendFeedback(
  logId: string | null | undefined,
  payload: { rating?: "up" | "down"; feedbackText?: string }
): Promise<void> {
  if (!logId) return; // Supabase unconfigured / not logged — nothing to attach to.
  try {
    await fetch("/api/feedback", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ logId, ...payload }),
    });
  } catch {
    // Best-effort: never let feedback failures break the results view.
  }
}

export default function ResultCard({
  result,
  logId,
  onRetake,
}: {
  result: MatchResult;
  logId?: string | null;
  onRetake: () => void;
}) {
  const { match, runnersUp, traits, matchTraits, acrossUniverses } = result;

  const [rating, setRating] = useState<"up" | "down" | null>(null);
  const [suggestion, setSuggestion] = useState("");
  const [sending, setSending] = useState(false);
  const [sent, setSent] = useState(false);

  function rate(value: "up" | "down") {
    setRating(value);
    void sendFeedback(logId, { rating: value });
  }

  async function sendSuggestion() {
    const text = suggestion.trim();
    if (!text || sending) return;
    setSending(true);
    await sendFeedback(logId, { feedbackText: text });
    setSending(false);
    setSent(true);
  }

  return (
    <div className="space-y-8">
      {/* Closest match */}
      <section className="rounded-2xl border border-accent/40 bg-surface/60 p-6 text-center shadow-lg">
        <p className="mb-4 text-sm uppercase tracking-widest text-accent/80">
          Your closest match
        </p>
        <MatchAvatar name={match.name} image={match.image} />
        <h2 className="mt-1 text-4xl font-bold text-accent">{match.name}</h2>
        <p className="mt-3 text-fg/90">{match.blurb}</p>
        <p className="mt-4 inline-block rounded-full border border-accent/30 px-4 py-1 text-sm text-muted">
          {pct(match.similarity)} match
        </p>
      </section>

      {/* Radar: you vs match */}
      <section className="rounded-2xl border border-border bg-surface/40 p-4">
        <h3 className="mb-2 text-center text-lg font-semibold text-fg">
          You vs. {match.name}
        </h3>
        <RadarChart user={traits} match={matchTraits} matchName={match.name} />
      </section>

      {/* OCEAN trait percentages */}
      <section className="rounded-2xl border border-border bg-surface/40 p-6">
        <h3 className="mb-4 text-lg font-semibold text-fg">
          Your personality traits
        </h3>
        <div className="space-y-3">
          {TRAITS.map((t) => (
            <div key={t}>
              <div className="mb-1 flex justify-between text-sm">
                <span className="text-fg/90">{TRAIT_LABELS[t]}</span>
                <span className="text-accent">{Math.round(traits[t])}%</span>
              </div>
              <div className="h-2.5 w-full overflow-hidden rounded-full bg-border/60">
                <div
                  className="h-full rounded-full bg-gradient-to-r from-accent/70 to-accent"
                  style={{ width: `${Math.round(traits[t])}%` }}
                />
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* Runners-up */}
      <section className="rounded-2xl border border-border bg-surface/40 p-6">
        <h3 className="mb-4 text-lg font-semibold text-fg">
          You're also a bit like…
        </h3>
        <ol className="space-y-3">
          {runnersUp.map((r, i) => (
            <li
              key={r.name}
              className="flex items-center gap-3 rounded-lg border border-border/60 bg-surface/40 p-3"
            >
              <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full border border-accent/40 text-sm text-accent">
                {i + 2}
              </span>
              <div className="min-w-0 flex-1">
                <p className="font-semibold text-fg">{r.name}</p>
                <p className="truncate text-sm text-muted">{r.blurb}</p>
              </div>
              <span className="shrink-0 text-sm text-accent">
                {pct(r.similarity)}
              </span>
            </li>
          ))}
        </ol>
      </section>

      {/* Across Universes: same profile ranked against every franchise's cast */}
      {acrossUniverses && acrossUniverses.length > 0 && (
        <section className="rounded-2xl border border-border bg-surface/40 p-6">
          <h3 className="text-lg font-semibold text-fg">Across Universes</h3>
          <p className="mb-4 text-sm text-muted">
            Who you'd be in every world we know.
          </p>
          <ol className="space-y-3">
            {acrossUniverses.map((u, i) => (
              <li
                key={`${u.franchise}-${u.name}`}
                className="flex items-center gap-3 rounded-lg border border-border/60 bg-surface/40 p-3"
              >
                <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full border border-accent/40 text-sm text-accent">
                  {i + 1}
                </span>
                <div className="min-w-0 flex-1">
                  <p className="font-semibold text-fg">{u.name}</p>
                  <p className="text-xs uppercase tracking-wide text-accent/70">
                    {u.franchiseName}
                  </p>
                  <p className="truncate text-sm text-muted">{u.blurb}</p>
                </div>
                <span className="shrink-0 text-sm text-accent">
                  {pct(u.similarity)}
                </span>
              </li>
            ))}
          </ol>
        </section>
      )}

      {/* Feedback: was the match accurate + open suggestions */}
      <section className="rounded-2xl border border-border bg-surface/40 p-6">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <h3 className="text-lg font-semibold text-fg">Was this accurate?</h3>
          <div className="flex items-center gap-2">
            <button
              type="button"
              aria-label="Thumbs up"
              aria-pressed={rating === "up"}
              onClick={() => rate("up")}
              className={`rounded-lg border px-4 py-2 text-lg transition ${
                rating === "up"
                  ? "border-accent bg-accent/10"
                  : "border-border hover:border-accent/50"
              }`}
            >
              👍
            </button>
            <button
              type="button"
              aria-label="Thumbs down"
              aria-pressed={rating === "down"}
              onClick={() => rate("down")}
              className={`rounded-lg border px-4 py-2 text-lg transition ${
                rating === "down"
                  ? "border-accent bg-accent/10"
                  : "border-border hover:border-accent/50"
              }`}
            >
              👎
            </button>
          </div>
        </div>
        {rating && (
          <p className="mt-2 text-sm text-muted">Thanks for the feedback!</p>
        )}

        <div className="mt-5">
          <label
            htmlFor="suggestion"
            className="mb-2 block text-sm text-fg/90"
          >
            Suggestions, improvements or new series ideas
          </label>
          {sent ? (
            <p className="rounded-lg border border-accent/40 bg-accent/10 p-3 text-sm text-fg">
              Thanks for the feedback!
            </p>
          ) : (
            <>
              <textarea
                id="suggestion"
                value={suggestion}
                onChange={(e) => setSuggestion(e.target.value)}
                rows={3}
                placeholder="Tell us what you think…"
                className="w-full rounded-lg border border-border bg-surface/40 p-3 text-sm text-fg placeholder:text-muted focus:border-accent/60 focus:outline-none"
              />
              <div className="mt-2 text-right">
                <button
                  type="button"
                  onClick={sendSuggestion}
                  disabled={!suggestion.trim() || sending}
                  className="rounded-lg border border-accent/40 px-4 py-2 text-accent transition hover:bg-accent/10 disabled:cursor-not-allowed disabled:opacity-40"
                >
                  {sending ? "Sending…" : "Send"}
                </button>
              </div>
            </>
          )}
        </div>
      </section>

      <div className="text-center">
        <button
          onClick={onRetake}
          className="rounded-lg border border-accent/40 px-6 py-2 text-accent transition hover:bg-accent/10"
        >
          Take it again
        </button>
      </div>
    </div>
  );
}
