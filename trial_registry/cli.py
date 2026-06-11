from __future__ import annotations

import argparse
import json
import sys

from .runner import run_batch, run_query


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Fetch trial registry records from known literature registry IDs."
    )
    parser.add_argument("input", nargs="?", help="UMIN ID, receipt number, or detail URL.")
    parser.add_argument(
        "--input-file",
        default=None,
        help="Batch input file. Currently supports TXT lines like '- file.pdf: UMIN000019339'.",
    )
    parser.add_argument(
        "--input-format",
        default="txt",
        help="Batch input format. Available now: txt. Default: txt",
    )
    parser.add_argument("--source", default="umin_ctr", help="Registry source. Default: umin_ctr")
    parser.add_argument(
        "--formats",
        default="csv",
        help="Comma-separated export formats. Available now: csv,json,txt,md. Default: csv",
    )
    parser.add_argument("--output-dir", default="output", help="Base output directory. Default: output")
    parser.add_argument(
        "--all-matches",
        action="store_true",
        default=True,
        help="Save all matches. This is the default for v1.",
    )
    parser.add_argument("--run-id", default=None, help="Optional run id for reproducible output paths.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    formats = [item.strip() for item in args.formats.split(",") if item.strip()]
    if args.input_file:
        result = run_batch(
            args.input_file,
            input_format=args.input_format,
            formats=formats,
            output_root=args.output_dir,
        )
        print(
            json.dumps(
                {
                    "output_root": str(result.output_root),
                    "index": str(result.index_path),
                    "total_count": result.total_count,
                    "saved_count": result.saved_count,
                    "pending_count": result.pending_count,
                    "failure_count": result.failure_count,
                    "runs": [
                        {
                            "run_id": item.run_id,
                            "output_dir": str(item.output_dir),
                            "files": {key: str(path) for key, path in item.files.items()},
                            "manifest": str(item.manifest_path),
                            "match_count": item.match_count,
                            "failure_count": item.failure_count,
                        }
                        for item in result.results
                    ],
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 1 if result.failure_count else 0

    if not args.input:
        raise SystemExit("Either input or --input-file is required.")

    result = run_query(
        args.input,
        source=args.source,
        formats=formats,
        output_root=args.output_dir,
        run_id=args.run_id,
    )
    print(
        json.dumps(
            {
                "run_id": result.run_id,
                "output_dir": str(result.output_dir),
                "files": {key: str(path) for key, path in result.files.items()},
                "manifest": str(result.manifest_path),
                "match_count": result.match_count,
                "failure_count": result.failure_count,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 1 if result.failure_count else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
