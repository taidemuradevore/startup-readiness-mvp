export default function Loading() {
  return (
    <div className="min-h-screen bg-slate-50 px-6 py-12">
      <div className="mx-auto max-w-6xl animate-pulse">
        <div className="mb-8 h-10 w-64 rounded bg-slate-200" />
        <div className="mb-10 h-5 w-96 rounded bg-slate-200" />
        <div className="grid gap-6 md:grid-cols-2 xl:grid-cols-3">
          {Array.from({ length: 6 }).map((_, index) => (
            <div key={index} className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
              <div className="mb-4 h-6 w-40 rounded bg-slate-200" />
              <div className="mb-3 h-4 w-full rounded bg-slate-100" />
              <div className="mb-3 h-4 w-3/4 rounded bg-slate-100" />
              <div className="h-4 w-1/2 rounded bg-slate-100" />
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
