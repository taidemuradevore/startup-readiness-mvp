import Link from "next/link";

import { DeckVisibilityToggle } from "@/components/deck-visibility-toggle";
import { DeleteDeckButton } from "@/components/delete-deck-button";
import { DeckUploadWidget } from "@/components/deck-upload-widget";
import { ProfileModal } from "@/components/profile-modal";
import { SignOutButton } from "@/components/sign-out-button";
import { getDecks, getUserProfile, type UserProfile } from "@/lib/api";
import { isExampleDeckId } from "@/lib/decks";
import { getAccessToken } from "@/lib/supabase/access-token";

export const dynamic = "force-dynamic";

function ScorePill({
  label,
  value,
}: {
  label: string;
  value: string;
}) {
  return (
    <div className="rounded-full border border-slate-200 bg-white px-3 py-1 text-xs font-medium text-slate-700">
      <span className="text-slate-500">{label}:</span> {value}
    </div>
  );
}

export default async function HomePage() {
  const accessToken = await getAccessToken();
  const { decks, isFallback, error } = await getDecks({ accessToken });
  let profile: UserProfile | null = null;
  let shouldAutoOpenProfile = false;

  try {
    profile = await getUserProfile({ accessToken });
    shouldAutoOpenProfile = !profile;
  } catch {
    shouldAutoOpenProfile = false;
  }
  const isVcProfile = profile?.profile_type === "vc";

  return (
    <div className="min-h-screen bg-[linear-gradient(180deg,#f5f7fb_0%,#eef2ff_38%,#f8fafc_100%)] px-6 py-10">
      <div className="mx-auto max-w-[1500px]">
        <header className="rounded-[2rem] border border-slate-200 bg-white/80 px-8 py-8 shadow-sm backdrop-blur">
          <div className="flex flex-col gap-5 lg:flex-row lg:items-end lg:justify-between">
            <div className="max-w-4xl">
              <p className="text-xs font-semibold uppercase tracking-[0.3em] text-slate-500">Startup Readiness</p>
              <h1 className="mt-3 text-4xl font-semibold tracking-tight text-slate-950 lg:text-5xl">
                Ingested deck gallery with live scoring context
              </h1>
              <p className="mt-4 max-w-3xl text-sm leading-7 text-slate-600">
                Review uploaded pitch decks as full PDFs, scan their evaluation footprint, and insert the next deck from the same surface.
              </p>
            </div>

            <div className="grid grid-cols-2 gap-3 text-sm text-slate-600 sm:w-fit">
              <div className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3">
                <p className="text-xs uppercase tracking-[0.18em] text-slate-500">Decks</p>
                <p className="mt-1 text-2xl font-semibold text-slate-950">{decks.length}</p>
              </div>
              <div className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3">
                <p className="text-xs uppercase tracking-[0.18em] text-slate-500">Mode</p>
                <p className="mt-1 text-sm font-medium text-slate-950">{isFallback ? "Example fallback" : "Live backend"}</p>
              </div>
              <ProfileModal initialProfile={profile} autoOpen={shouldAutoOpenProfile} className="w-full" />
              <SignOutButton className="w-full" />
            </div>
          </div>

          {isFallback ? (
            <div className="mt-6 rounded-2xl border border-amber-200 bg-amber-50 px-5 py-4 text-sm leading-6 text-amber-700">
              Backend gallery data is unavailable.
              {error ? <span className="mt-2 block font-medium">Reason: {error}</span> : null}
            </div>
          ) : null}
        </header>

        <section className="mt-10">
          <div className="mb-5 flex items-center justify-between">
            <div>
              <h2 className="text-2xl font-semibold tracking-tight text-slate-950">
                {isVcProfile ? "Top deck matches" : "Deck gallery"}
              </h2>
              <p className="mt-1 text-sm text-slate-600">
                {isVcProfile
                  ? "VC-visible decks ranked by your thesis, sector focus, stage focus, and deck quality."
                  : "Full-document previews with the latest stored evaluation summary."}
              </p>
            </div>
          </div>

          <div className="grid gap-8 xl:grid-cols-2">
            {!decks.length ? (
              <div className="rounded-[2rem] border border-slate-200 bg-white px-6 py-10 text-sm leading-7 text-slate-600 shadow-sm xl:col-span-2">
                No decks are available for this account yet. If you expected decks here, check that the frontend Vercel project has
                `NEXT_PUBLIC_API_URL`, `NEXT_PUBLIC_SUPABASE_URL`, and `NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY` set, and that the backend is reachable.
              </div>
            ) : null}
            {decks.map((deck) => (
              <article
                key={deck.deck_id}
                className="overflow-hidden rounded-[2rem] border border-slate-200 bg-white shadow-sm"
              >
                <div className="border-b border-slate-200 px-6 py-5">
                  <div className="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
                    <div>
                      <h3 className="text-2xl font-semibold tracking-tight text-slate-950">{deck.company_name}</h3>
                      <p className="mt-2 text-sm text-slate-500">Deck ID: {deck.deck_id}</p>
                    </div>
                    <div className="flex flex-wrap gap-2">
                      <ScorePill label="Stage" value={deck.stage || "Unknown"} />
                      <ScorePill
                        label="Score"
                        value={deck.score_summary?.overall_score != null ? `${Number(Number(deck.score_summary.overall_score / 110 * 100).toFixed(2))}%` : "Pending"}
                      />
                      <ScorePill
                        label="Red flags"
                        value={String(deck.score_summary?.red_flag_count ?? 0)}
                      />
                      <ScorePill
                        label="VC visibility"
                        value={deck.visible_to_vcs ? "Visible" : "Hidden"}
                      />
                      {deck.match_score != null ? (
                        <ScorePill
                          label="Match"
                          value={`${deck.match_score}%`}
                        />
                      ) : null}
                    </div>
                  </div>

                  {deck.match_reason ? (
                    <div className="mt-4 rounded-2xl border border-blue-100 bg-blue-50 px-4 py-3 text-sm leading-6 text-blue-900">
                      {deck.match_reason}
                      {deck.matched_facets?.length ? (
                        <div className="mt-3 flex flex-wrap gap-2">
                          {deck.matched_facets.map((facet) => (
                            <span
                              key={`${deck.deck_id}-${facet.facet_type}`}
                              className="rounded-full border border-blue-200 bg-white px-3 py-1 text-xs font-medium text-blue-800"
                            >
                              {facet.facet_title}: {facet.score}%
                            </span>
                          ))}
                        </div>
                      ) : null}
                    </div>
                  ) : null}

                  <div className="mt-4 grid gap-4 text-sm sm:grid-cols-3">
                    <div>
                      <p className="text-slate-500">Sector</p>
                      <p className="mt-1 font-medium text-slate-900">{deck.sector || "Unknown"}</p>
                    </div>
                    <div className="sm:col-span-2">
                      <p className="text-slate-500">Team</p>
                      <p className="mt-1 font-medium text-slate-900">
                        {deck.team.length ? deck.team.join(", ") : "No team listed"}
                      </p>
                    </div>
                  </div>
                </div>

                <div className="grid gap-0 lg:grid-cols-[minmax(0,1fr)_20rem]">
                  <div className="min-h-[720px] bg-slate-100">
                    {deck.deck_pdf_url ? (
                      <iframe
                        title={`${deck.company_name} PDF`}
                        src={deck.deck_pdf_url}
                        className="h-[720px] w-full"
                      />
                    ) : (
                      <div className="flex h-[720px] items-center justify-center px-8 text-center text-sm leading-7 text-slate-500">
                        No uploaded PDF is available for inline preview on this deck yet.
                      </div>
                    )}
                  </div>

                  <div className="flex flex-col gap-5 border-t border-slate-200 p-6 lg:border-l lg:border-t-0">
                    <div>
                      <p className="text-xs font-semibold uppercase tracking-[0.22em] text-slate-500">Score Snapshot</p>
                      <div className="mt-3 rounded-[1.5rem] bg-slate-950 p-5 text-white">
                        <p className="text-4xl font-semibold tracking-tight">
                          {deck.score_summary?.overall_score != null ? `${Number(Number(deck.score_summary.overall_score / 110 * 100).toFixed(2))}%`: "—"}
                        </p>
                        <p className="mt-1 text-sm text-slate-300">Overall percentage</p>
                        <p className="mt-4 text-xs uppercase tracking-[0.18em] text-slate-400">
                          {deck.score_summary?.scored_sections ?? 0} scored sections
                        </p>
                      </div>
                    </div>

                    <div>
                      <p className="text-xs font-semibold uppercase tracking-[0.22em] text-slate-500">Section Highlights</p>
                      <div className="mt-3 space-y-3">
                        {(deck.score_summary?.score_breakdown ?? []).slice(0, 4).map((item) => (
                          <div key={`${deck.deck_id}-${item.rubric_section}`} className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3">
                            <p className="text-sm font-medium text-slate-900">{item.rubric_section}</p>
                            <p className="mt-1 text-sm text-slate-600">
                              {item.value != null ? `${item.value} pts` : "Not scored"}
                            </p>
                          </div>
                        ))}
                        {!(deck.score_summary?.score_breakdown?.length) ? (
                          <div className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-500">
                            Evaluation summary is not available for this deck yet.
                          </div>
                        ) : null}
                      </div>
                    </div>

                    <div className="mt-auto space-y-3">
                      <Link
                        href={`/decks/${deck.deck_id}`}
                        className="inline-flex w-full items-center justify-center rounded-xl bg-slate-900 px-4 py-3 text-sm font-medium text-white transition hover:bg-slate-800"
                      >
                        Open deck detail
                      </Link>
                      {deck.can_manage_visibility ? (
                        <DeckVisibilityToggle
                          deckId={deck.deck_id}
                          initialVisible={Boolean(deck.visible_to_vcs)}
                          className="w-full"
                        />
                      ) : null}
                      {!isFallback && deck.can_manage_visibility && !isExampleDeckId(deck.deck_id) ? (
                        <DeleteDeckButton deckId={deck.deck_id} className="w-full" />
                      ) : null}
                    </div>
                  </div>
                </div>
              </article>
            ))}
          </div>
        </section>

        {!isFallback ? (
          <section className="mt-12">
            <DeckUploadWidget />
          </section>
        ) : null}
      </div>
    </div>
  );
}
