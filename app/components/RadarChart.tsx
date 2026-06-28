"use client";

import {
  Radar,
  RadarChart as ReRadarChart,
  PolarGrid,
  PolarAngleAxis,
  PolarRadiusAxis,
  ResponsiveContainer,
  Legend,
} from "recharts";
import { TRAITS, type TraitScores } from "@/lib/types";

const LABELS: Record<string, string> = {
  openness: "Openness",
  conscientiousness: "Conscientiousness",
  extraversion: "Extraversion",
  agreeableness: "Agreeableness",
  neuroticism: "Neuroticism",
};

export default function RadarChart({
  user,
  match,
  matchName,
}: {
  user: TraitScores;
  match: TraitScores;
  matchName: string;
}) {
  const data = TRAITS.map((t) => ({
    trait: LABELS[t],
    You: Math.round(user[t]),
    [matchName]: Math.round(match[t]),
  }));

  return (
    <div className="h-80 w-full">
      <ResponsiveContainer width="100%" height="100%">
        <ReRadarChart data={data} outerRadius="70%">
          <PolarGrid stroke="rgb(var(--border))" />
          <PolarAngleAxis
            dataKey="trait"
            tick={{ fill: "rgb(var(--fg))", fontSize: 12 }}
          />
          <PolarRadiusAxis
            domain={[0, 100]}
            tick={{ fill: "rgb(var(--muted))", fontSize: 10 }}
            axisLine={false}
          />
          <Radar
            name="You"
            dataKey="You"
            stroke="rgb(var(--accent))"
            fill="rgb(var(--accent))"
            fillOpacity={0.35}
          />
          <Radar
            name={matchName}
            dataKey={matchName}
            stroke="rgb(var(--danger))"
            fill="rgb(var(--danger))"
            fillOpacity={0.25}
          />
          <Legend wrapperStyle={{ color: "rgb(var(--fg))" }} />
        </ReRadarChart>
      </ResponsiveContainer>
    </div>
  );
}
