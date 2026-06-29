"use client";

import { useMemo, useState } from "react";
import type { FranchiseMeta, MatchResult, Question } from "@/lib/types";
import ResultCard from "./ResultCard";

/** Fisher-Yates shuffle (returns a new array). */
function shuffle<T>(arr: T[]): T[] {
  const a = [...arr];
  for (let i = a.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [a[i], a[j]] = [a[j], a[i]];
  }
  return a;
}

export default function Quiz({
  meta,
  questions,
}: {
  meta: FranchiseMeta;
  questions: Question[];
}) {
  // Shuffle order once per mount → a fresh order on every visit/reload.
  // `nonce` lets "Take it again" reshuffle without a full reload.
  const [nonce, setNonce] = useState(0);
  const ordered = useMemo(
    () => shuffle(questions),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [nonce]
  );

  const [answers, setAnswers] = useState<Record<string, number>>({});
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<MatchResult | null>(null);

  const answeredCount = Object.keys(answers).length;
  const total = ordered.length;
  const allAnswered = answeredCount === total;

  function select(qid: string, value: number) {
    setAnswers((prev) => ({ ...prev, [qid]: value }));
  }

  async function submit() {
    setSubmitting(true);
    setError(null);
    try {
      const res = await fetch("/api/match", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ franchise: meta.id, answers }),
      });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data.error ?? `Request failed (${res.status}).`);
      }
      const data: MatchResult = await res.json();
      setResult(data);
      window.scrollTo({ top: 0, behavior: "smooth" });
    } catch (e) {
      setError(e instanceof Error ? e.message : "Something went wrong.");
    } finally {
      setSubmitting(false);
    }
  }

  function retake() {
    setResult(null);
    setAnswers({});
    setError(null);
    setNonce((n) => n + 1); // reshuffle
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  if (result) {
    return (
      <ResultCard result={result} logId={result.logId} onRetake={retake} />
    );
  }

  return (
    <div className="space-y-6">
      {/* Sticky progress */}
      <div className="sticky top-0 z-10 -mx-5 bg-bg/90 px-5 py-3 backdrop-blur">
        <div className="flex items-center justify-between text-sm text-muted">
          <span>
            {answeredCount} / {total} answered
          </span>
          <span>{Math.round((answeredCount / total) * 100)}%</span>
        </div>
        <div className="mt-2 h-1.5 w-full overflow-hidden rounded-full bg-border/60">
          <div
            className="h-full rounded-full bg-accent transition-all"
            style={{ width: `${(answeredCount / total) * 100}%` }}
          />
        </div>
      </div>

      <ol className="space-y-6">
        {ordered.map((q, idx) => (
          <li
            key={q.id}
            className="rounded-2xl border border-border bg-surface/40 p-5"
          >
            <p className="mb-4 font-semibold text-fg">
              <span className="mr-2 text-accent">{idx + 1}.</span>
              {q.text}
            </p>
            <div className="space-y-2">
              {q.options.map((o) => {
                const checked = answers[q.id] === o.value;
                return (
                  <label
                    key={o.value}
                    className={`flex cursor-pointer items-center gap-3 rounded-lg border p-3 text-sm transition ${
                      checked
                        ? "border-accent bg-accent/10 text-fg"
                        : "border-border text-muted hover:border-accent/50"
                    }`}
                  >
                    <input
                      type="radio"
                      name={q.id}
                      value={o.value}
                      checked={checked}
                      onChange={() => select(q.id, o.value)}
                      className="sr-only"
                    />
                    <span
                      className={`flex h-4 w-4 shrink-0 items-center justify-center rounded-full border ${
                        checked ? "border-accent" : "border-border"
                      }`}
                    >
                      {checked && (
                        <span className="h-2 w-2 rounded-full bg-accent" />
                      )}
                    </span>
                    {o.label}
                  </label>
                );
              })}
            </div>
          </li>
        ))}
      </ol>

      {error && (
        <p className="rounded-lg border border-danger/50 bg-danger/10 p-3 text-sm text-fg">
          {error}
        </p>
      )}

      <div className="sticky bottom-0 -mx-5 bg-bg/90 px-5 py-4 backdrop-blur">
        <button
          onClick={submit}
          disabled={!allAnswered || submitting}
          className="w-full rounded-lg bg-accent py-3 font-semibold text-accent-ink transition enabled:hover:brightness-110 disabled:cursor-not-allowed disabled:opacity-40"
        >
          {submitting
            ? "Reading the runes…"
            : allAnswered
            ? "Reveal my match"
            : `Answer all ${total} questions`}
        </button>
      </div>
    </div>
  );
}
