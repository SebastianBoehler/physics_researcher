import { AppShell } from "@/components/app-shell";
import { BenchmarkCard, OverviewHero, StatCard } from "@/components/cards";
import { getBenchmarkReports, getCampaigns, getHealth, getSkills } from "@/lib/api";

export default async function HomePage() {
  const [campaigns, skills, benchmarks, health] = await Promise.all([
    getCampaigns(),
    getSkills(),
    getBenchmarkReports(),
    getHealth()
  ]);

  return (
    <AppShell activePath="/">
      <OverviewHero />
      <section className="stats-grid">
        <StatCard
          copy="Registered campaign definitions visible through the control plane."
          label="Campaigns"
          value={campaigns.length}
        />
        <StatCard
          copy="Typed skill entries exported from the ADK-facing registry."
          label="Skills"
          value={skills.length}
        />
        <StatCard
          copy="Benchmark summaries indexed from artifacts/benchmarks."
          label="Benchmark reports"
          value={benchmarks.length}
        />
        <StatCard
          copy="Current API heartbeat and dependency configuration."
          label="API status"
          value={health.status.toUpperCase()}
        />
      </section>
      <section className="panel content-panel">
        <div className="section-header">
          <div>
            <h2>Recent benchmark traces</h2>
            <p className="section-copy">
              This page stays read-only, but the route model is already aligned with the benchmark
              hub and run twin plans.
            </p>
          </div>
        </div>
        <div className="campaign-grid">
          {benchmarks.slice(0, 4).map((report) => (
            <BenchmarkCard key={report.benchmark_name} report={report} />
          ))}
        </div>
      </section>
    </AppShell>
  );
}
