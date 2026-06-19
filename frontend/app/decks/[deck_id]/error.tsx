"use client";

export default function DeckError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-50 px-6">
      <div className="max-w-xl rounded-2xl border border-red-200 bg-white p-8 shadow-sm">
        <p className="text-sm font-semibold uppercase tracking-[0.2em] text-red-600">Deck Error</p>
        <h1 className="mt-3 text-2xl font-semibold text-slate-900">The deck could not be loaded.</h1>
        <p className="mt-3 text-sm leading-6 text-slate-600">{error.message || "Unexpected application error."}</p>
        <button
          onClick={reset}
          className="mt-6 rounded-xl bg-slate-900 px-4 py-2.5 text-sm font-medium text-white"
        >
          Retry
        </button>
      </div>
    </div>
  );
}
