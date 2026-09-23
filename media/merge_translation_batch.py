"""Safely merge a completed translation batch and optionally remove its parts."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def plain_text(text: str) -> str:
    """Remove the working chapters' Markdown without rewriting their prose."""
    text = re.sub(r"(?m)^#{1,6} +", "", text)
    text = re.sub(r"(?m)^> ?", "", text)
    text = re.sub(r"\*\*([^*\n]+)\*\*", r"\1", text)
    text = re.sub(r"(?<!\w)\*([^*\n]+)\*(?!\w)", r"\1", text)
    text = re.sub(r"`([^`\n]+)`", r"\1", text)
    return text.rstrip() + "\n"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("translation_dir", type=Path)
    parser.add_argument("first", type=int)
    parser.add_argument("last", type=int)
    parser.add_argument("output", type=Path)
    parser.add_argument("--delete", action="store_true")
    parser.add_argument("--plain-text", action="store_true")
    parser.add_argument("--review-report", type=Path)
    args = parser.parse_args()
    if args.first < 1 or args.last < args.first:
        parser.error("invalid inclusive sequence range")

    parts = []
    for number in range(args.first, args.last + 1):
        matches = sorted(args.translation_dir.glob(f"{number:03d}_*.md"))
        if len(matches) != 1:
            raise SystemExit(f"expected exactly one translation for {number:03d}, found {len(matches)}")
        parts.append(matches[0])

    originals = [path.read_bytes() for path in parts]
    if args.review_report:
        review = args.review_report.read_text(encoding="utf-8")
        if not re.search(r"(?m)^Status: Complete\.", review):
            raise SystemExit("review report must explicitly declare Status: Complete.")
    payloads = []
    headings = []
    for path, original in zip(parts, originals):
        text = original.decode("utf-8")
        if args.plain_text:
            text = plain_text(text)
            found = re.findall(r"(?m)^Chapter \d+: .+$", text)
            if len(found) != 1 or len(text.split()) < 50:
                raise SystemExit(f"expected one chapter heading and a nonempty body: {path}")
            if re.search(r"[\u3400-\u9fff\ufffd]|\b(?:TODO|TBD|FIXME)\b|(?im:^#{1,6} |^> )|[*`]", text):
                raise SystemExit(f"untranslated text, placeholder, or Markdown remains: {path}")
            headings.append(found[0])
        payloads.append(text.rstrip().encode("utf-8") + b"\n")
    # Assign separators to their preceding part so exact byte ranges cover the file.
    payloads = [data + (b"\n" if i < len(parts) - 1 else b"")
                for i, data in enumerate(payloads)]
    merged = b"".join(payloads)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(merged)
    written = args.output.read_bytes()
    if written != merged:
        raise SystemExit("merged output failed byte-for-byte verification")

    entries = []
    offset = 0
    for i, (path, original, data) in enumerate(zip(parts, originals, payloads)):
        entries.append({
            "number": args.first + i, "file": path.name,
            "source_sha256": digest(original), "sha256": digest(data),
            "offset_bytes": offset, "length_bytes": len(data),
            **({"heading": headings[i]} if headings else {}),
        })
        offset += len(data)
    record = {
        "schema_version": 2,
        "output": args.output.name,
        "format": "UTF-8 plain text" if args.plain_text else "UTF-8 Markdown",
        "first": args.first,
        "last": args.last,
        "count": len(parts),
        "sha256": digest(written),
        "bytes": len(written),
        "word_count_whitespace": len(written.decode("utf-8").split()),
        "parts": entries,
        "parts_deleted": False,
    }
    if args.review_report:
        record["review_report"] = str(args.review_report.resolve())
        record["review_report_sha256"] = digest(args.review_report.read_bytes())
        record["review_status"] = "complete"
    if headings:
        record["first_heading"] = headings[0]
        record["last_heading"] = headings[-1]
    manifest_path = args.output.with_suffix(args.output.suffix + ".manifest.json")
    manifest_path.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")

    saved = json.loads(manifest_path.read_text(encoding="utf-8"))
    if saved != record or saved["sha256"] != digest(args.output.read_bytes()):
        raise SystemExit("manifest verification failed")
    for entry in saved["parts"]:
        start = entry["offset_bytes"]
        data = written[start:start + entry["length_bytes"]]
        if digest(data) != entry["sha256"]:
            raise SystemExit("part byte-range verification failed")

    if args.delete:
        if any(path.read_bytes() != original for path, original in zip(parts, originals)):
            raise SystemExit("working chapters changed during merge; nothing deleted")
        for path in parts:
            path.unlink()
        record["parts_deleted"] = True
        manifest_path.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")

    print(f"verified merge of {len(parts)} translations into {args.output}")
    if args.delete:
        print(f"deleted {len(parts)} verified per-chapter files")


if __name__ == "__main__":
    main()
