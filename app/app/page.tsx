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
          quiz, and we&apos;ll match you to a character using the{" "}
          <a
            href="https://openpsychometrics.org/tests/IPIP-BFFM/"
            target="_blank"
            rel="noopener noreferrer"
            className="text-accent underline underline-offset-2 hover:no-underline"
          >
            Big Five (OCEAN) personality test
          </a>
          .
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
                className="group relative flex h-60 flex-col justify-end overflow-hidden rounded-2xl border border-border transition hover:border-accent/60"
              >
                {f.image ? (
                  <div
                    className="absolute inset-0 bg-cover bg-center transition duration-500 group-hover:scale-105"
                    style={{ backgroundImage: `url(${f.image})` }}
                    aria-hidden
                  />
                ) : (
                  <div className="absolute inset-0 bg-surface" aria-hidden />
                )}
                {/* Scrim so card text stays legible over the art. */}
                <div
                  className="absolute inset-0 bg-gradient-to-t from-black/90 via-black/55 to-black/15"
                  aria-hidden
                />
                <div className="relative p-6 [text-shadow:0_1px_3px_rgb(0_0_0_/_0.7)]">
                  <h2 className="text-2xl font-semibold text-white">
                    {f.display_name}
                  </h2>
                  {f.tagline && (
                    <p className="mt-1 text-sm italic text-white/80">
                      {f.tagline}
                    </p>
                  )}
                  {f.description && (
                    <p className="mt-2 line-clamp-2 text-sm text-white/75">
                      {f.description}
                    </p>
                  )}
                  <span className="mt-3 inline-block text-sm font-medium text-white">
                    Take the test →
                  </span>
                </div>
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
