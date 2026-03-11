# Peptide Research

The peptide-research path adapts the repository's existing research-orchestration style to a retrieval-first biomolecule workflow.

## Scope

- Input: free-text prompts such as `clearer skin`, `fewer wrinkles`, `barrier repair`
- Output: normalized claims, ranked mechanisms, ranked peptide families, retrieved market-neighborhood references, and optional conservative candidate variants
- Benchmarking: expectation-aware scoring for claim-cluster recall, mechanism match, family match, descriptor plausibility, novelty penalty, and market-neighborhood recall

## Pipeline

1. Prompt normalization maps free text onto claim clusters.
2. Mechanism ranking converts those claims into mechanistic priors.
3. Retrieval ranks a versioned peptide reference dataset instead of trying to generate de novo first.
4. Family ranking aggregates the retrieved references into peptide-family hypotheses.
5. Candidate generation makes conservative single-site variants from the retrieved neighborhood.
6. Filtering scores simple descriptor plausibility for cosmetic-style peptides.
7. Benchmarking compares output against optional expected claim, mechanism, and family labels.

## Current limitations

- The current dataset is intentionally small and cosmetic-heavy.
- Candidate generation is motif-preserving and deterministic, not structure-conditioned.
- Descriptor checks are simple heuristics, not synthesis, stability, delivery, or toxicity models.

## Interfaces

- API: `POST /peptide-research`
- CLI: `uv run autolab research-peptides "fewer wrinkles around the eyes"`
- Dataset build script:
  `uv run python scripts/build_peptide_reference_dataset.py --input packages/agents/src/autolab/agents/data/peptide_references.seed.jsonl --dataset-id cosmetic-peptide-market-neighborhoods --version 1.1.0 --description "Curated cosmetic-peptide references with lightweight literature-backed evidence fields, generated from canonical seed records." --output packages/agents/src/autolab/agents/data/peptide_references.v1.1.0.json --manifest packages/agents/src/autolab/agents/data/peptide_references.manifest.json --set-default --offline`

## Data maintenance

- Runtime datasets are resolved through `peptide_references.manifest.json`.
- Canonical seed records live in `packages/agents/src/autolab/agents/data/peptide_references.seed.jsonl`.
- Seed inputs can be CSV or JSONL.
- Citation metadata can be provided inline, resolved from DOI or PMID, or mixed.
- The build script can append new versions to the manifest and optionally set them as default.

## Suggested next steps

- Introduce embeddings for retrieval and novelty scoring.
- Add domain-specific filters for immunogenicity, aggregation, and formulation constraints.
