"""Decode a Chinese novel and split it into stable chapter-part batches."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

CHAPTER_RE = re.compile(r"(?m)^(第.{1,14}章[^\r\n]*)\r?$")


def split_novel(source: Path, output_dir: Path, encoding: str, batch_size: int) -> dict:
    text = source.read_text(encoding=encoding).replace("\r\n", "\n").replace("\r", "\n")
    matches = list(CHAPTER_RE.finditer(text))
    if not matches:
        raise ValueError("no chapter headings found")

    output_dir.mkdir(parents=True, exist_ok=True)
    sections: list[tuple[str, str]] = []
    front_matter = text[: matches[0].start()]
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        sections.append((match.group(1).strip(), text[match.start():end].rstrip() + "\n"))

    batches = []
    expected_files: set[str] = set()
    for offset in range(0, len(sections), batch_size):
        group = sections[offset:offset + batch_size]
        first_number = offset + 1
        last_number = offset + len(group)
        filename = f"batch_{len(batches) + 1:03d}_chapters_{first_number:04d}-{last_number:04d}.txt"
        expected_files.add(filename)
        body = (front_matter if offset == 0 else "") + "\n".join(section for _, section in group)
        (output_dir / filename).write_text(body, encoding="utf-8", newline="\n")
        batches.append({
            "file": filename,
            "first": first_number,
            "last": last_number,
            "count": len(group),
            "first_heading": group[0][0],
            "last_heading": group[-1][0],
        })

    # Remove only stale files created by this script; never touch other content.
    for path in output_dir.glob("batch_*_chapters_*.txt"):
        if path.name not in expected_files:
            path.unlink()

    manifest = {
        "source": source.name,
        "source_encoding": encoding,
        "output_encoding": "utf-8",
        "batch_size": batch_size,
        "chapter_parts": len(sections),
        "batches": batches,
    }
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("output_dir", type=Path)
    parser.add_argument("--encoding", default="gb18030")
    parser.add_argument("--batch-size", type=int, default=50)
    args = parser.parse_args()
    if args.batch_size < 1:
        parser.error("--batch-size must be positive")
    manifest = split_novel(args.source, args.output_dir, args.encoding, args.batch_size)
    print(f"decoded {manifest['chapter_parts']} chapter-parts into {len(manifest['batches'])} batches")


if __name__ == "__main__":
    main()
