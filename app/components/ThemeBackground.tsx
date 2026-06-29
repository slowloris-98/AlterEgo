"use client";

import { useEffect, useMemo, useState, type CSSProperties } from "react";

/**
 * Ambient, decorative animated background for a test theme. Purely client-side
 * (CSS keyframes), sits behind page content, ignores pointer events, and is
 * hidden entirely under `prefers-reduced-motion` (see globals.css `.ae-bg`).
 *
 * Colours come from the theme CSS variables of the surrounding `[data-theme]`
 * wrapper, so each franchise tints automatically.
 */

type Kind =
  | "snow"
  | "ash"
  | "spark"
  | "firefly"
  | "cup"
  | "steam"
  | "crystal"
  | "bubble";

interface Layer {
  kind: Kind;
  count: number;
}

const EFFECTS: Record<string, Layer[]> = {
  got: [
    { kind: "snow", count: 28 },
    { kind: "ash", count: 16 },
  ],
  hp: [
    { kind: "spark", count: 24 },
    { kind: "firefly", count: 10 },
  ],
  friends: [
    { kind: "cup", count: 9 },
    { kind: "steam", count: 8 },
  ],
  // Breaking Bad: drifting "Blue Sky" meth crystals + rising flask bubbles.
  breakingbad: [
    { kind: "crystal", count: 18 },
    { kind: "bubble", count: 12 },
  ],
};

/** Random float in [min, max). */
function rand(min: number, max: number): number {
  return min + Math.random() * (max - min);
}

interface Particle {
  kind: Kind;
  style: CSSProperties;
}

/** Build the randomized inline style for one particle of a given kind. */
function makeParticle(kind: Kind): Particle {
  const left = rand(0, 100);
  const delay = -rand(0, 14); // negative → mid-animation on first paint
  const drift = `${rand(-40, 40)}px`;

  switch (kind) {
    case "snow": {
      const size = rand(2, 5);
      return {
        kind,
        style: {
          left: `${left}%`,
          top: "-5%",
          width: `${size}px`,
          height: `${size}px`,
          opacity: rand(0.3, 0.8),
          ["--ae-drift" as string]: drift,
          animationName: "ae-fall",
          animationDuration: `${rand(8, 16)}s`,
          animationDelay: `${delay}s`,
        },
      };
    }
    case "ash": {
      const size = rand(2, 4);
      return {
        kind,
        style: {
          left: `${left}%`,
          bottom: "-5%",
          width: `${size}px`,
          height: `${size}px`,
          ["--ae-drift" as string]: drift,
          animationName: "ae-rise, ae-flicker",
          animationDuration: `${rand(7, 13)}s, ${rand(0.6, 1.6)}s`,
          animationDelay: `${delay}s, ${delay}s`,
        },
      };
    }
    case "spark": {
      const size = rand(2, 4);
      return {
        kind,
        style: {
          left: `${left}%`,
          top: `${rand(0, 100)}%`,
          width: `${size}px`,
          height: `${size}px`,
          animationName: "ae-twinkle",
          animationDuration: `${rand(1.8, 4)}s`,
          animationDelay: `${delay}s`,
        },
      };
    }
    case "firefly": {
      const size = rand(4, 7);
      return {
        kind,
        style: {
          left: `${left}%`,
          top: `${rand(10, 90)}%`,
          width: `${size}px`,
          height: `${size}px`,
          ["--ae-dx" as string]: `${rand(-60, 60)}px`,
          ["--ae-dy" as string]: `${rand(-50, 50)}px`,
          animationName: "ae-wander",
          animationDuration: `${rand(6, 12)}s`,
          animationDelay: `${delay}s`,
        },
      };
    }
    case "cup": {
      const size = rand(20, 34);
      return {
        kind,
        style: {
          left: `${left}%`,
          bottom: "-10%",
          width: `${size}px`,
          height: `${size}px`,
          opacity: rand(0.12, 0.26),
          ["--ae-drift" as string]: `${rand(-50, 50)}px`,
          animationName: "ae-float",
          animationDuration: `${rand(16, 26)}s`,
          animationDelay: `${delay}s`,
        },
      };
    }
    case "steam": {
      return {
        kind,
        style: {
          left: `${left}%`,
          bottom: "-6%",
          width: `${rand(12, 20)}px`,
          height: `${rand(18, 30)}px`,
          opacity: rand(0.1, 0.22),
          ["--ae-drift" as string]: `${rand(-24, 24)}px`,
          animationName: "ae-rise",
          animationDuration: `${rand(9, 15)}s`,
          animationDelay: `${delay}s`,
        },
      };
    }
    case "crystal": {
      const size = rand(9, 18);
      return {
        kind,
        style: {
          left: `${left}%`,
          top: "-6%",
          width: `${size}px`,
          height: `${size}px`,
          ["--ae-drift" as string]: drift,
          ["--ae-spin" as string]: `${rand(-220, 220)}deg`,
          animationName: "ae-crystal, ae-glint",
          animationDuration: `${rand(11, 20)}s, ${rand(2.2, 4.5)}s`,
          animationDelay: `${delay}s, ${delay}s`,
        },
      };
    }
    case "bubble": {
      const size = rand(3, 7);
      return {
        kind,
        style: {
          left: `${left}%`,
          bottom: "-5%",
          width: `${size}px`,
          height: `${size}px`,
          ["--ae-drift" as string]: `${rand(-26, 26)}px`,
          animationName: "ae-rise",
          animationDuration: `${rand(8, 15)}s`,
          animationDelay: `${delay}s`,
        },
      };
    }
  }
}

/** Minimal coffee-cup glyph, tinted with the theme accent. */
function CupIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" width="100%" height="100%">
      <path
        d="M4 9h13v5a4 4 0 0 1-4 4H8a4 4 0 0 1-4-4V9Z"
        stroke="rgb(var(--accent))"
        strokeWidth="1.6"
      />
      <path
        d="M17 10h2.2a2.3 2.3 0 0 1 0 4.6H17"
        stroke="rgb(var(--accent))"
        strokeWidth="1.6"
      />
      <path
        d="M7 2.5c-.6.9-.6 1.6 0 2.5M11 2.5c-.6.9-.6 1.6 0 2.5"
        stroke="rgb(var(--fg))"
        strokeWidth="1.3"
        strokeLinecap="round"
      />
    </svg>
  );
}

/** Soft rising steam wisp. */
function SteamIcon() {
  return (
    <svg viewBox="0 0 12 24" fill="none" width="100%" height="100%">
      <path
        d="M6 23c-3-3 3-6 0-9s3-6 0-9S9 1 6 1"
        stroke="rgb(var(--fg))"
        strokeWidth="1.4"
        strokeLinecap="round"
      />
    </svg>
  );
}

/** Faceted "Blue Sky" meth crystal shard. Fixed blue (not theme-tinted) so the
 *  show's signature colour reads clearly over the green hazmat theme. */
function CrystalIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" width="100%" height="100%">
      <path
        d="M7 2h10l5 7-10 13L2 9l5-7Z"
        fill="rgb(56 198 240 / 0.45)"
        stroke="rgb(150 230 255 / 0.95)"
        strokeWidth="1"
        strokeLinejoin="round"
      />
      <path
        d="M7 2l5 7 5-7M2 9h20M12 9v13"
        stroke="rgb(190 240 255 / 0.8)"
        strokeWidth="0.7"
      />
    </svg>
  );
}

/** Static corner accent: the iconic yellow peephole picture frame. */
function FrameAccent() {
  return (
    <div
      aria-hidden
      className="absolute right-4 top-20 h-20 w-16 rotate-6 rounded-sm opacity-[0.18]"
      style={{
        border: "3px solid rgb(var(--accent))",
        boxShadow: "0 0 0 2px rgb(var(--accent) / 0.35)",
      }}
    />
  );
}

export default function ThemeBackground({ effect }: { effect?: string }) {
  const [mounted, setMounted] = useState(false);
  // Reduce density on small screens for performance.
  const [dense, setDense] = useState(true);

  useEffect(() => {
    setDense(window.innerWidth >= 640);
    setMounted(true);
  }, []);

  const layers = effect ? EFFECTS[effect] : undefined;

  const particles = useMemo<Particle[]>(() => {
    if (!layers) return [];
    const scale = dense ? 1 : 0.55;
    return layers.flatMap((layer) =>
      Array.from({ length: Math.round(layer.count * scale) }, () =>
        makeParticle(layer.kind)
      )
    );
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [effect, dense]);

  // Decorative + randomized → render client-only to avoid hydration mismatch.
  if (!mounted || !layers) return null;

  return (
    <div
      aria-hidden
      className="ae-bg pointer-events-none fixed inset-0 -z-10 overflow-hidden"
    >
      {particles.map((p, i) => (
        <span key={i} className={`ae-particle ae-${p.kind}`} style={p.style}>
          {p.kind === "cup" && <CupIcon />}
          {p.kind === "steam" && <SteamIcon />}
          {p.kind === "crystal" && <CrystalIcon />}
        </span>
      ))}
      {effect === "friends" && <FrameAccent />}
    </div>
  );
}
