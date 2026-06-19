export default function DeckLoading() {
  return (
    <div className="min-h-screen bg-slate-50 px-6 py-12">
      <div className="mx-auto max-w-5xl animate-pulse">
        <div className="mb-4 h-4 w-32 rounded bg-slate-200" />
        <div className="mb-3 h-10 w-80 rounded bg-slate-200" />
        <div className="mb-8 h-5 w-60 rounded bg-slate-200" />
        <div className="space-y-4">
          {Array.from({ length: 4 }).map((_, index) => (
            <div key={index} className="rounded-2xl border border-slate-200 bg-white p-5">
              <div className="mb-3 h-5 w-40 rounded bg-slate-200" />
              <div className="mb-2 h-4 w-full rounded bg-slate-100" />
              <div className="mb-2 h-4 w-5/6 rounded bg-slate-100" />
              <div className="h-4 w-2/3 rounded bg-slate-100" />
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
