const readiness = [
  { label: "API health", status: "Ready", tone: "bg-emerald-100 text-emerald-800" },
  { label: "PostgreSQL + pgvector", status: "Configured", tone: "bg-sky-100 text-sky-800" },
  { label: "Redis", status: "Configured", tone: "bg-sky-100 text-sky-800" },
  { label: "Business workflows", status: "Deferred", tone: "bg-amber-100 text-amber-800" },
];

const roadmap = [
  "P1 Mock commerce data",
  "P2 Versioned policy retrieval",
  "P3 Grounded Agent workflow",
  "P4 Approval and MCP execution",
];

export default function Home() {
  return (
    <main className="min-h-screen bg-panel text-ink">
      <div className="mx-auto grid min-h-screen max-w-7xl grid-cols-1 lg:grid-cols-[260px_1fr]">
        <aside className="border-b border-line bg-white px-6 py-6 lg:border-b-0 lg:border-r">
          <div className="text-sm font-semibold uppercase text-signal">CommerceFlow</div>
          <h1 className="mt-2 text-2xl font-semibold">Agent Console</h1>
          <nav className="mt-8 space-y-2 text-sm text-slate-600">
            <div className="rounded-md bg-slate-100 px-3 py-2 font-medium text-ink">Baseline</div>
            <div className="px-3 py-2">Cases</div>
            <div className="px-3 py-2">Approvals</div>
            <div className="px-3 py-2">Evaluation</div>
          </nav>
        </aside>

        <section className="px-6 py-8 lg:px-10">
          <div className="flex flex-col gap-3 border-b border-line pb-6 md:flex-row md:items-end md:justify-between">
            <div>
              <p className="text-sm font-medium text-signal">Phase 0</p>
              <h2 className="mt-1 text-3xl font-semibold">Engineering baseline</h2>
            </div>
            <div className="rounded-md border border-line bg-white px-4 py-2 text-sm text-slate-600">
              Local demo shell
            </div>
          </div>

          <div className="mt-8 grid gap-4 md:grid-cols-2 xl:grid-cols-4">
            {readiness.map((item) => (
              <div key={item.label} className="rounded-md border border-line bg-white p-4">
                <div className="text-sm text-slate-500">{item.label}</div>
                <div className={`mt-4 inline-flex rounded px-2 py-1 text-xs font-semibold ${item.tone}`}>
                  {item.status}
                </div>
              </div>
            ))}
          </div>

          <div className="mt-8 grid gap-6 lg:grid-cols-[1fr_320px]">
            <div className="rounded-md border border-line bg-white p-6">
              <h3 className="text-lg font-semibold">Delivery boundary</h3>
              <div className="mt-5 grid gap-3 md:grid-cols-2">
                {[
                  "FastAPI health endpoint",
                  "Next.js console shell",
                  "PostgreSQL and Redis compose services",
                  "Pytest and lint baselines",
                ].map((item) => (
                  <div key={item} className="border-l-4 border-signal bg-slate-50 px-4 py-3 text-sm">
                    {item}
                  </div>
                ))}
              </div>
            </div>

            <div className="rounded-md border border-line bg-white p-6">
              <h3 className="text-lg font-semibold">Next milestones</h3>
              <ol className="mt-5 space-y-3 text-sm text-slate-700">
                {roadmap.map((item) => (
                  <li key={item} className="flex items-center gap-3">
                    <span className="h-2 w-2 rounded-full bg-warning" />
                    <span>{item}</span>
                  </li>
                ))}
              </ol>
            </div>
          </div>
        </section>
      </div>
    </main>
  );
}

