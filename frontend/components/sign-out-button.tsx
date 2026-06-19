export function SignOutButton({ className = "" }: { className?: string }) {
  return (
    <form action="/auth/sign-out" method="post">
      <button
        type="submit"
        className={`rounded-xl border border-slate-200 bg-white px-4 py-2.5 text-sm font-medium text-slate-700 transition hover:bg-slate-50 ${className}`}
      >
        Sign out
      </button>
    </form>
  );
}
