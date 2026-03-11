import Link from "next/link";

import { AppShell } from "@/components/app-shell";
import { EmptyState } from "@/components/cards";
import { getCampaigns } from "@/lib/api";

export default async function RunsIndexPage() {
  const campaigns = await getCampaigns();

  return (
    <AppShell activePath="/runs">
      <section className="panel content-panel">
        <div className="section-header">
          <div>
            <span className="eyebrow">Run twin entry</span>
            <h2>Select a campaign</h2>
            <p className="section-copy">
              Runs remain campaign-scoped. This route is the top-level entry point before dropping
              into a specific run twin.
            </p>
          </div>
        </div>
        {campaigns.length ? (
          <div className="campaign-grid">
            {campaigns.map((campaign) => (
              <article key={campaign.id} className="campaign-card">
                <div>
                  <span className="eyebrow">{campaign.simulator}</span>
                  <h3>{campaign.name}</h3>
                  <p className="meta-copy">{campaign.id}</p>
                </div>
                <div className="meta-grid filter-grid-two">
                  <div className="meta-item">
                    <span className="meta-label">Status</span>
                    <span>{campaign.status}</span>
                  </div>
                  <div className="meta-item">
                    <span className="meta-label">Budget</span>
                    <span>{campaign.budget.max_runs} runs</span>
                  </div>
                </div>
                <div className="button-row">
                  <Link className="button button-primary" href={`/campaigns/${campaign.id}`}>
                    Open run twin
                  </Link>
                </div>
              </article>
            ))}
          </div>
        ) : (
          <EmptyState copy="No campaigns are available yet." />
        )}
      </section>
    </AppShell>
  );
}
