"use client";

import { useDeferredValue, useState } from "react";

import { Skill } from "@/lib/api";

import { EmptyState, SkillCard } from "./cards";

type SkillCatalogClientProps = {
  skills: Skill[];
};

export function SkillCatalogClient({ skills }: SkillCatalogClientProps) {
  const [query, setQuery] = useState("");
  const [domain, setDomain] = useState("");
  const [trustLevel, setTrustLevel] = useState("");
  const deferredQuery = useDeferredValue(query);

  const domains = [...new Set(skills.map((skill) => skill.domain))].sort();
  const filtered = skills.filter((skill) => {
    const haystack = [
      skill.name,
      skill.description,
      skill.domain,
      skill.trust_level,
      ...skill.tags
    ]
      .join(" ")
      .toLowerCase();
    const matchesQuery =
      deferredQuery.trim().length === 0 || haystack.includes(deferredQuery.trim().toLowerCase());
    const matchesDomain = !domain || skill.domain === domain;
    const matchesTrust = !trustLevel || skill.trust_level === trustLevel;
    return matchesQuery && matchesDomain && matchesTrust;
  });

  return (
    <>
      <div className="filter-grid">
        <div className="field">
          <label htmlFor="search">Search</label>
          <input
            id="search"
            onChange={(event) => setQuery(event.target.value)}
            placeholder="search by name, tag, or description"
            value={query}
          />
        </div>
        <div className="field">
          <label htmlFor="domain">Domain</label>
          <select id="domain" onChange={(event) => setDomain(event.target.value)} value={domain}>
            <option value="">All domains</option>
            {domains.map((entry) => (
              <option key={entry} value={entry}>
                {entry}
              </option>
            ))}
          </select>
        </div>
        <div className="field">
          <label htmlFor="trustLevel">Trust level</label>
          <select
            id="trustLevel"
            onChange={(event) => setTrustLevel(event.target.value)}
            value={trustLevel}
          >
            <option value="">All trust levels</option>
            <option value="execution_safe">execution_safe</option>
            <option value="requires_operator_review">requires_operator_review</option>
            <option value="planner_only">planner_only</option>
          </select>
        </div>
      </div>
      {filtered.length ? (
        <div className="skill-grid">
          {filtered.map((skill) => (
            <SkillCard key={skill.name} skill={skill} />
          ))}
        </div>
      ) : (
        <EmptyState copy="No skills matched the current filters." />
      )}
    </>
  );
}
