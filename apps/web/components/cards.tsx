import Link from "next/link";

import { Artifact, BenchmarkReport, Campaign, Run, Skill } from "@/lib/api";

function formatNumber(value: number | string) {
  return typeof value === "number" ? value.toFixed(4) : value;
}

function formatDate(value: string) {
  return new Date(value).toLocaleString();
}

function statusStyle(status: string) {
  if (status === "completed" || status === "succeeded") {
    return { color: "var(--accent)" };
  }
  if (status === "failed" || status === "timed_out") {
    return { color: "var(--signal)" };
  }
  return {};
}

export function OverviewHero() {
  return (
    <section className="panel content-panel">
      <div className="hero-grid">
        <div>
          <span className="eyebrow">Read-only v1</span>
          <h1 className="hero-title">Campaigns, runs, skills, and benchmark traces.</h1>
          <p className="section-copy">
            The frontend is now a real Next.js app-router surface. Data loading happens on the
            server so the structure is ready for richer route-level read models without pushing auth
            or orchestration concerns into the browser.
          </p>
        </div>
        <div className="hero-card">
          <p className="hero-note">
            {`GET /campaigns
GET /campaigns/{campaign_id}/runs
GET /runs/{run_id}/artifacts
GET /skills
GET /benchmarks/reports`}
          </p>
        </div>
      </div>
    </section>
  );
}

export function StatCard(props: { label: string; value: string | number; copy: string }) {
  return (
    <article className="stat-card">
      <span className="meta-label">{props.label}</span>
      <strong>{props.value}</strong>
      <p className="meta-copy">{props.copy}</p>
    </article>
  );
}

export function BenchmarkCard({ report }: { report: BenchmarkReport }) {
  return (
    <article className="card">
      <span className="eyebrow">{report.primary_metric || "benchmark"}</span>
      <h2>{report.benchmark_name}</h2>
      <p className="section-copy">{report.description || "No description recorded."}</p>
      <div className="meta-grid">
        <div className="meta-item">
          <span className="meta-label">Generated</span>
          <span>{formatDate(report.generated_at)}</span>
        </div>
        <div className="meta-item">
          <span className="meta-label">Task count</span>
          <span>{report.task_count}</span>
        </div>
        <div className="meta-item">
          <span className="meta-label">Report path</span>
          <span>{report.report_path}</span>
        </div>
        <div className="meta-item">
          <span className="meta-label">Manifest path</span>
          <span>{report.manifest_path || "n/a"}</span>
        </div>
      </div>
    </article>
  );
}

export function CampaignCard({ campaign }: { campaign: Campaign }) {
  return (
    <article className="campaign-card">
      <div>
        <span className="eyebrow">{campaign.mode.replaceAll("_", " ")}</span>
        <h3>{campaign.name}</h3>
        <p className="meta-copy">{campaign.id}</p>
      </div>
      <div className="meta-grid">
        <div className="meta-item">
          <span className="meta-label">Simulator</span>
          <span>{campaign.simulator}</span>
        </div>
        <div className="meta-item">
          <span className="meta-label">Status</span>
          <span style={statusStyle(campaign.status)}>{campaign.status}</span>
        </div>
        <div className="meta-item">
          <span className="meta-label">Max runs</span>
          <span>{campaign.budget.max_runs}</span>
        </div>
        <div className="meta-item">
          <span className="meta-label">Batch size</span>
          <span>{campaign.budget.batch_size}</span>
        </div>
        <div className="meta-item">
          <span className="meta-label">Failure budget</span>
          <span>{campaign.budget.max_failures}</span>
        </div>
        <div className="meta-item">
          <span className="meta-label">Tags</span>
          <span>{campaign.tags.join(", ") || "none"}</span>
        </div>
      </div>
      <div className="button-row">
        <Link className="button button-primary" href={`/campaigns/${campaign.id}`}>
          Open runs
        </Link>
      </div>
    </article>
  );
}

export function RunCard(props: {
  run: Run;
  allArtifacts: Artifact[];
  filteredArtifacts: Artifact[];
  stageName?: string;
}) {
  const metricEntries = Object.entries(props.run.metrics).slice(0, 6);
  const seenStages = [...new Set(props.allArtifacts.map((artifact) => artifact.metadata.stage_name))].filter(
    Boolean
  );
  return (
    <article className="run-card">
      <div>
        <span className="eyebrow">{props.run.simulator}</span>
        <h3>{props.run.id}</h3>
        <p className="meta-copy">Created {formatDate(props.run.created_at)}</p>
      </div>
      <div className="meta-grid">
        <div className="meta-item">
          <span className="meta-label">Status</span>
          <span style={statusStyle(props.run.status)}>{props.run.status}</span>
        </div>
        <div className="meta-item">
          <span className="meta-label">Failure class</span>
          <span>{props.run.failure_class}</span>
        </div>
        <div className="meta-item">
          <span className="meta-label">Attempt</span>
          <span>{props.run.attempt}</span>
        </div>
        <div className="meta-item">
          <span className="meta-label">Updated</span>
          <span>{formatDate(props.run.updated_at)}</span>
        </div>
      </div>
      <div className="metric-row">
        {metricEntries.length ? (
          metricEntries.map(([key, value]) => (
            <span key={key} className="metric">
              {key}: {formatNumber(value)}
            </span>
          ))
        ) : (
          <span className="meta-copy">No metrics recorded.</span>
        )}
      </div>
      <div className="artifact-banner">
        {props.filteredArtifacts.length} artifacts
        {props.stageName ? ` for stage ${props.stageName}` : ""}
        {seenStages.length ? ` · stages: ${seenStages.join(", ")}` : ""}
      </div>
    </article>
  );
}

export function EmptyState(props: { copy: string }) {
  return (
    <div className="empty-state">
      <p className="empty-copy">{props.copy}</p>
    </div>
  );
}

export function SkillCard({ skill }: { skill: Skill }) {
  const inputProperties = Object.keys(skill.input_schema.properties || {});
  const outputProperties = Object.keys(skill.output_schema.properties || {});
  return (
    <article className="skill-card">
      <div>
        <span className="eyebrow">{skill.domain}</span>
        <h3>{skill.name}</h3>
        <p className="section-copy">{skill.description}</p>
      </div>
      <div className="meta-grid">
        <div className="meta-item">
          <span className="meta-label">Trust level</span>
          <span>{skill.trust_level}</span>
        </div>
        <div className="meta-item">
          <span className="meta-label">Source</span>
          <span>{skill.source}</span>
        </div>
        <div className="meta-item">
          <span className="meta-label">Required context</span>
          <span>{skill.required_context.join(", ") || "none"}</span>
        </div>
        <div className="meta-item">
          <span className="meta-label">Tags</span>
          <span>{skill.tags.join(", ") || "none"}</span>
        </div>
      </div>
      <div className="schema-grid">
        <div className="schema-box">
          <span className="meta-label">Input schema</span>
          <code>{inputProperties.join(", ") || "No properties."}</code>
        </div>
        <div className="schema-box">
          <span className="meta-label">Output schema</span>
          <code>{outputProperties.join(", ") || "No properties."}</code>
        </div>
      </div>
    </article>
  );
}
