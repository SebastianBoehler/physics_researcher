import { AppShell } from "@/components/app-shell";
import { CampaignCard, EmptyState } from "@/components/cards";
import { getCampaigns } from "@/lib/api";

export default async function CampaignsPage() {
  const campaigns = await getCampaigns();

  return (
    <AppShell activePath="/campaigns">
      <section className="panel content-panel">
        <div className="section-header">
          <div>
            <span className="eyebrow">Campaign registry</span>
            <h2>Read-only campaign list</h2>
            <p className="section-copy">
              Server-rendered against <code>GET /campaigns</code>, with deep links into the run
              twin route.
            </p>
          </div>
        </div>
        {campaigns.length ? (
          <div className="campaign-grid">
            {campaigns.map((campaign) => (
              <CampaignCard key={campaign.id} campaign={campaign} />
            ))}
          </div>
        ) : (
          <EmptyState copy="No campaigns have been created yet." />
        )}
      </section>
    </AppShell>
  );
}
