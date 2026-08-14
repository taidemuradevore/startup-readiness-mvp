const accounts = [
  {
    label: "VC admin",
    email: "dummy-vc-admin@example.com",
    password: "DummyVCAdmin!2026",
    description: "Use this account to test VC ranked deck results and embedding queries.",
  },
  {
    label: "Startup admin",
    email: "dummy-startup-admin@example.com",
    password: "DummyStartupAdmin!2026",
    description: "Use this account to test startup deck ownership, upload, ingestion, and VC visibility.",
  },
];

function dummyLoginEnabled() {
  return process.env.NODE_ENV !== "production" || process.env.ENABLE_DUMMY_LOGIN === "true";
}

export default function TestSignInPage() {
  const enabled = dummyLoginEnabled();

  return (
    <main className="min-h-screen bg-slate-50 px-6 py-12">
      <div className="mx-auto max-w-3xl">
        <p className="text-xs font-semibold uppercase tracking-[0.22em] text-slate-500">Test accounts</p>
        <h1 className="mt-3 text-3xl font-semibold tracking-tight text-slate-950">Dummy admin sign-in</h1>
        <p className="mt-3 max-w-2xl text-sm leading-6 text-slate-600">
          These seeded accounts are for local QA of startup deck ingestion, VC visibility, and embedding-ranked deck discovery.
        </p>

        {!enabled ? (
          <div className="mt-6 rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
            Dummy login is disabled. Set ENABLE_DUMMY_LOGIN=true to enable this route outside local development.
          </div>
        ) : null}

        <div className="mt-8 grid gap-4 md:grid-cols-2">
          {accounts.map((account) => (
            <section key={account.email} className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
              <h2 className="text-lg font-semibold text-slate-950">{account.label}</h2>
              <p className="mt-2 text-sm leading-6 text-slate-600">{account.description}</p>
              <dl className="mt-4 space-y-2 text-sm">
                <div>
                  <dt className="font-medium text-slate-500">Email</dt>
                  <dd className="break-all text-slate-900">{account.email}</dd>
                </div>
                <div>
                  <dt className="font-medium text-slate-500">Password</dt>
                  <dd className="break-all text-slate-900">{account.password}</dd>
                </div>
              </dl>
              <form action="/auth/password-sign-in" method="post" className="mt-5">
                <input type="hidden" name="email" value={account.email} />
                <input type="hidden" name="password" value={account.password} />
                <input type="hidden" name="next" value="/" />
                <button
                  type="submit"
                  disabled={!enabled}
                  className="w-full rounded-xl bg-slate-950 px-4 py-2.5 text-sm font-medium text-white transition hover:bg-slate-800 disabled:cursor-not-allowed disabled:bg-slate-300"
                >
                  Sign in as {account.label}
                </button>
              </form>
            </section>
          ))}
        </div>
      </div>
    </main>
  );
}
