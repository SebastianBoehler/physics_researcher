from __future__ import annotations

import argparse
from pathlib import Path

from autolab.agents.citation_metadata import CitationMetadataResolver
from autolab.agents.peptide_dataset_builder import (
    PeptideReferenceDatasetBuilder,
    update_dataset_manifest,
)
from autolab.core.settings import get_settings


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build a versioned peptide reference dataset from CSV or JSONL seed files."
    )
    parser.add_argument(
        "--input",
        dest="inputs",
        nargs="+",
        required=True,
        help="One or more CSV or JSONL seed files.",
    )
    parser.add_argument("--dataset-id", required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument("--scope", default="cosmetic_peptides")
    parser.add_argument("--description", required=True)
    parser.add_argument("--generated-on")
    parser.add_argument("--output", required=True)
    parser.add_argument("--manifest", help="Optional manifest file to update.")
    parser.add_argument(
        "--set-default",
        action="store_true",
        help="If a manifest is provided, set the built version as default.",
    )
    parser.add_argument(
        "--offline",
        action="store_true",
        help="Do not resolve missing citation metadata over the network.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    resolver = None if args.offline else CitationMetadataResolver(get_settings())
    builder = PeptideReferenceDatasetBuilder(resolver=resolver)
    input_paths = [Path(value) for value in args.inputs]
    dataset = builder.build_dataset(
        seeds=builder.load_seed_records(input_paths),
        dataset_id=args.dataset_id,
        version=args.version,
        scope=args.scope,
        description=args.description,
        generated_on=args.generated_on,
    )
    output_path = Path(args.output)
    builder.write_dataset(dataset, output_path)
    if args.manifest:
        update_dataset_manifest(
            manifest_path=Path(args.manifest),
            dataset=dataset,
            filename=output_path.name,
            set_default=args.set_default,
        )
    print(
        f"Wrote {len(dataset.entries)} entries to {output_path} "
        f"(dataset {dataset.dataset_id} v{dataset.version})."
    )


if __name__ == "__main__":
    main()
