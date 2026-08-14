import Link from "next/link";
import { notFound } from "next/navigation";

import { AnnotatedPdfViewer } from "@/components/annotated-pdf-viewer";
import { DeleteDeckButton } from "@/components/delete-deck-button";
import { SignOutButton } from "@/components/sign-out-button";
import { getDeckDetail } from "@/lib/api";
import { isExampleDeckId } from "@/lib/decks";
import { getAccessToken } from "@/lib/supabase/access-token";

export const dynamic = "force-dynamic";

export default async function DeckDetailPage({
  params,
}: {
  params: Promise<{ deck_id: string }>;
}) {
  const { deck_id } = await params;
  const accessToken = await getAccessToken();
  const detail = await getDeckDetail(deck_id, { accessToken }).catch(() => null);
  if (!detail) {
    notFound();
  }

  const { deck, slides, isFallback } = detail;
  const scoreBreakdown = deck.score_summary?.score_breakdown ?? [];

  return (
    <div className="min-h-screen bg-[linear-gradient(180deg,#f8fafc_0%,#eef2ff_100%)] px-6 py-12">
      <div className="mx-auto max-w-[1500px]">
        <Link href="/" className="text-sm font-medium text-slate-600 transition hover:text-slate-900">
          ← Back to gallery
        </Link>
        <div className="mt-4">
          <SignOutButton />
        </div>

        <div className="mt-6 rounded-[2rem] border border-slate-200 bg-white p-8 shadow-sm">
          <div className="flex flex-col gap-5 xl:flex-row xl:items-start xl:justify-between">
            <div className="max-w-3xl">
              <p className="text-sm font-semibold uppercase tracking-[0.2em] text-slate-500">{deck.stage}</p>
              <h1 className="mt-2 text-4xl font-semibold tracking-tight text-slate-950">{deck.company_name}</h1>
              <p className="mt-4 text-sm leading-7 text-slate-600">
                Sector: <span className="font-medium text-slate-900">{deck.sector}</span>
              </p>
              <p className="mt-1 text-sm leading-7 text-slate-600">
                Team: <span className="font-medium text-slate-900">{deck.team.length ? deck.team.join(", ") : "No team listed"}</span>
              </p>
            </div>

            <div className="flex w-full max-w-sm flex-col gap-3">
              <div className="rounded-[1.5rem] bg-slate-950 p-5 text-white">
                <p className="text-xs uppercase tracking-[0.2em] text-slate-400">Overall score</p>
                <p className="mt-2 text-4xl font-semibold tracking-tight">
                  {deck.score_summary?.overall_score != null ? deck.score_summary.overall_score : "—"}
                </p>
                {deck.score_summary?.raw_overall_score != null &&
                deck.score_summary.raw_overall_score !== deck.score_summary.overall_score ? (
                  <p className="mt-1 text-sm text-slate-300">
                    Raw score: {deck.score_summary.raw_overall_score}
                  </p>
                ) : null}
                <p className="mt-1 text-sm text-slate-300">
                  {deck.score_summary?.scored_sections ?? 0} scored sections
                </p>
                <p className="mt-4 text-sm text-slate-300">
                  {deck.score_summary?.red_flag_count ?? 0} red flag{deck.score_summary?.red_flag_count === 1 ? "" : "s"}
                </p>
              </div>
              {!isFallback && !isExampleDeckId(deck.deck_id) ? <DeleteDeckButton deckId={deck.deck_id} redirectToHome /> : null}
              {isFallback ? (
                <div className="rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-700">
                  Using fallback slide data because the backend content endpoints are unavailable.
                </div>
              ) : null}
            </div>
          </div>
        </div>

        <div className="mt-8 grid gap-8 xl:grid-cols-[minmax(0,1fr)_24rem]">
          <section className="overflow-hidden rounded-[2rem] border border-slate-200 bg-white shadow-sm">
            <div className="border-b border-slate-200 px-6 py-4">
              <h2 className="text-xl font-semibold text-slate-950">Annotated deck review</h2>
            </div>
            <AnnotatedPdfViewer pdfUrl={deck.deck_pdf_url} slides={slides} scoreBreakdown={scoreBreakdown} />
          </section>

          <aside className="space-y-6">
            <section className="rounded-[2rem] border border-slate-200 bg-white p-6 shadow-sm">
              <div className="flex items-center justify-between">
                <h2 className="text-xl font-semibold text-slate-950">Score breakdown</h2>
              </div>
              <div className="mt-4 space-y-3">
                {scoreBreakdown.map((item) => (
                  <div key={`${deck.deck_id}-${item.rubric_section}`} className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-4">
                    <div className="flex items-center justify-between gap-3">
                      <p className="text-sm font-medium text-slate-900">{item.rubric_section}</p>
                      <span className="rounded-full bg-white px-3 py-1 text-xs font-medium text-slate-700">
                        {item.value != null ? `${item.value} pts` : item.raw_score || "Not scored"}
                      </span>
                    </div>
                    {(item.confidence != null || item.adjusted_value != null || item.verification_status) ? (
                      <div className="mt-3 flex flex-wrap gap-2 text-xs font-medium text-slate-600">
                        {item.confidence != null ? (
                          <span className="rounded-full bg-white px-3 py-1">
                            Confidence {Math.round(item.confidence * 100)}%
                          </span>
                        ) : null}
                        {item.adjusted_value != null ? (
                          <span className="rounded-full bg-white px-3 py-1">
                            Adjusted {item.adjusted_value} pts
                          </span>
                        ) : null}
                        {item.verification_status ? (
                          <span className="rounded-full bg-white px-3 py-1">
                            Verification {item.verification_status.replaceAll("_", " ")}
                          </span>
                        ) : null}
                      </div>
                    ) : null}
                    {item.feedback ? (
                      <p className="mt-3 text-sm leading-7 text-slate-700">{item.feedback}</p>
                    ) : null}
                    {item.confidence_reason ? (
                      <p className="mt-2 text-sm leading-6 text-slate-600">{item.confidence_reason}</p>
                    ) : null}
                    {item.critic_notes ? (
                      <p className="mt-2 text-sm leading-6 text-slate-600">{item.critic_notes}</p>
                    ) : null}
                    {item.external_checks?.length ? (
                      <div className="mt-3 space-y-2">
                        {item.external_checks.slice(0, 2).map((check, index) => (
                          <div key={`${deck.deck_id}-${item.rubric_section}-check-${index}`} className="rounded-xl border border-slate-200 bg-white p-3">
                            <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">
                              {check.status} via {check.source}
                            </p>
                            <p className="mt-1 text-sm leading-6 text-slate-700">{check.claim}</p>
                            {check.url ? (
                              <a href={check.url} className="mt-1 block truncate text-sm font-medium text-blue-700 hover:text-blue-900">
                                {check.url}
                              </a>
                            ) : null}
                          </div>
                        ))}
                      </div>
                    ) : null}
                  </div>
                ))}
                {!scoreBreakdown.length ? (
                  <div className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-500">
                    No evaluation summary is available.
                  </div>
                ) : null}
              </div>
            </section>

            <section className="rounded-[2rem] border border-slate-200 bg-white p-6 shadow-sm">
              <div className="flex items-center justify-between">
                <h2 className="text-xl font-semibold text-slate-950">Red flags</h2>
                <p className="text-sm text-slate-500">
                  {deck.score_summary?.red_flag_count ?? 0} total
                </p>
              </div>

              <div className="mt-4 space-y-4">
                {deck.score_summary?.red_flags?.length ? (
                  <div className="space-y-3">
                    {deck.score_summary.red_flags.map((flag, index) => (
                      <div key={`${deck.deck_id}-red-flag-${index}`} className="rounded-2xl border border-rose-200 bg-rose-50 p-4">
                        <p className="text-sm leading-7 text-rose-900">{flag}</p>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-500">
                    No red flags are recorded for this deck.
                  </div>
                )}
              </div>
            </section>
          </aside>
        </div>
      </div>
    </div>
  );
}
