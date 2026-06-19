import Link from "next/link";

export default async function AuthErrorPage({
  searchParams,
}: {
  searchParams: Promise<{ message?: string }>;
}) {
  const { message } = await searchParams;

  return (
    <main className="flex min-h-screen items-center justify-center bg-slate-50 px-6">
      <div className="w-full max-w-md rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
        <p className="text-xs font-semibold uppercase tracking-[0.22em] text-slate-500">Authentication</p>
        <h1 className="mt-3 text-2xl font-semibold tracking-tight text-slate-950">Sign-in failed</h1>
        <p className="mt-3 text-sm leading-6 text-slate-600">
          {message ?? "Google sign-in could not be completed."}
        </p>
        <Link
          href="/auth/sign-in"
          className="mt-5 inline-flex rounded-xl bg-slate-950 px-4 py-2.5 text-sm font-medium text-white"
        >
          Try again
        </Link>
      </div>
    </main>
  );
}
