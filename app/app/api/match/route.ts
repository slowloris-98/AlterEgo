import { NextResponse } from "next/server";
import { loadFranchise } from "@/lib/registry";
import { scoreAnswers } from "@/lib/scoring";
import { getClientIp, logSubmission } from "@/lib/log";
import type { MatchResult, TraitScores } from "@/lib/types";

export const runtime = "nodejs";

interface MatchRequest {
  franchise?: string;
  answers?: Record<string, number>;
}

export async function POST(req: Request) {
  let body: MatchRequest;
  try {
    body = await req.json();
  } catch {
    return NextResponse.json({ error: "Invalid JSON body." }, { status: 400 });
  }

  const { franchise, answers } = body;
  if (!franchise || typeof franchise !== "string") {
    return NextResponse.json({ error: "Missing 'franchise'." }, { status: 400 });
  }
  if (!answers || typeof answers !== "object") {
    return NextResponse.json({ error: "Missing 'answers'." }, { status: 400 });
  }

  const fr = loadFranchise(franchise);
  if (!fr) {
    return NextResponse.json(
      { error: `Unknown franchise: ${franchise}` },
      { status: 404 }
    );
  }

  // Require an answer for every question (values must be in range).
  for (const q of fr.quiz.questions) {
    const v = answers[q.id];
    if (typeof v !== "number" || v < 1 || v > 5) {
      return NextResponse.json(
        { error: `Missing or invalid answer for ${q.id}.` },
        { status: 400 }
      );
    }
  }

  const { raw, ranked } = scoreAnswers(answers, fr.quiz.questions, fr.data);
  const match = ranked[0];
  const runnersUp = ranked.slice(1, 4);

  const matchCharacter = fr.data.characters.find((c) => c.name === match.name)!;
  const matchTraits: TraitScores = matchCharacter.raw;

  // Best-effort logging; never blocks or fails the response. The row id lets
  // the client attach later feedback (thumbs / suggestions) to this submission.
  const logId = await logSubmission({
    franchise,
    answers,
    traitScores: raw,
    match,
    runnersUp,
    ip: getClientIp(req.headers),
  });

  const result: MatchResult = {
    franchise,
    match,
    runnersUp,
    traits: raw,
    matchTraits,
    logId,
  };

  return NextResponse.json(result);
}
