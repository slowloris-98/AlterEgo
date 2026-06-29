import { NextResponse } from "next/server";
import { updateFeedback } from "@/lib/log";

export const runtime = "nodejs";

interface FeedbackRequest {
  logId?: string;
  rating?: "up" | "down";
  feedbackText?: string;
}

export async function POST(req: Request) {
  let body: FeedbackRequest;
  try {
    body = await req.json();
  } catch {
    return NextResponse.json({ error: "Invalid JSON body." }, { status: 400 });
  }

  const { logId, rating, feedbackText } = body;
  if (!logId || typeof logId !== "string") {
    return NextResponse.json({ error: "Missing 'logId'." }, { status: 400 });
  }
  if (rating !== undefined && rating !== "up" && rating !== "down") {
    return NextResponse.json({ error: "Invalid 'rating'." }, { status: 400 });
  }
  const text =
    typeof feedbackText === "string" ? feedbackText.trim() : undefined;
  if (!rating && !text) {
    return NextResponse.json(
      { error: "Nothing to record." },
      { status: 400 }
    );
  }

  // Best-effort; never blocks or fails on logging issues.
  await updateFeedback(logId, { rating, feedbackText: text });

  return NextResponse.json({ ok: true });
}
