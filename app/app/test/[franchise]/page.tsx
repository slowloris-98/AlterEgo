import Link from "next/link";
import { notFound } from "next/navigation";
import { listFranchises, loadFranchise } from "@/lib/registry";
import Quiz from "@/components/Quiz";
import ThemeBackground from "@/components/ThemeBackground";

// Pre-render a page per known franchise; still works for new ones on demand.
export function generateStaticParams() {
  return listFranchises().map((f) => ({ franchise: f.id }));
}

export default async function TestPage({
  params,
}: {
  params: Promise<{ franchise: string }>;
}) {
  const { franchise } = await params;
  const fr = loadFranchise(franchise);
  if (!fr) notFound();

  return (
    <div
      data-theme={fr.meta.theme ?? fr.meta.id}
      className="-mx-5 min-h-screen px-5"
    >
      <ThemeBackground effect={fr.meta.theme ?? fr.meta.id} />
      <main className="space-y-8">
        <header className="text-center">
          <Link
            href="/"
            className="text-sm text-muted transition hover:text-accent"
          >
            ← All tests
          </Link>
          <h1 className="mt-2 text-4xl font-bold text-accent">
            {fr.meta.display_name}
          </h1>
          {fr.meta.tagline && (
            <p className="mt-2 italic text-muted">{fr.meta.tagline}</p>
          )}
        </header>

        <Quiz meta={fr.meta} questions={fr.quiz.questions} />
      </main>
    </div>
  );
}
