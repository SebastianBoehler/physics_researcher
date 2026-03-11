import "server-only";

type RunStatus =
  | "pending"
  | "prepared"
  | "queued"
  | "running"
  | "succeeded"
  | "failed"
  | "cancelled"
  | "timed_out";

export type Campaign = {
  id: string;
  name: string;
  status: string;
  simulator: string;
  mode: string;
  budget: {
    max_runs: number;
    batch_size: number;
    max_failures: number;
  };
  tags: string[];
};

export type Run = {
  id: string;
  campaign_id: string;
  candidate_id: string;
  simulator: string;
  status: RunStatus;
  failure_class: string;
  job_id: string | null;
  attempt: number;
  metrics: Record<string, number>;
  metadata: Record<string, unknown>;
  created_at: string;
  updated_at: string;
};

export type Artifact = {
  id: string;
  campaign_id: string;
  run_id: string | null;
  artifact_type: string;
  path: string;
  media_type: string;
  sha256: string;
  metadata: Record<string, unknown>;
  created_at: string;
};

export type Skill = {
  name: string;
  description: string;
  domain: string;
  source: string;
  trust_level: string;
  tags: string[];
  required_context: string[];
  required_integrations: string[];
  input_schema: {
    properties?: Record<string, unknown>;
  };
  output_schema: {
    properties?: Record<string, unknown>;
  };
};

export type BenchmarkReport = {
  benchmark_name: string;
  description: string;
  paper_hypothesis: string;
  primary_metric: string;
  generated_at: string;
  report_path: string;
  manifest_path: string | null;
  task_count: number;
  summary: Record<string, number | string | boolean | null | Record<string, unknown>>;
};

type HealthResponse = {
  status: string;
  services: Record<string, string>;
};

function baseUrl() {
  return (
    process.env.AUTOLAB_API_BASE_URL ||
    process.env.NEXT_PUBLIC_AUTOLAB_API_BASE_URL ||
    "http://127.0.0.1:8000"
  );
}

function authToken() {
  return process.env.AUTOLAB_API_TOKEN || "dev-token";
}

async function apiFetch<T>(path: string): Promise<T> {
  const response = await fetch(`${baseUrl()}${path}`, {
    headers: {
      Authorization: `Bearer ${authToken()}`
    },
    cache: "no-store"
  });
  if (!response.ok) {
    const text = await response.text();
    throw new Error(`${response.status} ${response.statusText}: ${text}`);
  }
  return (await response.json()) as T;
}

export async function getHealth() {
  return apiFetch<HealthResponse>("/health");
}

export async function getCampaigns() {
  const response = await apiFetch<{ campaigns: Campaign[] }>("/campaigns");
  return response.campaigns;
}

export async function getCampaign(campaignId: string) {
  return apiFetch<Campaign>(`/campaigns/${campaignId}`);
}

export async function getRuns(campaignId: string) {
  const response = await apiFetch<{ runs: Run[] }>(`/campaigns/${campaignId}/runs`);
  return response.runs;
}

export async function getRunArtifacts(runId: string, stageName?: string) {
  const query = stageName ? `?stage_name=${encodeURIComponent(stageName)}` : "";
  const response = await apiFetch<{ artifacts: Artifact[] }>(`/runs/${runId}/artifacts${query}`);
  return response.artifacts;
}

export async function getSkills() {
  const response = await apiFetch<{ skills: Skill[] }>("/skills");
  return response.skills;
}

export async function getBenchmarkReports() {
  const response = await apiFetch<{ reports: BenchmarkReport[] }>("/benchmarks/reports");
  return response.reports;
}
