"use client";

import { useEffect, useRef, useState } from "react";

type DeckSlide = {
  slide_number: number;
  text: string;
  graph_desc: string[];
  section: string;
};

type ScoreBreakdownItem = {
  rubric_section: string;
  value: number | null;
  raw_score?: string | null;
  feedback?: string | null;
  evidence?: string | null;
  confidence?: number | null;
  adjusted_value?: number | null;
  confidence_reason?: string | null;
  verification_status?: string | null;
  critic_notes?: string | null;
};

type AnnotatedPdfViewerProps = {
  pdfUrl: string | null | undefined;
  slides: DeckSlide[];
  scoreBreakdown: ScoreBreakdownItem[];
};

function normalizeSectionName(section: string) {
  return section.toLowerCase().replace(/[^a-z0-9]+/g, " ").trim();
}

function findScoreForSlide(section: string, scoreBreakdown: ScoreBreakdownItem[]) {
  const normalizedSlideSection = normalizeSectionName(section);
  return (
    scoreBreakdown.find((item) => normalizeSectionName(item.rubric_section) === normalizedSlideSection) ??
    scoreBreakdown.find((item) => normalizedSlideSection.includes(normalizeSectionName(item.rubric_section))) ??
    scoreBreakdown.find((item) => normalizeSectionName(item.rubric_section).includes(normalizedSlideSection)) ??
    null
  );
}

function PageCanvas({
  pdfUrl,
  pageNumber,
  className = "",
}: {
  pdfUrl: string;
  pageNumber: number;
  className?: string;
}) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    let renderTask: { cancel?: () => void; promise?: Promise<unknown> } | null = null;

    async function renderPage() {
      try {
        const pdfjs = await import("pdfjs-dist/build/pdf.mjs");
        const workerSrc = new URL("pdfjs-dist/build/pdf.worker.min.mjs", import.meta.url).toString();
        pdfjs.GlobalWorkerOptions.workerSrc = workerSrc;

        const loadingTask = pdfjs.getDocument(pdfUrl);
        const pdf = await loadingTask.promise;
        const page = await pdf.getPage(pageNumber);
        const viewport = page.getViewport({ scale: 1.25 });
        const canvas = canvasRef.current;
        if (!canvas || cancelled) return;

        const context = canvas.getContext("2d");
        if (!context) {
          setError("Canvas rendering is unavailable in this browser.");
          return;
        }

        canvas.width = viewport.width;
        canvas.height = viewport.height;

        renderTask = page.render({
          canvasContext: context,
          viewport,
        });
        await renderTask.promise;
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "PDF page render failed.");
        }
      }
    }

    void renderPage();

    return () => {
      cancelled = true;
      renderTask?.cancel?.();
    };
  }, [pageNumber, pdfUrl]);

  if (error) {
    return (
      <div className="rounded-2xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
        PDF render failed for page {pageNumber}: {error}
      </div>
    );
  }

  return <canvas ref={canvasRef} className={`h-auto w-full rounded-[1.25rem] bg-white shadow-sm ${className}`} />;
}

export function AnnotatedPdfViewer({
  pdfUrl,
  slides,
  scoreBreakdown,
}: AnnotatedPdfViewerProps) {
  const [selectedSlideNumber, setSelectedSlideNumber] = useState<number | null>(null);

  if (!pdfUrl) {
    return (
      <div className="flex h-[980px] items-center justify-center px-8 text-center text-sm leading-7 text-slate-500">
        No stored PDF is available for this deck.
      </div>
    );
  }

  const selectedSlide = selectedSlideNumber !== null
    ? slides.find((slide) => slide.slide_number === selectedSlideNumber) ?? null
    : null;
  const selectedScore = selectedSlide ? findScoreForSlide(selectedSlide.section || "", scoreBreakdown) : null;

  return (
    <>
      <div className="space-y-8 bg-slate-100 p-6">
        {slides.map((slide) => {
          const matchedScore = findScoreForSlide(slide.section || "", scoreBreakdown);

          return (
            <section
              key={`pdf-page-${slide.slide_number}`}
              className="rounded-[1.75rem] border border-slate-200 bg-slate-50 p-4"
            >
              <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_22rem]">
                <button
                  type="button"
                  onClick={() => setSelectedSlideNumber(slide.slide_number)}
                  className="min-w-0 text-left transition hover:opacity-95"
                >
                  <PageCanvas pdfUrl={pdfUrl} pageNumber={slide.slide_number} />
                  <div className="mt-3 flex items-center justify-between px-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="rounded-full bg-slate-900 px-3 py-1 text-xs font-semibold uppercase tracking-[0.18em] text-white">
                        Slide {slide.slide_number}
                      </span>
                      <span className="rounded-full bg-white px-3 py-1 text-xs font-medium text-slate-700">
                        {slide.section || "Uncategorized"}
                      </span>
                    </div>
                    <span className="text-xs font-medium uppercase tracking-[0.18em] text-slate-500">Click to expand</span>
                  </div>
                </button>

                <aside className="rounded-[1.5rem] border border-slate-200 bg-white p-4">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="rounded-full bg-slate-900 px-3 py-1 text-xs font-semibold uppercase tracking-[0.18em] text-white">
                      Slide {slide.slide_number}
                    </span>
                    <span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-medium text-slate-700">
                      {slide.section || "Uncategorized"}
                    </span>
                    {matchedScore?.value != null ? (
                      <span className="rounded-full bg-emerald-100 px-3 py-1 text-xs font-medium text-emerald-800">
                        {matchedScore.value} pts
                      </span>
                    ) : null}
                  </div>

                  <div className="mt-4 space-y-4">
                    <div>
                      <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">Evaluator feedback</p>
                      <p className="mt-2 text-sm leading-7 text-slate-700">
                        {matchedScore?.feedback || "No evaluator feedback is stored for this slide section yet."}
                      </p>
                    </div>

                    {matchedScore?.evidence ? (
                      <div className="rounded-xl border border-slate-200 bg-slate-50 p-3">
                        <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">Quoted evidence</p>
                        <p className="mt-2 text-sm leading-6 text-slate-700">{matchedScore.evidence}</p>
                      </div>
                    ) : null}

                    {matchedScore?.confidence != null ? (
                      <div className="rounded-xl border border-slate-200 bg-white p-3">
                        <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">Confidence</p>
                        <p className="mt-2 text-sm leading-6 text-slate-700">
                          {Math.round(matchedScore.confidence * 100)}%
                          {matchedScore.adjusted_value != null ? `, adjusted to ${matchedScore.adjusted_value} pts` : ""}
                        </p>
                        {matchedScore.confidence_reason ? (
                          <p className="mt-2 text-sm leading-6 text-slate-600">{matchedScore.confidence_reason}</p>
                        ) : null}
                      </div>
                    ) : null}

                    {slide.graph_desc.length ? (
                      <div>
                        <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">Visual notes</p>
                        <ul className="mt-2 space-y-2 text-sm text-slate-700">
                          {slide.graph_desc.map((item, index) => (
                            <li key={index}>• {item}</li>
                          ))}
                        </ul>
                      </div>
                    ) : null}
                  </div>
                </aside>
              </div>
            </section>
          );
        })}
      </div>

      {selectedSlide ? (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/80 p-6">
          <div className="grid max-h-[92vh] w-full max-w-7xl gap-4 overflow-hidden rounded-[2rem] bg-white p-4 shadow-2xl xl:grid-cols-[minmax(0,1fr)_24rem]">
            <div className="overflow-auto rounded-[1.5rem] bg-slate-100 p-4">
              <PageCanvas pdfUrl={pdfUrl} pageNumber={selectedSlide.slide_number} className="mx-auto max-w-full" />
            </div>

            <aside className="overflow-auto rounded-[1.5rem] border border-slate-200 bg-white p-5">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="rounded-full bg-slate-900 px-3 py-1 text-xs font-semibold uppercase tracking-[0.18em] text-white">
                      Slide {selectedSlide.slide_number}
                    </span>
                    <span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-medium text-slate-700">
                      {selectedSlide.section || "Uncategorized"}
                    </span>
                    {selectedScore?.value != null ? (
                      <span className="rounded-full bg-emerald-100 px-3 py-1 text-xs font-medium text-emerald-800">
                        {selectedScore.value} pts
                      </span>
                    ) : null}
                  </div>
                  <h3 className="mt-4 text-xl font-semibold text-slate-950">Slide-specific review</h3>
                </div>
                <button
                  type="button"
                  onClick={() => setSelectedSlideNumber(null)}
                  className="rounded-full border border-slate-200 px-3 py-1 text-sm font-medium text-slate-600 hover:bg-slate-50"
                >
                  Close
                </button>
              </div>

              <div className="mt-5 space-y-5">
                <div>
                  <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">Evaluator feedback</p>
                  <p className="mt-2 text-sm leading-7 text-slate-700">
                    {selectedScore?.feedback || "No evaluator feedback is stored for this slide section yet."}
                  </p>
                </div>

                {selectedScore?.evidence ? (
                  <div className="rounded-xl border border-slate-200 bg-slate-50 p-4">
                    <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">Quoted evidence</p>
                    <p className="mt-2 text-sm leading-6 text-slate-700">{selectedScore.evidence}</p>
                  </div>
                ) : null}

                {selectedScore?.confidence != null ? (
                  <div className="rounded-xl border border-slate-200 bg-white p-4">
                    <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">Confidence</p>
                    <p className="mt-2 text-sm leading-6 text-slate-700">
                      {Math.round(selectedScore.confidence * 100)}%
                      {selectedScore.adjusted_value != null ? `, adjusted to ${selectedScore.adjusted_value} pts` : ""}
                    </p>
                    {selectedScore.confidence_reason ? (
                      <p className="mt-2 text-sm leading-6 text-slate-600">{selectedScore.confidence_reason}</p>
                    ) : null}
                    {selectedScore.critic_notes ? (
                      <p className="mt-2 text-sm leading-6 text-slate-600">{selectedScore.critic_notes}</p>
                    ) : null}
                  </div>
                ) : null}

                {selectedSlide.graph_desc.length ? (
                  <div>
                    <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">Visual notes</p>
                    <ul className="mt-2 space-y-2 text-sm text-slate-700">
                      {selectedSlide.graph_desc.map((item, index) => (
                        <li key={index}>• {item}</li>
                      ))}
                    </ul>
                  </div>
                ) : null}
              </div>
            </aside>
          </div>
        </div>
      ) : null}
    </>
  );
}
