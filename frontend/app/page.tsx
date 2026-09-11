const backendUrl = process.env.BACKEND_URL ?? "http://localhost:8000";

async function getBackendStatus() {
  try {
    const response = await fetch(`${backendUrl}/health`, { cache: "no-store" });
    if (!response.ok) return "unavailable";

    const body = (await response.json()) as { status?: string };
    return body.status ?? "unknown";
  } catch {
    return "unavailable";
  }
}

export default async function Home() {
  const status = await getBackendStatus();
  const isHealthy = status === "ok";

  return (
    <main className="min-h-screen px-6 py-8 sm:px-10 sm:py-12">
      <div className="mx-auto flex min-h-[calc(100vh-6rem)] max-w-5xl flex-col justify-between rounded-[2rem] border border-black/10 bg-white/75 p-8 shadow-[0_24px_80px_rgba(42,52,40,0.12)] backdrop-blur sm:p-12">
        <header className="flex items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <span className="grid size-10 place-items-center rounded-xl bg-[#17483b] text-lg text-[#f4df9b]">✦</span>
            <span className="font-[family-name:var(--font-geist-mono)] text-xs font-semibold uppercase tracking-[0.18em] text-[#17483b]">
              Local intelligence
            </span>
          </div>
          <span className="rounded-full border border-[#17483b]/15 px-3 py-1 font-[family-name:var(--font-geist-mono)] text-[11px] uppercase tracking-wider text-[#17483b]/70">
            Scaffold 0.1
          </span>
        </header>

        <section className="max-w-3xl py-16 sm:py-24">
          <p className="mb-5 font-[family-name:var(--font-geist-mono)] text-sm uppercase tracking-[0.2em] text-[#c56b3d]">
            GraphRAG Engine
          </p>
          <h1 className="max-w-2xl text-5xl font-semibold leading-[0.98] tracking-tight text-[#17352f] sm:text-7xl">
            Your documents, connected with intent.
          </h1>
          <p className="mt-7 max-w-xl text-lg leading-8 text-[#416058]">
            The workspace is ready for local retrieval, reasoning, and a transparent agent workflow.
          </p>
        </section>

        <section className="flex flex-col gap-4 border-t border-[#17483b]/15 pt-6 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <p className="text-sm text-[#416058]">GraphRAG Engine - Backend status:</p>
            <p className="mt-2 flex items-center gap-2 text-xl font-semibold text-[#17352f]">
              <span className={`size-2.5 rounded-full ${isHealthy ? "bg-[#3e9b70]" : "bg-[#c56b3d]"}`} />
              {status}
            </p>
          </div>
          <p className="max-w-xs text-sm leading-6 text-[#416058]/80">
            Start FastAPI on port 8000 to connect this first screen to the backend health check.
          </p>
        </section>
      </div>
    </main>
  );
}
