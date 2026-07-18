"""Mark the words in already-read papers / books as familiar.

Scans reading material (default: ``media/read/``), extracts every word, maps
inflected forms back to their base word, and raises the learner's familiarity
for each known word.

Usage:
    uv run python -m scripts.mark_familiar                # scans media/read/
    uv run python -m scripts.mark_familiar path/to/file.pdf
    uv run python -m scripts.mark_familiar media/read --level 4
    uv run python -m scripts.mark_familiar file.txt --dry-run
"""

from __future__ import annotations

import argparse
from collections import Counter
from pathlib import Path

from vocab.loader import PROJECT_ROOT, load_dataset
from vocab.models import FAMILIARITY_LABELS, Familiarity
from vocab.progress import ProgressStore
from vocab.textscan import LemmaResolver, extract_text, iter_text_files, tokenize

DEFAULT_TARGET = PROJECT_ROOT / "media" / "read"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "target",
        nargs="?",
        default=str(DEFAULT_TARGET),
        help="File or directory to scan (default: media/read/).",
    )
    parser.add_argument(
        "--level",
        type=int,
        default=int(Familiarity.FAMILIAR),
        choices=[int(f) for f in Familiarity],
        help="Familiarity level to assign (default: 3 = Familiar).",
    )
    parser.add_argument(
        "--min-count",
        type=int,
        default=1,
        help="Only mark words that appear at least this many times.",
    )
    parser.add_argument(
        "--downgrade",
        action="store_true",
        help="Also lower familiarity if a word is already rated higher "
        "(default: only raise).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report what would change without writing progress.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    target = Path(args.target)
    if not target.exists():
        raise SystemExit(f"error: path not found: {target}")

    dataset = load_dataset()
    resolver = LemmaResolver(dataset)
    store = ProgressStore()

    files = list(iter_text_files(target))
    if not files:
        raise SystemExit(f"error: no supported files found under {target}")

    counts: Counter[str] = Counter()
    total_tokens = 0
    for path in files:
        try:
            text = extract_text(path)
        except Exception as exc:  # noqa: BLE001
            print(f"  ! skipped {path.name}: {exc}")
            continue
        tokens = tokenize(text)
        total_tokens += len(tokens)
        for token in tokens:
            base = resolver.resolve(token)
            if base is not None:
                counts[base] += 1
        print(f"  scanned {path.name} ({len(tokens):,} tokens)")

    known_words = [w for w, c in counts.items() if c >= args.min_count]

    changed = 0
    for word in known_words:
        current = int(store.familiarity(word))
        if args.downgrade or args.level > current:
            if not args.dry_run:
                store.set_familiarity(word, args.level)
            if args.level != current:
                changed += 1

    print("-" * 52)
    print(f"Files scanned:        {len(files)}")
    print(f"Word tokens:          {total_tokens:,}")
    print(f"Known unique words:   {len(known_words):,}")
    label = FAMILIARITY_LABELS[Familiarity(args.level)]
    verb = "would mark" if args.dry_run else "marked"
    print(f"{verb.capitalize()} {changed:,} words as {label}")
    if args.dry_run:
        print("(dry run: no progress written)")


if __name__ == "__main__":
    main()
