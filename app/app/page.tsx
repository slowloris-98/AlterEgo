import Link from "next/link";
import { listFranchises } from "@/lib/registry";

export default function Home() {
  const franchises = listFranchises();

  return (
    <main className="space-y-10">
      <header className="text-center">
        <h1 className="text-5xl font-bold text-fg">AlterEgo</h1>
        <p className="mx-auto mt-4 max-w-xl text-muted">
          Which character are you? Pick a world below, answer a short themed
          quiz, and we&apos;ll match you to a character using the Big Five
          (OCEAN) personality traits.
        </p>
      </header>

      {franchises.length === 0 ? (
        <p className="text-center text-muted">
          No tests available yet.
        </p>
      ) : (
        <ul className="grid gap-4 sm:grid-cols-2">
          {franchises.map((f) => (
            <li key={f.id}>
              <Link
                href={`/test/${f.id}`}
                className="block h-full rounded-2xl border border-border bg-surface/40 p-6 transition hover:border-accent/60 hover:bg-surface"
              >
                <h2 className="text-2xl font-semibold text-fg">
                  {f.display_name}
                </h2>
                {f.tagline && (
                  <p className="mt-1 text-sm italic text-muted">
                    {f.tagline}
                  </p>
                )}
                {f.description && (
                  <p className="mt-3 text-sm text-muted">
                    {f.description}
                  </p>
                )}
                <span className="mt-4 inline-block text-sm text-accent">
                  Take the test →
                </span>
              </Link>
            </li>
          ))}
        </ul>
      )}

      <footer className="pt-6 text-center text-xs text-muted/60">
        Curious? Look under the{" "}
        <a
          href="https://github.com/slowloris-98/AlterEgo"
          target="_blank"
          rel="noopener noreferrer"
          className="text-accent underline underline-offset-2"
        >
          hood
        </a>
        .
      </footer>
    </main>
  );
}
