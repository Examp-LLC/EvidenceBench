"""Fetch and freeze the public-domain DOJ/NIJ caselaw table cataloged by Data.gov."""

from __future__ import annotations

import argparse
from pathlib import Path

from evidencebench.data_gov import write_snapshot


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-html", type=Path)
    parser.add_argument("--output", type=Path, default=Path("data/doj-nij-post-pcast-2024.json"))
    args = parser.parse_args()
    html = args.input_html.read_bytes() if args.input_html else None
    payload = write_snapshot(args.output, html)
    print(f"wrote {payload['record_count']} records to {args.output}")
    print(f"records sha256: {payload['records_sha256']}")


if __name__ == "__main__":
    main()
