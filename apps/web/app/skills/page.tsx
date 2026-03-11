import { AppShell } from "@/components/app-shell";
import { SkillCatalogClient } from "@/components/skill-catalog-client";
import { getSkills } from "@/lib/api";

export default async function SkillsPage() {
  const skills = await getSkills();

  return (
    <AppShell activePath="/skills">
      <section className="panel content-panel">
        <div className="section-header">
          <div>
            <span className="eyebrow">Typed registry</span>
            <h2>Skill catalog</h2>
            <p className="section-copy">
              Search and filter the machine-readable skill export without pushing data fetching into
              the browser.
            </p>
          </div>
        </div>
        <SkillCatalogClient skills={skills} />
      </section>
    </AppShell>
  );
}
