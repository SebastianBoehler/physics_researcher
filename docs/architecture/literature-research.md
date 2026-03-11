# Literature Research Workflow

Autolab now includes an arXiv-first literature research workflow that sits alongside campaigns and review threads.

## Integration point

- The literature workflow lives in `packages/agents` as a separate analysis path.
- It does not reuse `SimulationWorkflow` or campaign stages.
- It can be called directly through:
  - `POST /literature-research`
  - `uv run autolab research-literature ...`

## Input contract

Example request:

```json
{
  "topic": "Quantum sensor stability",
  "papers": [{ "arxiv_id": "2401.12345" }, { "url": "https://arxiv.org/abs/2402.54321" }],
  "notes": "Review the literature and compare papers.",
  "include_markdown": true
}
```

## Output contract

The workflow returns a structured result with:

- normalized paper metadata
- intake clusters
- contradictions
- citation chains
- research gaps
- methodology audit
- synthesis
- assumptions
- knowledge map
- so-what summary
- per-stage status and errors
- optional markdown rendering

Example result excerpt:

```json
{
  "result": {
    "mode": "literature_research",
    "topic": "Quantum sensor stability",
    "papers": [
      {
        "paper_id": "2401.12345",
        "arxiv_id": "2401.12345",
        "title": "Quantum Sensor Stability",
        "year": 2024
      }
    ],
    "knowledge_map": {
      "central_claim": "Quantum sensor stability improves accuracy.",
      "supporting_pillars": ["Improved low-noise performance."],
      "contested_zones": [],
      "frontier_questions": []
    }
  }
}
```

## Design notes

- arXiv metadata lookup is supported for IDs, URLs, and title-based search.
- Raw PDF parsing, DOI lookup, and external citation-graph enrichment are intentionally out of scope for v1.
- `swarm_payload` remains reserved for a later Wizwand Swarm integration.
