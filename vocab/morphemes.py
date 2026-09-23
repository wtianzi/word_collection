"""Searchable English roots and affixes loaded from a small curated dataset."""

from __future__ import annotations

import json
from collections.abc import Collection
from pathlib import Path

from .morpheme_supplement import explain as explain_supplement, load_index


DATA_FILE = Path(__file__).resolve().parent.parent / "resources" / "morphemes.json"
KINDS = ("prefix", "root", "suffix")


class MorphemeDictionary:
    """Load, validate, and search the root/affix dictionary."""

    def __init__(self, path: Path = DATA_FILE) -> None:
        raw = json.loads(path.read_text(encoding="utf-8"))
        self.entries: list[dict] = []
        for item in raw:
            entry = {
                "id": str(item["id"]),
                "kind": str(item["kind"]),
                "form": str(item["form"]),
                "meaning": str(item["meaning"]),
                "origin": str(item.get("origin", "")),
                "variants": list(item.get("variants", [])),
                "examples": list(item.get("examples", [])),
            }
            if entry["kind"] not in KINDS:
                raise ValueError(f"invalid morpheme kind: {entry['kind']}")
            self.entries.append(entry)
        self.supplementary_index = load_index()

    def search(self, query: str = "", kind: str | None = None, limit: int = 100) -> list[dict]:
        """Search forms, variants, meanings, origins, and example words."""

        needle = query.strip().lower().strip("-")
        selected_kind = kind if kind in KINDS else None
        matches = []
        for entry in self.entries:
            if selected_kind and entry["kind"] != selected_kind:
                continue
            searchable = " ".join(
                [entry["form"], entry["meaning"], entry["origin"], *entry["variants"]]
                + [f"{example['word']} {example['note']}" for example in entry["examples"]]
            ).lower()
            if needle and needle not in searchable:
                continue
            matches.append(entry)
        return matches[: max(1, min(limit, 300))]

    def counts(self) -> dict[str, int]:
        return {kind: sum(item["kind"] == kind for item in self.entries) for kind in KINDS}

    def explain(self, word: str, vocabulary: Collection[str] | None = None) -> dict:
        """Explain curated examples or a productive affix on a known base word."""

        key = word.strip().lower()
        if not key.isalpha():
            return {"word": key, "parts": [], "note": ""}

        explicit = [
            (entry, example)
            for entry in self.entries
            for example in entry["examples"]
            if example["word"].lower() == key
        ]
        if explicit:
            parts = []
            for entry, _ in explicit:
                forms = [entry["form"], *entry["variants"]]
                matched = next(
                    (form for form in forms if self._matches(key, form, entry["kind"])),
                    entry["form"],
                )
                parts.append({"form": matched, "kind": entry["kind"], "meaning": entry["meaning"]})
            # An example may be listed under its prefix but also contain a
            # longer root documented elsewhere in the table.
            known = {entry["id"] for entry, _ in explicit}
            for entry in self.entries:
                if entry["kind"] != "root" or entry["id"] in known:
                    continue
                matched = next(
                    (form for form in [entry["form"], *entry["variants"]]
                     if len(form) >= 4 and form.lower() in key),
                    None,
                )
                if matched:
                    parts.append({"form": matched, "kind": "root", "meaning": entry["meaning"]})
            return {"word": key, "parts": parts, "note": explicit[0][1]["note"]}
        candidates = []
        if vocabulary is not None:
            for entry in self.entries:
                if entry["kind"] not in {"prefix", "suffix"}:
                    continue
                for form in [entry["form"], *entry["variants"]]:
                    letters = form.strip("-").lower()
                    if len(letters) < 2 or not self._matches(key, form, entry["kind"]):
                        continue
                    base = key[len(letters):] if entry["kind"] == "prefix" else key[:-len(letters)]
                    if len(base) >= 3 and base in vocabulary:
                        candidates.append((len(letters), entry, form, base))
        if candidates:
            _, entry, form, base = max(candidates, key=lambda item: item[0])
            return {
                "word": key,
                "parts": [{"form": form, "kind": entry["kind"], "meaning": entry["meaning"]}],
                "note": f"词干：{base}",
            }
        supplementary_parts = explain_supplement(self.supplementary_index, key)
        if supplementary_parts:
            return {"word": key, "parts": supplementary_parts, "note": "", "language": "en"}
        return {"word": key, "parts": [], "note": ""}

    @staticmethod
    def _matches(word: str, form: str, kind: str) -> bool:
        letters = form.strip("-").lower()
        if kind == "prefix":
            return word.startswith(letters) and len(word) > len(letters)
        if kind == "suffix":
            return word.endswith(letters) and len(word) > len(letters)
        return letters in word
