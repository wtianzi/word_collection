"""One-time migration of stored word forms to canonical dictionary lemmas."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from vocab.loader import load_dataset
from vocab.mastered import SHARDS
from vocab.textscan import LemmaResolver


DATA = ROOT / "data"


def _read_word_set(path: Path) -> set[str]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(raw, dict):
        raw = raw.get("words", [])
    return {str(word).strip().lower() for word in raw if str(word).strip()}


def _write_json(path: Path, payload: object) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def _merge_progress(items: list[dict]) -> dict:
    return {
        "familiarity": max(int(item.get("familiarity", 1)) for item in items),
        "seen": sum(int(item.get("seen", 0)) for item in items),
        "correct": sum(int(item.get("correct", 0)) for item in items),
        "wrong": sum(int(item.get("wrong", 0)) for item in items),
        "updated": max(str(item.get("updated", "")) for item in items),
    }


def migrate(apply: bool) -> dict:
    resolver = LemmaResolver(load_dataset())

    def canonical(word: str) -> str:
        key = word.strip().lower()
        return resolver.resolve(key) or key

    progress_path = DATA / "progress.json"
    ignore_path = DATA / "ignore.json"
    mastered_dir = DATA / "mastered"
    progress = json.loads(progress_path.read_text(encoding="utf-8"))
    ignored = _read_word_set(ignore_path)
    mastered: set[str] = set()
    mastered_paths = sorted(mastered_dir.glob("*.json"))
    for path in mastered_paths:
        mastered.update(_read_word_set(path))

    progress_groups: dict[str, list[dict]] = {}
    for word, item in progress.items():
        progress_groups.setdefault(canonical(word), []).append(item)
    new_progress = {
        word: _merge_progress(items) for word, items in progress_groups.items()
    }
    new_ignored = {canonical(word) for word in ignored}
    new_mastered = {canonical(word) for word in mastered}

    # Words outside the five-level process must not remain duplicated in its
    # progress file.  Preserve an ignore/mastered overlap because those two
    # choices have no safe automatic precedence.
    excluded = new_ignored | new_mastered
    removed_from_progress = set(new_progress) & excluded
    for word in removed_from_progress:
        new_progress.pop(word)

    result = {
        "progress": {"before": len(progress), "after": len(new_progress)},
        "ignored": {"before": len(ignored), "after": len(new_ignored)},
        "mastered": {"before": len(mastered), "after": len(new_mastered)},
        "removed_from_progress": len(removed_from_progress),
        "ignore_mastered_overlap": len(new_ignored & new_mastered),
    }
    if not apply:
        return result

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup = DATA / "backups" / f"lemma-migration-{stamp}"
    backup.mkdir(parents=True, exist_ok=False)
    shutil.copy2(progress_path, backup / progress_path.name)
    shutil.copy2(ignore_path, backup / ignore_path.name)
    shutil.copytree(mastered_dir, backup / "mastered")

    _write_json(progress_path, new_progress)
    _write_json(ignore_path, {"words": sorted(new_ignored)})
    for shard in (*SHARDS, "_other"):
        words = sorted(
            word
            for word in new_mastered
            if (word[:1] if word[:1] in SHARDS else "_other") == shard
        )
        _write_json(mastered_dir / f"{shard}.json", {"words": words})
    result["backup"] = str(backup.relative_to(ROOT))
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="write migrated data")
    args = parser.parse_args()
    print(json.dumps(migrate(args.apply), ensure_ascii=False, indent=2))
