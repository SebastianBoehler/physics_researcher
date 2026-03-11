import { AppShell } from "@/components/app-shell";
import { EmptyState, RunCard } from "@/components/cards";
import { getCampaign, getRunArtifacts, getRuns } from "@/lib/api";

type CampaignRunsPageProps = {
  params: Promise<{ campaignId: string }>;
  searchParams: Promise<{ stageName?: string }>;
};

export default async function CampaignRunsPage({
  params,
  searchParams
}: CampaignRunsPageProps) {
  const { campaignId } = await params;
  const { stageName } = await searchParams;

  const [campaign, runs] = await Promise.all([getCampaign(campaignId), getRuns(campaignId)]);
  const runsWithArtifacts = await Promise.all(
    runs.map(async (run) => {
      const [allArtifacts, filteredArtifacts] = await Promise.all([
        getRunArtifacts(run.id),
        getRunArtifacts(run.id, stageName)
      ]);
      return {
        run,
        allArtifacts,
        filteredArtifacts
      };
    })
  );

  return (
    <AppShell activePath="/campaigns">
      <section className="panel content-panel">
        <div className="section-header">
          <div>
            <span className="eyebrow">{campaign.simulator}</span>
            <h2>{campaign.name}</h2>
            <p className="section-copy">
              Run twin for campaign <code>{campaign.id}</code>
              {stageName ? ` · filtering artifacts by stage "${stageName}"` : ""}.
            </p>
          </div>
          <div className="pill-row">
            <span className="pill">status: {campaign.status}</span>
            <span className="pill">max runs: {campaign.budget.max_runs}</span>
            <span className="pill">batch size: {campaign.budget.batch_size}</span>
          </div>
        </div>
        <form className="filter-grid filter-grid-two" method="get">
          <div className="field">
            <label htmlFor="stageName">Stage filter</label>
            <input
              defaultValue={stageName || ""}
              id="stageName"
              name="stageName"
              placeholder="Optional stage name"
            />
          </div>
          <div className="field">
            <label htmlFor="applyFilter">Apply</label>
            <div className="button-row">
              <button className="button button-primary" id="applyFilter" type="submit">
                Filter artifacts
              </button>
            </div>
          </div>
        </form>
        {runsWithArtifacts.length ? (
          <div className="run-grid">
            {runsWithArtifacts.map(({ run, allArtifacts, filteredArtifacts }) => (
              <RunCard
                key={run.id}
                allArtifacts={allArtifacts}
                filteredArtifacts={filteredArtifacts}
                run={run}
                stageName={stageName}
              />
            ))}
          </div>
        ) : (
          <EmptyState copy="This campaign does not have runs yet." />
        )}
      </section>
    </AppShell>
  );
}
