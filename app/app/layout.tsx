import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "AlterEgo — Personality Tests",
  description:
    "Discover which character you are. Answer a themed quiz scored on the Big Five (OCEAN) traits.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>
        <div className="mx-auto max-w-3xl px-5 py-10">{children}</div>
        {/* theme tokens cascade from :root (hub) or [data-theme] wrappers */}
      </body>
    </html>
  );
}
