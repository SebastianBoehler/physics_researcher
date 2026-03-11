import type { Route } from "next";
import Link from "next/link";
import { ReactNode } from "react";

const navigation = [
  {
    href: "/" as Route,
    title: "Workbench",
    copy: "Overview and benchmark pulse"
  },
  {
    href: "/campaigns" as Route,
    title: "Campaigns",
    copy: "Read-only registry and budget summary"
  },
  {
    href: "/runs" as Route,
    title: "Runs",
    copy: "Campaign-scoped run twin"
  },
  {
    href: "/skills" as Route,
    title: "Skill Catalog",
    copy: "Typed tools, trust level, and schema"
  }
];

type AppShellProps = {
  activePath: string;
  children: ReactNode;
};

export function AppShell({ activePath, children }: AppShellProps) {
  return (
    <div className="page-shell">
      <aside className="sidebar">
        <section className="panel brand-panel">
          <span className="eyebrow">Materials workbench</span>
          <h1 className="brand-title">Autolab</h1>
          <p className="brand-copy">
            Read-only Next.js surface for campaigns, runs, skills, and benchmark evidence.
          </p>
        </section>
        <section className="panel nav-panel">
          <p className="meta-label">Navigation</p>
          <nav className="nav-list">
            {navigation.map((item) => {
              const isActive = activePath === item.href || activePath.startsWith(`${item.href}/`);
              return (
                <Link
                  key={item.href}
                  className={`nav-link${isActive ? " active" : ""}`}
                  href={item.href}
                >
                  <div>
                    <strong>{item.title}</strong>
                    <span>{item.copy}</span>
                  </div>
                </Link>
              );
            })}
          </nav>
        </section>
        <section className="panel config-panel">
          <p className="meta-label">Runtime config</p>
          <div className="config-list">
            <div className="config-item">
              <span>API base URL</span>
              <code>{process.env.AUTOLAB_API_BASE_URL || "http://127.0.0.1:8000"}</code>
            </div>
            <div className="config-item">
              <span>Bearer token source</span>
              <code>{process.env.AUTOLAB_API_TOKEN ? "AUTOLAB_API_TOKEN" : "dev-token fallback"}</code>
            </div>
            <div className="config-item">
              <span>Routing</span>
              <code>App Router · server-first fetch · no-store</code>
            </div>
          </div>
        </section>
      </aside>
      <main className="main-column">{children}</main>
    </div>
  );
}
