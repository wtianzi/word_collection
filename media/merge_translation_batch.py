"""Safely merge a completed translation batch and optionally remove its parts."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("translation_dir", type=Path)
    parser.add_argument("first", type=int)
    parser.add_argument("last", type=int)
    parser.add_argument("output", type=Path)
    parser.add_argument("--delete", action="store_true")
    args = parser.parse_args()
    if args.first < 1 or args.last < args.first:
        parser.error("invalid inclusive sequence range")

    parts = []
    for number in range(args.first, args.last + 1):
        matches = sorted(args.translation_dir.glob(f"{number:03d}_*.md"))
        if len(matches) != 1:
            raise SystemExit(f"expected exactly one translation for {number:03d}, found {len(matches)}")
        parts.append(matches[0])

    payloads = [path.read_bytes().rstrip() + b"\n" for path in parts]
    merged = b"\n".join(payloads)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(merged)
    written = args.output.read_bytes()
    if written != merged:
        raise SystemExit("merged output failed byte-for-byte verification")

    record = {
        "output": args.output.name,
        "first": args.first,
        "last": args.last,
        "count": len(parts),
        "sha256": digest(written),
        "parts": [{"file": p.name, "sha256": digest(data)} for p, data in zip(parts, payloads)],
        "parts_deleted": False,
    }
    manifest_path = args.output.with_suffix(args.output.suffix + ".manifest.json")
    manifest_path.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")

    if args.delete:
        for path in parts:
            path.unlink()
        record["parts_deleted"] = True
        manifest_path.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")

    print(f"verified merge of {len(parts)} translations into {args.output}")
    if args.delete:
        print(f"deleted {len(parts)} verified per-chapter files")


if __name__ == "__main__":
    main()
